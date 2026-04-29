# task-cli

Minimal command-line task tracker. Python 3.8+, stdlib only — no install needed.

## Usage

```bash
python task.py add "Buy milk"          # Added task #1: Buy milk
python task.py add "Write report"      # Added task #2: Write report
python task.py list                    # [2] [ ] Write report
                                       # [1] [ ] Buy milk
python task.py done 1                  # Task #1 marked done.
python task.py list                    # [2] [ ] Write report
                                       # [1] [x] Buy milk
python task.py delete 2                # Task #2 deleted.
python task.py list                    # [1] [x] Buy milk
```

Tasks persist in `./tasks.json` by default. Use `--file` to override:

```bash
python task.py --file ~/work.json add "Ship feature"
```

## Commands

| Command | Description |
|---------|-------------|
| `add <text>` | Add a task (exits 0, prints confirmation) |
| `list` | List tasks — pending first, done last |
| `done <id>` | Mark task done (exits 1 if ID not found) |
| `delete <id>` | Remove task (exits 1 if ID not found) |

## Tests

```bash
python test_task.py
```
