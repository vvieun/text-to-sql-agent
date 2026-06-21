import os

import anthropic

from .tracing import observe, record_generation

MODEL = os.environ.get("DWH_AGENT_MODEL", "claude-opus-4-8")

_client = None


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


@observe(name="llm", as_type="generation")
def complete(system, user, max_tokens=1500):
    resp = client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    record_generation(MODEL, {"system": system, "user": user}, text, resp.usage)
    return text
