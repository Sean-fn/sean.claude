# Stage B → C Branch — Mode 1 vs Mode 2

This is the most important automated decision in the workflow. Get it right and the user almost never has to intervene. Get it wrong and you either over-review trivial work or under-review dangerous work.

## What `choose_mode.py` does

Reads the plan markdown produced by `/claude-mem:make-plan`, runs the rules below, and prints one of three results plus a short reason:

```
$ python3 scripts/choose_mode.py --plan path/to/plan.md
one-shot: 2 phases, no risk keywords, narrow file scope
```

```
$ python3 scripts/choose_mode.py --plan path/to/plan.md
phase-by-phase: matched keyword "auth" in Phase 2
```

```
$ python3 scripts/choose_mode.py --plan path/to/plan.md
ambiguous: 3 phases, one mild keyword match ("token" appears once in a non-secret context)
```

## Rule set

### Default to one-shot when ALL hold

1. ≤ 3 implementation phases (excluding Phase 0 doc discovery and the final Verification phase).
2. No phase mentions any of these keywords (case-insensitive whole-word):
   - **Auth / secrets**: auth, oauth, jwt, password, credential, secret, token (in security context), session, cookie, csrf
   - **Crypto**: encryption, decrypt, hash (in security context), signing
   - **Money**: payment, billing, invoice, charge, refund, money, currency, stripe
   - **Data risk**: migration, schema change, drop table, delete, deletion, rollback, backfill
   - **Infra risk**: production, deploy, rollout, feature flag, breaking change, breaking
3. No phase mentions changing > ~5 files (heuristic: count distinct file paths in the phase's "What to implement" section).
4. No "caution signals" recorded from Stage A in `state.json.history`.

### Default to phase-by-phase when ANY hold

- More than 3 implementation phases
- Any phase contains a keyword from the list above
- Any phase touches > 5 files
- "Caution signals" recorded in Stage A
- Any phase mentions "refactor across", "rewrite", "framework upgrade", "migrate from X to Y"

### Ambiguous when

- Exactly 3 phases AND one weak keyword match (e.g., "token" appears in a context that may not be secret-related — like an API rate-limit token, or a parser token)
- Plan is short but mentions a borderline keyword in passing
- Heuristic confidence is low — the script computes a score and falls into a gray band (configurable threshold)

When ambiguous, stop and ask the user via `AskUserQuestion`.

## When ambiguous, how to ask

Use a single 2-option question. Both options should preview the trade-off:

```
Question: "The plan has 3 phases and mentions 'token' once. Should I run it end-to-end or pause between phases for review?"

Option 1 (Recommended if user signaled speed):
  Label: "One-shot"
  Description: "Hand to /claude-mem:do, run all phases continuously. Faster, single review pass at the end."

Option 2 (Recommended if user signaled caution):
  Label: "Phase-by-phase"
  Description: "Pause between phases for /self-review and conditional security/perf reviews. Slower but safer."
```

Don't add "I'm not sure" / "Other" — the AskUserQuestion tool already adds an "Other" automatically. Picking either explicit option is preferred over Other.

## Why this design

- **Heuristic > model judgment**: Same plan should always pick the same mode. Model judgment drifts. A small Python script does not.
- **Conservative by default**: Tie-breaks go toward Mode 2 (phase-by-phase). Over-reviewing is annoying; under-reviewing is dangerous.
- **One stop point only**: The user is asked at most once per task about execution mode. Once chosen, never re-ask.
- **No mode switch mid-flight**: If a Mode 1 task starts revealing risk, that's not a "switch to Mode 2" event — that's a Mode 1 stop event handled by `/claude-mem:do`'s own logic. Forcing mode-switch capability would explode the state machine.

## Tuning the keyword list

The keyword list lives in `scripts/choose_mode.py`. After iteration 1 of evals, the user feedback may show false positives (Mode 2 chosen when Mode 1 was clearly better) or false negatives (the reverse). Adjust the lists, not the SKILL.md prose — the SKILL.md should stay stable.

## What to put in `state.json.history`

When the branch decision is made, log the event:

```json
{"timestamp": "...", "event": "mode_chosen", "mode": "phase-by-phase", "reason": "matched keyword 'auth' in Phase 2", "ambiguous": false}
```

If the user was asked, set `"ambiguous": true` and add `"user_choice": true`. This makes downstream debugging trivial.
