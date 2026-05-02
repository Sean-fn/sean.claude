# Stage A — Problem Definition Protocol

The goal of Stage A is **not to make the user feel interviewed**. It's to extract enough signal that you can write the goal as a verifiable sentence, then move on.

## Default opening (single AskUserQuestion call)

Ask 2–3 questions that cover: **outcome, scope, and acceptance criteria**. Resist asking 4 questions if 2 will do — this is not a checklist exercise.

Examples of good multi-question calls:

| Header | Question | Options shape |
|---|---|---|
| Outcome | What does "done" mean for this task? | concrete option labels reflecting your reading of the request |
| Scope | What's explicitly out of scope? | "nothing", "tests", "docs", "infra", or "Other" |
| Acceptance | How will we verify success? | "tests pass", "manual smoke test", "code review only", "perf benchmark" |

## When to ask more

Add a follow-up call only if the user's first answers contradict each other, OR they used vague terms ("better", "faster", "cleaner") without specifying what they're measured against.

If the user says "make it faster", the very first question MUST pin down a target metric. Don't even attempt to plan without one. Acceptable answers: "p50 latency under X ms", "request count under Y per page", "cold start under Z seconds". "Just faster" is not acceptable.

## When to escalate to a real conversation

If after 2 question calls you still cannot write the goal as a verifiable sentence, stop using AskUserQuestion (which forces multiple-choice) and write a plain text response with your current understanding + the gap. Let them respond freely. Some asks need words, not radio buttons.

## When the user resists questions

If the user says "just figure it out" or "don't ask, just do it":

1. State your best-guess interpretation as 1–3 sentences.
2. State the assumptions you're making (top 2 risk).
3. Ask ONE final yes/no question: "Proceed with this interpretation?"
4. If yes → write goal, advance.
5. If no → they have to give you something. They don't get a third pass.

## Caution-signal words

Capture these from the conversation history, you'll use them at the B→C branch:

- **"careful", "thorough", "review each step", "production", "be safe"** → push toward Mode 2 (phase-by-phase).
- **"quick", "small", "just", "trivial", "throwaway"** → push toward Mode 1 (one-shot).

Save these to `state.json.history` as a `caution_signals` event so `choose_mode.py` can read them.

## Format for the final goal sentence

Once Stage A is complete, write the goal in this shape and store it as `state.json.goal`:

> "[Verb] [object] so that [verifiable outcome], measured by [acceptance criterion]. Out of scope: [list]."

Examples:

- "Add JWT auth to the Express app so that authenticated requests can access /api/* routes, measured by: integration tests pass for login + protected route access. Out of scope: refresh tokens, password reset, frontend changes."
- "Fix the off-by-one in `parse_range` so that `parse_range(1, 5)` includes index 5, measured by: a regression test that fails before the fix and passes after. Out of scope: refactoring adjacent code."

If you cannot write a sentence in this shape, Stage A is not done.
