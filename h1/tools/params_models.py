# tools/params_models.py
# Pydantic BaseModel pentru parametrii fiecarui tool
# zona varificatorilor / verificarilor de intrare pentru fiecare tool

from pydantic import BaseModel, Field


class CalculatorParams(BaseModel):
    expression: str = Field(
        description="Expresia matematica de calculat. Ex: '2 + 2', '15 * 4.5', '100 / 3'"
    )


class GetDatetimeParams(BaseModel):
    format: str = Field(
        default="%Y-%m-%d %H:%M:%S",
        description="Formatul datei. Default: '%Y-%m-%d %H:%M:%S'"
    )


class WebSearchParams(BaseModel):
    query: str = Field(
        description="Termenul de cautat pe web"
    )
    max_results: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Numarul maxim de rezultate returnate (1-10)"
    )