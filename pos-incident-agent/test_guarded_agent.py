"""Small regression checks for safety decisions and what the UI reveals."""

import unittest
from unittest.mock import patch

import pos_incident_agent as agent
from web_app import SessionStore, load_samples, page


def check(stage, blocked=False):
    return {
        "stage": stage, "blocked": blocked, "moderation": int(blocked),
        "injection": 0 if stage == "input" else None, "pii": [],
        "version": "1.1.0", "action": "保留" if blocked else "通過",
    }


class GuardedAgentTests(unittest.TestCase):
    def test_missing_system_does_not_reuse_another_record(self):
        alerts, systems = agent.load_data(agent.HERE)
        result = agent.execute_call("lookup_system", '{"system_id":"STORE-099-POS"}', alerts, systems)
        self.assertFalse(result["found"])
        self.assertIsNone(result["record"])

    def test_input_check_error_never_runs_agent(self):
        with patch.object(agent, "evaluate", side_effect=RuntimeError("service unavailable")), patch.object(agent, "run_agent") as run:
            with self.assertRaises(RuntimeError):
                agent.run_guarded_agent("question", {}, agent.HERE)
        run.assert_not_called()

    def test_blocked_input_never_runs_agent(self):
        with patch.object(agent, "evaluate", return_value=check("input", True)), patch.object(agent, "run_agent") as run:
            result = agent.run_guarded_agent("attack", {}, agent.HERE)
        run.assert_not_called()
        self.assertEqual(result["answer"], "")
        self.assertEqual(len(result["checks"]), 1)

    def test_blocked_output_is_withheld(self):
        with patch.object(agent, "evaluate", side_effect=[check("input"), check("output", True)]), patch.object(
            agent, "run_agent", return_value=("SECRET_ANSWER", [])
        ):
            result = agent.run_guarded_agent("question", {}, agent.HERE)
        self.assertEqual(result["answer"], "")
        self.assertEqual(result["checks"][-1]["stage"], "output")

    def test_normal_answer_displays_both_checks(self):
        with patch.object(agent, "evaluate", side_effect=[check("input"), check("output")]), patch.object(
            agent, "run_agent", return_value=("初動対応票", [])
        ):
            result = agent.run_guarded_agent("question", {}, agent.HERE)
        self.assertEqual(result["answer"], "初動対応票")
        self.assertEqual(len(result["checks"]), 2)

    def test_samples_and_session_history(self):
        samples = load_samples(agent.HERE / "demo_questions.md")
        self.assertEqual(len(samples), 7)
        self.assertIn("ALT-20261008-001", samples[0]["question"])
        rendered = page(samples).decode()
        self.assertIn("コンテンツモデレーション", rendered)
        self.assertIn("プロンプトインジェクション", rendered)
        store = SessionStore()
        store.add_turn("session-a", "最初の質問", "最初の回答")
        self.assertEqual(store.history("session-a"), [
            {"role": "user", "content": "最初の質問"},
            {"role": "assistant", "content": "最初の回答"},
        ])
        self.assertEqual(store.history("session-b"), [])


if __name__ == "__main__":
    unittest.main()
