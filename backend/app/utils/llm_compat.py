import json
import logging
from typing import Any, Callable


logger = logging.getLogger(__name__)


def _extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if text is not None:
                    parts.append(str(text))
                    continue
                if item.get("type") == "output_text" and item.get("content") is not None:
                    parts.append(str(item["content"]))
                    continue
            text = getattr(item, "text", None)
            if text is not None:
                parts.append(str(text))
        if parts:
            return "".join(parts)

    if content is None:
        return ""

    return str(content)


def normalize_llm_text_response(response: Any) -> str:
    if isinstance(response, str):
        return response

    content = getattr(response, "content", None)
    if content is not None:
        return _extract_text_from_content(content)

    if isinstance(response, dict):
        for key in ("text", "content", "output_text"):
            if key in response:
                return _extract_text_from_content(response[key])
        try:
            return json.dumps(response, ensure_ascii=False)
        except TypeError:
            return str(response)

    text = getattr(response, "text", None)
    if text is not None:
        return _extract_text_from_content(text)

    return str(response)


def invoke_llm_text(llm: Any, prompt: str) -> str:
    try:
        response = llm.invoke(prompt)
        return normalize_llm_text_response(response)
    except AttributeError as exc:
        if "model_dump" not in str(exc):
            raise

        logger.warning(
            "Caught model_dump compatibility error during string invoke; retrying with chat message payload."
        )
        response = llm.invoke([("human", prompt)])
        return normalize_llm_text_response(response)


def stream_llm_text(
    llm: Any,
    prompt: str,
    chunk_callback: Callable[[str], None] | None = None,
) -> str:
    try:
        parts: list[str] = []
        for chunk in llm.stream(prompt):
            text = normalize_llm_text_response(chunk)
            if text:
                parts.append(text)
                if chunk_callback:
                    chunk_callback(text)
        return "".join(parts)
    except AttributeError as exc:
        if "model_dump" not in str(exc):
            raise

        logger.warning(
            "Caught model_dump compatibility error during string stream; retrying with chat message payload."
        )
        parts = []
        for chunk in llm.stream([("human", prompt)]):
            text = normalize_llm_text_response(chunk)
            if text:
                parts.append(text)
                if chunk_callback:
                    chunk_callback(text)
        return "".join(parts)
