import unittest

from app.models.domain import KCState, UserState
from app.services.knowledge_state import (
    KnowledgeState,
    confidence_from_variance,
    dag_reverse_propagate,
    mastery_expectation,
    mastery_variance,
    seed_alpha_beta,
    time_decay_gamma,
    update_kc_with_bkt,
)


class TestKnowledgeStateMath(unittest.TestCase):
    def test_mastery_expectation_and_variance(self):
        alpha = 3.0
        beta = 1.0
        mean = mastery_expectation(alpha, beta)
        var = mastery_variance(alpha, beta)

        self.assertAlmostEqual(mean, 0.75, places=6)
        # 3*1 / ((4^2) * 5) = 3/80 = 0.0375
        self.assertAlmostEqual(var, 0.0375, places=6)

    def test_confidence_from_variance(self):
        self.assertAlmostEqual(confidence_from_variance(0.0), 1.0, places=6)
        self.assertAlmostEqual(confidence_from_variance(0.25), 0.0, places=6)

    def test_seed_alpha_beta(self):
        alpha, beta = seed_alpha_beta(0.6, 0.5)
        self.assertGreater(alpha, 0.0)
        self.assertGreater(beta, 0.0)
        self.assertGreater(alpha, beta)


class TestKnowledgeStateUpdate(unittest.TestCase):
    def test_time_decay_gamma(self):
        self.assertAlmostEqual(time_decay_gamma(5.0, 10.0), 1.0, places=6)

        slow_gamma = time_decay_gamma(20.0, 10.0)
        self.assertGreaterEqual(slow_gamma, 0.2)
        self.assertLess(slow_gamma, 1.0)

    def test_update_with_time_penalty(self):
        kc = KCState(kc_id="kc_1", alpha=2.0, beta=2.0, mastery=0.5, confidence=0.2)

        fast = update_kc_with_bkt(kc=kc, correctness=1.0, gamma=1.0)
        fast_delta = fast["alpha_after"] - fast["alpha_before"]

        slow = update_kc_with_bkt(kc=kc, correctness=1.0, gamma=0.3)
        slow_delta = slow["alpha_after"] - slow["alpha_before"]

        self.assertAlmostEqual(fast_delta, 1.0, places=3)
        self.assertAlmostEqual(slow_delta, 0.3, places=3)

    def test_dag_reverse_propagate(self):
        user_state = UserState(
            session_id="s1",
            user_id="u1",
            kcs={
                "pre": KCState(kc_id="pre", alpha=3.0, beta=2.0, mastery=0.6, confidence=0.4),
                "adv": KCState(kc_id="adv", alpha=9.0, beta=1.0, mastery=0.9, confidence=0.9),
            },
            vocab_bucket=set(),
            dag_state={
                "nodes": {"pre": {}, "adv": {}},
                "edges": [{"from": "pre", "to": "adv", "weight": 0.5}],
                "target_tier": 2,
            },
            global_level="INTERMEDIATE",
        )

        before_alpha = user_state.kcs["pre"].alpha
        records = dag_reverse_propagate(user_state=user_state, source_kc_ids=["adv"])
        after_alpha = user_state.kcs["pre"].alpha

        self.assertTrue(records)
        self.assertGreater(after_alpha, before_alpha)


class TestKnowledgeStateClass(unittest.TestCase):
    def test_knowledge_state_properties(self):
        state = KnowledgeState(alpha=4.0, beta=2.0)
        self.assertAlmostEqual(state.mastery, 4.0 / 6.0, places=6)
        self.assertGreaterEqual(state.confidence, 0.0)
        self.assertLessEqual(state.confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
