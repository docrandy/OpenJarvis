"""Tests for configuration, hardware detection, and engine recommendation."""

from __future__ import annotations

from pathlib import Path

from openjarvis.core.config import (
    ChannelConfig,
    EngineConfig,
    GpuInfo,
    HardwareInfo,
    JarvisConfig,
    SecurityConfig,
    generate_default_toml,
    load_config,
    recommend_engine,
)


class TestDefaults:
    def test_jarvis_config_defaults(self) -> None:
        cfg = JarvisConfig()
        assert cfg.engine.default == "ollama"
        assert cfg.memory.default_backend == "sqlite"
        assert cfg.telemetry.enabled is True

    def test_engine_config_defaults(self) -> None:
        ec = EngineConfig()
        assert ec.ollama_host == "http://localhost:11434"
        assert ec.vllm_host == "http://localhost:8000"


class TestRecommendEngine:
    def test_no_gpu(self) -> None:
        hw = HardwareInfo(platform="linux")
        assert recommend_engine(hw) == "llamacpp"

    def test_apple_silicon(self) -> None:
        hw = HardwareInfo(
            platform="darwin",
            gpu=GpuInfo(vendor="apple", name="Apple M2 Max"),
        )
        assert recommend_engine(hw) == "ollama"

    def test_nvidia_datacenter(self) -> None:
        hw = HardwareInfo(
            platform="linux",
            gpu=GpuInfo(vendor="nvidia", name="NVIDIA A100-SXM4-80GB", vram_gb=80),
        )
        assert recommend_engine(hw) == "vllm"

    def test_nvidia_consumer(self) -> None:
        hw = HardwareInfo(
            platform="linux",
            gpu=GpuInfo(vendor="nvidia", name="NVIDIA GeForce RTX 4090", vram_gb=24),
        )
        assert recommend_engine(hw) == "ollama"

    def test_amd(self) -> None:
        hw = HardwareInfo(
            platform="linux",
            gpu=GpuInfo(vendor="amd", name="Radeon RX 7900 XTX"),
        )
        assert recommend_engine(hw) == "vllm"


class TestTomlLoading:
    def test_load_missing_file_uses_defaults(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "nonexistent.toml")
        assert isinstance(cfg, JarvisConfig)
        # engine default is derived from detected hardware — just ensure it's a string
        assert isinstance(cfg.engine.default, str)

    def test_load_overrides(self, tmp_path: Path) -> None:
        toml_file = tmp_path / "config.toml"
        toml_file.write_text(
            '[engine]\ndefault = "vllm"\n\n[memory]\ndefault_backend = "faiss"\n'
        )
        cfg = load_config(toml_file)
        assert cfg.engine.default == "vllm"
        assert cfg.memory.default_backend == "faiss"


class TestGenerateToml:
    def test_contains_engine_section(self) -> None:
        hw = HardwareInfo(
            platform="linux",
            cpu_brand="Intel Xeon",
            cpu_count=16,
            ram_gb=64.0,
            gpu=GpuInfo(vendor="nvidia", name="NVIDIA H100", vram_gb=80),
        )
        toml = generate_default_toml(hw)
        assert "[engine]" in toml
        assert 'default = "vllm"' in toml
        assert "H100" in toml


class TestSecurityConfig:
    def test_security_config_defaults(self) -> None:
        sc = SecurityConfig()
        assert sc.enabled is True
        assert sc.scan_input is True
        assert sc.scan_output is True
        assert sc.mode == "warn"
        assert sc.secret_scanner is True
        assert sc.pii_scanner is True
        assert sc.enforce_tool_confirmation is True

    def test_security_config_on_jarvis_config(self) -> None:
        cfg = JarvisConfig()
        assert isinstance(cfg.security, SecurityConfig)

    def test_security_config_loads_from_toml(self, tmp_path: Path) -> None:
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('[security]\nmode = "block"\nscan_input = false\n')
        cfg = load_config(toml_file)
        assert cfg.security.mode == "block"
        assert cfg.security.scan_input is False

    def test_security_config_in_default_toml(self) -> None:
        output = generate_default_toml(HardwareInfo())
        assert "[security]" in output


class TestChannelConfig:
    def test_channel_config_defaults(self) -> None:
        cc = ChannelConfig()
        assert cc.enabled is False
        assert cc.gateway_url == "ws://127.0.0.1:18789/ws"
        assert cc.default_agent == "simple"
        assert cc.reconnect_interval == 5.0

    def test_channel_config_on_jarvis_config(self) -> None:
        cfg = JarvisConfig()
        assert isinstance(cfg.channel, ChannelConfig)

    def test_channel_config_loads_from_toml(self, tmp_path: Path) -> None:
        toml_file = tmp_path / "config.toml"
        toml_file.write_text(
            '[channel]\nenabled = true\ngateway_url = "ws://custom:9999/ws"\n'
        )
        cfg = load_config(toml_file)
        assert cfg.channel.enabled is True
        assert cfg.channel.gateway_url == "ws://custom:9999/ws"

    def test_channel_config_in_default_toml(self) -> None:
        output = generate_default_toml(HardwareInfo())
        assert "[channel]" in output
