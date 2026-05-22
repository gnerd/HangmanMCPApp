from __future__ import annotations

import random
import uuid
from typing import Literal

from pydantic import BaseModel

Status = Literal["in_progress", "won", "lost"]
Difficulty = Literal["easy", "hard"]

WORDS: dict[Difficulty, list[str]] = {
    "easy": ["APPLE", "RIVER", "CLOUD", "TIGER", "BREAD", "PLANT", "HOUSE", "PIANO"],
    "hard": [
        "ALGORITHM",
        "JAVASCRIPT",
        "PROTOCOL",
        "KEYBOARD",
        "ADVENTURE",
        "SYMPHONY",
        "ZEPHYR",
        "QUARTZ",
        "MNEMONIC",
        "PHLEGMATIC",
        "JUXTAPOSE",
        "CHIAROSCURO",
    ],
}


class LastGuess(BaseModel):
    kind: Literal["letter", "word", "hint"]
    value: str | None = None
    correct: bool | None = None
    delta_points: int = 0


class GameState(BaseModel):
    game_id: str
    difficulty: Difficulty
    secret_length: int
    masked_word: str
    guessed: list[str]
    wrong_guesses: list[str]
    wrong_count: int
    max_wrong: int
    status: Status
    points: int
    hints_used: int
    last_guess: LastGuess | None = None
    message: str = ""
    revealed: str | None = None


class _Game:
    def __init__(self, difficulty: Difficulty, max_wrong: int):
        self.id: str = uuid.uuid4().hex
        self.difficulty: Difficulty = difficulty
        self.secret: str = random.choice(WORDS[difficulty]).upper()
        self.guessed: set[str] = set()
        self.wrong: list[str] = []
        self.max_wrong: int = max_wrong
        self.status: Status = "in_progress"
        self.points: int = 0
        self.hints_used: int = 0

    @property
    def mult(self) -> int:
        return 2 if self.difficulty == "hard" else 1

    def mask(self) -> str:
        return " ".join(ch if ch in self.guessed else "_" for ch in self.secret)

    def snapshot(self, last: LastGuess | None, msg: str) -> GameState:
        revealed = self.secret if self.status in ("won", "lost") else None
        return GameState(
            game_id=self.id,
            difficulty=self.difficulty,
            secret_length=len(self.secret),
            masked_word=self.mask(),
            guessed=sorted(self.guessed),
            wrong_guesses=list(self.wrong),
            wrong_count=len(self.wrong),
            max_wrong=self.max_wrong,
            status=self.status,
            points=self.points,
            hints_used=self.hints_used,
            last_guess=last,
            message=msg,
            revealed=revealed,
        )

    def apply_letter(self, L: str) -> tuple[LastGuess | None, str]:
        if self.status != "in_progress":
            return None, "Game is already over."
        if len(L) != 1 or not L.isalpha():
            return None, "Guess must be a single letter A-Z."
        L = L.upper()
        if L in self.guessed or L in self.wrong:
            return None, f"Already guessed {L}."

        matches = self.secret.count(L)
        if matches > 0:
            self.guessed.add(L)
            delta = 10 * matches * self.mult
            msg = f"Correct! {L} appears {matches} time(s). +{delta} pts."
            if all(ch in self.guessed for ch in self.secret):
                bonus = 50 * self.mult
                delta += bonus
                self.status = "won"
                msg = f"Correct! {L} appears {matches} time(s). Solved! +{delta} pts (includes +{bonus} solve bonus)."
            self.points += delta
            return LastGuess(kind="letter", value=L, correct=True, delta_points=delta), msg

        self.wrong.append(L)
        delta = -1 * self.mult
        self.points += delta
        msg = f"Wrong. {delta} pts. ({len(self.wrong)}/{self.max_wrong})"
        if len(self.wrong) >= self.max_wrong:
            self.status = "lost"
            msg = f"Wrong. {delta} pts. Out of guesses — you lost."
        return LastGuess(kind="letter", value=L, correct=False, delta_points=delta), msg

    def apply_word(self, W: str) -> tuple[LastGuess | None, str]:
        if self.status != "in_progress":
            return None, "Game is already over."
        if not W or not W.isalpha():
            return None, "Word guess must be letters only."
        W = W.upper()
        if W == self.secret:
            for ch in self.secret:
                self.guessed.add(ch)
            delta = 50 * self.mult
            self.points += delta
            self.status = "won"
            msg = f"Solved! +{delta} pts."
            return LastGuess(kind="word", value=W, correct=True, delta_points=delta), msg

        delta = -5 * self.mult
        self.points += delta
        msg = f"Not the word. {delta} pts."
        return LastGuess(kind="word", value=W, correct=False, delta_points=delta), msg

    def apply_hint(self) -> LastGuess:
        delta = -5 * self.mult
        self.points += delta
        self.hints_used += 1
        return LastGuess(kind="hint", value=None, correct=None, delta_points=delta)
