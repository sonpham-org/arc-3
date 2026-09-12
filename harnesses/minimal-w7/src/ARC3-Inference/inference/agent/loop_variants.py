"""Single mutually exclusive loop treatment, default OFF. No observation rewriting."""
import os

VERSION='loop_variants_v1'
FLAG='ARC3_LOOP_VARIANT'
MODES=('off','a','b','c','d','e')


def mode():
    value=os.environ.get(FLAG,'off')
    if value not in MODES:raise ValueError(FLAG+' must be off/a/b/c/d/e')
    if value not in ('off','a') and os.environ.get('ARC3_INPUT_ACCESS','0')!='1':
        raise ValueError('Loop experiment requires ARC3_INPUT_ACCESS=1')
    return value


# Deliberately narrow: visual priors, representation/search preferences and budgets
# remain inherited. F audits those independently; A is not an all-guidance removal.
RULES={
 'system':[
  (' Treat each turn as one observe-plan-act cycle: re-understand the current state from the newest frame, update your working world model in Python, choose the next best action or short sequence against the goal as currently understood, execute it, and expect to re-evaluate on the next turn from the updated state.',''),
  ('- Keep a compact world model: entities, action effects, likely goal, uncertainties, and shortest reliable plan. ','- '),
  ('- Default loop: summarize objects, infer the desired change, choose a probe or searched plan, execute it with `action(...)`, then check `last_action_result` and the refreshed board. Match objects','- Match objects'),
  ('- After every action, distinguish gameplay change from a timer/progress-bar-only change. Stop immediately','- Stop immediately'),
  (' Call `action(...)` inside Python; batch a reliable sequence or call it repeatedly in a loop, checking refreshed state after each call.',' Call `action(...)` inside Python.'),
 ],
 'tool':[
  ('After acting, check `last_action_result`; compare `previous_frame` with `current_frame` for the latest settled change. ',
   '`last_action_result` reports action outcomes; `previous_frame` and `current_frame` provide the latest settled endpoints. '),
 ],
 'user':[('Ground on `current_frame` in Python before acting.\n','')],
 'retry':[
  ('You have not acted yet. Investigate first. ','You have not acted yet. '),
  ('Then investigate and revise your working world model of what the level contains, what actions appear to do, what the current goal seems to be, and what plan looks best. ',''),
  ('If helpful, include short world-model update lines such as `World model:`, `Goal model:`, `Action model:`, `Recent findings:`, `Open questions:`, `Plan:`, or `Cross-level notes:`. ',''),
  ('Call the `python` tool with code that inspects `current_frame`, `previous_frame`, `last_transition`, `history`, or `valid_actions` -- use `current_frame.segmentation` as the primary view, and `.ascii` only for a small specific region -- compare `previous_frame` to `current_frame` for the most recent change, derives a compact board summary, programs a small search or scorer over candidate actions or short sequences, then call `action(actions)` inside Python with the best valid action or ordered batch that your code selected. ',
   'Use the `python` tool to access available observations or execute valid actions via `action(actions)`. '),
 ],
}
STATIC={
 'a':'',
 'b':'\nLoop guidance:\nInspect the latest state, update your understanding, choose and execute a valid action or short sequence, then evaluate the result.\n',
 'c':'\nLoop guidance:\nChoose when to inspect, plan, and act. Reconsider your approach when observations contradict your expectations or progress stalls.\n',
 'd':'\nPrediction checking:\nFor an uncertain action with a concrete testable prediction, use `checked_action` to compare the observed outcome with that prediction. Normal reasoning resumes afterward. Do not manufacture certainty when the outcome is ambiguous.\n',
 'e':'\nGuarded execution:\nWhen you have a short plan and concrete expected intermediate outcomes, use `execute_checked` to continue while checks match. Replan after a mismatch, missing evidence, interruption or completed plan. Checks do not establish that the game model is correct.\n',
}
COMMON_API=(
 ' Define `extract(o)` to return a compact observable value from an observation using `.ascii` or `.segmentation`; '
 'return None if identification is ambiguous. Expected/extracted values must be nonempty JSON values '
 '(tuples are accepted as arrays), at most 256 characters and 64 nodes; null/NaN are not checkable. '
 'The extractor runs on CPU before and after each action, cannot call action, and should not print. '
 'Predictions are frozen before acting. Equality produces matched/contradicted; missing or invalid evidence '
 'produces uncheckable. Only selected facts are checked, not an entire simulator or a probability of correctness. '
 'Results are automatically returned compactly under `checks`; do not print full boards. '
 'Calling either method ends this Python snippet; place it last. Existing action/terminal/animation/time guards apply. '
 'Methods are optional; ordinary `action(...)` remains available. No checks or methods persist across snippets.'
)
API={
 'd':' `checked_action(command, extract, expected)` executes at most one action, checks the outcome, then returns control. '
     'Example shape: `checked_action("RIGHT", locate_player, expected=[12,19])`, where you define `locate_player(o)` from observed evidence.'+COMMON_API,
 'e':' `execute_checked(commands, extract, expected)` takes 1..14 single actions and equally many expected extracted values; '
     'executes one at a time without another model call while checks match. Stops on contradiction, uncheckable evidence, '
     'error, host checkpoint, level/shape change, terminal result or plan completion. '
     'Example shape: `execute_checked(["RIGHT","RIGHT"], locate_player, expected=[[12,19],[12,20]])`.'+COMMON_API,
}


def transform(text,surface):
    selected=mode()
    if selected=='off':return text
    if surface not in RULES:raise ValueError(surface)
    # Preserve the malformed-call repair branch verbatim; this is not minimal-retry.
    if surface=='retry' and 'We detected `<tool_call>` markup' in text:return text
    for before,after in RULES[surface]:text=text.replace(before,after)
    if surface=='system':text+=STATIC[selected]
    if surface in ('system','tool') and selected in API:
        text+=('\nChecked-action runtime methods:\n' if surface=='system' else ' ')+API[selected]
    return text
