"""Cache key -- architecture.md section 22.

SHA256(action + normalized_parameters + content_hash + prompt_version +
provider + model). Every input that can change the output is in the key --
drop `model` and the cache serves a different model's answer for a request
that asked for another; drop parameters and it serves the wrong language.
"""
from __future__ import annotations

import hashlib
import json


def compute_cache_key(
    *,
    action: str,
    normalized_parameters: dict[str, str],
    content_hash: str,
    prompt_version: str,
    provider: str,
    model: str,
) -> str:
    payload = json.dumps(
        {
            "action": action,
            "parameters": normalized_parameters,
            "content_hash": content_hash,
            "prompt_version": prompt_version,
            "provider": provider,
            "model": model,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
