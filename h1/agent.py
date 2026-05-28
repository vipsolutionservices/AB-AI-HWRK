# agent.py
# QAAgent cu ReAct pattern: Think -> Act -> Observe -> Repeat
# - Lant de provideri: Gemini -> Groq -> OpenAI, cu fallback automat
# - Prompturi incarcate din YAML + renderizare Jinja2
# - Executie tool-uri cu validare Pydantic + catalog JSON Schema
# - Istoric conversatiei + logging structurat in fisierul: agent.log
# Comenzi interactive: 'exit' pentru iesire | 'reset' pentru stergerea istoricului
# Scensariile de testare sunt definite in fisierul word: test_scenarios.docx

import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage


from tools import ToolWrapper
from prompts.registry import get_prompt_registry

load_dotenv()


# ============================================================ #START logging_config
# CONFIGURARE LOGGING
# Format: fisier | datetime | pas | actiune
# Output: consola + fisier agent.log
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("agent.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


def log(pas: str, actiune: str): #START log
    # Helper pentru loguri structurate
    # Ex: agent.py | 2026-05-26 11:25:03 AM | Pas 1 | Initializare agent
    now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    logger.info(f"agent.py | {now} | {pas} | {actiune}")
#END log
# ============================================================ #END logging_config


# ============================================================ #START QAAgent
# CLASA QAAgent
# - Initializeaza lantul de provideri: Gemini -> Groq -> OpenAI
# - Fallback automat cu comutare permanenta pe sesiune
# - Incarca system prompt din PromptRegistry (YAML + Jinja2)
# - Ruleaza ReAct loop: Think -> Act -> Observe -> Answer
# - Gestioneaza istoricul conversatiei
# ============================================================
class QAAgent:

    def __init__(self, max_iterations: int = 10): #START __init__
        log("Pas 1", "Initializare agent QA")

        # Lantul de provideri: Gemini -> Groq -> OpenAI
        # active_provider_index indica providerul activ in sesiunea curenta
        # Odata comutat, ramane pe noul provider pana la restart
        self.providers = [
            {
                "name": "gemini-2.5-flash",
                "llm": ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash",
                    temperature=0.3,
                    max_retries=0,
                )
            },
            {
                "name": "groq/llama-3.1-8b-instant",
                "llm": ChatGroq(
                    model="llama-3.1-8b-instant",
                    temperature=0.3,
                    max_retries=0,
                )
            },
            {
                "name": "openai/gpt-4o-mini",
                "llm": ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0.3,
                    max_retries=0,
                )
            },
        ]
        self.active_provider_index = 0

        for p in self.providers:
            log("Pas 1.1", f"Provider inregistrat: {p['name']}")
        log("Pas 1.1", f"Provider activ la start: {self.providers[0]['name']}")

        # Limita de siguranta - previne loop infinit si costuri necontrolate
        self.max_iterations = max_iterations

        # Memoria conversatiei - lista de HumanMessage / AIMessage
        self.history = []

        # Incarca prompturile din fisierele YAML
        self.registry = get_prompt_registry()
        log("Pas 1.2", f"PromptRegistry incarcat: {self.registry.list_templates()}")

        # Genereaza catalogul JSON Schema al tool-urilor pentru LLM
        self.tools = ToolWrapper.catalog()
        log("Pas 1.3", f"Tools inregistrate: {[t['function']['name'] for t in self.tools]}")

        log("Pas 1", "Agent initializat cu succes")
    #END __init__

    def _get_system_prompt(self) -> str: #START _get_system_prompt
        # Renderizeaza promptul 'planner' din YAML cu data curenta injectata
        return self.registry.render(
            "planner",
            current_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    #END _get_system_prompt

    def _invoke_llm(self, messages: list): #START _invoke_llm
        # Incearca providerul activ curent
        # Daca esueaza (rate limit / eroare) -> avanseaza PERMANENT la urmatorul
        # Odata comutat, ramane pe noul provider pentru tot restul sesiunii

        while self.active_provider_index < len(self.providers):
            provider = self.providers[self.active_provider_index]
            try:
                response = provider["llm"].bind_tools(self.tools).invoke(messages)
                log("Pas 3", f"Provider activ: {provider['name']}")
                return response

            except Exception as e:
                eroare = str(e)
                # Detectam erori de tip rate limit sau quota
                is_rate_limit = (
                    "429" in eroare or
                    "RESOURCE_EXHAUSTED" in eroare or
                    "quota" in eroare.lower() or
                    "rate_limit" in eroare.lower() or
                    "rate limit" in eroare.lower() or
                    "RateLimitError" in eroare
                )

                if is_rate_limit and self.active_provider_index + 1 < len(self.providers):
                    # Comutare permanenta la urmatorul provider din lant
                    urmatorul = self.providers[self.active_provider_index + 1]
                    print(f"\n[!] {provider['name']} rate limit — comut pe {urmatorul['name']} pentru aceasta sesiune...")
                    log("Comutare", f"{provider['name']} -> {urmatorul['name']} (permanent pe sesiune)")
                    self.active_provider_index += 1
                    # continua while loop cu noul provider
                else:
                    # Eroare necunoscuta sau am epuizat toti providerii
                    log("Eroare", f"Provider {provider['name']} a esuat: {eroare[:100]}")
                    raise

        log("Eroare", "Toti providerii au esuat")
        raise RuntimeError("Toti providerii LLM sunt indisponibili.")
    #END _invoke_llm

    def _execute_tool_calls(self, tool_calls) -> list: #START _execute_tool_calls
        # Executa tool calls cerute de LLM si returneaza rezultatele
        # LLM returneaza INTENTIA - noi executam efectiv si trimitem rezultatul inapoi
        results = []

        for tool_call in tool_calls:
            # Extrage numele, id-ul si argumentele tool-ului din raspunsul LLM
            name = tool_call.get("name") or tool_call.function.name
            # tool_call_id necesar pentru ToolMessage - OpenAI e strict la acest format
            tool_call_id = (
                tool_call.get("id")
                or getattr(tool_call, "id", None)
                or f"call_{name}"
            )
            try:
                args = tool_call.get("args") or json.loads(tool_call.function.arguments)
            except Exception:
                args = {}

            log("Act", f"Execut tool: {name}({args})")
            result = ToolWrapper.call(name, **args)
            log("Observe", f"Rezultat {name}: {result}")
            results.append({"tool": name, "result": result, "tool_call_id": tool_call_id})

        return results
    #END _execute_tool_calls

    def chat(self, user_message: str) -> str: #START chat
        # Punctul de intrare principal
        # Flow: construieste context -> apeleaza LLM -> executa tools -> raspuns final
        log("Pas 2", f"Mesaj primit: '{user_message}'")

        # Construieste contextul complet: system prompt + istoric + mesaj nou
        messages = [
            SystemMessage(content=self._get_system_prompt()),
            *self.history,
            HumanMessage(content=user_message),
        ]
        log("Pas 2.1", f"Context construit: {len(messages)} mesaje")

        # ReAct loop - se repeta pana la raspuns final sau limita de iteratii
        for iteration in range(self.max_iterations):
            log("Pas 3", f"ReAct iteratie {iteration + 1}/{self.max_iterations}")

            # Apeleaza LLM - cu fallback automat si comutare permanenta
            response = self._invoke_llm(messages)

            # THINK + ACT: LLM a cerut unul sau mai multe tool calls
            if hasattr(response, "tool_calls") and response.tool_calls:
                log("Think", f"LLM solicita {len(response.tool_calls)} tool call(s)")

                # Executa tool-urile si colecteaza rezultatele
                tool_results = self._execute_tool_calls(response.tool_calls)

                # Adauga raspunsul LLM + rezultatele in context pentru urmatoarea iteratie
                messages.append(response)
                for tr in tool_results:
                    # ToolMessage in loc de HumanMessage - compatibil cu toti providerii
                    messages.append(ToolMessage(
                        content=str(tr['result']),
                        tool_call_id=tr['tool_call_id']
                    ))

            # ANSWER: LLM a dat raspunsul final, fara tool calls
            else:
                final_answer = response.content
                log("Pas 4", f"Raspuns final generat ({len(final_answer)} caractere)")

                # Salveaza tura curenta in istoricul conversatiei
                self.history.append(HumanMessage(content=user_message))
                self.history.append(AIMessage(content=final_answer))
                log("Pas 4.1", f"Istoric actualizat: {len(self.history)} mesaje total")

                return final_answer

        # Safety net - limita de iteratii atinsa fara raspuns final
        log("Eroare", f"Limita de {self.max_iterations} iteratii atinsa")
        return "Am atins limita de iteratii fara raspuns final."
    #END chat

    def clear_history(self): #START clear_history
        # Reseteaza istoricul - util la inceputul unui subiect nou
        self.history = []
        log("Pas 5", "Istoric conversatie resetat")
    #END clear_history

#END QAAgent


# ============================================================ #START main
# PUNCT DE INTRARE - rulare interactiva din linia de comanda
# Comenzi: 'exit' -> iese | 'reset' -> sterge istoricul
# ============================================================
if __name__ == "__main__":
    log("Start", "Pornire aplicatie QAAgent")

    agent = QAAgent()

    print("\n" + "=" * 55)
    print("  Agent QA cu ReAct Pattern + Tools + Prompts YAML")
    print("  Comenzi: 'exit' pentru iesire | 'reset' pentru istoric")
    print("=" * 55)

    while True:
        user_input = input("\nTu: ").strip()

        if not user_input:
            continue
        elif user_input.lower() == "exit":
            log("Stop", "Aplicatie oprita de user")
            print("La revedere!")
            break
        elif user_input.lower() == "reset":
            agent.clear_history()
            print("Istoric resetat!")
        else:
            raspuns = agent.chat(user_input)
            print(f"\nAgent: {raspuns}")
#END main