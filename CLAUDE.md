# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

OpenJarvis is a research framework for studying on-device AI systems. Phase 5 (v1.0) complete, Phase 6 (trace system + learning) in progress. Core abstractions: Intelligence, Engine, Agentic Logic, Memory — with trace-driven learning as a cross-cutting concern. Python SDK (`Jarvis` class), OpenClaw agent infrastructure, benchmarking framework, Docker deployment all ready. ~576 tests pass (8 skipped for optional deps).

## Build & Development Commands

```bash
uv sync --extra dev          # Install deps + dev tools
uv run pytest tests/ -v      # Run ~576 tests (8 skipped if optional deps missing)
uv run ruff check src/ tests/ # Lint
uv run jarvis --version      # 1.0.0
uv run jarvis ask "Hello"    # Query via discovered engine (direct mode)
uv run jarvis ask --agent simple "Hello"           # SimpleAgent route
uv run jarvis ask --agent orchestrator "Hello"     # OrchestratorAgent route
uv run jarvis ask --agent orchestrator --tools calculator,think "What is 2+2?"
uv run jarvis ask --router heuristic "Hello"       # Explicit heuristic policy
uv run jarvis ask --no-context "Hello"  # Query without memory context injection
uv run jarvis model list     # List models from running engines
uv run jarvis model info qwen3:8b  # Show model details
uv run jarvis memory index ./docs/   # Index documents into memory
uv run jarvis memory search "topic"  # Search memory for relevant chunks
uv run jarvis memory stats           # Show memory backend statistics
uv run jarvis telemetry stats        # Show aggregated telemetry stats
uv run jarvis telemetry export --format json  # Export records as JSON
uv run jarvis telemetry export --format csv   # Export records as CSV
uv run jarvis telemetry clear --yes  # Delete all telemetry records
uv run jarvis channel list           # List available messaging channels
uv run jarvis channel send slack "Hello"  # Send a message to a channel
uv run jarvis channel status         # Show channel bridge connection status
uv run jarvis bench run              # Run all benchmarks against engine
uv run jarvis bench run -n 20 --json # Run with 20 samples, JSON output
uv run jarvis bench run -b latency -o results.jsonl  # Specific benchmark to file
uv run jarvis serve --port 8000      # OpenAI-compatible API server (requires openjarvis[server])
uv run jarvis --help         # Show all subcommands
uv run jarvis init --force   # Detect hardware, write ~/.openjarvis/config.toml
```

### Python SDK

```python
from openjarvis import Jarvis

j = Jarvis()                          # Uses default config + auto-detected engine
j = Jarvis(model="qwen3:8b")         # Override model
j = Jarvis(engine_key="ollama")       # Override engine

response = j.ask("Hello")            # Returns string
full = j.ask_full("Hello")           # Returns dict with content, usage, model, engine
response = j.ask("Hello", agent="orchestrator", tools=["calculator"])

j.memory.index("./docs/")            # Index documents
results = j.memory.search("topic")   # Search memory
j.memory.stats()                     # Backend stats

j.list_models()                       # Available models
j.list_engines()                      # Registered engines
j.close()                             # Release resources
```

- **Package manager:** `uv` with `hatchling` build backend
- **Config:** `pyproject.toml` with extras for optional backends (e.g., `openjarvis[inference-vllm]`, `openjarvis[memory-colbert]`, `openjarvis[server]`, `openjarvis[openclaw]`)
- **CLI entry point:** `jarvis` (Click-based) — subcommands: `init`, `ask`, `serve`, `model`, `memory`, `telemetry`, `bench`
- **Python:** 3.10+ required
- **Node.js:** 22+ required only for OpenClaw agent

## Architecture

OpenJarvis is a research framework for on-device AI organized around **four core abstractions** plus a cross-cutting learning system, each with a clear ABC interface and a decorator-based registry for runtime discovery.

### Four Core Abstractions

