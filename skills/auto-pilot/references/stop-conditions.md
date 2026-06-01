# Stop Conditions — Exhaustive Catalogue

The autopilot is "strict" — it should run without interruption except in these enumerated cases. If you find yourself stopping for a reason not on this list, you've drifted. Re-read SKILL.md.

## Legitimate stops

### 1. Stage A — until problem is pinned

You may call `AskUserQuestion` repeatedly in Stage A. Each call must extract real information; don't loop on the same question.

Stop ends when: you can write the goal sentence per `references/stage-a-define.md`.

### 2. Stage B → C branch — only if `choose_mode.py` returned "ambiguous"

Single AskUserQuestion call presenting both modes. Once the user picks (or "Other" with custom guidance), the choice is final. No re-ask.

Stop ends when: state.json.execution_mode is set.

### 3. Stage C (Mode 1) — only if `/claude-mem:do` itself stops

You delegated to `/claude-mem:do`. If it succeeds, advance to Stage D. If it stops or fails, capture its stop reason in state.json and surface to user. Do NOT retry by default — the user must tell you whether to retry, switch to Mode 2, or abort.

Stop ends when: user gives direction.

### 4. Stage C (Mode 2) — fix would change plan direction

Specifically:
- Critical/High finding requires touching files outside the phase's stated scope (cross-module collateral).
- Critical/High finding requires re-architecting (the fix invalidates Phase N+1's plan).
- Multiple valid fixes exist and they have meaningfully different trade-offs.
- Same issue persists after one auto-fix attempt (don't loop on stubborn issues).

Stop ends when: user picks a direction.

### 5. Stage C (Mode 2) — iteration cap exceeded

After 3 fix-attempts on a single phase, escalate regardless of severity. The cap is hard.

Stop ends when: user picks a direction (continue, abort, plan-rewrite).

### 6. Stage C — test infra missing or broken

If the phase's verification checklist cannot be executed (missing tools, missing test data, broken pipeline), do NOT advance blindly. Stop.

Stop ends when: user resolves infra OR explicitly tells you to skip verification (and accept that risk).

### 7. Stage D — completion (this is a successful stop)

The skill exits naturally. Surface the summary, offer `/merge-commit-msg`, mark state.stage=D.

## Illegitimate stops (do NOT do these)

These are common temptations. Resist:

| Temptation | Why it's wrong |
|---|---|
| "Should I commit this phase?" | Routine commits don't need permission. The plan said commit per phase or at milestones; follow the plan. |
| "Found 2 medium issues, want me to fix?" | Mediums with clear fixes auto-fix. Stop is for direction questions only. |
| "The test passed — should I move on?" | Yes. If C2 + C3 cleared, you advance. Don't ask. |
| "Should I run /optimize on this phase?" | The classifier decides. Don't ask. |
| "Is this code style OK?" | Style is Low severity. Low is "advance" per the matrix. |
| "What if there's an issue I haven't seen?" | That's why the reviews run. Trust the process. |

## How to phrase a legitimate stop

When you do stop, the AskUserQuestion call should:

1. State the **stop reason** clearly (cite the catalogue number above).
2. Quote the specific finding or failure.
3. Present **2–3 actionable options**, not "what should I do?". Options shape:
   - Option A: "Apply fix X (described below)"
   - Option B: "Abort and refine the plan"
   - Option C: "Skip the failing check, accept the risk"

Bad: "I found a high-severity issue, what should I do?"

Good: "Phase 2 review flagged: SQL injection risk in `auth.controller.ts:45` — user-supplied `email` interpolated into a query string. The fix would either be (A) parameterize the query, (B) use the ORM's safe query builder, or (C) escape input via the existing `sanitize()` helper. Which approach?"

## Logging stops

Every stop must be logged:

```bash
python3 scripts/update_state.py --slug <slug> --set stop_reason="<catalogue_number>: <short reason>"
```

So when the loop resumes, the state file knows exactly why it paused.
