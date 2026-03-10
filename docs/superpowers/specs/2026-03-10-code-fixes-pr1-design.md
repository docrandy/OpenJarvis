# Code Fixes PR 1 — Design Spec

**Date:** 2026-03-10
**Branch:** new branch off main (post PR #27 + #28 merge)
**Target:** main

## Context

External review identified 11 improvement areas. PR #27 addressed silent exceptions (~118 blocks). PR #28 fixed Apple Silicon VRAM and test failures. This PR covers the remaining code-level fixes.

## Scope

| # | Item | Files |
|---|------|-------|
| 1 | `jarvis doctor` vague labels | `cli/doctor_cmd.py` |
| 2 | Config verbosity — minimal default + `--full` | `core/config.py`, `cli/init_cmd.py` |
| 3 | Identity consistency — "pillars" → "primitives" | `pyproject.toml` |
| 4 | Remaining silent exception blocks (~19) | 6 files (see below) |

**Out of scope:** Apple Silicon VRAM (fixed in PR #28), Apple Silicon test (fixed in PR #28), all docs/identity items (PR 2).

---

## Task 1: `jarvis doctor` Labels

**File:** `src/openjarvis/cli/doctor_cmd.py` lines 213-220

**Current:**
```python
optional_packages = [
    ("fastapi", "openjarvis[server]"),
    ("torch", "torch (for learning)"),
    ("pynvml", "pynvml (GPU monitoring)"),
    ("amdsmi", "openjarvis[energy-amd]"),
    ("colbert", "openjarvis[memory-colbert]"),
    ("zeus", "openjarvis[energy-apple]"),
]
```

**Proposed:** Align all labels to descriptive format with install hint:
```python
optional_packages = [
    ("fastapi", "openjarvis[server]", "REST API server"),
    ("torch", "pip install torch", "SFT/GRPO training"),
    ("pynvml", "openjarvis[energy-nvidia]", "NVIDIA energy monitoring"),
    ("amdsmi", "openjarvis[energy-amd]", "AMD energy monitoring"),
    ("colbert", "openjarvis[memory-colbert]", "ColBERT memory backend"),
    ("zeus", "openjarvis[energy-apple]", "Apple Silicon energy monitoring"),
]
```

Update the loop on line 221 from `for pkg, label in optional_packages:` to:
```python
for pkg, install_hint, description in optional_packages:
    try:
        __import__(pkg)
        results.append(CheckResult(f"Optional: {description}", "ok", "Installed"))
    except Exception:
        results.append(
            CheckResult(f"Optional: {description}", "warn", f"Not installed ({install_hint})")
        )
```

**Verification:** `uv run pytest tests/cli/ -v --tb=short`

---

## Task 2: Minimal Config Default

### 2a: Add `generate_minimal_toml()` to `core/config.py`

New function alongside existing `generate_default_toml()`. ~20-30 lines:

```python
def generate_minimal_toml(hw: HardwareInfo) -> str:
    """Render a minimal TOML config with only essential settings."""
    engine = recommend_engine(hw)
    model = recommend_model(hw, engine)
    gpu_comment = ""
    if hw.gpu:
        mem_label = "unified memory" if hw.gpu.vendor == "apple" else "VRAM"
        gpu_comment = f"\n# GPU: {hw.gpu.name} ({hw.gpu.vram_gb} GB {mem_label})"
    return f"""\
# OpenJarvis configuration
# Hardware: {hw.cpu_brand} ({hw.cpu_count} cores, {hw.ram_gb} GB RAM){gpu_comment}
# Full reference config: jarvis init --full

[engine]
default = "{engine}"

[intelligence]
default_model = "{model}"

[agent]
default_agent = "simple"

[tools]
enabled = ["code_interpreter", "web_search", "file_read", "shell_exec"]
"""
```

### 2b: Update `cli/init_cmd.py` to use minimal by default

- Update the import (line ~16) to also import `generate_minimal_toml`
- Add `--full` flag to the click command: `@click.option("--full", "full_config", is_flag=True, help="Generate full reference config with all sections")`
- On line 155, change:
  - Default (`full_config=False`): call `generate_minimal_toml(hw)`
  - With `--full` flag: call existing `generate_default_toml(hw)`
- Also add `generate_minimal_toml` to the `__all__` list in `core/config.py`

**Verification:** `uv run pytest tests/cli/test_init_guidance.py -v --tb=short`

---

## Task 3: Identity Consistency

**File:** `pyproject.toml` line 8

**Change:**
```
"OpenJarvis — modular AI assistant backend with composable intelligence pillars"
→
"OpenJarvis — modular AI assistant backend with composable intelligence primitives"
```

One word. No other surfaces need changes (README, mkdocs.yml, docs/index.md already say "primitives").

**Verification:** `grep -r "pillar" pyproject.toml` returns nothing.

---

## Task 4: Remaining Silent Exception Blocks

Same design as PR #27. Log-level policy:
- `warning` — operational failures in API endpoints
- `debug` — best-effort, telemetry, fallback mechanisms

### 4a: `cli/serve.py` (4 blocks)

| Line | Context | Level |
|------|---------|-------|
| 81-82 | Telemetry store init | `debug` |
| 108-109 | Energy monitor creation | `debug` |
| 112-113 | InstrumentedEngine wrapping | `debug` |
| 209-210 | Speech backend discovery | `debug` |

### 4b: `core/config.py`

No remaining silent exceptions — the `except OSError: pass` at line 157 already catches a specific exception type for hardware detection. No change needed.

### 4c: `server/api_routes.py` (11 blocks)

All `warning` level — these are API endpoints where callers need visibility into failures. Each gets `logger.warning("Failed to <action>: %s", exc)` before returning the fallback.

### 4d: `tools/` (4 blocks)

| File | Line | Context | Level |
|------|------|---------|-------|
| `agent_tools.py` | 198-199 | Event bus publish | `debug` |
| `git_tool.py` | 384-385 | Rust fallback to CLI | `debug` |
| `http_request.py` | 121-122 | Content fetch fallback | `debug` |
| `templates/loader.py` | 188-189 | Template parse skip | `debug` |

### Rules (same as PR #27):
- `except ImportError` blocks: **never touch**
- Logger: `logging.getLogger(__name__)`
- Format: `%s` style (not f-strings)
- Each file gets `import logging` + `logger = ...` if not already present

**Verification:** `grep -rn "except.*:$" <file> | grep -v Import` shows no bare handlers without logging.

---

## Verification Criteria

1. `uv run ruff check src/ tests/` — all clean
2. `uv run pytest tests/ -m "not live and not cloud and not slow"` — no new failures
3. `grep -r "pillar" pyproject.toml` — empty
4. No `except ImportError` blocks modified
