# prompts/registry.py
# PromptRegistry: incarca YAML + renderizeaza cu Jinja2

import os
import yaml
from jinja2 import Template


class PromptRegistry:

    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = prompts_dir
        self._templates = {}
        self._load_all()

    def _load_all(self):
        """Incarca toate fisierele YAML din folder."""
        for filename in os.listdir(self.prompts_dir):
            if filename.endswith(".yaml"):
                path = os.path.join(self.prompts_dir, filename)
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    # sarim fisierele YAML goale sau invalide
                    if data is None or "name" not in data:
                        continue
                    self._templates[data["name"]] = data

    def get(self, name: str) -> dict:
        """Returneaza template-ul dupa nume."""
        if name not in self._templates:
            raise KeyError(f"Promptul '{name}' nu exista. Disponibile: {list(self._templates.keys())}")
        return self._templates[name]

    def render(self, name: str, **variables) -> str:
        """Renderizeaza promptul cu variabilele date."""
        template_data = self.get(name)
        template = Template(template_data["prompt"])
        return template.render(**variables)

    def list_templates(self) -> list:
        """Listeaza toate prompturile disponibile."""
        return list(self._templates.keys())


# Singleton
_registry = None

def get_prompt_registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry