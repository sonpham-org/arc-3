"""Opening-persona arm for the system prompt.

`default`  -- the stock opening: you are playing a video game, this game is
            generally easy for humans, think about it like a human and not like
            a coding agent. This is the control.
`streamer` -- the Boss's Gen Z Twitch streamer framing (21-Sep-2026, verbatim):
            a coding agent that will not bore its audience with obsessive
            planning and prefers confidence, action and reassessment.

Motivation: every arm run on 21-Sep-2026 showed the same failure -- the model
reads the board correctly, then spends the turn re-deriving and reconciling
instead of pressing anything. The only intervention that produced actions was
forcing them. This arm tests whether a persona that treats deliberation as
boring does the same job without the force.

Only the opening sentences change. The control-name sentences (UP/DOWN/LEFT/
RIGHT/SPACE/MOUSE/ACTION7) are shared by both arms, because the model needs the
names of the buttons it is allowed to press regardless of who it thinks it is.

Selected by ARC3_PERSONA so one checkout runs either arm. Default is `default`;
set ARC3_PERSONA=streamer for the treatment arm.
"""
from __future__ import annotations

import os

DEFAULT_OPENING = (
    "You are playing a video game. This game is generally easy for humans. "
    "Think about the game like a human and not like a coding agent. "
)

STREAMER_OPENING = (
    "You are a coding agent with a Gen Z Twitch streamer persona: You don't waste "
    "time thinking on stuff that's going to bore the audience. You prioritize "
    "confidence, action, and reassessment over obsessive planning. "
)


def persona() -> str:
    name = os.environ.get("ARC3_PERSONA", "").strip().lower()
    return "streamer" if name == "streamer" else "default"


def streamer_persona_enabled() -> bool:
    return persona() == "streamer"


def opening_persona_block() -> str:
    return STREAMER_OPENING if streamer_persona_enabled() else DEFAULT_OPENING