1. **Intelligence** (`src/openjarvis/intelligence/`) — The local LM. Model management and query routing. `ModelRegistry` maps model keys to `ModelSpec`. Heuristic router selects model based on query characteristics.
2. **Engine** (`src/openjarvis/engine/`) — The inference runtime. Backends: vLLM, SGLang, Ollama, llama.cpp, MLX. All implement `InferenceEngine` ABC with `generate()`, `stream()`, `list_models()`, `health()`. Engines extract and pass through `tool_calls` in OpenAI format.
3. **Agentic Logic** (`src/openjarvis/agents/`) — Pluggable logic for handling queries, making tool/API calls, managing memory. `SimpleAgent` (single-turn, no tools), `OrchestratorAgent` (multi-turn tool-calling loop with `ToolExecutor`), `CustomAgent` (template for user-defined agents), `OpenClawAgent` (HTTP/subprocess transport). All implement `BaseAgent` ABC with `run()`. Can be static or learned from traces.
4. **Memory** (`src/openjarvis/memory/`) — Persistent searchable storage. Backends: SQLite/FTS5 (default), FAISS, ColBERTv2, BM25, Hybrid (RRF fusion). All implement `MemoryBackend` ABC with `store()`, `retrieve()`, `delete()`, `clear()`.

### Cross-cutting: Learning & Traces

- **Traces** (`src/openjarvis/traces/`) — Full interaction-level recording. Every agent interaction produces a `Trace` capturing the sequence of `TraceStep`s (route, retrieve, generate, tool_call, respond) with timing, inputs, outputs, and outcomes. `TraceStore` persists to SQLite. `TraceCollector` wraps any `BaseAgent` to record traces automatically. `TraceAnalyzer` provides aggregated stats for the learning system.
- **Learning** (`src/openjarvis/learning/`) — Router policy that determines which model handles a query. `RouterPolicyRegistry` enables pluggable policies. Implementations: `HeuristicRouter` (6 priority rules, registered as "heuristic"), `TraceDrivenPolicy` (learns from trace outcomes, registered as "learned"), `GRPORouterPolicy` (stub for RL training, registered as "grpo"). `HeuristicRewardFunction` scores inference results on latency/cost/efficiency.

### Python SDK (`src/openjarvis/sdk.py`)

- `Jarvis` class: High-level sync API wrapping CLI code paths
- `MemoryHandle`: Lazy memory backend proxy on `j.memory`
- `ask()` / `ask_full()`: Direct engine or agent mode, with router policy selection
- Lazy engine initialization, telemetry recording, resource cleanup via `close()`

### Tool System (`src/openjarvis/tools/`)

- `_stubs.py` — `ToolSpec` dataclass, `BaseTool` ABC (abstract `spec`, `execute()`), `ToolExecutor` (dispatch with event bus integration, JSON argument parsing, latency tracking)
- Built-in tools: `CalculatorTool` (ast-based safe eval), `ThinkTool` (reasoning scratchpad), `RetrievalTool` (memory search), `LLMTool` (sub-model calls), `FileReadTool` (safe file reading with path validation)
- All registered via `@ToolRegistry.register("name")` decorator

### Benchmarking Framework (`src/openjarvis/bench/`)

- `_stubs.py` — `BenchmarkResult` dataclass, `BaseBenchmark` ABC, `BenchmarkSuite` runner
- `latency.py` — `LatencyBenchmark`: measures per-call latency (mean, p50, p95, min, max)
- `throughput.py` — `ThroughputBenchmark`: measures tokens/second throughput
- All registered via `BenchmarkRegistry` with `ensure_registered()` pattern
- CLI: `jarvis bench run` with options for model, engine, samples, benchmark selection, JSON/JSONL output

### OpenClaw Infrastructure (`src/openjarvis/agents/openclaw*.py`)

- `openclaw_protocol.py` — `MessageType` enum, `ProtocolMessage` dataclass, JSON-line `serialize()`/`deserialize()`
- `openclaw_transport.py` — `OpenClawTransport` ABC, `HttpTransport` (HTTP POST to OpenClaw server), `SubprocessTransport` (Node.js stdin/stdout)
- `openclaw.py` — `OpenClawAgent`: transport-based agent with tool-call loop, event bus integration
- `openclaw_plugin.py` — `ProviderPlugin` (wraps engine for OpenClaw), `MemorySearchManager` (wraps memory for OpenClaw)

