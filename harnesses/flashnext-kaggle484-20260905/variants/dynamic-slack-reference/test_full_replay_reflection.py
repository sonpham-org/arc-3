from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("ARC3_REPLAY_ENABLED", "1")
os.environ.setdefault("ARC3_REPLAY_ARM", "C")
os.environ.setdefault("ARC3_REPLAY_TRIGGER_REMINDER", "1")
os.environ.setdefault("ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED", "1")
os.environ.setdefault("LOCAL_ANALYZER_MODEL_ID", "test-model")

from inference.agent.python_tool_sandbox import run_sandboxed_python
from inference.agent.runtime_state import Frame, HistoryEntry
from inference.agent.tool_agent import (
    ToolAgent,
    _PYTHON_TOOL_DESCRIPTION,
    _build_system_prompt,
    _common_themes_prompt_block,
    _validated_level_reflection,
)


def main() -> None:
    prompt = _build_system_prompt(tool_output_tokens=1024)
    assert "last_animation.region(i).inspect()" in _PYTHON_TOOL_DESCRIPTION
    assert "replay.repeated_states()" in _PYTHON_TOOL_DESCRIPTION
    assert "Lossless replay memory:" in prompt
    assert "historical transitions do not retain animation objects" in prompt

    reflection, error = _validated_level_reflection(
        '{"winning_world_model":"Match colors to open the exit.",'
        '"decisive_evidence":"The engine confirmed the level after the match.",'
        '"minimal_recipe":"Select the target, then place the matching piece.",'
        '"redundant_actions":"#2:LEFT and #3:RIGHT were a net-zero pair.",'
        '"next_level_rule":"Transfer the color rule, then verify roles."}'
    )
    assert not error, error
    assert "Winning world model:" in reflection
    assert "Carry to next level:" in reflection

    frame_a = Frame(grid=((0, 0), (0, 0)), step=0, level=1)
    frame_b = Frame(grid=((0, 1), (0, 0)), step=1, level=1)
    history = [
        HistoryEntry(action="", frame=frame_a),
        HistoryEntry(action="DOWN", frame=frame_b),
        HistoryEntry(action="UP", frame=frame_a),
    ]
    agent = ToolAgent()
    agent._active_level_reflection = reflection
    agent._active_reflection_source_level = 1
    user_prompt = agent._build_user_prompt(
        2,
        valid_actions=["UP", "DOWN"],
        current_frame=frame_a,
        history_entries=history,
    )
    assert "Replay trigger:" in user_prompt
    assert "Winning world model from the immediately completed level:" in user_prompt

    initial_state = {
        "current_frame": {
            "ascii": "",
            "step": 2,
            "level": 1,
            "shape": [2, 2],
            "grid": [[0, 0], [0, 0]],
        },
        "history": [
            {
                "action": entry.action,
                "frame": {
                    "ascii": "",
                    "step": entry.frame.step,
                    "level": entry.frame.level,
                    "shape": [2, 2],
                    "grid": [list(row) for row in entry.frame.grid],
                },
            }
            for entry in history
        ],
        "replay_enabled": True,
        "valid_actions": ["UP", "DOWN"],
        "last_action_result": {},
        "last_animation": {
            "animation_frame_count": 2,
            "animation_changed_frame_count": 1,
            "keyframes": [],
            "regions": [],
        },
    }
    sandbox = run_sandboxed_python(
        code="result={'events':replay.stats()['events'],'animation':last_animation.total_frames}",
        timeout_seconds=10,
        initial_state=initial_state,
        action_handler=lambda _actions: (_ for _ in ()).throw(
            AssertionError("inspection must not execute actions")
        ),
    )
    assert not sandbox.get("error"), sandbox
    assert sandbox["result"] == {"events": 3, "animation": 2}

    with tempfile.TemporaryDirectory() as directory:
        ledger = Path(directory) / "themes.json"
        ledger.write_text(
            json.dumps(
                {
                    "revision": 1,
                    "updated_at": "test",
                    "games_observed_total": 2,
                    "frames_observed_total": 10,
                    "influence_mode": "nvfp4_persistent_world_models_to_gameplay",
                    "themes": [
                        {
                            "theme_id": "wm-1",
                            "category": "mechanic",
                            "confidence": "medium",
                            "theme": "Verify repeated-state loops before retrying.",
                            "support_games": ["a", "b"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        old_path = os.environ.get("ARC3_COMMON_THEMES_PATH")
        os.environ["ARC3_COMMON_THEMES_PATH"] = str(ledger)
        try:
            block, metadata = _common_themes_prompt_block()
        finally:
            if old_path is None:
                os.environ.pop("ARC3_COMMON_THEMES_PATH", None)
            else:
                os.environ["ARC3_COMMON_THEMES_PATH"] = old_path
        assert metadata["status"] == "injected"
        assert "wm-1" in block

    print(
        json.dumps(
            {
                "status": "ok",
                "system_prompt_chars": len(prompt),
                "combined_user_prompt_chars": len(user_prompt),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
