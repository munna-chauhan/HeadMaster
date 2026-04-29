"""Tests for task.py CLI — drives task.py via subprocess."""
import json
import os
import subprocess
import sys
import tempfile
import unittest


TASK_PY = os.path.join(os.path.dirname(__file__), "task.py")


def run(*args, file=None):
    cmd = [sys.executable, TASK_PY]
    if file:
        cmd += ["--file", file]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


class TestAdd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.close()
        os.unlink(self.tmp.name)  # let task.py create it

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_add_exits_0_and_prints_confirmation(self):
        # AC-1
        result = run("add", "Buy milk", file=self.tmp.name)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Added task #1: Buy milk", result.stdout)

    def test_add_increments_id(self):
        run("add", "First", file=self.tmp.name)
        result = run("add", "Second", file=self.tmp.name)
        self.assertIn("#2", result.stdout)

    def test_add_empty_text_exits_1(self):
        result = run("add", "", file=self.tmp.name)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr)


class TestList(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.close()
        os.unlink(self.tmp.name)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_list_empty_prints_no_tasks(self):
        # AC-5
        result = run("list", file=self.tmp.name)
        self.assertEqual(result.returncode, 0)
        self.assertIn("No tasks.", result.stdout)

    def test_list_missing_file_prints_no_tasks(self):
        # AC-5
        result = run("list", file="/tmp/nonexistent_tasks_xyz.json")
        self.assertEqual(result.returncode, 0)
        self.assertIn("No tasks.", result.stdout)

    def test_list_shows_pending_before_done(self):
        # AC-2
        run("add", "Task A", file=self.tmp.name)
        run("add", "Task B", file=self.tmp.name)
        run("done", "1", file=self.tmp.name)
        result = run("list", file=self.tmp.name)
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        # Pending task (id=2) should appear before done task (id=1)
        pending_idx = next(i for i, l in enumerate(lines) if "Task B" in l)
        done_idx = next(i for i, l in enumerate(lines) if "Task A" in l)
        self.assertLess(pending_idx, done_idx)

    def test_list_format(self):
        # AC-2: [id] [status] text
        run("add", "Buy milk", file=self.tmp.name)
        result = run("list", file=self.tmp.name)
        self.assertRegex(result.stdout.strip(), r"\[1\].*Buy milk")


class TestDone(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.close()
        os.unlink(self.tmp.name)
        run("add", "Task A", file=self.tmp.name)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_done_exits_0_with_confirmation(self):
        # AC-3
        result = run("done", "1", file=self.tmp.name)
        self.assertEqual(result.returncode, 0)
        self.assertIn("1", result.stdout)

    def test_done_nonexistent_exits_1_with_stderr(self):
        # AC-4
        result = run("done", "999", file=self.tmp.name)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr)


class TestDelete(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.close()
        os.unlink(self.tmp.name)
        run("add", "Task A", file=self.tmp.name)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_delete_exits_0_with_confirmation(self):
        # AC-3
        result = run("delete", "1", file=self.tmp.name)
        self.assertEqual(result.returncode, 0)
        self.assertIn("1", result.stdout)

    def test_delete_nonexistent_exits_1_with_stderr(self):
        # AC-4
        result = run("delete", "999", file=self.tmp.name)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr)

    def test_delete_removes_task_from_list(self):
        run("delete", "1", file=self.tmp.name)
        result = run("list", file=self.tmp.name)
        self.assertIn("No tasks.", result.stdout)


class TestFileFlag(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.close()
        os.unlink(self.tmp.name)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_custom_file_path_used(self):
        # AC-6
        run("add", "Custom file task", file=self.tmp.name)
        self.assertTrue(os.path.exists(self.tmp.name))
        with open(self.tmp.name) as f:
            data = json.load(f)
        self.assertEqual(len(data["tasks"]), 1)
        self.assertEqual(data["tasks"][0]["text"], "Custom file task")


if __name__ == "__main__":
    unittest.main()
