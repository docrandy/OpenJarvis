# API Reference: Security

The `openjarvis.security` package provides text scanning, content guardrails, file path filtering, and audit logging. All public components are documented below.

For usage examples and configuration, see the [Security user guide](../user-guide/security.md). For the architectural design, see [Security architecture](../architecture/security.md).

---

## Types

Core data types shared across the security subsystem.

### ThreatLevel

Severity classification for individual scan findings. Ordered from least to most severe: `LOW` < `MEDIUM` < `HIGH` < `CRITICAL`.

::: openjarvis.security.types.ThreatLevel
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

### RedactionMode

Controls the action taken by `GuardrailsEngine` when findings are detected.

::: openjarvis.security.types.RedactionMode
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

### SecurityEventType

Categories of security events recorded by `AuditLogger`.

::: openjarvis.security.types.SecurityEventType
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

### ScanFinding

A single match produced by a scanner. Includes the pattern name, matched text, position, threat level, and a human-readable description.

::: openjarvis.security.types.ScanFinding
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

### ScanResult

Aggregated result from one or more scanner passes. The `clean` property returns `True` when no findings were detected; `highest_threat` returns the most severe `ThreatLevel` found.

::: openjarvis.security.types.ScanResult
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

### SecurityEvent

A recorded security event, as persisted by `AuditLogger`.

::: openjarvis.security.types.SecurityEvent
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

---

## BaseScanner

`BaseScanner` is the abstract base class for all scanner implementations. Implement both `scan()` and `redact()` to create a custom scanner.

::: openjarvis.security._stubs.BaseScanner
    options:
      show_source: true
      show_root_heading: true
      heading_level: 3

---

## SecretScanner

Detects API keys, tokens, passwords, and credentials in text using regex patterns. See the [pattern reference table](../user-guide/security.md#pattern-reference) in the user guide for the full list of patterns and their threat levels.

::: openjarvis.security.scanner.SecretScanner
    options:
      show_source: true
      show_root_heading: true
      heading_level: 3

---

## PIIScanner

Detects personally identifiable information including email addresses, Social Security Numbers, credit card numbers, phone numbers, and public IP addresses.

::: openjarvis.security.scanner.PIIScanner
    options:
      show_source: true
      show_root_heading: true
      heading_level: 3

---

## GuardrailsEngine

`GuardrailsEngine` wraps any `InferenceEngine` with security scanning on both input and output. It implements the full `InferenceEngine` interface, so it can be used anywhere an engine is expected.

!!! note "Registration"
    `GuardrailsEngine` is **not** registered in `EngineRegistry`. Instantiate it directly by wrapping an existing engine instance.

::: openjarvis.security.guardrails.GuardrailsEngine
    options:
      show_source: true
      show_root_heading: true
      heading_level: 3

### SecurityBlockError

Raised by `GuardrailsEngine` when `mode=RedactionMode.BLOCK` and findings are detected during a scan. Catch this exception to handle blocked requests gracefully.

```python
from openjarvis.security.guardrails import GuardrailsEngine, SecurityBlockError
from openjarvis.security.types import RedactionMode

guarded = GuardrailsEngine(engine, mode=RedactionMode.BLOCK)

try:
    response = guarded.generate(messages, model="qwen3:8b")
except SecurityBlockError as exc:
    # exc.args[0] describes the direction and finding count
    print(f"Request blocked: {exc}")
```

::: openjarvis.security.guardrails.SecurityBlockError
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

---

## File Policy

Functions and constants for filtering sensitive file paths. Used internally by `FileReadTool` and the memory ingest path.

### DEFAULT_SENSITIVE_PATTERNS

The default set of glob patterns used to identify sensitive files. This is a `frozenset[str]` exported from `openjarvis.security.file_policy`.

See the [sensitive file patterns table](../user-guide/security.md#sensitive-file-patterns) in the user guide for the complete list.

::: openjarvis.security.file_policy.DEFAULT_SENSITIVE_PATTERNS
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

### is_sensitive_file

::: openjarvis.security.file_policy.is_sensitive_file
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

### filter_sensitive_paths

::: openjarvis.security.file_policy.filter_sensitive_paths
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

---

## AuditLogger

Append-only SQLite-backed storage for security events. Subscribes to `SECURITY_SCAN`, `SECURITY_ALERT`, and `SECURITY_BLOCK` events on the `EventBus` when a bus is provided.

The default database path is `~/.openjarvis/audit.db`, overridable via `security.audit_log_path` in `config.toml`.

```python title="audit_logger_example.py"
from openjarvis.core.events import EventBus
from openjarvis.security.audit import AuditLogger
from openjarvis.security.guardrails import GuardrailsEngine
from openjarvis.security.types import RedactionMode

bus = EventBus()
audit = AuditLogger(bus=bus)

guarded = GuardrailsEngine(engine, mode=RedactionMode.WARN, bus=bus)

# Security events from guarded engine are now persisted automatically
events = audit.query(limit=10)
print(f"Logged {audit.count()} events")
audit.close()
```

::: openjarvis.security.audit.AuditLogger
    options:
      show_source: true
      show_root_heading: true
      heading_level: 3
