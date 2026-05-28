# tools/basic_tools.py
# Implementarea tool-urilor: calculator, get_datetime, web_search

from datetime import datetime
from tools.registry import register_tool
from tools.params_models import CalculatorParams, GetDatetimeParams, WebSearchParams


@register_tool
def calculator(expression: str) -> str:
    """Calculeaza expresii matematice. Foloseste pentru orice calcul numeric."""
    import math
    try:
        params = CalculatorParams(expression=expression)
        # Contextul de evaluare include toate functiile din modulul math
        # Exemplu: sqrt(144), sin(0), log(10), pi, etc.
        math_env = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        math_env["__builtins__"] = {}
        result = eval(params.expression, math_env)
        return str(result)
    except Exception as e:
        return f"Eroare la calcul: {str(e)}"


@register_tool
def get_datetime(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Returneaza data si ora curenta. Foloseste cand userul intreaba de timp/data."""
    try:
        params = GetDatetimeParams(format=format)
        return datetime.now().strftime(params.format)
    except Exception as e:
        return f"Eroare la data: {str(e)}"


@register_tool
def web_search(query: str, max_results: int = 3) -> str:
    """Simuleaza o cautare web. Foloseste pentru informatii recente sau externe."""
    try:
        params = WebSearchParams(query=query, max_results=max_results)
        # Simulare - in productie ai folosi un API real (Tavily, SerpAPI etc.)
        return (
            f"Rezultate cautare pentru '{params.query}':\n"
            f"1. [Rezultat simulat] Informatii despre {params.query}\n"
            f"2. [Rezultat simulat] Mai multe detalii despre {params.query}\n"
            f"3. [Rezultat simulat] Surse relevante pentru {params.query}"
        )
    except Exception as e:
        return f"Eroare la cautare: {str(e)}"