### API Server (`src/openjarvis/server/`)

- OpenAI-compatible server via `jarvis serve` (FastAPI + uvicorn, optional `[server]` extra)
- `POST /v1/chat/completions` — non-streaming through agent/engine, streaming via SSE
- `GET /v1/models` — list available models
- `GET /health` — health check
- Pydantic request/response models matching OpenAI API format

### Trace System (`src/openjarvis/traces/`)

- `store.py` — `TraceStore` writes complete `Trace` objects (with `TraceStep` lists) to SQLite. Supports filtering by agent, model, outcome, time range. Subscribes to `TRACE_COMPLETE` events on EventBus.
- `collector.py` — `TraceCollector` wraps any `BaseAgent` and records a `Trace` for every `run()`. Subscribes to EventBus events (inference, tool, memory) during agent execution, converting them to `TraceStep` objects. Automatically persists traces and publishes `TRACE_COMPLETE`.
- `analyzer.py` — `TraceAnalyzer` read-only query layer: `summary()`, `per_route_stats()`, `per_tool_stats()`, `traces_for_query_type()`, `export_traces()`. Time-range filtering. Provides inputs for the learning system.
- Dataclasses: `RouteStats`, `ToolStats`, `TraceSummary`

### Telemetry (`src/openjarvis/telemetry/`)

- `store.py` — `TelemetryStore` writes records to SQLite via EventBus subscription (append-only)
- `aggregator.py` — `TelemetryAggregator` read-only query layer: `per_model_stats()`, `per_engine_stats()`, `top_models()`, `summary()`, `export_records()`, `clear()`. Time-range filtering via `since`/`until`.
- `wrapper.py` — `instrumented_generate()` wraps engine calls with timing and telemetry publishing
- Dataclasses: `ModelStats`, `EngineStats`, `AggregatedStats`

### Security (`src/openjarvis/security/`)

- `_stubs.py` — `BaseScanner` ABC (abstract `scan()`, `redact()`)
- `types.py` — `ThreatLevel`, `RedactionMode`, `ScanFinding`, `ScanResult`, `SecurityEvent`, `SecurityEventType`
- `scanner.py` — `SecretScanner` (API keys, tokens, passwords, connection strings, private keys), `PIIScanner` (email, SSN, credit cards, phone, IP)
- `guardrails.py` — `GuardrailsEngine` wraps any `InferenceEngine` with input/output scanning. Modes: WARN (pass-through + event), REDACT (replace sensitive content), BLOCK (raise `SecurityBlockError`). `stream()` does post-hoc scan of accumulated output.
- `file_policy.py` — `is_sensitive_file()` checks filename against `DEFAULT_SENSITIVE_PATTERNS` (`.env`, `*.pem`, `*.key`, `credentials.*`, etc.). `filter_sensitive_paths()` filters path lists.
- `audit.py` — `AuditLogger` persists security events to SQLite for compliance/forensics.

### Channels (`src/openjarvis/channels/`)

- `_stubs.py` — `BaseChannel` ABC (`connect()`, `disconnect()`, `send()`, `status()`, `list_channels()`, `on_message()`), `ChannelMessage` dataclass, `ChannelStatus` enum, `ChannelHandler` type
- `openclaw_bridge.py` — `OpenClawChannelBridge`: WebSocket/HTTP bridge to OpenClaw gateway. Background listener thread, reconnect logic, handler registration, event bus integration. Registered as `"openclaw"` in `ChannelRegistry`.

### Core Module (`src/openjarvis/core/`)

