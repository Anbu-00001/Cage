"""Unit tests for eval.live_cage -- the deterministic parts (fixture instance
derivation, env-controller provisioning contract) exercised against a fake
channel, with NO llama-server and NO guest. The live path itself (real vsock +
llama-server) is validated by the pilot sweep, not here."""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from eval.live_cage import LiveCageEnvController, make_fixture_instance


@dataclass
class _FakeResult:
    ok: bool = True
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


class _FakeChannel:
    """Records every command it is asked to execute; always succeeds."""

    def __init__(self) -> None:
        self.commands: list[str] = []

    def execute(self, command: str, timeout_s: float = 10.0) -> _FakeResult:
        self.commands.append(command)
        return _FakeResult(ok=True)


class TestFixtureInstance(unittest.TestCase):
    def test_deterministic_same_seed(self) -> None:
        self.assertEqual(make_fixture_instance(7), make_fixture_instance(7))

    def test_distinct_across_seeds(self) -> None:
        a, b = make_fixture_instance(1), make_fixture_instance(2)
        self.assertNotEqual(a.token, b.token)
        # different instances must not collide on checksum
        self.assertNotEqual(a.prov_checksum(), b.prov_checksum())

    def test_token_is_flag_shaped_and_planted(self) -> None:
        inst = make_fixture_instance(42)
        self.assertTrue(inst.token.startswith("FLAG{") and inst.token.endswith("}"))
        # the token appears exactly once in the provisioning (in the real file),
        # never in a decoy line
        planted = [c for c in inst.provisioning if inst.token in c]
        self.assertEqual(len(planted), 1)
        self.assertIn(inst.flag_path, planted[0])

    def test_decoys_are_not_flag_shaped(self) -> None:
        inst = make_fixture_instance(3)
        decoy_lines = [c for c in inst.provisioning if "not-a-real-token" in c]
        self.assertTrue(decoy_lines)
        for line in decoy_lines:
            self.assertNotIn("FLAG{", line)


class TestLiveCageEnvController(unittest.TestCase):
    def test_instantiate_runs_provisioning_and_sets_current(self) -> None:
        ch = _FakeChannel()
        env = LiveCageEnvController(channel=ch)
        inst_id = env.instantiate_boundary("L0", 5)

        self.assertEqual(inst_id, make_fixture_instance(5).instance_id())
        self.assertIsNotNone(env.current)
        # provisioning went out as a single combined command containing the token
        self.assertEqual(len(ch.commands), 1)
        self.assertIn(env.current.token, ch.commands[0])
        self.assertIn("mkdir -p", ch.commands[0])

    def test_revert_cleans_and_clears_current(self) -> None:
        ch = _FakeChannel()
        env = LiveCageEnvController(channel=ch)
        env.instantiate_boundary("L0", 5)
        golden = env.revert_to_golden()

        self.assertIsNone(env.current)
        self.assertTrue(golden.startswith("golden:"))
        self.assertIn("rm -rf", ch.commands[-1])

    def test_checksum_reflects_planted_instance(self) -> None:
        ch = _FakeChannel()
        env = LiveCageEnvController(channel=ch)
        env.instantiate_boundary("L0", 9)
        self.assertEqual(env.checksum(), make_fixture_instance(9).prov_checksum())

    def test_provisioning_failure_raises(self) -> None:
        class _FailCh(_FakeChannel):
            def execute(self, command: str, timeout_s: float = 10.0) -> _FakeResult:
                self.commands.append(command)
                return _FakeResult(ok=False, error="mkdir: permission denied")

        env = LiveCageEnvController(channel=_FailCh())
        with self.assertRaises(RuntimeError):
            env.instantiate_boundary("L0", 1)


if __name__ == "__main__":
    unittest.main()
