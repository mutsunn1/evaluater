from __future__ import annotations

import math
from typing import Dict, List, Tuple

from app.models.domain import KCState, UserState


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def mastery_expectation(alpha: float, beta: float) -> float:
    """Beta posterior mean: E[X] = alpha / (alpha + beta)."""
    denom = max(alpha + beta, 1e-8)
    return alpha / denom


def mastery_variance(alpha: float, beta: float) -> float:
    """Beta posterior variance: Var[X] = ab / ((a+b)^2 * (a+b+1))."""
    s = max(alpha + beta, 1e-8)
    return (alpha * beta) / (s * s * (s + 1.0))


def confidence_from_variance(variance: float) -> float:
    """Map uncertainty to confidence in [0,1].

    Bernoulli maximum variance is 0.25. We normalize and invert:
    confidence = 1 - min(Var / 0.25, 1).
    """
    max_var = 0.25
    normalized = _clamp(variance / max_var, 0.0, 1.0)
    return 1.0 - normalized


def seed_alpha_beta(initial_mastery: float, initial_confidence: float) -> Tuple[float, float]:
    """Convert heuristic initial mastery/confidence into Beta prior.

    We approximate effective sample size with confidence and clamp to keep
    priors weak enough for online adaptation but stable enough for noise.
    """
    p = _clamp(initial_mastery, 0.01, 0.99)
    prior_strength = 2.0 + 10.0 * _clamp(initial_confidence, 0.0, 1.0)
    alpha = max(0.1, p * prior_strength)
    beta = max(0.1, (1.0 - p) * prior_strength)
    return alpha, beta


def ensure_kc_prior(kc: KCState) -> None:
    """Backfill alpha/beta for legacy sessions that do not carry priors."""
    if kc.alpha > 0 and kc.beta > 0:
        return
    alpha, beta = seed_alpha_beta(kc.mastery, kc.confidence)
    kc.alpha = alpha
    kc.beta = beta


class KnowledgeState:
    """Bayesian KT state wrapper for a single KC.

    Update rule uses fractional evidence with time penalty gamma in [0,1].
    For a correct and slow answer, alpha increment is gamma (< 1), which
    prevents over-estimating mastery from delayed recalls.
    """

    def __init__(self, alpha: float, beta: float) -> None:
        self.alpha = max(1e-6, float(alpha))
        self.beta = max(1e-6, float(beta))

    @property
    def mastery(self) -> float:
        return mastery_expectation(self.alpha, self.beta)

    @property
    def confidence(self) -> float:
        return confidence_from_variance(mastery_variance(self.alpha, self.beta))

    def update(self, correctness: float, gamma: float) -> None:
        """Bayesian evidence update with latency-aware weighting.

        correctness: soft correctness in [0,1].
        gamma: time decay factor in [0,1], where 1 means no penalty.

        Evidence increments:
        - alpha += gamma * correctness
        - beta  += (1 - correctness) * (1 + 0.5 * (1 - gamma))

        Interpretation:
        - Correct but slow (gamma << 1) contributes less positive evidence.
        - Wrong answers increase beta, and slow wrong answers are slightly
          amplified to reflect retrieval instability.
        """
        c = _clamp(correctness, 0.0, 1.0)
        g = _clamp(gamma, 0.0, 1.0)

        self.alpha += g * c
        self.beta += (1.0 - c) * (1.0 + 0.5 * (1.0 - g))


def time_decay_gamma(actual_time_sec: float, expected_time_sec: float) -> float:
    """Compute latency penalty gamma.

    Let r = T_actual / T_expected. For r <= 1, gamma = 1.
    For r > 1, gamma = exp(-k * (r - 1)), then clipped by floor.
    """
    ratio = max(0.0, actual_time_sec) / max(0.1, expected_time_sec)
    if ratio <= 1.0:
        return 1.0
    gamma = math.exp(-1.6 * (ratio - 1.0))
    return _clamp(gamma, 0.2, 1.0)


def update_kc_with_bkt(kc: KCState, correctness: float, gamma: float) -> Dict[str, float]:
    ensure_kc_prior(kc)
    state = KnowledgeState(alpha=kc.alpha, beta=kc.beta)

    before_alpha = state.alpha
    before_beta = state.beta
    before_mastery = state.mastery
    before_confidence = state.confidence

    state.update(correctness=correctness, gamma=gamma)

    kc.alpha = state.alpha
    kc.beta = state.beta
    kc.mastery = state.mastery
    kc.confidence = state.confidence

    return {
        "alpha_before": round(before_alpha, 4),
        "alpha_after": round(kc.alpha, 4),
        "beta_before": round(before_beta, 4),
        "beta_after": round(kc.beta, 4),
        "mastery_before": round(before_mastery, 4),
        "mastery_after": round(kc.mastery, 4),
        "confidence_before": round(before_confidence, 4),
        "confidence_after": round(kc.confidence, 4),
    }


def dag_reverse_propagate(
    user_state: UserState,
    source_kc_ids: List[str],
    mastery_threshold: float = 0.78,
    confidence_threshold: float = 0.68,
    base_boost: float = 0.35,
) -> List[Dict[str, float]]:
    """Reverse propagate confidence from advanced KC to prerequisites.

    If a target KC has high posterior mastery/confidence, distribute a small
    alpha boost to incoming prerequisite nodes using edge weight.
    """
    edges = user_state.dag_state.get("edges", [])
    records: List[Dict[str, float]] = []
    if not isinstance(edges, list):
        return records

    for source_kc_id in source_kc_ids:
        source = user_state.kcs.get(source_kc_id)
        if source is None:
            continue
        ensure_kc_prior(source)
        if source.mastery < mastery_threshold or source.confidence < confidence_threshold:
            continue

        for edge in edges:
            if not isinstance(edge, dict) or edge.get("to") != source_kc_id:
                continue
            prereq_id = edge.get("from")
            if not isinstance(prereq_id, str) or prereq_id not in user_state.kcs:
                continue

            prereq = user_state.kcs[prereq_id]
            ensure_kc_prior(prereq)

            weight = float(edge.get("weight", 0.25))
            delta_alpha = _clamp(base_boost * weight * source.mastery * source.confidence, 0.0, 0.6)
            if delta_alpha <= 0:
                continue

            before_alpha = prereq.alpha
            prereq.alpha += delta_alpha
            prereq.mastery = mastery_expectation(prereq.alpha, prereq.beta)
            prereq.confidence = confidence_from_variance(mastery_variance(prereq.alpha, prereq.beta))

            records.append(
                {
                    "from_kc": source_kc_id,
                    "to_prereq_kc": prereq_id,
                    "weight": round(weight, 4),
                    "alpha_before": round(before_alpha, 4),
                    "alpha_after": round(prereq.alpha, 4),
                    "delta_alpha": round(delta_alpha, 4),
                }
            )

    return records
