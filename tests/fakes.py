"""Offline stand-ins for the OpenAI client (same attribute shape as openai>=1.72)."""
from types import SimpleNamespace


def _usage():
    return SimpleNamespace(input_tokens=100, output_tokens=10, input_tokens_details=SimpleNamespace(cached_tokens=0))


class Item(SimpleNamespace):
    def model_dump(self, exclude_none=True):
        return {k: v for k, v in vars(self).items() if v is not None}


def text_response(text):
    return SimpleNamespace(output=[Item(type="message", role="assistant",
                                        content=[{"type": "output_text", "text": text}])],
                           output_text=text, usage=_usage())


def call_response(name, arguments, call_id="call_1"):
    return SimpleNamespace(output=[Item(type="function_call", name=name, arguments=arguments, call_id=call_id)],
                           output_text="", usage=_usage())


class FakeResponses:
    def __init__(self, parse_fn=None, script=None):
        self.parse_fn, self.script = parse_fn, list(script or [])
        self.parse_calls, self.create_calls = [], []

    def parse(self, model, instructions, input, text_format):
        self.parse_calls.append((model, text_format.__name__, input))
        return SimpleNamespace(output_parsed=self.parse_fn(model, text_format), usage=_usage())

    def create(self, model, instructions, input, tools):
        self.create_calls.append((model, input))
        return self.script.pop(0)


class FakeClient:
    def __init__(self, **kw):
        self.responses = FakeResponses(**kw)
