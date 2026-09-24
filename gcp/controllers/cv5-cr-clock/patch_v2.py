"""v2 arms for items 1-3 (NOTE: the runtime probe derives feature flags from sandbox globals -- `replay`, `vision`,
`workspace`, `load_helper` must never be defined here; symbolic_v2's scorer is therefore check_model()): reuse the feature flags, but give the model executable, host-checked tools.

Son, 24-Sep: "For item 1 to 3 you can reuse the flag but you should have your own take and build on these things."

The three flag arms (execution / memory / symbolic) give the model *declarative* memory: text rules, a
JSON symbolic spec, an expected_next check the host evaluates. The v2 arms keep those flags and add a
per-game **code store** the host persists across snippets and context rotations, plus one executable
verification primitive per arm. The common thread is the ablation study's finding that *verification*
(predict, act, compare, stop on mismatch) is the load-bearing component: every v2 primitive replays
model-written code against the FULL recorded transition history, and the host, not the model, decides
whether the code has earned the right to act in batches.

  kernel (all three)  store / save(**fields): JSON-safe per-game store; save(code=...) is re-executed at
                      the start of every later snippet, so helpers, predict(), encode()/step() survive.
  execution_v2        verify(predict): replay predict(before_frame, action) -> grid | cells | None over the
                      history; fidelity report with the first mismatches. When a saved predict() exists
                      every action() is auto-checked and a mismatch halts the batch (stop-on-mismatch).
                      Batches of more than one action need a verified predict (fidelity >= 0.8 on >= 3
                      transitions); otherwise the batch is cut to its first action.
  memory_v2           rule(id, text, holds): evidence-linked rules whose predicate (source of a
                      lambda over one transition) is replayed over the whole history at the start of
                      every snippet; the first counterexample REVOKES the rule and is reported. rules()
                      / drop(id). The model's memory can no longer keep a rule the history contradicts.
  symbolic_v2         encode(frame) -> state and step(state, action) -> state as plain Python; replay()
                      scores them over the history; plan(goal, max_depth, actions) is a bounded BFS over
                      the executable model from the current state. Same batch gate and auto-check as
                      execution_v2, driven by replay fidelity.

Applied to a candidate tree with constant-only prompt edits (the selftests' prompt identity test
re-executes the assembling functions against installed constants, so it still holds), a sandbox
bootstrap edit, one host edit in python_tool_sandbox.py (the store), and one call-site edit in
tool_agent.py (store_key). No triple quotes inside the bootstrap: it lives in a raw string.

Usage: python patch_v2.py <candidate_src_root> <execution_v2|memory_v2|symbolic_v2>
"""
import sys
from pathlib import Path

ARMS = ("execution_v2", "memory_v2", "symbolic_v2")

# ----------------------------------------------------------------------------- host: per-game code store
HOST_SIG_OLD = '''    workspace_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rgb_python_tool_") as sandbox_dir:
'''
HOST_SIG_NEW = '''    workspace_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    store_key: str | None = None,
) -> dict[str, Any]:
    # v2 kernel: a small JSON store per game (keyed by the caller's per-game directory) that survives
    # fresh snippets and context rotations. The sandbox reads it in its initial payload and patches it
    # with a "store" message; nothing here is rendered into the prompt, the model reads it in Python.
    store = _CODE_STORES.setdefault(store_key, {}) if store_key else {}
    with tempfile.TemporaryDirectory(prefix="rgb_python_tool_") as sandbox_dir:
'''
HOST_STORE_DEF_OLD = '''def run_sandboxed_python(
'''
HOST_STORE_DEF_NEW = '''_CODE_STORES: dict[str, dict[str, Any]] = {}
_CODE_STORE_MAX_CHARS = 24_000


def _apply_store_updates(store: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    try:
        json.dumps(updates, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        return {"saved": False, "error": f"store patch is not JSON-safe: {exc}"}
    merged = dict(store)
    for key, value in updates.items():
        if value is None:
            merged.pop(str(key), None)
        else:
            merged[str(key)] = value
    size = len(json.dumps(merged, ensure_ascii=False))
    if size > _CODE_STORE_MAX_CHARS:
        return {"saved": False, "error": f"store would be {size} chars; limit {_CODE_STORE_MAX_CHARS}. Drop or shorten fields."}
    store.clear()
    store.update(merged)
    return {"saved": True, "keys": sorted(store), "chars": size}


def run_sandboxed_python(
'''
HOST_PAYLOAD_OLD = '''                "symbolic_enabled": symbolic_handler is not None,
                "workspace_enabled": workspace_handler is not None,
            },
'''
HOST_PAYLOAD_NEW = '''                "symbolic_enabled": symbolic_handler is not None,
                "workspace_enabled": workspace_handler is not None,
                "store": dict(store),
                # ARC3_V2_BATCH_GATE=1 is exported by the startup after every bundled selftest (they batch
                # actions bare); in gameplay it makes multi-action batches require a verified model.
                "batch_gate": os.environ.get("ARC3_V2_BATCH_GATE") == "1",
            },
'''
HOST_LOOP_OLD = '''            if msg_type == "remember":
'''
HOST_LOOP_NEW = '''            if msg_type == "store":
                try:
                    value = _apply_store_updates(store, dict(message.get("updates") or {}))
                except Exception:  # Fail open, like remember.
                    value = {"saved": False, "error": "store failed in sandbox host"}
                _send_json_line(process.stdin, {"type": "store_result", "value": value})
                continue
            if msg_type == "remember":
'''

AGENT_CALL_OLD = '''            workspace_handler=_handle_workspace if self._programmatic_workspace is not None else None,
        )
'''
AGENT_CALL_NEW = '''            workspace_handler=_handle_workspace if self._programmatic_workspace is not None else None,
            store_key=str(state_path.parent),
        )
'''

# ----------------------------------------------------------------------------- sandbox: kernel
SANDBOX_ACTION_OLD = '''        def action(actions):
            normalized_actions = _normalize_actions(actions)
            _send({"type": "action", "actions": normalized_actions})
            reply = _recv()
            if reply.get("type") == "action_error":
                raise RuntimeError(str(reply.get("error", "action failed")))
            if reply.get("type") != "action_result":
                raise RuntimeError("Invalid action response from sandbox host.")
            action_result = reply.get("action_result") or {}
            action_results.append(action_result)
            _refresh_state(reply.get("state") or {})
            if reply.get("interrupt_execution"):
                raise _ActionSequenceInterrupted(
                    str(action_result.get("stop_detail") or "Action sequence stopped")
                )
            return action_result
'''

KERNEL = r'''
        # ---- v2 kernel: host-persistent per-game store + replay helpers (no triple quotes: bootstrap string)
        store = dict(initial.get("store") or {})

        def save(**fields):
            # Persist JSON-safe fields for this game. save(code=src) is re-executed at the start of every
            # later snippet (helpers, predict, encode/step survive). Pass None to delete a field.
            _send({"type": "store", "updates": fields})
            reply = _recv()
            value = reply.get("value") if reply.get("type") == "store_result" else None
            if not isinstance(value, dict):
                return {"saved": False, "error": "invalid store response"}
            if value.get("saved"):
                for key, val in fields.items():
                    if val is None:
                        store.pop(key, None)
                    else:
                        store[key] = val
                if fields.get("code"):
                    # saved code runs now as well as at the start of every later snippet
                    try:
                        exec(compile(str(fields["code"]), "<stored_code>", "exec"), runtime_globals, runtime_globals)
                    except Exception as exc:
                        value = dict(value)
                        value["code_error"] = _sanitize_exception(exc)[-300:]
            return value

        def _grid(frame):
            return None if frame is None else [list(row) for row in frame._grid]

        def _diff_cells(a, b):
            out = []
            for r in range(max(len(a), len(b))):
                ra = a[r] if r < len(a) else []
                rb = b[r] if r < len(b) else []
                for c in range(max(len(ra), len(rb))):
                    va = ra[c] if c < len(ra) else None
                    vb = rb[c] if c < len(rb) else None
                    if va != vb:
                        out.append((r, c, va, vb))
            return out

        def _action_label(entry):
            # Same label the history uses: UP / DOWN / LEFT / RIGHT / SPACE / MOUSE(row=r, col=c) / RESET.
            name = str(entry.get("action", "")).strip().upper()
            if name == "MOUSE" and "row" in entry and "col" in entry:
                return "MOUSE(row=" + str(entry["row"]) + ", col=" + str(entry["col"]) + ")"
            return name

        def _recorded():
            return [t for t in (runtime_globals.get("transitions") or []) if t.before_frame is not None]

        def _compare_prediction(pred, actual_frame):
            # pred: full grid, list of (row, col, color) cells, or None (abstain). Returns (ok, detail).
            if pred is None:
                return None, "abstained"
            actual = _grid(actual_frame)
            if actual is None:
                return None, "no frame"
            if isinstance(pred, (list, tuple)) and pred and isinstance(pred[0], (list, tuple)) and len(pred[0]) == 3 and not isinstance(pred[0][0], (list, tuple)):
                bad = []
                for cell in pred:
                    r, c, v = cell
                    if not (0 <= r < len(actual) and 0 <= c < len(actual[r])) or actual[r][c] != v:
                        bad.append((r, c, v, actual[r][c] if 0 <= r < len(actual) and 0 <= c < len(actual[r]) else None))
                return (not bad), ("cells wrong: " + str(bad[:6]) if bad else "cells ok")
            if isinstance(pred, (list, tuple)):
                d = _diff_cells([list(row) for row in pred], actual)
                return (not d), (str(len(d)) + " cells wrong (row, col, predicted, actual): " + str(d[:6]) if d else "grid ok")
            return None, "prediction must be a grid, a list of (row, col, color) cells, or None"

        def _run_stored_code():
            src = str(store.get("code") or "")
            if not src:
                return
            try:
                exec(compile(src, "<stored_code>", "exec"), runtime_globals, runtime_globals)
            except Exception as exc:
                print("[stored code failed] " + _sanitize_exception(exc)[-300:] + " -- fix it and save(code=...) again")

        def _gate_batch(normalized_actions, report_key, what):
            # Multi-action batches need a verified executable model (fidelity >= 0.8 on >= 3 transitions).
            if len(normalized_actions) <= 1 or not initial.get("batch_gate"):
                return normalized_actions
            rep = store.get(report_key) or {}
            n = int(rep.get("exact", 0)) + int(rep.get("wrong", 0))
            fid = float(rep.get("fidelity", 0.0))
            if n >= 3 and fid >= 0.8:
                return normalized_actions
            print("[batch cut to 1 action] " + what + " fidelity " + str(fid) + " on " + str(n)
                  + " transitions; a verified model (>= 0.8 on >= 3) is required to batch. Acting once, then re-verify.")
            return normalized_actions[:1]

        runtime_globals["store"] = store
        runtime_globals["save"] = save
'''

# each arm: extra kernel definitions + the action() body + snippet-start hook + prompt constants
ARM_CODE = {
    "execution_v2": dict(
        defs=r'''
        def verify(predict, last=None, show=3):
            # Replay predict(before_frame, action_label) -> grid | [(row, col, color), ...] | None over the
            # recorded transitions. The report is saved under store["verify"] and gates action batches.
            ts = _recorded()
            if last:
                ts = ts[-int(last):]
            exact = wrong = skipped = 0
            misses = []
            for t in ts:
                try:
                    pred = predict(t.before_frame, t.action)
                except Exception as exc:
                    wrong += 1
                    misses.append({"step": t.after_frame.step, "action": t.action, "error": _sanitize_exception(exc)[-160:]})
                    continue
                ok, detail = _compare_prediction(pred, t.after_frame)
                if ok is None:
                    skipped += 1
                elif ok:
                    exact += 1
                else:
                    wrong += 1
                    misses.append({"step": t.after_frame.step, "action": t.action, "detail": detail})
            report = {"transitions": len(ts), "exact": exact, "wrong": wrong, "abstained": skipped,
                      "fidelity": round(exact / max(1, exact + wrong), 3), "misses": misses[:int(show)]}
            save(verify=report)
            return report

        runtime_globals["verify"] = verify
''',
        action=r'''
        def action(actions):
            normalized_actions = _gate_batch(_normalize_actions(actions), "verify", "predict()")
            predict = runtime_globals.get("predict")
            before_frame = runtime_globals.get("current_frame")
            _send({"type": "action", "actions": normalized_actions})
            reply = _recv()
            if reply.get("type") == "action_error":
                raise RuntimeError(str(reply.get("error", "action failed")))
            if reply.get("type") != "action_result":
                raise RuntimeError("Invalid action response from sandbox host.")
            action_result = reply.get("action_result") or {}
            _refresh_state(reply.get("state") or {})
            checked = None
            if callable(predict) and before_frame is not None and len(normalized_actions) == 1:
                try:
                    pred = predict(before_frame, _action_label(normalized_actions[0]))
                    checked, detail = _compare_prediction(pred, runtime_globals.get("current_frame"))
                except Exception as exc:
                    checked, detail = False, "predict raised " + _sanitize_exception(exc)[-160:]
                if checked is not None:
                    action_result = dict(action_result)
                    action_result["prediction_check"] = {"ok": checked, "detail": detail}
            action_results.append(action_result)
            if reply.get("interrupt_execution"):
                raise _ActionSequenceInterrupted(
                    str(action_result.get("stop_detail") or "Action sequence stopped")
                )
            if checked is False:
                print("[prediction mismatch] " + _action_label(normalized_actions[0]) + ": " + detail)
                raise _ActionSequenceInterrupted(
                    "predict() disagreed with the real transition; batch halted. Inspect the diff, fix predict(), save(code=...), verify()."
                )
            return action_result
''',
        start=r'''
        _run_stored_code()
''',
        tool=(
            " Executable verification is enabled: `store` (per-game dict) and `save(**fields)` persist across snippets; "
            "`save(code=src)` re-executes `src` at the start of every later snippet, so define helpers and a "
            "`predict(before_frame, action) -> grid | [(row, col, color), ...] | None` there. `verify(predict)` replays it "
            "over every recorded transition and returns fidelity plus the first mismatches. Once a `predict` exists, every "
            "single action is auto-checked and a mismatch halts the batch; batches longer than one action require a verified "
            "predict (fidelity >= 0.8 on >= 3 transitions)."
        ),
        bullet=(
            "- Build the mechanics as code, not prose: write `predict(before_frame, action)` for what you believe, `save(code=...)`, "
            "run `verify(predict)` and read the misses. Predict only the cells you understand (return a cell list; `None` to abstain). "
            "A mismatch during an action is the most informative event in the game: fix the model before acting again.\\n"
        ),
    ),
    "memory_v2": dict(
        defs=r'''
        def _rule_fn(src):
            return eval(compile(str(src), "<rule>", "eval"), runtime_globals, runtime_globals)

        def _replay_rules(announce):
            rules = store.get("rules") or {}
            if not rules:
                return
            ts = _recorded()
            changed = False
            live = []
            revoked = []
            for rid, entry in rules.items():
                if entry.get("status") == "dropped":
                    continue
                try:
                    fn = _rule_fn(entry["holds"])
                except Exception as exc:
                    entry["status"] = "broken"
                    entry["detail"] = "predicate does not compile: " + _sanitize_exception(exc)[-120:]
                    changed = True
                    revoked.append(rid + " (broken)")
                    continue
                support = 0
                counter = None
                for t in ts:
                    if t.after_frame.step < int(entry.get("since_step", 0)):
                        continue
                    try:
                        v = fn(t)
                    except Exception as exc:
                        counter = {"step": t.after_frame.step, "action": t.action, "error": _sanitize_exception(exc)[-120:]}
                        break
                    if v is True:
                        support += 1
                    elif v is False:
                        counter = {"step": t.after_frame.step, "action": t.action}
                        break
                if counter is not None:
                    if entry.get("status") != "revoked":
                        changed = True
                    entry["status"] = "revoked"
                    entry["counterexample"] = counter
                    revoked.append(rid + " @step " + str(counter["step"]) + " " + str(counter["action"]))
                else:
                    if entry.get("support") != support:
                        changed = True
                    entry["status"] = "live"
                    entry["support"] = support
                    live.append(rid + "(+" + str(support) + ")")
            if changed:
                save(rules=rules)
            if announce:
                print("rules: live " + (" ".join(live) or "-") + " | revoked " + (", ".join(revoked) or "-"))

        def rule(id, text, holds):
            # Register an evidence-linked rule. holds: source of a predicate over ONE transition t
            # (t.action, t.before_frame, t.after_frame, t.result) returning True (supports), False (refutes)
            # or None (not applicable). Replayed over the whole history now and at the start of every snippet;
            # the first False revokes the rule and names the counterexample.
            rid = str(id).strip()
            if not rid or len(rid) > 32:
                return {"accepted": False, "error": "rule id must be 1..32 chars"}
            try:
                fn = _rule_fn(holds)
                if not callable(fn):
                    return {"accepted": False, "error": "holds must be the source of a callable, e.g. 'lambda t: ...'"}
            except Exception as exc:
                return {"accepted": False, "error": "holds does not compile: " + _sanitize_exception(exc)[-160:]}
            rules = dict(store.get("rules") or {})
            if len(rules) >= 12 and rid not in rules:
                return {"accepted": False, "error": "at most 12 rules; drop(id) one first"}
            cur = runtime_globals.get("current_frame")
            rules[rid] = {"text": str(text)[:160], "holds": str(holds)[:400], "since_step": 0,
                          "proposed_step": int(cur.step) if cur is not None else 0, "status": "live", "support": 0}
            res = save(rules=rules)
            if not res.get("saved"):
                return {"accepted": False, "error": res.get("error")}
            _replay_rules(False)
            entry = (store.get("rules") or {}).get(rid) or {}
            return {"accepted": True, "id": rid, "status": entry.get("status"), "support": entry.get("support"),
                    "counterexample": entry.get("counterexample")}

        def rules():
            return {rid: {k: v for k, v in e.items() if k != "holds"} for rid, e in (store.get("rules") or {}).items()}

        def drop(id):
            rs = dict(store.get("rules") or {})
            if str(id) in rs:
                rs[str(id)]["status"] = "dropped"
                save(rules=rs)
                return {"dropped": True}
            return {"dropped": False, "error": "unknown rule id"}

        runtime_globals["rule"] = rule
        runtime_globals["rules"] = rules
        runtime_globals["drop"] = drop
''',
        action=SANDBOX_ACTION_OLD,
        start=r'''
        _run_stored_code()
        _replay_rules(True)
''',
        tool=(
            " Evidence-linked rules are enabled: `rule(id, text, holds)` registers a rule whose `holds` is the source of a "
            "predicate over one transition `t` (`t.action`, `t.before_frame`, `t.after_frame`, `t.result`) returning True, "
            "False or None. The host replays every rule over the full history at the start of each snippet; the first "
            "False revokes it and reports the counterexample step. `rules()` lists them, `drop(id)` retires one. `store` / "
            "`save(**fields)` persist across snippets and `save(code=src)` re-executes `src` each snippet."
        ),
        bullet=(
            "- State every mechanic you rely on as a `rule(...)` with a checkable predicate, not just as text. A rule that "
            "survives many transitions is evidence; a revoked rule is a discovery -- read the counterexample and replace the "
            "rule. Mirror only live, well-supported rules into `remember(confirmed_rules=...)`.\\n"
        ),
    ),
    "symbolic_v2": dict(
        defs=r'''
        def check_model(last=None, show=3):
            # Score the executable model encode(frame) -> state, step(state, action) -> state | None over the history.
            encode = runtime_globals.get("encode")
            step = runtime_globals.get("step")
            if not callable(encode) or not callable(step):
                return {"ok": False, "error": "define encode(frame) and step(state, action) (save them with save(code=...)) first"}
            ts = _recorded()
            if last:
                ts = ts[-int(last):]
            exact = wrong = unknown = 0
            misses = []
            for t in ts:
                try:
                    predicted = step(encode(t.before_frame), t.action)
                    actual = encode(t.after_frame)
                except Exception as exc:
                    wrong += 1
                    misses.append({"step": t.after_frame.step, "action": t.action, "error": _sanitize_exception(exc)[-160:]})
                    continue
                if predicted is None:
                    unknown += 1
                elif predicted == actual:
                    exact += 1
                else:
                    wrong += 1
                    misses.append({"step": t.after_frame.step, "action": t.action, "predicted": str(predicted)[:160], "actual": str(actual)[:160]})
            report = {"ok": True, "transitions": len(ts), "exact": exact, "wrong": wrong, "unknown": unknown,
                      "fidelity": round(exact / max(1, exact + wrong), 3), "misses": misses[:int(show)]}
            save(fidelity=report)
            return report

        def plan(goal, max_depth=12, actions=None, max_nodes=20000):
            # Bounded BFS over the executable model from the current state. goal(state) -> bool.
            # actions: labels to branch on (default: valid_actions minus RESET; MOUSE needs explicit
            # 'MOUSE(row=r, col=c)' labels). Returns the shortest label sequence found, or found=False.
            encode = runtime_globals.get("encode")
            step = runtime_globals.get("step")
            if not callable(encode) or not callable(step):
                return {"found": False, "error": "define encode/step first"}
            cur = runtime_globals.get("current_frame")
            if cur is None:
                return {"found": False, "error": "no current frame"}
            labels = [str(a) for a in (actions if actions is not None else runtime_globals.get("valid_actions") or []) if str(a).upper() != "RESET" and str(a).upper() != "MOUSE"]
            start = encode(cur)
            try:
                if goal(start):
                    return {"found": True, "actions": [], "depth": 0, "expanded": 0}
            except Exception as exc:
                return {"found": False, "error": "goal raised " + _sanitize_exception(exc)[-160:]}
            frontier = [(start, [])]
            seen = {json.dumps(start, sort_keys=True, default=str)}
            expanded = 0
            depth = 0
            while frontier and depth < int(max_depth):
                depth += 1
                nxt = []
                for state, path in frontier:
                    for lab in labels:
                        expanded += 1
                        if expanded > int(max_nodes):
                            return {"found": False, "expanded": expanded, "depth": depth, "error": "node budget exhausted"}
                        try:
                            s2 = step(state, lab)
                        except Exception as exc:
                            return {"found": False, "error": "step raised on " + lab + ": " + _sanitize_exception(exc)[-160:]}
                        if s2 is None:
                            continue
                        key = json.dumps(s2, sort_keys=True, default=str)
                        if key in seen:
                            continue
                        seen.add(key)
                        p2 = path + [lab]
                        if goal(s2):
                            return {"found": True, "actions": p2, "depth": depth, "expanded": expanded}
                        nxt.append((s2, p2))
                frontier = nxt
            return {"found": False, "expanded": expanded, "depth": depth, "error": "no goal state within max_depth"}

        runtime_globals["check_model"] = check_model
        runtime_globals["plan"] = plan
''',
        action=r'''
        def action(actions):
            normalized_actions = _gate_batch(_normalize_actions(actions), "fidelity", "encode/step")
            encode = runtime_globals.get("encode")
            step = runtime_globals.get("step")
            before_frame = runtime_globals.get("current_frame")
            _send({"type": "action", "actions": normalized_actions})
            reply = _recv()
            if reply.get("type") == "action_error":
                raise RuntimeError(str(reply.get("error", "action failed")))
            if reply.get("type") != "action_result":
                raise RuntimeError("Invalid action response from sandbox host.")
            action_result = reply.get("action_result") or {}
            _refresh_state(reply.get("state") or {})
            checked = None
            detail = ""
            if callable(encode) and callable(step) and before_frame is not None and len(normalized_actions) == 1:
                try:
                    predicted = step(encode(before_frame), _action_label(normalized_actions[0]))
                    actual = encode(runtime_globals.get("current_frame"))
                    if predicted is not None:
                        checked = predicted == actual
                        detail = "predicted " + str(predicted)[:160] + " actual " + str(actual)[:160]
                except Exception as exc:
                    checked, detail = False, "model raised " + _sanitize_exception(exc)[-160:]
                if checked is not None:
                    action_result = dict(action_result)
                    action_result["model_check"] = {"ok": checked, "detail": detail}
            action_results.append(action_result)
            if reply.get("interrupt_execution"):
                raise _ActionSequenceInterrupted(
                    str(action_result.get("stop_detail") or "Action sequence stopped")
                )
            if checked is False:
                print("[model mismatch] " + _action_label(normalized_actions[0]) + ": " + detail)
                raise _ActionSequenceInterrupted(
                    "encode/step disagreed with the real transition; batch halted. Fix the model, save(code=...), check_model()."
                )
            return action_result
''',
        start=r'''
        _run_stored_code()
''',
        tool=(
            " An executable world model is enabled: define `encode(frame) -> state` (a small JSON-able summary) and "
            "`step(state, action) -> state | None` in Python and persist them with `save(code=src)` (`store` / `save` survive "
            "across snippets; saved code re-executes each snippet). `check_model()` scores the model over every recorded "
            "transition and returns fidelity with the first misses; `plan(goal, max_depth=12, actions=None)` is a bounded "
            "BFS over the model from the current state returning the shortest action labels. Each action is auto-checked "
            "against the model and a mismatch halts the batch; batches longer than one action need check_model() fidelity >= 0.8 "
            "on >= 3 transitions. `symbolic_search` remains available for scalar specs."
        ),
        bullet=(
            "- Prefer an executable model to a described one: encode the few quantities that matter, write step() for the "
            "mechanics you have seen, save it, check_model() it, and only plan() with it once it agrees with the history. When "
            "an action contradicts the model, the miss tells you which mechanic is wrong -- fix that before exploring further.\\n"
        ),
    ),
}

SANDBOX_GLOBALS_OLD = '''        runtime_globals["action"] = action
        runtime_globals["remember"] = remember
        _refresh_state(initial.get("state") or {})

        try:
            compiled = compile(str(initial.get("code", "")), "<python_tool>", "exec")
            with contextlib.redirect_stdout(stdout):
                exec(compiled, runtime_globals, runtime_globals)
'''
SANDBOX_GLOBALS_NEW = '''        runtime_globals["action"] = action
        runtime_globals["remember"] = remember
        _refresh_state(initial.get("state") or {})

        try:
            compiled = compile(str(initial.get("code", "")), "<python_tool>", "exec")
            with contextlib.redirect_stdout(stdout):
                __SNIPPET_START__
                exec(compiled, runtime_globals, runtime_globals)
'''

TOOL_DESC_OLD = '''    "fields are rejected. Use `print(...)` for compact output or assign to `result`."
)'''
ADDENDUM_ANCHOR = '''    "- Use `print(...)` or `result` for short decision-oriented output. Call `action(...)` inside Python; batch a reliable sequence or call it repeatedly in a loop, checking refreshed state after each'''


def sub_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    assert n == 1, f"{label}: expected exactly one match, found {n}"
    return text.replace(old, new)


def _indent_block(block: str, spaces: int) -> str:
    import textwrap
    pad = " " * spaces
    return "\n".join((pad + line if line.strip() else line) for line in textwrap.dedent(block).strip("\n").splitlines())


