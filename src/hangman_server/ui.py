from __future__ import annotations

import html
import json

from .game import GameState


def render_board(state: GameState) -> str:
    game_id = state.game_id
    in_progress = state.status == "in_progress"
    guessed_set = set(state.guessed)

    keyboard_buttons = []
    for code in range(ord("A"), ord("Z") + 1):
        letter = chr(code)
        disabled = "disabled" if (letter in guessed_set or not in_progress) else ""
        keyboard_buttons.append(
            f'<button class="key" data-letter="{letter}" {disabled}>{letter}</button>'
        )
    keyboard_html = "\n      ".join(keyboard_buttons)

    wrong_html = html.escape(", ".join(state.wrong_guesses)) if state.wrong_guesses else "—"
    masked_html = html.escape(state.masked_word)
    message_html = html.escape(state.message) if state.message else ""

    hint_button_html = (
        f'<button id="hint" class="hint" data-game="{html.escape(game_id)}">💡 Hint (−5 × mult)</button>'
        if in_progress
        else ""
    )

    if not in_progress:
        revealed = html.escape(state.revealed or "")
        banner_html = (
            f'<div class="banner banner-{html.escape(state.status)}">'
            f"<strong>{html.escape(state.status.upper())}</strong> — the word was "
            f"<code>{revealed}</code></div>"
        )
    else:
        banner_html = ""

    game_id_js = json.dumps(game_id)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Hangman</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 16px; color: #222; }}
  .meta {{ color: #666; font-size: 0.9em; }}
  .score {{ font-weight: 600; margin: 8px 0; }}
  h1.word {{ font-family: monospace; letter-spacing: 0.3em; font-size: 2.2em; margin: 12px 0; }}
  .wrong {{ color: #b00; margin: 8px 0; }}
  .keyboard {{ display: grid; grid-template-columns: repeat(13, 1fr); gap: 6px; margin: 12px 0; max-width: 540px; }}
  .key {{ padding: 8px 0; font-weight: 600; cursor: pointer; border: 1px solid #999; background: #f7f7f7; border-radius: 4px; }}
  .key:disabled {{ opacity: 0.35; cursor: default; background: #eee; }}
  .key:not(:disabled):hover {{ background: #e6f0ff; }}
  .hint {{ margin-top: 8px; padding: 8px 14px; cursor: pointer; border: 1px solid #c80; background: #fff7e6; border-radius: 4px; font-weight: 600; }}
  .hint:hover {{ background: #ffe9bf; }}
  .message {{ margin: 8px 0; font-style: italic; color: #444; }}
  .banner {{ margin-top: 12px; padding: 12px; border-radius: 4px; font-size: 1.1em; }}
  .banner-won {{ background: #e6f7e6; border: 1px solid #2a7; }}
  .banner-lost {{ background: #fbeaea; border: 1px solid #c33; }}
</style>
</head>
<body>
  <div class="meta">Difficulty: <strong>{html.escape(state.difficulty)}</strong> · Hints used: <strong>{state.hints_used}</strong></div>
  <div class="score">Score: <strong>{state.points}</strong></div>
  <h1 class="word">{masked_html}</h1>
  <div class="wrong">Wrong ({state.wrong_count}/{state.max_wrong}): {wrong_html}</div>
  <div class="message">{message_html}</div>
  <div class="keyboard">
      {keyboard_html}
  </div>
  {hint_button_html}
  {banner_html}
<script>
  const GAME_ID = {game_id_js};
  function send(toolName, params) {{
    window.parent.postMessage({{ type: "tool", payload: {{ toolName: toolName, params: params }} }}, "*");
  }}
  document.querySelectorAll(".key").forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      if (btn.disabled) return;
      send("guess_letter", {{ game_id: GAME_ID, letter: btn.dataset.letter }});
    }});
  }});
  const hintBtn = document.getElementById("hint");
  if (hintBtn) {{
    hintBtn.addEventListener("click", function () {{
      send("get_hint", {{ game_id: hintBtn.dataset.game }});
    }});
  }}
</script>
</body>
</html>
"""
