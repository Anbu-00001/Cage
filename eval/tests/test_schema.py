"""Unit tests for `eval.schema`: the canonical episode record round-trips
through JSON and matches its own declared JSON Schema's required fields
(docs/EVALUATION.md Part 6/7)."""

from __future__ import annotations

import unittest

from eval.schema import (
    EPISODE_JSON_SCHEMA,
    Condition,
    EpisodeRecord,
    InferenceBackendConfig,
    MemoryTelemetry,
    ProbeVariant,
    ThermalTelemetry,
)
from eval.taxonomy import FailureCode


def _sample_episode() -> EpisodeRecord:
    return EpisodeRecord(
        episode_id="ep-0001",
        timestamp_utc="2026-09-24T00:00:00Z",
        seed=7,
        boundary_class="L6",
        boundary_instance_id="abc123",
        probe_variant=ProbeVariant.HELD_OUT,
        condition=Condition.TREATMENT_FULL,
        backend=InferenceBackendConfig(
            engine="llama.cpp",
            engine_commit="deadbeef",
            model_id="qwen2.5-3b-instruct",
            quantization="Q4_K_M",
            ctx_length=4096,
            n_threads=4,
            pinned_cores=(0, 1),
            temperature=0.0,
            top_p=1.0,
            top_k=1,
            repeat_penalty=1.1,
            sampling_seed=42,
        ),
        outcome=FailureCode.EXPLOITED_INTENDED,
        solved=True,
        gave_up=False,
        steps_taken=6,
        optimal_steps=4,
        tokens_prompt=1200,
        tokens_completion=340,
        wall_clock_seconds=48.5,
        tok_per_sec_decode=14.2,
        ttft_seconds=0.9,
        energy_joules=610.0,
        thermal=ThermalTelemetry(
            pkg_temp_c_max=78.0, pkg_watt_avg=13.5, sustained_p_core_mhz_avg=3100.0,
            throttle_events=0, equilibrated_before_trial=True,
        ),
        memory=MemoryTelemetry(
            peak_rss_mb=3120.0, swap_used_mb=0.0, psi_some_avg10=1.2,
            psi_full_avg10=0.0, caches_dropped_before_trial=True,
        ),
        vm_snapshot_checksum_pre="sha256:golden",
        vm_snapshot_checksum_post_revert="sha256:golden",
        trace_ref="traces/ep-0001.jsonl",
    )


class EpisodeRecordJsonRoundTripTests(unittest.TestCase):
    def test_round_trip_preserves_all_fields(self) -> None:
        original = _sample_episode()
        restored = EpisodeRecord.from_json(original.to_json())
        self.assertEqual(original, restored)

    def test_json_uses_plain_string_enum_values(self) -> None:
        import json

        raw = json.loads(_sample_episode().to_json())
        self.assertEqual(raw["condition"], "treatment_full")
        self.assertEqual(raw["probe_variant"], "held_out")
        self.assertEqual(raw["outcome"], "exploited_intended")

    def test_pinned_cores_round_trips_as_tuple(self) -> None:
        restored = EpisodeRecord.from_json(_sample_episode().to_json())
        self.assertIsInstance(restored.backend.pinned_cores, tuple)
        self.assertEqual(restored.backend.pinned_cores, (0, 1))


class EpisodeJsonSchemaTests(unittest.TestCase):
    def test_required_fields_are_all_present_on_a_real_record(self) -> None:
        import json

        raw = json.loads(_sample_episode().to_json())
        for field_name in EPISODE_JSON_SCHEMA["required"]:
            self.assertIn(field_name, raw)

    def test_enum_declared_values_match_the_live_enums(self) -> None:
        self.assertEqual(set(EPISODE_JSON_SCHEMA["properties"]["condition"]["enum"]), {c.value for c in Condition})
        self.assertEqual(
            set(EPISODE_JSON_SCHEMA["properties"]["outcome"]["enum"]), {c.value for c in FailureCode}
        )


if __name__ == "__main__":
    unittest.main()
