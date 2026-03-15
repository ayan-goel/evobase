"""Stack-aware system prompt builder.

The system prompt is the highest-leverage part of the prompt chain.
It tells the model exactly what kind of expert it should be, what the
codebase context looks like, and where to focus attention.

Each framework gets a dedicated focus list derived from common patterns
in that ecosystem. This specificity dramatically improves signal quality
compared to a generic "find bugs" prompt.

Framework-specific focus strings live in the ``frameworks/`` sub-package.
Each framework module exports a ``FOCUS`` constant (bullet points +
structured rule catalog). The ``get_framework_focus`` function dispatches
to the correct module by framework name.
"""

from runner.detector.types import DetectionResult
from runner.llm.prompts.frameworks import get_framework_focus


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def build_system_prompt(detection: DetectionResult) -> str:
    """Build a detailed, stack-aware system prompt from a DetectionResult.

    The returned prompt should be used as the `system` role message for all
    agent calls in a single run. It establishes the model's persona, the
    codebase context, and framework-specific focus areas.
    """
    framework_label = detection.framework or "JavaScript/TypeScript"
    package_manager = detection.package_manager or "npm"
    install_cmd = detection.install_cmd or f"{package_manager} install"
    test_cmd = detection.test_cmd or "(none detected)"
    build_cmd = detection.build_cmd or "(none detected)"

    framework_focus = get_framework_focus(detection.framework)

    return f"""You are a senior software engineer specialising in {framework_label} performance \
optimisation and code quality.

You are analysing a {framework_label} repository with the following configuration:
  Package manager : {package_manager}
  Install command : {install_cmd}
  Build command   : {build_cmd}
  Test command    : {test_cmd}

Your mission is to identify concrete, measurable improvements — not style preferences.
Every opportunity you identify must meet ALL of these criteria:
  1. It is a real performance, correctness, or tech-debt issue (not a stylistic one).
  2. It can be fixed with a targeted code change of ≤200 lines across ≤5 files.
  3. The fix does NOT modify tests, config files, or package.json / lock files.
  4. The improvement is objectively measurable (speed, memory, bundle size, error rate).

{framework_focus}

Output format:
  Always respond with valid JSON. Include a top-level `"reasoning"` field that
  contains your detailed chain-of-thought before giving the answer. This reasoning
  is surfaced to the developer in the UI so they can understand how you reached
  each conclusion.

Constraints (hard limits — never violate):
  - Touch at most 5 files per patch.
  - Change at most 200 lines per patch.
  - Never modify test files (*test*, *spec*, *.test.*, *.spec.*).
  - Never modify config files (*.config.*, *.json, *.yaml, *.yml, *.toml, *.env).
  - Never modify package.json or any lock file.
"""