def apply(root: Path, arm: str) -> dict:
    assert arm in ARMS, arm
    spec = ARM_CODE[arm]
    agent = root / "inference" / "agent"

    sb = agent / "python_tool_sandbox.py"
    s = sb.read_text(encoding="utf-8")
    # host
    s = sub_once(s, HOST_STORE_DEF_OLD, HOST_STORE_DEF_NEW, "host store definitions")
    s = sub_once(s, HOST_SIG_OLD, HOST_SIG_NEW, "host signature")
    s = sub_once(s, HOST_PAYLOAD_OLD, HOST_PAYLOAD_NEW, "host initial payload")
    s = sub_once(s, HOST_LOOP_OLD, HOST_LOOP_NEW, "host message loop")
    # sandbox
    s = sub_once(s, SANDBOX_ACTION_OLD, KERNEL + spec["defs"] + spec["action"], "sandbox action()")
    start = _indent_block(spec["start"], 16)
    s = sub_once(s, SANDBOX_GLOBALS_OLD, SANDBOX_GLOBALS_NEW.replace("                __SNIPPET_START__", start), "sandbox snippet start")
    sb.write_text(s, encoding="utf-8", newline="\n")

    ta = agent / "tool_agent.py"
    t = ta.read_text(encoding="utf-8")
    t = sub_once(t, AGENT_CALL_OLD, AGENT_CALL_NEW, "tool_agent store_key")
    t = sub_once(t, TOOL_DESC_OLD,
                 '    "fields are rejected. Use `print(...)` for compact output or assign to `result`."\n'
                 '    "' + spec["tool"].replace('"', '\\"') + '"\n)', "tool description constant")
    ta.write_text(t, encoding="utf-8", newline="\n")

    pr = agent / "prompts.py"
    p = pr.read_text(encoding="utf-8")
    p = sub_once(p, ADDENDUM_ANCHOR, '    "' + spec["bullet"].replace('"', '\\"') + '"\n' + ADDENDUM_ANCHOR, "PYTHON_ADDENDUM bullet")
    pr.write_text(p, encoding="utf-8", newline="\n")

    # the bootstrap must still be valid Python once dedented
    import importlib.util
    spec_ = importlib.util.spec_from_file_location("ptsb_check", sb)
    mod = importlib.util.module_from_spec(spec_)
    sys.path.insert(0, str(root))
    spec_.loader.exec_module(mod)  # type: ignore[union-attr]
    compile(mod._SANDBOX_BOOTSTRAP, "<bootstrap>", "exec")
    return {"arm": arm, "changed": [str(x.relative_to(root)) for x in (sb, ta, pr)]}


if __name__ == "__main__":
    print(apply(Path(sys.argv[1]).resolve(), sys.argv[2]))
