"""Claude CLI provider -- architecture.md section 17.1.

Invokes the local `claude` binary in headless mode, reusing the operator's
existing subscription login. No API key is provisioned or stored.

Security notes (see 17.1 for the full reasoning):
- prompt goes over stdin, never argv (length, quoting, `ps` visibility)
- --restricted --disable-slash-commands --allowedTools '' --max-turns 1
  strip the agent down to a single text completion -- clipboard content is
  untrusted input, so this bounds the blast radius of prompt injection
- create_subprocess_exec, never _shell -- no shell quoting of clipboard data
- start_new_session=True + os.killpg on timeout -- kills the whole process
  group, not just the direct child
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
from decimal import Decimal

from copiq_server.providers.base import PROMPT_TEMPLATE, AiProviderError, AiRequest, AiResult


class ClaudeCliProvider:  # satisfies AiProvider structurally
    def __init__(self, *, model: str = "haiku", timeout_seconds: int = 120) -> None:
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def execute(self, request: AiRequest) -> AiResult:
        model = request.model or self._model
        cmd = [
            "claude",
            "-p",
            "--model", model,
            "--output-format", "json",
            "--restricted",
            "--disable-slash-commands",
            "--allowedTools", "",
            "--max-turns", "1",
        ]

        prompt = PROMPT_TEMPLATE.format(instruction=request.prompt, content=request.input)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,  # own process group, so we can killpg it
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(prompt.encode("utf-8")),
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            _kill_process_group(proc)
            raise AiProviderError(f"claude CLI timed out after {self._timeout_seconds}s") from None

        if proc.returncode != 0:
            raise AiProviderError(
                f"claude CLI exited {proc.returncode}: {stderr.decode('utf-8', 'replace')[:2000]}"
            )

        try:
            data = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise AiProviderError(f"claude CLI produced non-JSON output: {e}") from e

        if data.get("is_error"):
            raise AiProviderError(f"claude CLI reported an error: {data.get('result')!r}")

        model_usage = data.get("modelUsage") or {}
        canonical_model = next(iter(model_usage), model)
        usage = model_usage.get(canonical_model, {})

        return AiResult(
            content=data.get("result", ""),
            model=canonical_model,
            provider_version="claude-cli",
            input_tokens=usage.get("inputTokens"),
            output_tokens=usage.get("outputTokens"),
            cost_usd=Decimal(str(data["total_cost_usd"])) if "total_cost_usd" in data else None,
            duration_ms=data.get("duration_ms", 0),
        )


def _kill_process_group(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
