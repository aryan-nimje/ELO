"""Multi-participant Elo calculation.

Each participant is compared pairwise against every other participant.
  expected_i = sum over j != i of 1 / (1 + 10 ** ((R_j - R_i) / scale))
  actual_i   = sum over j != i of (1 if i ranked above j, 0.5 if tied, 0 otherwise)
  delta_i    = K * (actual_i - expected_i) / (N - 1)

Dividing by (N - 1) keeps the change in the range [-K, +K] regardless of
how many people took part.
"""

from dataclasses import dataclass


@dataclass
class Player:
    user_id: str
    rating: float
    contests_played: int
    score: float
    penalty: float


@dataclass
class Result:
    user_id: str
    rank: int
    old_rating: int
    new_rating: int
    delta: int
    expected_rank: float
    k_factor_used: float


def k_for(contests_played: int) -> float:
    """Newcomers move faster so they reach their true level quickly."""
    if contests_played < 5:
        return 40.0
    if contests_played < 15:
        return 32.0
    return 24.0


def expected_score(rating_a: float, rating_b: float, scale: float = 400.0) -> float:
    """Probability-like expected result of A against B."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / scale))


def compute_ranks(players: list[Player]) -> dict[str, int]:
    """Higher score is better; lower penalty breaks ties.
    Players with identical score AND penalty share a rank (1, 1, 3, ...)."""
    ordered = sorted(players, key=lambda p: (-p.score, p.penalty))
    ranks: dict[str, int] = {}
    prev_key = None
    prev_rank = 0
    for position, p in enumerate(ordered, start=1):
        key = (p.score, p.penalty)
        rank = prev_rank if key == prev_key else position
        ranks[p.user_id] = rank
        prev_key, prev_rank = key, rank
    return ranks


def calculate(
    players: list[Player],
    k_override: float | None = None,
    scale: float = 400.0,
    min_rating: int = 0,
) -> list[Result]:
    n = len(players)
    if n < 2:
        raise ValueError("At least 2 participants are required to calculate ratings.")

    ranks = compute_ranks(players)
    results: list[Result] = []

    for p in players:
        expected = 0.0
        actual = 0.0
        for q in players:
            if q.user_id == p.user_id:
                continue
            expected += expected_score(p.rating, q.rating, scale)
            if ranks[p.user_id] < ranks[q.user_id]:
                actual += 1.0
            elif ranks[p.user_id] == ranks[q.user_id]:
                actual += 0.5

        k = k_override if k_override is not None else k_for(p.contests_played)
        delta = k * (actual - expected) / (n - 1)
        new_rating = max(min_rating, round(p.rating + delta))

        results.append(
            Result(
                user_id=p.user_id,
                rank=ranks[p.user_id],
                old_rating=round(p.rating),
                new_rating=new_rating,
                delta=new_rating - round(p.rating),
                # Expected rank = 1 + expected number of people who beat you
                expected_rank=round(1 + (n - 1) - expected, 2),
                k_factor_used=k,
            )
        )

    results.sort(key=lambda r: r.rank)
    return results
