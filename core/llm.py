"""
core/llm.py — LLM interaction via NVIDIA NIM (OpenAI-compatible API).

No UI framework imports. call_llm() is a generator for streaming; both
clients handle the stream differently (Streamlit: write_stream, Flask: join).
extract_events() returns a plain dict — each client renders it as needed.
"""

import json
from typing import Generator

from openai import OpenAI

from .config import NVIDIA_API_KEY, NVIDIA_MODEL
from .prompts import event_system_prompt, system_prompt

# Event-related keywords used to detect whether a query targets events.
_EVENT_KEYWORDS: frozenset[str] = frozenset({
    "event", "events", "conference", "summit", "meetup", "hackathon",
    "workshop", "seminar", "forum", "expo", "congress", "webinar",
    "festival", "bootcamp", "upcoming", "schedule", "hackaton","agenda","hackatons"
})


def is_event_query(prompt: str) -> bool:
    """Returns True when the prompt is requesting events / schedules.

    Simple keyword intersection — fast and requires no external call.

    Args:
        prompt (str): The user's raw query.

    Returns:
        bool: True if the query appears to be about events.
    """
    return bool(set(prompt.lower().split()) & _EVENT_KEYWORDS)


def _nvidia_client() -> OpenAI:
    """Returns an OpenAI client pointed at the NVIDIA NIM endpoint."""
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY,
    )


def call_llm(
    prompt: str,
    with_context: bool = True,
    context: str | None = None,
) -> Generator[str, None, None]:
    """Streams an LLM answer via NVIDIA NIM.

    Args:
        prompt (str): The user question.
        with_context (bool): Whether to attach a system prompt + context.
        context (str | None): Pre-assembled context string from the web pipeline.

    Yields:
        str: Token chunks as they arrive from the API.

    Notes:
        Callers that need the full answer as a string can do:
            answer = "".join(call_llm(...))
    """
    if not NVIDIA_API_KEY:
        yield "❌ NVIDIA_API_KEY is not set. Add it to your .env file."
        return

    if with_context:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {prompt}"},
        ]
    else:
        messages = [{"role": "user", "content": prompt}]

    response = _nvidia_client().chat.completions.create(
        model=NVIDIA_MODEL,
        messages=messages,
        temperature=0.2,
        top_p=0.7,
        max_tokens=1024,
        stream=True,
    )

    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content


def extract_events(context: str, prompt: str) -> dict:
    """Extracts structured event data from context using the event system prompt.

    Non-streaming call — the full response must arrive before JSON parsing.
    Returns a safe dict in all cases; never raises.

    Args:
        context (str): Assembled web context (output of build_context_from_crawl).
        prompt (str): The original user query.

    Returns:
        dict: {
            "events": [ <event objects matching the schema in event_system_prompt> ],
            "error":  <str if something went wrong, otherwise absent>
        }
    """
    if not NVIDIA_API_KEY:
        return {"events": [], "error": "NVIDIA_API_KEY is not set."}

    messages = [
        {"role": "system", "content": event_system_prompt},
        {"role": "user", "content": f"Context:\n{context}\n\nQuery: {prompt}"},
    ]

    try:
        response = _nvidia_client().chat.completions.create(
            model=NVIDIA_MODEL,
            messages=messages,
            temperature=0.1,   # deterministic JSON output
            top_p=0.7,
            max_tokens=2048,   # allow large event lists
            stream=False,      # must be synchronous — we parse the full response
        )
        raw: str = response.choices[0].message.content.strip()
        print(f"Event extractor raw ({len(raw)} chars): {raw[:200]}")

        # Strip accidental markdown code fences (some models add them anyway)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        return json.loads(raw)

    except json.JSONDecodeError as exc:
        print(f"JSON parse error: {exc}")
        return {"events": [], "error": f"Model returned invalid JSON: {exc}"}
    except Exception as exc:
        print(f"Event extraction API error: {exc}")
        return {"events": [], "error": str(exc)}
