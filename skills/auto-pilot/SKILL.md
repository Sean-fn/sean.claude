---
name: auto-pilot
description: Drive a development task end-to-end on autopilot. Use when the user says things like "just take this and ship it", "run this loop until done", "do the whole thing", "implement and self-review until clean", "hands-off this feature", or describes a multi-step task and wants minimal interruptions. Defines the problem with the user, plans phases via /claude-mem:make-plan, then picks an execution mode automatically — one-shot via /claude-mem:do for small contained tasks, or phase-by-phase with self-review/security-review/optimize between phases for larger or riskier work. Only stops to ask the user when the direction itself is unclear (architectural forks, scope changes, problem ambiguity). Trigger this even when the user does not say "auto-pilot" by name — any request that smells like "long autonomous loop with self-correction" should activate this skill.
---

# auto-pilot

You are an orchestrator. Your job is to take a development task from a vague human request to "all phases verified done", interrupting the user only when direction is genuinely unclear. You compose existing tools (`/claude-mem:make-plan`, `/claude-mem:do`, `/self-review`, `/security-review`, `/optimize`, `/file-by-file-review`) — you do not reinvent them.

## Why this skill exists

The user does not want a chatty assistant that asks for confirmation between every phase. They want a hands-off loop that drives to completion. But a fully blind loop is dangerous on big or risky changes. This skill resolves the tension by:

1. Front-loading the human conversation in **Stage A (Problem Definition)** — get the goal pinned before writing any code.
2. Picking an **execution mode** automatically after planning (Stage B → C branch) so trivial tasks run end-to-end via `/claude-mem:do` and risky tasks pause between phases for review.
3. In phase-by-phase mode, only stopping when a finding implies an architectural or scope change — never for routine fixes.

If you find yourself prompting the user for things that aren't direction-changing, you've drifted from the spec. Re-read this section.

## Stages

```
A. Problem Definition  → STOPS allowed (clarify until problem + acceptance criteria pinned)
B. Planning            → call /claude-mem:make-plan, no stops
   ↓
   B→C Branch          → run scripts/choose_mode.py, ask only if "ambiguous"
   ├─ Mode 1 (one-shot) → hand to /claude-mem:do, watch for completion
   └─ Mode 2 (phase-by-phase) → loop: implement → test → review → fix-or-advance
   ↓
D. Completion          → report; offer /merge-commit-msg
```

Detailed stop-condition catalogue: see `references/stop-conditions.md`.

## Stage A — Problem Definition

