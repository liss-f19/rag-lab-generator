"""
Role:   Prompt template loader; templates live as .md files next to this module.
Input:  Template name and format kwargs.
Output: Rendered prompt string.
Flow:   Reads <name>.md from this directory, formats {placeholders} with kwargs.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(name: str, **kwargs: str) -> str:
    template = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return template.format(**kwargs) if kwargs else template
