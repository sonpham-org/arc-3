"""Versioned, independently switchable prompt-only ablations.

Only harness-owned instruction surfaces pass through this function. Never
transform observations, tool results, or retained assistant reasoning.
"""
import os
from inference.agent import loop_variants

VERSION = 'prompt_ablation_v2_repeated_guidance'
# Remove entire repeated instructions before narrower legacy substitutions.
# The original six flags retain byte-identical behavior when these are OFF.
ARMS = ('repeat_strategy', 'repeat_mouse', 'view', 'loop', 'search', 'coords', 'priors', 'transition')
FLAGS = {arm: 'ARC3_PROMPT_ABLATE_' + arm.upper() for arm in ARMS}

# Each entry is (surface, exact old text, replacement). Tool interfaces and
# runtime behavior are intentionally unchanged. All switches OFF is identity.
RULES = {
    'repeat_strategy': [
        ('user', 'Use compact inspection/search code, revise the carried world model in brief assistant text when needed, then execute the shortest reliable valid action or batch via `action(actions)`. ', ''),
    ],
    'repeat_mouse': [
        ('user', '\nIf you use MOUSE, include integer row and col arguments.', ''),
    ],
    'view': [
        ('system', ' Use this as the primary board view and `.ascii` only for a small local crop.', ''),
        ('system', '- Inspect `current_frame.segmentation`, `history`, and `valid_actions`; use ASCII only for a tiny crop. Print compact object lists, diffs, counts, coordinates, or local crops--never a full board or full animation frames.', '- Print output within the tool output limit; truncation is reported. Do not print full animation frames wholesale.'),
        ('tool', 'Use `current_frame.segmentation` for objects and `.ascii` only for a small local crop. ', '`current_frame.segmentation` and `current_frame.ascii` are available board representations. '),
        ('retry', ' -- use `current_frame.segmentation` as the primary view, and `.ascii` only for a small specific region -- ', ' -- `current_frame.segmentation` and `.ascii` are available -- '),
    ],
    'loop': [
        ('system', '- You are called repeatedly over the course of a run. Treat each turn as one observe-plan-act cycle: re-understand the current state from the newest frame, update your working world model in Python, choose the next best action or short sequence against the goal as currently understood, execute it, and expect to re-evaluate on the next turn from the updated state.', '- You are called repeatedly over the course of a run.'),
        ('system', '- Keep a compact world model: entities, action effects, likely goal, uncertainties, and shortest reliable plan. ', '- '),
        ('system', '- Default loop: summarize objects, infer the desired change, choose a probe or searched plan, execute it with `action(...)`, then check `last_action_result` and the refreshed board. Match objects', '- Match objects'),
        ('user', 'Use compact inspection/search code, revise the carried world model in brief assistant text when needed, then execute the shortest reliable valid action or batch via `action(actions)`.', 'Execute valid actions via `action(actions)`.'),
        ('retry', 'You have not acted yet. Investigate first. ', 'You have not acted yet. '),
        ('retry', 'Then investigate and revise your working world model of what the level contains, what actions appear to do, what the current goal seems to be, and what plan looks best. ', ''),
        ('retry', 'If helpful, include short world-model update lines such as `World model:`, `Goal model:`, `Action model:`, `Recent findings:`, `Open questions:`, `Plan:`, or `Cross-level notes:`. ', ''),
        ('retry', 'derives a compact board summary, ', ''),
    ],
    'search': [
        ('system', '; once mechanics are understood, use a scorer, BFS/shortest-path search, or small action-sequence search.', '.'),
        ('system', 'choose a probe or searched plan', 'choose a probe or plan'),
        ('user', 'Use compact inspection/search code,', 'Use compact inspection code,'),
        ('retry', 'programs a small search or scorer over candidate actions or short sequences, ', ''),
        ('retry', 'that your code selected', 'that you selected'),
    ],
    'coords': [
        ('system', '- Use coordinates only to target actions or describe local evidence. Do not frame the objective as reaching a specific absolute row or column.\n', ''),
    ],
    'priors': [
        ('system', '- Background colors are often white or gray/black-ish large regions, but not always. Verify background hypotheses by area, stability, and object boundaries rather than assuming them.\n', ''),
        ('system', '- In many games, a long horizontal or vertical line near an edge is a timer or remaining-steps bar. It often shrinks or changes each step. If you identify such a bar, do not get distracted by it or treat it as core gameplay state unless there is concrete evidence that it interacts with the puzzle mechanics.\n', ''),
        ('system', "A common failure mode is to mistake a segmented edge bar for clickable puzzle pieces. If a repeated strip of small blocks sits flush against the top, bottom, left, or right border and actions only change that strip while the interior board stays the same, classify it as HUD/timer state, not as an object to click through segment by segment. DON'T DO THIS!\n", ''),
    ],
    'transition': [
        ('user', 'Inspect the newest transition in Python and distinguish gameplay change from HUD-only change.\n', ''),
    ],
}


def enabled_flags():
    values = {}
    for arm, key in FLAGS.items():
        value = os.environ.get(key, '0')
        if value not in ('0', '1'):
            raise ValueError(f'{key} must be 0 or 1, got {value!r}')
        values[arm] = value == '1'
    return values


def transform(text, surface):
    if surface not in ('system', 'tool', 'user', 'retry'):
        raise ValueError(surface)
    for arm, enabled in enabled_flags().items():
        if enabled:
            for target, before, after in RULES[arm]:
                if target == surface:
                    text = text.replace(before, after)
    return loop_variants.transform(text, surface)