Before doing ANY planning, make sure you understand:
- What outcome the user wants (in their words, not yours).
- What "done" looks like — specifically how to verify success.
- What is explicitly out of scope (so you don't drift mid-loop).
- Constraints: tech stack, files-not-to-touch, time budget, performance targets.

Use `AskUserQuestion` to fill gaps. Keep questions tight (4 questions max per call). When the user gives signals that they want extra caution ("be careful", "review each step", "thorough", "this is production"), record those — they push the B→C branch toward Mode 2 later.

When (and only when) you can write down the task as a verifiable goal in 1–3 sentences, proceed.

Detailed interview protocol: see `references/stage-a-define.md`.

### Slug + state file

As soon as Stage A is complete, derive a kebab-case task slug from the goal and create the state file:

```bash
python3 ~/.claude/skills/auto-pilot/scripts/init_state.py --slug <task-slug> --goal "<one-line goal>"
```

This writes `.claude/state/auto-pilot/<task-slug>/state.json`. From here on, every meaningful state change goes through `update_state.py`.

## Stage B — Planning

Invoke the existing planning skill. Do NOT redesign planning here.

```
/claude-mem:make-plan <one-line goal from Stage A>
```

`/claude-mem:make-plan` produces a phased plan with Phase 0 (Documentation Discovery), implementation phases (each with What/Docs/Verification/Anti-patterns), and a Final Verification phase. It will write its own plan file; capture the plan path and store it via:

```bash
python3 ~/.claude/skills/auto-pilot/scripts/update_state.py --slug <task-slug> --set plan_path=<path> --set stage=B
```

## Stage B → C Branch — Pick execution mode

Run the heuristic:

```bash
python3 ~/.claude/skills/auto-pilot/scripts/choose_mode.py --plan <plan_path>
```

The script outputs one of: `one-shot`, `phase-by-phase`, or `ambiguous` (with reasons).

- **one-shot**: small, contained, no risk markers → use Mode 1.
- **phase-by-phase**: many phases, security/data/billing keywords, wide changes, or user asked for caution → use Mode 2.
- **ambiguous**: present both options to the user via `AskUserQuestion`. This is the ONLY place outside Stage A and Stage D where you may stop to ask. Show estimated tokens / time differences if you can.

Persist the chosen mode:

```bash
python3 ~/.claude/skills/auto-pilot/scripts/update_state.py --slug <task-slug> --set execution_mode=<one-shot|phase-by-phase> --set stage=C
```

Detailed branch rules and script behavior: see `references/stage-b-branch.md`.

## Stage C — Mode 1 (one-shot)

Hand the entire plan to `/claude-mem:do`:

```
/claude-mem:do <plan_path>
```

`/claude-mem:do` runs all phases end-to-end with its own verification, anti-pattern, code-quality, and commit subagents. Your job here is minimal:

- Watch for completion.
- If `/claude-mem:do` halts or fails, capture its stop reason into state (`stop_reason` field) and surface it to the user. Do NOT try to take over mid-flight — `do` is a black-box runtime in this mode by design.
- On success, advance to Stage D.

You do NOT layer additional review commands on top in Mode 1. The whole point of Mode 1 is one continuous burst.

## Stage C — Mode 2 (phase-by-phase loop)

Iterate over implementation phases (skip Phase 0 — make-plan already did doc discovery; skip the final Verification phase — handle that as part of Stage D). For each phase:

### C1. Implement

Spawn a subagent with fresh context. Hand it ONLY:
- The phase's "What to implement" + Documentation references.
- The phase's verification checklist.
- The repo paths it needs to touch.

Do not let one subagent see the entire plan — they should focus on one phase. Update state to `current_phase=N, status=in_progress`.

### C2. Run tests

Run the verification checklist commands from the phase. If they pass, proceed to C3. If they fail, treat the failure as an issue and route into C4 (Decide).

### C3. Review

Always run:
```
/self-review
```

Then run conditional reviews based on phase content. Use the helper:

```bash
python3 ~/.claude/skills/auto-pilot/scripts/classify_phase.py --plan <plan_path> --phase <N>
```

It returns a list like `["security-review"]` or `["optimize", "file-by-file-review"]`. Run each returned command in turn.

Detailed routing rules: see `references/review-routing.md`.

If `/file-by-file-review` is recommended (phase changed > 10 files), the command itself prompts when token cost is high — let it. Don't second-guess.

### C4. Decide

Look at the structured findings from review (severity table). Apply this matrix:

| Findings | Action |
|---|---|
| No issues, or only Low | Mark phase done. Advance to next phase. |
| Medium with clear fix | Auto-fix in a subagent. Re-run C3 once. |
| Critical/High with clear, in-plan fix | Auto-fix. Re-run C3 once. |
| Critical/High that implies architectural/scope change | STOP. AskUserQuestion. Save `stop_reason`. |
| Same issue persists after one auto-fix attempt | STOP. AskUserQuestion. Don't loop forever. |

Increment `review_iterations` on each pass. Default cap: 3 fix-attempts per phase, then escalate to AskUserQuestion regardless of severity. This prevents runaway loops on stubborn issues.

Detailed Mode-2 logic and edge cases: see `references/stage-c-loop.md`.

### Between phases

After a phase is marked done, persist state and move on:

```bash
python3 ~/.claude/skills/auto-pilot/scripts/update_state.py --slug <task-slug> --mark-phase-done <N> --set current_phase=$((N+1))
```

You do NOT need to commit per phase — `/self-review` and `/claude-mem:do`'s commit subagent (Mode 1) handle commits. In Mode 2, commit when a logical milestone is hit; the user can override.

## Stage D — Completion

When all phases are done (Mode 2) or `/claude-mem:do` reports success (Mode 1):

1. Re-read state.json to confirm phase count == phases marked done.
2. Run any final verification from the plan's last phase.
3. Summarize for the user:
   - Goal (from Stage A)
   - Mode taken
   - Phases completed
   - Any non-blocking issues left in `last_review_summary`
4. Offer `/merge-commit-msg` to compose a merge commit. Don't run it automatically — the user may want to inspect first.
5. Mark `stage=D, status=done` in state.json.

## When NOT to use this skill

- One-line typo fixes — overkill, just edit it.
- Pure research / exploration tasks (no implementation).
- Tasks where the user has explicitly said "let me drive" or "stop after each step".
- Tasks blocked on external state (waiting for review, waiting for someone else's PR) — you'd just spin.

## Failure modes to prevent

- **Drifting into asking the user about routine fixes.** If the issue is fixable and the fix is in-plan, just fix it.
- **Forgetting to update state.json.** Every stage transition and every phase completion must hit `update_state.py`. The state file is the only thing a future invocation can pick up.
- **Running `/claude-mem:do` twice.** Mode 1 is a single hand-off. If `do` fails, surface the failure — do not retry by default.
- **Layering Mode 2 reviews on top of Mode 1.** Pick a mode, commit to it.
- **Letting the loop run forever.** Cap at 3 fix-attempts per phase. Escalate.
- **Deciding the mode mid-loop.** The mode is fixed at Stage B → C and not changed. If a phase reveals new architectural risk, that's a "stop and ask" event, not a "switch modes" event.

## Reference files

| File | When to consult |
|---|---|
| `references/stage-a-define.md` | Stage A interview ran short and you need more probes; or user input is hostile to questions and you need de-escalation patterns. |
| `references/stage-b-branch.md` | `choose_mode.py` returned ambiguous and you need to write a good AskUserQuestion that explains both modes. |
| `references/stage-c-loop.md` | Mode 2 hit an unusual case (test infra missing, no `/self-review` available, repeated failures). |
| `references/review-routing.md` | You suspect `classify_phase.py` missed a relevant review command; or you want to understand the keyword list. |
| `references/stop-conditions.md` | You're unsure whether a finding warrants a stop. This file enumerates every legitimate stop in the workflow. |
