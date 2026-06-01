# note-cli

Tiny multi-file Python CLI for managing personal notes. Used as an auto-pilot eval fixture.

## Usage

```
python -m note_cli add "Buy milk"
python -m note_cli list
python -m note_cli search "milk"
python -m note_cli export out.md
python -m note_cli login alice
```

## Layout

- `note_cli/cli.py` — argparse entrypoint, 5 subcommands
- `note_cli/storage.py` — sqlite3 wrapper
- `note_cli/search.py` — in-memory search helpers
- `note_cli/auth.py` — password verification
- `note_cli/export.py` — markdown export (do not modify in eval)
- `note_cli/ai_summary.py` — AI summarization stub (do not modify in eval)

## Tests

```
pip install -e .[test]
pytest
```
