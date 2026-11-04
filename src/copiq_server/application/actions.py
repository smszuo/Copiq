"""Action registry -- architecture.md section 15.1, 18, 18.2, 19-22.

Each action names its default prompt_version and the parameter keys it
accepts. Unknown parameter keys are rejected (section 15.1); unknown values
fall back to configured defaults.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# architecture.md section 22 -- the diagram type is part of the cache key
# via normalized_parameters, so a different type never serves a stale
# diagram for a different one. "auto" means "let the model choose".
_DIAGRAM_TYPES: dict[str, str] = {
    "auto": "",
    "flowchart": "flowchart",
    "sequence": "sequenceDiagram",
    "class": "classDiagram",
    "er": "erDiagram",
}


@dataclass(frozen=True)
class ActionSpec:
    name: str
    prompt_version: str  # the default; [prompts.versions] in config can override it per-action
    param_keys: frozenset[str]


ACTIONS: dict[str, ActionSpec] = {
    "translate": ActionSpec("translate", "v1", frozenset({"targetLanguage"})),
    # v2 answers in targetLanguage throughout; v1 kept the explanation in
    # English (architecture.md section 20).
    "explain": ActionSpec("explain", "v2", frozenset({"targetLanguage"})),
    "simplify": ActionSpec("simplify", "v1", frozenset()),
    # Always simple English, so no targetLanguage -- unlike explain.
    "explain-simple": ActionSpec("explain-simple", "v1", frozenset()),
    "summarize": ActionSpec("summarize", "v1", frozenset()),
    "breakdown": ActionSpec("breakdown", "v1", frozenset()),
    # Same breakdown, but explained in targetLanguage (English parts kept).
    "breakdown-target": ActionSpec("breakdown-target", "v1", frozenset({"targetLanguage"})),
    "skeleton": ActionSpec("skeleton", "v1", frozenset()),
    # English meaning plus a targetLanguage translation per word.
    "vocabulary": ActionSpec("vocabulary", "v1", frozenset({"targetLanguage"})),
    "diagram": ActionSpec("diagram", "v1", frozenset({"diagramType"})),
}


class UnknownActionError(ValueError):
    pass


class InvalidParametersError(ValueError):
    """Any parameter validation failure -- an unknown key, or a known key
    with a value outside what that parameter accepts. Both are equally a
    bad request (section 16's 400), so this carries a plain message rather
    than assuming the unknown-key shape specifically."""


class PromptNotFoundError(RuntimeError):
    """Neither the configured override directory nor the bundled prompts
    directory has this action/version -- almost always a typo in
    [prompts.versions], section 18.2."""


class PromptRenderError(RuntimeError):
    """A custom prompt (section 18.2) contains a `{...}` placeholder this
    action doesn't supply a value for -- most often stray literal braces
    (e.g. a JSON example) that needed escaping as `{{`/`}}`, not a missing
    feature."""


def get_action(name: str) -> ActionSpec:
    try:
        return ACTIONS[name]
    except KeyError:
        raise UnknownActionError(name) from None


def normalize_parameters(
    spec: ActionSpec, raw: dict[str, object] | None, *, default_target_language: str
) -> dict[str, str]:
    """Reject unknown keys, fill defaults, sort keys, lower-case values.
    architecture.md section 15.1 -- this normalized form is what gets hashed."""
    raw = raw or {}
    unknown = set(raw.keys()) - spec.param_keys
    if unknown:
        raise InvalidParametersError(f"unknown parameters: {sorted(unknown)}")

    result: dict[str, str] = {}

    if "targetLanguage" in spec.param_keys:
        value = raw.get("targetLanguage", default_target_language)
        result["targetLanguage"] = str(value).strip().lower()

    if "diagramType" in spec.param_keys:
        value = str(raw.get("diagramType", "auto")).strip().lower()
        if value not in _DIAGRAM_TYPES:
            raise InvalidParametersError(
                f"diagramType must be one of {sorted(_DIAGRAM_TYPES)}, got {value!r}"
            )
        result["diagramType"] = value

    return dict(sorted(result.items()))


def resolve_prompt_version(spec: ActionSpec, version_overrides: dict[str, str]) -> str:
    """architecture.md section 18.2 -- [prompts.versions] lets an operator
    point one action at a different prompt version without a code change.
    Falls back to the action's built-in default when unlisted."""
    return version_overrides.get(spec.name, spec.prompt_version)


def load_template(name: str, version: str, prompts_dir: Path | None) -> str:
    """Look in the configured override directory first, falling back to the
    bundled prompt -- architecture.md section 18.2. This is what lets every
    prompt be replaced without touching the installed package: add
    `<prompts_dir>/<name>/<version>.txt` and either let it shadow an
    existing version's filename, or give it a new version string and point
    [prompts.versions] at it. The latter is what section 18's
    reproducibility principle actually asks for -- overwriting an existing
    version in place means `prompt_version` on old rows silently stops
    describing what produced them.
    """
    filename = f"{version}.txt"
    if prompts_dir is not None:
        override_path = Path(prompts_dir) / name / filename
        if override_path.is_file():
            return override_path.read_text(encoding="utf-8")

    bundled_path = _PROMPTS_DIR / name / filename
    if not bundled_path.is_file():
        raise PromptNotFoundError(
            f"no prompt found for action={name!r} version={version!r} "
            f"(checked {prompts_dir / name / filename if prompts_dir else '(no override dir configured)'} "
            f"and {bundled_path})"
        )
    return bundled_path.read_text(encoding="utf-8")


def build_prompt(
    spec: ActionSpec, normalized_params: dict[str, str], *, version: str, prompts_dir: Path | None
) -> str:
    template = load_template(spec.name, version, prompts_dir)

    if spec.name == "diagram":
        diagram_type = normalized_params.get("diagramType", "auto")
        mermaid_keyword = _DIAGRAM_TYPES[diagram_type]
        if mermaid_keyword:
            instruction = f"Use a Mermaid `{mermaid_keyword}` diagram specifically."
        else:
            instruction = (
                "Pick whichever Mermaid diagram type actually fits the content -- "
                "flowchart for a process, sequenceDiagram for a request/response "
                "flow, classDiagram for code structure, erDiagram for data "
                "relationships."
            )
        format_kwargs = {"diagram_type_instruction": instruction}
    else:
        format_kwargs = {"target_language": normalized_params.get("targetLanguage", "")}

    try:
        return template.format(**format_kwargs)
    except KeyError as e:
        raise PromptRenderError(
            f"prompt for action={spec.name!r} version={version!r} references "
            f"{{{e.args[0]}}}, which this action doesn't supply -- if you meant "
            f"literal curly braces (e.g. a JSON example), escape them as "
            f"{{{{ and }}}}"
        ) from e


_MERMAID_FENCE_RE = re.compile(r"```(?:mermaid)?\s*\n(.*?)```", re.DOTALL)


def postprocess_result(spec: ActionSpec, raw: str) -> str:
    """Defensive parsing for the diagram action's response, applied once
    server-side so both the CLI and the stored (cached) result get clean
    Mermaid source, not whatever wrapper prose the model happened to add
    that particular time. The default prompts/diagram/v1.txt asks for only
    a fenced ```mermaid block, but models don't always comply -- extract it
    if present; otherwise trust the response is already bare source and
    just trim it. Every other action passes its result through unchanged.
    Still applied to a custom diagram prompt (section 18.2) -- if a custom
    prompt asks for something other than a mermaid fence, this becomes a
    no-op in practice since the regex simply won't match."""
    if spec.name != "diagram":
        return raw
    match = _MERMAID_FENCE_RE.search(raw)
    return match.group(1).strip() if match else raw.strip()
