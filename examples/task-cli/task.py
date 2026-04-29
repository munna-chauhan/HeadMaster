"""Python CLI task tracker — stdlib only (argparse, json, pathlib)."""
import argparse
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

DEFAULT_FILE = "./tasks.json"


def load_tasks(path):
    p = Path(path)
    if not p.exists():
        return []
    with p.open() as f:
        return json.load(f).get("tasks", [])


def save_tasks(path, tasks):
    data = json.dumps({"tasks": tasks}, indent=2)
    dir_ = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def next_id(tasks):
    return max((t["id"] for t in tasks), default=0) + 1


def cmd_add(tasks, text):
    if not text.strip():
        print("Error: task text cannot be empty.", file=sys.stderr)
        sys.exit(1)
    task = {"id": next_id(tasks), "text": text, "status": "pending", "created_at": str(date.today())}
    tasks.append(task)
    print(f"Added task #{task['id']}: {task['text']}")
    return tasks


def cmd_list(tasks):
    if not tasks:
        print("No tasks.")
        return
    pending = [t for t in tasks if t["status"] == "pending"]
    done = [t for t in tasks if t["status"] == "done"]
    for t in pending:
        print(f"[{t['id']}] [ ] {t['text']}")
    for t in done:
        print(f"[{t['id']}] [x] {t['text']}")


def cmd_done(tasks, id_):
    for t in tasks:
        if t["id"] == id_:
            t["status"] = "done"
            print(f"Task #{id_} marked done.")
            return tasks
    print(f"Error: task #{id_} not found.", file=sys.stderr)
    sys.exit(1)


def cmd_delete(tasks, id_):
    for i, t in enumerate(tasks):
        if t["id"] == id_:
            tasks.pop(i)
            print(f"Task #{id_} deleted.")
            return tasks
    print(f"Error: task #{id_} not found.", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(prog="task.py", description="Simple CLI task tracker")
    parser.add_argument("--file", default=DEFAULT_FILE, metavar="PATH", help="path to tasks JSON file")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="add a task")
    p_add.add_argument("text", help="task description")

    sub.add_parser("list", help="list all tasks")

    p_done = sub.add_parser("done", help="mark task done")
    p_done.add_argument("id", type=int, help="task ID")

    p_del = sub.add_parser("delete", help="delete a task")
    p_del.add_argument("id", type=int, help="task ID")

    args = parser.parse_args()
    tasks = load_tasks(args.file)

    if args.cmd == "add":
        tasks = cmd_add(tasks, args.text)
        save_tasks(args.file, tasks)
    elif args.cmd == "list":
        cmd_list(tasks)
    elif args.cmd == "done":
        tasks = cmd_done(tasks, args.id)
        save_tasks(args.file, tasks)
    elif args.cmd == "delete":
        tasks = cmd_delete(tasks, args.id)
        save_tasks(args.file, tasks)


if __name__ == "__main__":
    main()
