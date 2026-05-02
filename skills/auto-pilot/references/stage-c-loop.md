# Stage C — Mode 2 Inner Loop (deep details)

This file covers edge cases, decision-matrix nuances, and how to recover from common failures in the phase-by-phase loop. SKILL.md has the happy path; this has everything else.

## Phase iteration order

`/claude-mem:make-plan` produces phases in this order:

1. Phase 0: Documentation Discovery (skip — make-plan already executed it)
2. Phase 1..N: Implementation phases (iterate these)
3. Final Phase: Verification (handle as part of Stage D, not Stage C)

You iterate Phase 1 → N. Stage D's final verification is separate.

## C1 — Implement (subagent contract)

The implementation subagent gets:
- The phase's "What to implement" verbatim
- The phase's "Documentation references" (file paths + line ranges)
- The phase's "Verification checklist" (so it knows the bar)
- The phase's "Anti-pattern guards"
- The repo paths it will touch

It does NOT get:
- Other phases' content (would dilute focus)
- The full SKILL.md of auto-pilot (irrelevant)
- The user's original conversation (causes drift)

If you need the same subagent to span >1 phase, that's a planning failure — go back, run `/claude-mem:make-plan` again with finer-grained phases.

## C2 — Run tests

The phase's verification checklist tells you what to run. Examples from real plans:

- `npm test -- --testPathPattern=auth` — focused test suite
- `grep -r "old-api-name" src/` — anti-pattern check
- `cargo build --release` — compile check

Run them in sequence. First failure → treat as an issue, route to C4 with severity High by default (unless the failure is clearly a flake — but don't second-guess, treat as real).

If the checklist includes a step you cannot execute (missing tool, missing test data), STOP and AskUserQuestion. Do NOT silently skip checklist items.

## C3 — Review composition

`/self-review` always. Then `classify_phase.py` returns conditional reviews. Common combinations:

| Phase content keywords | Reviews to run |
|---|---|
| (none beyond "implement") | `/self-review` |
| auth, login, password, jwt, token (security) | `/self-review`, `/security-review` |
| api endpoint accepting user input | `/self-review`, `/security-review` |
| sql query, raw query, db.execute | `/self-review`, `/security-review`, `/optimize` |
| n+1, loop with await, hot path | `/self-review`, `/optimize` |
| > 10 changed files | `/self-review`, `/file-by-file-review` (with token warning) |

The classifier uses keyword sets. Don't try to be clever — clear keyword matches > inferred intent.

## C4 — Decision matrix (extended)

| Findings severity | Fix is in-plan? | Action |
|---|---|---|
| None / Low only | n/a | Mark phase done. Advance. |
| Medium | Yes | Auto-fix subagent. Re-run C3. |
| Medium | No (out of plan scope) | Note in `last_review_summary`. Advance. (Don't expand scope mid-loop.) |
| High | Yes, clear fix | Auto-fix. Re-run C3. |
| High | Ambiguous (multiple valid fixes) | STOP. AskUserQuestion. |
| Critical | Yes, clear fix | Auto-fix. Re-run C3. |
| Critical | Ambiguous OR implies plan rewrite | STOP. AskUserQuestion. |

"In-plan" means: the fix is consistent with the phase's stated goal and doesn't require touching files outside the phase's stated scope. If the fix needs to touch files the phase didn't claim, that's an architectural fork → STOP.

## Loop guards

- **Max review iterations per phase: 3.** After 3 fix attempts on the same phase, escalate via AskUserQuestion regardless of severity. State the iteration count and what's repeatedly being flagged.
- **Same finding twice in a row → escalate immediately.** If the auto-fix didn't kill the issue, a second auto-fix probably won't either. Don't burn tokens.
- **Test infra failures → escalate.** If `/self-review` cannot run (missing baseline branch, no diff, broken tooling), do NOT continue blindly. Stop and ask.

## Edge cases

### Phase has no verification checklist

Sometimes `/claude-mem:make-plan` produces a phase with weak verification. If C2 has nothing to run, fall back to:
- `git diff --stat` to confirm the phase actually changed something.
- If no diff, the implementation subagent failed silently → escalate.

### Phase changed nothing

If the implementation subagent reports completion but `git diff` is empty, treat it as a failure. Either the phase was already done (mark phase done, advance — log this) or the subagent was confused (re-spawn with stricter prompt). Don't let "0-diff success" silently advance.

### Phase touched files outside its stated scope

The implementation subagent touched files the phase didn't claim. This is either:
- Necessary collateral (e.g., the phase changed an API and a caller needed updating) — usually fine, log it.
- Scope creep — STOP and ask.

Heuristic: if the extra files are in the same module/package as the phase's stated files, allow it. If they're cross-module, escalate.

### `/security-review` finds something but `/self-review` did not

Trust `/security-review` — it's specialized. Apply C4 matrix to its findings. Don't dismiss because `/self-review` was clean.

### `/optimize` recommends micro-optimizations

Filter `/optimize` findings: if Priority is Low AND the impact estimate is "negligible", skip. Don't burn fix-iterations on style-tier perf gains.

## State updates per phase

Every phase advance must hit `update_state.py`. The state schema events:

```json
{"timestamp":"...","event":"phase_started","phase":1}
{"timestamp":"...","event":"review_run","phase":1,"reviews":["self-review","security-review"],"findings_count":3}
{"timestamp":"...","event":"phase_fix_attempt","phase":1,"iteration":1}
{"timestamp":"...","event":"phase_done","phase":1,"final_iterations":2}
{"timestamp":"...","event":"phase_escalated","phase":1,"reason":"3 iterations exhausted"}
```

This makes `cat .claude/state/auto-pilot/<slug>/state.json | jq '.history[]'` a useful debug surface.
