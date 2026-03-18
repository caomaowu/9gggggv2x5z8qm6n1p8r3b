from typing import Any


_LBRACE_SENTINEL = "\u0000LBRACE\u0000"
_RBRACE_SENTINEL = "\u0000RBRACE\u0000"


def render_prompt_template(template: str, **values: Any) -> str:
    rendered = template.replace("{{", _LBRACE_SENTINEL).replace("}}", _RBRACE_SENTINEL)
    for key, value in values.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))
    return rendered.replace(_LBRACE_SENTINEL, "{").replace(_RBRACE_SENTINEL, "}")
