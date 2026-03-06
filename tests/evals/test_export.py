"""Tests for eval export utilities."""

from __future__ import annotations

import json

from openjarvis.evals.core.export import (
    export_artifacts_manifest,
    export_jsonl,
    export_summary_json,
)
from openjarvis.evals.core.trace import QueryTrace, TurnTrace


def _make_traces(n=3):
    traces = []
    for i in range(n):
        traces.append(QueryTrace(
            query_id=f"q{i:04d}",
            workload_type="test",
            query_text=f"Question {i}",
            response_text=f"Answer {i}",
            turns=[
                TurnTrace(
                    turn_index=0,
                    input_tokens=100 + i * 10,
                    output_tokens=50 + i * 5,
                    wall_clock_s=1.0 + i * 0.5,
                    gpu_energy_joules=5.0 + i,
                    cost_usd=0.01,
                ),
            ],
            total_wall_clock_s=1.0 + i * 0.5,
            completed=True,
            is_resolved=i % 2 == 0,
        ))
    return traces


class TestExportJsonl:
    def test_basic_export(self, tmp_path):
        traces = _make_traces()
        path = tmp_path / "traces.jsonl"
        result = export_jsonl(traces, path)
        assert result == path
        assert path.exists()

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 3
        for line in lines:
            d = json.loads(line)
            assert "query_id" in d
            assert "turns" in d

    def test_empty_traces(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        export_jsonl([], path)
        assert path.read_text() == ""

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "a" / "b" / "c" / "traces.jsonl"
        export_jsonl(_make_traces(1), path)
        assert path.exists()


class TestExportSummaryJson:
    def test_basic_summary(self, tmp_path):
        traces = _make_traces()
        path = tmp_path / "summary.json"
        result = export_summary_json(traces, {"model": "test"}, path)
        assert result == path
        assert path.exists()

        summary = json.loads(path.read_text())
        assert summary["totals"]["queries"] == 3
        assert summary["totals"]["completed"] == 3
        assert summary["totals"]["resolved"] == 2
        assert summary["totals"]["input_tokens"] > 0
        assert summary["totals"]["output_tokens"] > 0
        assert summary["config"]["model"] == "test"
        assert "statistics" in summary

    def test_statistics_keys(self, tmp_path):
        traces = _make_traces()
        path = tmp_path / "summary.json"
        export_summary_json(traces, {}, path)
        summary = json.loads(path.read_text())
        stats = summary["statistics"]
        expected_stat_keys = {
            "wall_clock_s", "gpu_energy_joules", "cpu_energy_joules",
            "gpu_power_watts", "cpu_power_watts",
            "input_tokens", "output_tokens", "total_tokens",
            "throughput_tokens_per_sec", "energy_per_token_joules",
            "cost_usd", "turns", "tool_calls",
        }
        assert set(stats.keys()) == expected_stat_keys

    def test_agg_stats_fields(self, tmp_path):
        traces = _make_traces()
        path = tmp_path / "summary.json"
        export_summary_json(traces, {}, path)
        summary = json.loads(path.read_text())
        wc_stats = summary["statistics"]["wall_clock_s"]
        assert "avg" in wc_stats
        assert "median" in wc_stats
        assert "min" in wc_stats
        assert "max" in wc_stats
        assert "std" in wc_stats

    def test_empty_traces(self, tmp_path):
        path = tmp_path / "summary.json"
        export_summary_json([], {}, path)
        summary = json.loads(path.read_text())
        assert summary["totals"]["queries"] == 0


class TestExportArtifactsManifest:
    def test_no_artifacts_dir(self, tmp_path):
        result = export_artifacts_manifest(tmp_path)
        assert result is None

    def test_with_artifacts(self, tmp_path):
        art_dir = tmp_path / "artifacts"
        q_dir = art_dir / "q0001_test"
        q_dir.mkdir(parents=True)
        (q_dir / "response.txt").write_text("hello")
        (q_dir / "metadata.json").write_text("{}")

        result = export_artifacts_manifest(tmp_path)
        assert result is not None
        assert result.exists()

        manifest = json.loads(result.read_text())
        assert len(manifest) == 1
        assert manifest[0]["query_dir"] == "q0001_test"
        assert len(manifest[0]["files"]) == 2