- `registry.py` — `RegistryBase[T]` generic base class adapted from IPW. Typed subclasses: `ModelRegistry`, `EngineRegistry`, `MemoryRegistry`, `AgentRegistry`, `ToolRegistry`, `RouterPolicyRegistry`, `BenchmarkRegistry`, `ChannelRegistry`.
- `types.py` — `Message`, `Conversation`, `ModelSpec`, `ToolResult`, `TelemetryRecord`, `StepType`, `TraceStep`, `Trace`.
- `config.py` — `JarvisConfig` dataclass hierarchy with TOML loader. Includes `LearningConfig` (default_policy, reward_weights), `ChannelConfig` (enabled, gateway_url, default_agent, reconnect_interval), `SecurityConfig` (enabled, scan_input, scan_output, mode, secret_scanner, pii_scanner, audit_log_path, enforce_tool_confirmation). User config lives at `~/.openjarvis/config.toml`. Hardware auto-detection populates defaults. TOML sections: `[engine]`, `[intelligence]`, `[learning]`, `[memory]`, `[agent]`, `[server]`, `[telemetry]`, `[channel]`, `[security]`.
- `events.py` — Pub/sub event bus for inter-pillar telemetry (synchronous dispatch). EventType values: INFERENCE_START/END, TOOL_CALL_START/END, MEMORY_STORE/RETRIEVE, AGENT_TURN_START/END, TELEMETRY_RECORD, TRACE_STEP/COMPLETE, CHANNEL_MESSAGE_RECEIVED/SENT, SECURITY_SCAN/ALERT/BLOCK.

### Docker & Deployment

- `Dockerfile` — Multi-stage build: Python 3.12-slim, installs `.[server]`, entrypoint `jarvis serve`
- `Dockerfile.gpu` — NVIDIA CUDA 12.4 runtime variant
- `docker-compose.yml` — Services: `jarvis` (port 8000) + `ollama` (port 11434)
- `deploy/systemd/openjarvis.service` — systemd unit file
- `deploy/launchd/com.openjarvis.plist` — macOS launchd plist

### Query Flow

User query &rarr; Security scanning (input) &rarr; Agentic Logic (determine tools/memory needs) &rarr; Memory retrieval &rarr; Context injection with source attribution &rarr; Learning/Router selects model (via RouterPolicyRegistry, heuristic or trace-driven) &rarr; Inference Engine generates response &rarr; Security scanning (output) &rarr; Trace recorded to SQLite (full interaction sequence) &rarr; Telemetry recorded &rarr; Learning policies update from accumulated traces.

### API Surface

OpenAI-compatible server via `jarvis serve`: `POST /v1/chat/completions`, `GET /v1/models`, `GET /v1/channels`, `POST /v1/channels/send`, `GET /v1/channels/status` with SSE streaming.

## Key Design Patterns

- **Registry pattern:** All extensible components use `@XRegistry.register("name")` decorator for registration and runtime discovery. New implementations are added by decorating a class — no factory modifications needed.
- **ABC interfaces:** Each pillar defines an ABC. Implement the ABC + register via decorator to add a new backend.
- **Offline-first:** Cloud APIs are optional. All core functionality works without network.
- **Hardware-aware:** Auto-detect GPU vendor/model/VRAM via `nvidia-smi`, `rocm-smi`, `system_profiler`, `/proc/cpuinfo`. Recommend engine accordingly.
- **Telemetry-native:** Every inference call records timing, tokens, energy, cost to SQLite via event bus. `TelemetryAggregator` provides read-only query/aggregation over stored records.
- **`ensure_registered()` pattern:** Benchmark and learning modules use lazy registration via `ensure_registered()` to survive registry clearing in tests.

## Development Phases

| Version | Phase | Delivers |
|---------|-------|----------|
| v0.1 | Phase 0 | Scaffolding, registries, core types, config, CLI skeleton |
| v0.2 | Phase 1 | Intelligence + Inference — `jarvis ask` works end-to-end |
| v0.3 | Phase 2 | Memory backends, document indexing, context injection |
| v0.4 | Phase 3 | Agents, tool system, OpenAI-compatible API server |
| v0.5 | Phase 4 | Learning implementations, telemetry aggregation, `--router` CLI, `jarvis telemetry` |
| v1.0 | Phase 5 | SDK, OpenClaw infrastructure, benchmarks, Docker, documentation |
| v1.1 | Phase 6 | Trace system, trace-driven learning, pluggable agent architectures |
