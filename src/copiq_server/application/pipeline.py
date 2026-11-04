"""AI action pipeline -- architecture.md section 16.

    Secret Gate (409) -> Validate Action/Params (400) -> Normalize ->
    Cache Key -> Lookup (hit -> return) -> Size Check (413) ->
    Build Prompt -> AI Provider (failure -> 502) -> Upsert -> Return
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from copiq_server.application.actions import (
    InvalidParametersError,
    PromptNotFoundError,
    PromptRenderError,
    UnknownActionError,
    build_prompt,
    get_action,
    normalize_parameters,
    postprocess_result,
    resolve_prompt_version,
)
from copiq_server.application.cache import compute_cache_key
from copiq_server.config import Settings
from copiq_server.domain.models import AiActionResult, ClipboardItem
from copiq_server.providers.base import AiProvider, AiProviderError, AiRequest


class PipelineError(Exception):
    """Base for pipeline errors; `status_code` is what the API layer returns."""

    status_code: int = 500


class SecretBlockedError(PipelineError):
    status_code = 409

    def __init__(self, matched_pattern: str) -> None:
        self.matched_pattern = matched_pattern
        super().__init__(f"content flagged by secret scanner: {matched_pattern}")


class BadActionRequestError(PipelineError):
    status_code = 400


class ContentTooLargeError(PipelineError):
    status_code = 413


class ProviderFailedError(PipelineError):
    status_code = 502


class PromptConfigError(PipelineError):
    """A [prompts] misconfiguration (section 18.2) -- a typo'd version in
    [prompts.versions], or a custom prompt referencing a placeholder the
    action doesn't supply. This is a server-side configuration problem,
    not something the client did wrong, hence 500 rather than 400."""

    status_code = 500


@dataclass
class ActionOutcome:
    result: AiActionResult
    cached: bool


async def run_action(
    db: Session,
    *,
    item: ClipboardItem,
    action_name: str,
    parameters: dict[str, object] | None,
    acknowledge_secret: bool,
    provider: AiProvider,
    provider_name: str,
    settings: Settings,
) -> ActionOutcome:
    # 1. Secret gate (architecture.md section 29.1)
    if item.has_possible_secret and not (acknowledge_secret and settings.secret_detection.allow_override):
        raise SecretBlockedError(matched_pattern="see clipboard item flag")

    # 2. Validate action + parameters
    try:
        spec = get_action(action_name)
    except UnknownActionError as e:
        raise BadActionRequestError(f"unknown action: {e}") from None

    try:
        normalized = normalize_parameters(
            spec, parameters, default_target_language=settings.ai.default_target_language
        )
    except InvalidParametersError as e:
        raise BadActionRequestError(str(e)) from None

    model = settings.ai.model_overrides.get(action_name, settings.ai.model)
    prompt_version = resolve_prompt_version(spec, settings.prompts.versions)
    prompts_dir = Path(settings.prompts.dir).expanduser() if settings.prompts.dir else None

    # 3. Cache key + lookup
    cache_key = compute_cache_key(
        action=action_name,
        normalized_parameters=normalized,
        content_hash=item.content_hash,
        prompt_version=prompt_version,
        provider=provider_name,
        model=model,
    )

    existing = db.execute(
        select(AiActionResult).where(AiActionResult.cache_key == cache_key)
    ).scalar_one_or_none()
    if existing is not None and existing.status == "completed":
        return ActionOutcome(result=existing, cached=True)

    # 4. Size check
    if len(item.content) > settings.ai.max_input_length:
        raise ContentTooLargeError(
            f"content ({len(item.content)} chars) exceeds ai.max_input_length "
            f"({settings.ai.max_input_length})"
        )

    # 5. Build prompt, call provider
    try:
        prompt = build_prompt(spec, normalized, version=prompt_version, prompts_dir=prompts_dir)
    except (PromptNotFoundError, PromptRenderError) as e:
        raise PromptConfigError(str(e)) from e
    request = AiRequest(prompt=prompt, input=item.content, model=model)

    row = existing or AiActionResult(
        clipboard_item_id=item.id,
        cache_key=cache_key,
        action=action_name,
        parameters=json.dumps(normalized, sort_keys=True) if normalized else None,
        provider=provider_name,
        model=model,
        prompt_version=prompt_version,
        status="pending",
    )

    try:
        ai_result = await provider.execute(request)
    except AiProviderError as e:
        row.status = "failed"
        row.error_message = str(e)[:4000]
        db.add(row)
        db.commit()
        db.refresh(row)
        raise ProviderFailedError(str(e)) from e

    row.status = "completed"
    row.result = postprocess_result(spec, ai_result.content)
    row.error_message = None
    row.model = ai_result.model
    row.provider_version = ai_result.provider_version
    db.add(row)
    db.commit()
    db.refresh(row)

    return ActionOutcome(result=row, cached=False)
