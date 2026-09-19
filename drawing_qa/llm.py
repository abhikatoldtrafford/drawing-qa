"""Thin OpenAI Responses-API wrapper that records token usage per model.
Tests inject a fake `client` with the same `.responses.parse/.create` shape."""
import base64
from collections import defaultdict


def image_part(png: bytes, detail="high"):
    return {"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(png).decode(), "detail": detail}


class LLMError(RuntimeError):
    """The model returned nothing usable (refusal, empty or unparseable structured output)."""


class LLM:
    def __init__(self, client=None, timeout=120.0, max_retries=2):
        if client is None:
            from openai import OpenAI
            client = OpenAI(timeout=timeout, max_retries=max_retries)
        self.client = client
        self.usage = defaultdict(lambda: defaultdict(int))  # model -> {input, cached, output, calls}

    def _record(self, model, usage):
        if usage is None:
            return
        u = self.usage[model]
        u["input"] += usage.input_tokens
        u["output"] += usage.output_tokens
        details = getattr(usage, "input_tokens_details", None)
        u["cached"] += getattr(details, "cached_tokens", 0) or 0
        u["calls"] += 1

    def parse(self, model, instructions, text, images, schema):
        content = [{"type": "input_text", "text": text}] + [image_part(p) for p in images]
        return self.parse_content(model, instructions, content, schema)

    def parse_content(self, model, instructions, content, schema):
        """Structured output from prepared content parts (text + images)."""
        r = self.client.responses.parse(model=model, instructions=instructions,
                                        input=[{"role": "user", "content": content}], text_format=schema)
        self._record(model, r.usage)
        if r.output_parsed is None:
            raise LLMError(f"{model} returned no parsed {schema.__name__} (refusal or empty output)")
        return r.output_parsed

    def create(self, model, instructions, input, tools):
        r = self.client.responses.create(model=model, instructions=instructions, input=input, tools=tools)
        self._record(model, r.usage)
        return r

    def usage_summary(self):
        return {m: dict(v) for m, v in self.usage.items()}
