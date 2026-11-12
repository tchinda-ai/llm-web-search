"""
core/llm.py — LLM interaction via NVIDIA NIM (OpenAI-compatible API).

No UI framework imports. call_llm() is a generator for streaming; both
clients handle the stream differently (Streamlit: write_stream, Flask: join).
extract_events() returns a plain dict — each client renders it as needed.
"""

import json
import time
from typing import Generator

from openai import OpenAI

from .config import NVIDIA_API_KEY, NVIDIA_MODEL
from .prompts import event_system_prompt, system_prompt, query_expansion_prompt

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


def _create_completion_with_retry(client: OpenAI, **kwargs):
    """Executes a chat completion with retry backoff for transient connection errors or 5xx."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            err_str = str(exc)
            is_transient = any(msg in err_str for msg in [
                "Connection", "RemoteDisconnected", "timeout", "timed out", 
                "500", "502", "503", "504", "RateLimitError", "429"
            ])
            if attempt < max_retries - 1 and is_transient:
                sleep_secs = 2 * (attempt + 1)
                print(f"NVIDIA API transient error ({err_str}). Retrying in {sleep_secs}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(sleep_secs)
                continue
            raise


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
        response = _create_completion_with_retry(
            _nvidia_client(),
            model=NVIDIA_MODEL,
            messages=messages,
            temperature=0.1,   # deterministic JSON output
            top_p=0.7,
            max_tokens=6144,   # allow large event lists without mid-stream JSON truncation
            stream=False,      # must be synchronous — we parse the full response
        )
        choice = response.choices[0]
        msg = choice.message
        raw: str = (msg.content or getattr(msg, "reasoning_content", None) or "").strip()
        if not raw:
            print(f"Event extractor warning: Model returned empty content (finish_reason={choice.finish_reason})")
            return {"events": [], "error": f"Model returned empty content (finish_reason={choice.finish_reason})"}
        print(f"Event extractor raw ({len(raw)} chars): {raw[:200]}")

        # Robustly extract JSON if wrapped in markdown code fences or conversational text
        import re
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)
        else:
            # Fallback if the regex fails (e.g., if there are no braces, though unlikely)
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

        data = json.loads(raw)
        events = data.get("events", [])
        if isinstance(events, list) and len(events) > 1:
            data["events"] = deduplicate_events(events)
        return data

    except json.JSONDecodeError as exc:
        print(f"JSON parse error: {exc}")
        return {"events": [], "error": f"Model returned invalid JSON: {exc}"}
    except Exception as exc:
        print(f"Event extraction API error: {exc}")
        return {"events": [], "error": str(exc)}

def deduplicate_events(events: list[dict]) -> list[dict]:
    """In-memory deduplication of extracted events within a search response.
    
    Clusters events by normalized core English title and start month/year.
    If duplicates exist, preserves the record with the longest description/highest confidence.
    """
    seen: dict[str, dict] = {}
    for ev in events:
        title = ev.get("title", "")
        # Extract English part if formatted as [en] ... [fr] ...
        en_part = title.split("[fr]")[0].replace("[en]", "").strip() if "[en]" in title else title
        # Strip marketing slogans, themes, or subtitles
        core_title = en_part.split(" - ")[0].split(" — ")[0].split(":")[0].strip().lower()
        # Extract YYYY-MM
        starts_at = ev.get("starts_at_raw", "")
        month_key = starts_at[:7] if len(starts_at) >= 7 else starts_at

        dedup_key = f"{core_title}|{month_key}"

        if dedup_key not in seen:
            seen[dedup_key] = ev
        else:
            existing = seen[dedup_key]
            existing_desc_len = len(existing.get("description") or "")
            new_desc_len = len(ev.get("description") or "")
            if new_desc_len > existing_desc_len or ev.get("confidence", 0) > existing.get("confidence", 0):
                seen[dedup_key] = ev

    return list(seen.values())

def generate_search_variants(prompt: str) -> list[str]:
    """Generates nuanced subcategory search queries based on the user's prompt.
    
    Args:
        prompt (str): The original user query.

    Returns:
        list[str]: A list of variant search queries. Returns empty list on failure.
    """
    if not NVIDIA_API_KEY:
        return []

    messages = [
        {"role": "system", "content": query_expansion_prompt},
        {"role": "user", "content": f"Prompt: {prompt}"},
    ]

    try:
        response = _create_completion_with_retry(
            _nvidia_client(),
            model=NVIDIA_MODEL,
            messages=messages,
            temperature=0.3,
            top_p=0.7,
            max_tokens=2048,   # allow reasoning/thinking tokens without truncating output
            stream=False,
        )
        choice = response.choices[0]
        msg = choice.message
        raw: str = (msg.content or getattr(msg, "reasoning_content", None) or "").strip()
        if not raw:
            print(f"Query expansion warning: Model returned empty content (finish_reason={choice.finish_reason})")
            return []

        # Robustly extract JSON if wrapped in markdown code fences or conversational text
        import re
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)
        elif raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        # Clean trailing commas which cause JSON parsing failures
        cleaned_json = re.sub(r',\s*([\]}])', r'\1', raw)

        raw_variants = []
        try:
            data = json.loads(cleaned_json)
            if isinstance(data, dict):
                raw_variants = data.get("variants", [])
            elif isinstance(data, list):
                raw_variants = data
        except Exception as json_err:
            # Fallback regex extraction of quoted strings if JSON has syntax errors
            print(f"Query expansion JSON parse fallback: {json_err}")
            raw_variants = re.findall(r'"([^"\n\\]{4,80})"', raw)

        valid_variants = []
        forbidden_substrings = {"string", "variant", "...", "dummy", "placeholder", "example", "<string"}
        for v in raw_variants:
            if not isinstance(v, str):
                continue
            v_clean = v.strip().strip('"').strip("'").strip()
            # Variants must be multi-word search phrases (2 to 7 words)
            words = v_clean.split()
            if len(words) < 2 or len(words) > 7:
                continue
            # Discard commentary, code, or syntax artifacts
            if any(char in v_clean for char in ['=', '{', '}', '<', '>', '[', ']', '(', ')', ';', ':']):
                continue
            v_lower = v_clean.lower()
            if any(bad in v_lower for bad in forbidden_substrings):
                continue
            if v_lower == prompt.lower() or v_clean in valid_variants:
                continue
            valid_variants.append(v_clean)
            # Strictly limit to 4 variants maximum
            if len(valid_variants) >= 4:
                break

        # Fallback to smart keyword variants if model returned placeholders or failed
        if not valid_variants:
            clean_prompt = re.sub(r'\b(upcoming|latest|current)\b', '', prompt, flags=re.IGNORECASE).strip()
            valid_variants = [
                f"{clean_prompt} 2026",
                f"{clean_prompt} schedule 2026",
            ]

        print(f"Generated {len(valid_variants)} search variants for '{prompt}': {valid_variants}")
        return valid_variants

    except Exception as exc:
        print(f"Query expansion error: {exc}")
        clean_prompt = re.sub(r'\b(upcoming|latest|current)\b', '', prompt, flags=re.IGNORECASE).strip()
        return [f"{clean_prompt} 2026", f"{clean_prompt} schedule 2026"]
