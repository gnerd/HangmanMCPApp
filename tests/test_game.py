from __future__ import annotations

from hangman_server.game import _Game


def _force_game(secret: str, difficulty: str = "easy", max_wrong: int = 6) -> _Game:
    g = _Game(difficulty, max_wrong)  # type: ignore[arg-type]
    g.secret = secret.upper()
    return g


def test_new_game_initial_state():
    g = _force_game("APPLE")
    snap = g.snapshot(None, "new")
    assert snap.status == "in_progress"
    assert snap.points == 0
    assert snap.hints_used == 0
    assert snap.wrong_count == 0
    assert snap.masked_word == "_ _ _ _ _"
    assert snap.revealed is None


def test_correct_letter_scores_and_unmasks():
    g = _force_game("APPLE")
    last, _ = g.apply_letter("P")
    assert last is not None and last.correct is True
    assert last.delta_points == 20
    assert g.points == 20
    snap = g.snapshot(last, "ok")
    assert snap.masked_word == "_ P P _ _"


def test_wrong_letter_penalty():
    g = _force_game("APPLE")
    last, _ = g.apply_letter("Z")
    assert last is not None and last.correct is False
    assert last.delta_points == -1
    assert g.points == -1
    assert "Z" in g.wrong


def test_duplicate_letter_no_change():
    g = _force_game("APPLE")
    g.apply_letter("P")
    before = g.points
    last, msg = g.apply_letter("P")
    assert last is None
    assert g.points == before
    assert "Already guessed" in msg


def test_hard_mode_doubles():
    g = _force_game("APPLE", difficulty="hard")
    last, _ = g.apply_letter("P")
    assert last is not None and last.delta_points == 40
    g2 = _force_game("APPLE", difficulty="hard")
    last2, _ = g2.apply_letter("Z")
    assert last2 is not None and last2.delta_points == -2


def test_solve_word_wins_with_bonus():
    g = _force_game("APPLE")
    last, _ = g.apply_word("APPLE")
    assert last is not None and last.correct is True
    assert g.status == "won"
    assert last.delta_points == 50
    snap = g.snapshot(last, "won")
    assert snap.revealed == "APPLE"


def test_wrong_word_penalty():
    g = _force_game("APPLE")
    last, _ = g.apply_word("GRAPE")
    assert last is not None and last.correct is False
    assert last.delta_points == -5
    assert g.status == "in_progress"


def test_loss_at_max_wrong():
    g = _force_game("APPLE", max_wrong=3)
    for ch in ("Z", "Y", "X"):
        g.apply_letter(ch)
    assert g.status == "lost"
    snap = g.snapshot(None, "lost")
    assert snap.revealed == "APPLE"


def test_hint_subtracts_and_increments():
    g = _force_game("APPLE")
    last = g.apply_hint()
    assert last.delta_points == -5
    assert g.points == -5
    assert g.hints_used == 1

    gh = _force_game("APPLE", difficulty="hard")
    last2 = gh.apply_hint()
    assert last2.delta_points == -10
    assert gh.points == -10
