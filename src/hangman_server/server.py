from __future__ import annotations

import logging
import sys
from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import SamplingMessage, TextContent
from mcp_ui_server import create_ui_resource
from pydantic import Field

from .game import WORDS, Difficulty, LastGuess, _Game
from .ui import render_board

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

mcp = FastMCP("hangman")

_games: dict[str, _Game] = {}


def _require(game_id: str) -> _Game:
    g = _games.get(game_id)
    if g is None:
        raise ValueError(f"Unknown game_id: {game_id}")
    return g


def _result(g: _Game, last: LastGuess | None, message: str) -> dict:
    state = g.snapshot(last, message)
    resource_uri = f"ui://hangman/board/{g.id}"
    ui = create_ui_resource(
        {
            "uri": resource_uri,
            "content": {"type": "rawHtml", "htmlString": render_board(state)},
            "encoding": "text",
        }
    )
    ui_dump = ui.model_dump(mode="json")
    return {
        "content": [{"type": "text", "text": message}],
        "structuredContent": state.model_dump(),
        "_meta": {"ui": {"resourceUri": resource_uri}},
        "resources": [ui_dump["resource"]],
    }


@mcp.tool()
def new_game(
    difficulty: Difficulty = "easy",
    max_wrong: Annotated[int, Field(ge=3, le=10)] = 6,
) -> dict:
    """Start a new Hangman game and return its initial state plus a rendered board.

    Pick `difficulty="easy"` for short common words and direct hints, or
    `difficulty="hard"` for longer uncommon words, cryptic hints, and 2x score
    multipliers. `max_wrong` caps wrong-letter guesses before the game is lost.
    """
    g = _Game(difficulty, max_wrong)
    _games[g.id] = g
    return _result(g, None, f"New {difficulty} game. Good luck!")


@mcp.tool()
def guess_letter(game_id: str, letter: str) -> dict:
    """Guess a single letter A-Z in the active game and return the updated board.

    Correct guesses score +10 per matched position (x2 on hard); wrong guesses
    cost -1 (x2 on hard) and bring the gallows closer. Duplicates are ignored
    without penalty.
    """
    g = _require(game_id)
    if g.status != "in_progress":
        return _result(g, None, "Game is already over.")
    letter = letter.upper().strip()
    if not (len(letter) == 1 and letter.isalpha()):
        raise ValueError("letter must be a single A-Z character")
    last, msg = g.apply_letter(letter)
    return _result(g, last, msg)


@mcp.tool()
def guess_word(game_id: str, word: str) -> dict:
    """Attempt to solve the active game with a full word guess.

    A correct guess wins immediately with a +50 bonus (x2 on hard). A wrong
    guess costs -5 (x2 on hard) but does not advance the gallows.
    """
    g = _require(game_id)
    if g.status != "in_progress":
        return _result(g, None, "Game is already over.")
    word = word.upper().strip()
    if not word or not word.isalpha():
        raise ValueError("word must be alphabetic")
    last, msg = g.apply_word(word)
    return _result(g, last, msg)


@mcp.tool()
def get_state(game_id: str) -> dict:
    """Return the current state and re-render the board without mutating the game."""
    g = _require(game_id)
    return _result(g, None, "Current state.")


@mcp.tool()
def give_up(game_id: str) -> dict:
    """Forfeit the active game, reveal the secret word, and mark the game lost."""
    g = _require(game_id)
    g.status = "lost"
    return _result(g, None, f"You gave up. The word was {g.secret}.")


_HINT_SYSTEM: dict[str, str] = {
    "easy": (
        "You give beginner-friendly Hangman hints. Reply with ONE short sentence "
        "(<=14 words). Mention the category or a vivid clue. NEVER reveal any "
        "unguessed letter of the word."
    ),
    "hard": (
        "You give cryptic Hangman hints in the style of crossword clues. Reply with "
        "ONE short sentence (<=14 words). Be allusive, never literal. NEVER reveal "
        "any unguessed letter of the word."
    ),
}


@mcp.tool()
async def get_hint(game_id: str, ctx: Context) -> dict:
    """Ask the host's LLM for a one-sentence Hangman hint via MCP sampling.

    Easy difficulty yields a direct beginner-friendly clue; hard difficulty
    yields a cryptic crossword-style clue. Each successful hint costs -5 points
    (x2 on hard). If the host declines sampling no points are deducted. Any
    unguessed letters of the secret are stripped from the hint before return.
    """
    g = _require(game_id)
    if g.status != "in_progress":
        return _result(g, None, "Game is already over.")

    system = _HINT_SYSTEM[g.difficulty]
    user_text = (
        f"Word ({len(g.secret)} letters): {g.secret}\n"
        f"Revealed so far: {g.mask()}\n"
        f"Guessed: {sorted(g.guessed)}\n"
        f"Wrong: {g.wrong}\n"
        "Write the hint now."
    )

    try:
        result = await ctx.session.create_message(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(type="text", text=user_text),
                )
            ],
            system_prompt=system,
            max_tokens=80,
            temperature=0.7,
        )
    except Exception as e:
        logging.warning("Sampling failed: %s", e)
        return _result(
            g, None, "The host declined to generate a hint - no points deducted."
        )

    hint: str | None = None
    if getattr(result.content, "type", None) == "text":
        hint = result.content.text

    if not hint or not hint.strip():
        return _result(
            g, None, "The host declined to generate a hint - no points deducted."
        )

    secret_letters = set(g.secret)
    safe = "".join(
        c
        for c in hint
        if not (c.isalpha() and c.upper() in secret_letters and c.upper() not in g.guessed)
    ).strip()

    if not safe:
        return _result(
            g, None, "The host declined to generate a hint - no points deducted."
        )

    last = g.apply_hint()
    msg = f"\U0001f4a1 Hint: {safe}  (-{5 * g.mult} pts)"
    return _result(g, last, msg)


@mcp.prompt()
def play_hangman(difficulty: str = "easy") -> str:
    """Kick off a Hangman session at the given difficulty (easy or hard)."""
    valid = ", ".join(WORDS.keys())
    return (
        f"Let's play Hangman ({difficulty}). Call the `new_game` tool with "
        f"difficulty=\"{difficulty}\" (valid: {valid}), then play by clicking "
        "letters on the rendered board. Use `get_hint` if you get stuck."
    )
