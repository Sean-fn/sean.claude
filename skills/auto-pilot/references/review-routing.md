# Review Routing — Keyword → Command Mapping

This file documents how `classify_phase.py` decides which conditional reviews to add on top of the always-run `/self-review`. Keep this file in sync with the script.

## Always run

- `/self-review` — runs on every phase, no conditions.

## Conditional matrices

### `/security-review`

Trigger when phase content matches ANY of these (case-insensitive whole-word):

| Category | Keywords |
|---|---|
| Auth | `auth`, `oauth`, `jwt`, `login`, `logout`, `signin`, `signup`, `password`, `credential`, `session`, `cookie`, `csrf`, `2fa`, `mfa` |
| Secrets | `secret`, `api key`, `private key`, `token` (in auth context) |
| Crypto | `encryption`, `decrypt`, `hash` (in security context), `bcrypt`, `argon`, `signing`, `signature verify` |
| Input | `user input`, `request body`, `query string`, `form data`, `file upload`, `multipart` |
| SQL/queries | `sql`, `query`, `db.execute`, `raw query`, `where clause` (with user input) |
| Permissions | `authorize`, `permission`, `role`, `admin`, `acl`, `rbac` |
| Network | `cors`, `csp`, `xss`, `injection`, `sanitize`, `escape` |

### `/optimize`

Trigger when phase content matches ANY of these:

| Category | Keywords |
|---|---|
| DB | `n+1`, `eager load`, `index`, `query`, `migration`, `bulk insert`, `batch` |
| Algorithm | `loop`, `nested loop`, `O(n^2)`, `complexity`, `recursion`, `memoize`, `cache` |
| I/O | `await in loop`, `parallel`, `concurrent`, `stream`, `pagination`, `lazy load` |
| Frontend | `re-render`, `memo`, `usememo`, `usecallback`, `bundle size`, `code split` |
| Memory | `leak`, `gc`, `weakmap`, `reference`, `large array`, `large object` |

### `/file-by-file-review`

Trigger when:
- Phase touches > 10 files (count distinct file paths in "What to implement").

This is expensive — `/file-by-file-review` itself prompts the user about token cost. Don't add additional warnings before invoking it.

## Disambiguation

Some words are dual-use. Examples:

| Word | Security context | Non-security context |
|---|---|---|
| `token` | "JWT token", "access token", "API token" | "lexer token", "rate-limit token", "CSRF token is security; parser token isn't" |
| `hash` | "password hash", "bcrypt hash" | "Map / hashmap", "git commit hash" |
| `key` | "API key", "private key" | "object key", "primary key" (DB), "key in a map" |

`classify_phase.py` uses simple substring matching first, then a small set of negative-context patterns to filter false positives. False positives are tolerable (over-running `/security-review` is annoying but safe). False negatives are dangerous (skipping `/security-review` when it was needed).

When in doubt, the script errs on the side of running the review.

## Output format

`classify_phase.py` returns a JSON list of command names:

```bash
$ python3 scripts/classify_phase.py --plan plan.md --phase 2
["self-review", "security-review"]
```

`/self-review` is always first in the list. The orchestrator runs them in returned order.

## Adding new conditional reviews

To wire in another review command:

1. Add its trigger keywords to a new section above.
2. Add the matching logic to `classify_phase.py`.
3. Document it here.

Don't add a review just because it exists. The bar: does it find a class of issue the existing reviews miss, on a meaningful fraction of phases?
