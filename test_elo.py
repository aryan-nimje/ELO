from fastapi.testclient import TestClient

from elo import Player, calculate, compute_ranks
from main import app

client = TestClient(app)


def test_tie_break_by_penalty_and_shared_ranks():
    players = [
        Player("a", 1500, 10, 300, 100),
        Player("b", 1500, 10, 300, 100),  # exact tie with a
        Player("c", 1500, 10, 300, 150),  # same score, worse penalty
        Player("d", 1500, 10, 100, 10),
    ]
    assert compute_ranks(players) == {"a": 1, "b": 1, "c": 3, "d": 4}


def test_equal_ratings_winner_gains_loser_drops():
    players = [
        Player("a", 1500, 10, 400, 50),
        Player("b", 1500, 10, 100, 50),
    ]
    res = {r.user_id: r for r in calculate(players)}
    assert res["a"].delta > 0 > res["b"].delta
    assert res["a"].delta == -res["b"].delta


def test_upset_gives_bigger_gain_than_expected_win():
    # Low-rated player beats high-rated one
    upset = calculate([Player("low", 1200, 10, 300, 0), Player("high", 1800, 10, 100, 0)])
    # High-rated player beats low-rated one
    expected = calculate([Player("low", 1200, 10, 100, 0), Player("high", 1800, 10, 300, 0)])
    upset_gain = next(r.delta for r in upset if r.user_id == "low")
    expected_gain = next(r.delta for r in expected if r.user_id == "high")
    assert upset_gain > expected_gain


def test_full_tie_among_equals_changes_nothing():
    players = [Player(x, 1500, 10, 200, 60) for x in "abc"]
    assert all(r.delta == 0 for r in calculate(players))


def test_min_rating_floor():
    players = [Player("a", 10, 0, 0, 0), Player("b", 2000, 0, 500, 0)]
    res = {r.user_id: r for r in calculate(players, min_rating=0)}
    assert res["a"].new_rating >= 0


def test_api_happy_path():
    body = {
        "contest_id": "weekly-1",
        "participants": [
            {"user_id": "u1", "current_rating": 1500, "contests_played": 0, "score": 300, "penalty": 95},
            {"user_id": "u2", "current_rating": 1720, "contests_played": 12, "score": 300, "penalty": 120},
            {"user_id": "u3", "contests_played": 0, "score": 100, "penalty": 40},  # new user
        ],
    }
    r = client.post("/calculate", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["participant_count"] == 3
    assert [x["user_id"] for x in data["results"]] == ["u1", "u2", "u3"]
    assert data["results"][2]["old_rating"] == 1000  # default rating applied


def test_api_rejects_single_participant():
    body = {"contest_id": "x", "participants": [{"user_id": "u1", "score": 1}]}
    assert client.post("/calculate", json=body).status_code == 422


def test_api_rejects_duplicate_ids():
    p = {"user_id": "u1", "score": 1}
    body = {"contest_id": "x", "participants": [p, p]}
    assert client.post("/calculate", json=body).status_code == 422
