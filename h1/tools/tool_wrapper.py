# tools/tool_wrapper.py
# ToolWrapper: call() + catalog()
# punctul central - executie / catalog 

from tools.registry import TOOL_REGISTRY
from tools.params_models import CalculatorParams, GetDatetimeParams, WebSearchParams

# Mapeaza numele tool-ului la modelul Pydantic corespunzator
TOOL_PARAMS = {
    "calculator": CalculatorParams,
    "get_datetime": GetDatetimeParams,
    "web_search": WebSearchParams,
}


class ToolWrapper:

    @staticmethod
    def call(tool_name: str, **kwargs) -> str:
        """Executa un tool dupa nume, cu validare Pydantic."""
        if tool_name not in TOOL_REGISTRY:
            return f"Eroare: tool-ul '{tool_name}' nu exista. Disponibile: {list(TOOL_REGISTRY.keys())}"

        try:
            # Valideaza parametrii cu Pydantic
            if tool_name in TOOL_PARAMS:
                TOOL_PARAMS[tool_name](**kwargs)

            # Executa tool-ul
            result = TOOL_REGISTRY[tool_name](**kwargs)
            return str(result)

        except Exception as e:
            return f"Eroare la executia tool-ului '{tool_name}': {str(e)}"

    @staticmethod
    def catalog() -> list[dict]:
        """Returneaza JSON Schema pentru toate tool-urile — pentru LLM."""
        tools = []
        for name, model in TOOL_PARAMS.items():
            schema = model.model_json_schema()
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": TOOL_REGISTRY[name].__doc__ or "",
                    "parameters": schema,
                }
            })
        return tools