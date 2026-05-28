TOOL_REGISTRY = {}

def register_tool(func):
    """Decorator care inregistreaza automat o functie ca tool."""
    TOOL_REGISTRY[func.__name__] = func
    return func