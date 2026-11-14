"""Optional advisory OpenAI planner.

Policy and all tools remain server-owned. This module is deliberately opt-in so
the synthetic demo runs without credentials or network access.
"""

import json
import os
from urllib.request import Request, urlopen


def advisory_plan(case_id: str, message: str) -> str | None:
    """Return a short, non-authoritative plan from the configured GPT model."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        "input": [
            {
                "role": "system",
                "content": (
                    "You are Saathi's advisory triage agent. Return one short sentence. "
                    "You cannot authorize refunds, change orders, or claim payment settlement."
                ),
            },
            {"role": "user", "content": f"Synthetic case {case_id}: {message}"},
        ],
        "max_output_tokens": 100,
    }
    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:  # nosec B310: fixed official endpoint
            data = json.loads(response.read())
        return data.get("output_text", "").strip()[:300] or None
    except Exception:
        # A failed advisor never changes the deterministic, safe workflow.
        return None
