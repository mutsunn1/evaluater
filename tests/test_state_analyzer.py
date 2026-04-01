import unittest

from app.agents import oxygent_workflows as workflows
from app.models.domain import KCState, UserState


class TestStateAnalyzerIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_state_analyzer_updates_bkt_and_dag(self):
        async def fake_call_agent(callee: str, query: str):
            self.assertEqual(callee, "state_analyzer")
            return {"correctness": 0.9, "bucket": "correct_slow", "reason": "ok"}

        original = workflows._call_agent
        workflows._call_agent = fake_call_agent
        try:
            user_state = UserState(
                session_id="s2",
                user_id="u2",
                kcs={
                    "G_Adjective_Predicate": KCState(
                        kc_id="G_Adjective_Predicate",
                        alpha=2.0,
                        beta=2.0,
                        mastery=0.5,
                        confidence=0.4,
                    ),
                    "G_Comparison_Bi": KCState(
                        kc_id="G_Comparison_Bi",
                        alpha=20.0,
                        beta=2.0,
                        mastery=20.0 / 22.0,
                        confidence=0.85,
                    ),
                },
                vocab_bucket=set(),
                dag_state={
                    "nodes": {"G_Adjective_Predicate": {}, "G_Comparison_Bi": {}},
                    "edges": [
                        {
                            "from": "G_Adjective_Predicate",
                            "to": "G_Comparison_Bi",
                            "weight": 0.6,
                        }
                    ],
                    "target_tier": 2,
                },
                global_level="INTERMEDIATE",
                last_question="请比较线上学习和线下学习",
                last_expected_time_sec=8.0,
                last_target_kcs=["G_Comparison_Bi"],
            )

            before_prereq_alpha = user_state.kcs["G_Adjective_Predicate"].alpha
            result = await workflows.state_analyzer_agent(
                user_state=user_state,
                user_response_text="我觉得线上学习比线下学习更方便。",
                actual_time_sec=12.0,
                expected_time_sec=8.0,
                target_kcs=["G_Comparison_Bi"],
            )

            self.assertIn("gamma", result)
            self.assertIn("updates", result)
            self.assertIn("dag_backprop", result)

            target_update = result["updates"]["G_Comparison_Bi"]
            self.assertIn("alpha_after", target_update)
            self.assertIn("beta_after", target_update)

            after_prereq_alpha = user_state.kcs["G_Adjective_Predicate"].alpha
            self.assertGreater(after_prereq_alpha, before_prereq_alpha)
            self.assertGreaterEqual(result["gamma"], 0.2)
            self.assertLessEqual(result["gamma"], 1.0)
        finally:
            workflows._call_agent = original


if __name__ == "__main__":
    unittest.main()
