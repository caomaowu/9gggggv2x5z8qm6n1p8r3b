import sys
import unittest
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.utils.llm_compat import (  # noqa: E402
    invoke_llm_text,
    normalize_llm_text_response,
    stream_llm_text,
)


class TextPart:
    def __init__(self, text: str):
        self.text = text


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def stream(self, payload):
        self.calls.append(payload)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        for item in response:
            if isinstance(item, Exception):
                raise item
            yield item


class LLMCompatTestCase(unittest.TestCase):
    def test_normalize_supports_string_content(self):
        self.assertEqual(normalize_llm_text_response(FakeResponse("hello")), "hello")

    def test_normalize_supports_direct_string(self):
        self.assertEqual(normalize_llm_text_response("plain text"), "plain text")

    def test_normalize_supports_content_blocks(self):
        response = FakeResponse(
            [
                {"type": "text", "text": "alpha "},
                TextPart("beta"),
                {"type": "output_text", "content": " gamma"},
            ]
        )

        self.assertEqual(normalize_llm_text_response(response), "alpha beta gamma")

    def test_invoke_retries_model_dump_error_with_chat_payload(self):
        llm = FakeLLM(
            [
                AttributeError("'str' object has no attribute 'model_dump'"),
                FakeResponse("recovered"),
            ]
        )

        result = invoke_llm_text(llm, "prompt body")

        self.assertEqual(result, "recovered")
        self.assertEqual(llm.calls[0], "prompt body")
        self.assertEqual(llm.calls[1], [("human", "prompt body")])

    def test_stream_collects_chunks(self):
        llm = FakeLLM([[FakeResponse("he"), FakeResponse("llo")]])
        seen = []

        result = stream_llm_text(llm, "prompt body", chunk_callback=seen.append)

        self.assertEqual(result, "hello")
        self.assertEqual(seen, ["he", "llo"])
        self.assertEqual(llm.calls[0], "prompt body")

    def test_stream_retries_model_dump_error_with_chat_payload(self):
        llm = FakeLLM(
            [
                AttributeError("'str' object has no attribute 'model_dump'"),
                [FakeResponse("re"), FakeResponse("covered")],
            ]
        )

        result = stream_llm_text(llm, "prompt body")

        self.assertEqual(result, "recovered")
        self.assertEqual(llm.calls[0], "prompt body")
        self.assertEqual(llm.calls[1], [("human", "prompt body")])


if __name__ == "__main__":
    unittest.main()
