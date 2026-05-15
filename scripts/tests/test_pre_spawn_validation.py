#!/usr/bin/env python
"""
Test FIX-019: Pre-spawn prompt validation
Validates that review subagent spawns are blocked if implementation context leaked.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


def run_validation_hook(tool_call: dict) -> tuple[bool, str]:
    """Run pre_spawn_validation hook and return result."""
    payload = {"tool_call": tool_call}

    result = subprocess.run(
        [PYTHON, ".claude/hooks/pre_spawn_validation.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        input=json.dumps(payload),
        timeout=5
    )

    if result.stdout:
        try:
            output = json.loads(result.stdout)
            return output.get("ok", False), output.get("reason", "")
        except json.JSONDecodeError:
            return False, "Hook returned invalid JSON"
    else:
        return False, "Hook returned no output"


def test_clean_prompt():
    """Test 1: Clean prompt with only TDD + diff should pass."""
    print("Test 1: Clean prompt...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "review-agent",
            "description": "Code review",
            "prompt": """Review the following git diff against TDD requirements.

TDD Section:
- Interface: UserService.createUser(email: string, name: string): Promise<User>
- Returns User object with id, email, name fields

Git Diff:
+++ src/services/UserService.ts
+export class UserService {
+  async createUser(email: string, name: string): Promise<User> {
+    return { id: uuid(), email, name };
+  }
+}

Verify TDD compliance and flag any security issues (OWASP Top 10).
"""
        }
    }

    ok, reason = run_validation_hook(tool_call)
    assert ok, f"Clean prompt should pass, got: {reason}"
    print("  [PASS] Clean prompt allowed")


def test_implementation_file_path():
    """Test 2: Implementation file path in prompt should block."""
    print("Test 2: Implementation file path...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "review-agent",
            "prompt": """Review the implementation in src/services/UserService.ts.

The file implements user creation with email validation.
Check for security issues.
"""
        }
    }

    ok, reason = run_validation_hook(tool_call)
    assert not ok, "Should block implementation file path"
    assert "file" in reason.lower(), f"Should mention file, got: {reason}"
    print(f"  [PASS] Blocked: {reason}")


def test_large_code_block():
    """Test 3: Large code block (>200 chars) should block."""
    print("Test 3: Large code block...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "review-agent",
            "prompt": """Review this implementation:

```typescript
export class UserService {
  private db: Database;
  private validator: EmailValidator;
  private logger: Logger;

  constructor(db: Database, validator: EmailValidator, logger: Logger) {
    this.db = db;
    this.validator = validator;
    this.logger = logger;
  }

  async createUser(email: string, name: string): Promise<User> {
    if (!this.validator.validate(email)) {
      throw new Error('Invalid email');
    }

    const user = await this.db.insert({ email, name });
    this.logger.info(`Created user: ${user.id}`);
    return user;
  }
}
```

Check for issues.
"""
        }
    }

    ok, reason = run_validation_hook(tool_call)
    assert not ok, "Should block large code block"
    assert "code block" in reason.lower(), f"Should mention code block, got: {reason}"
    print(f"  [PASS] Blocked: {reason}")


def test_small_code_snippet_allowed():
    """Test 4: Small code snippet (<200 chars) like TDD interface should pass."""
    print("Test 4: Small code snippet...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "review-agent",
            "prompt": """Review against TDD:

```typescript
interface UserService {
  createUser(email: string, name: string): Promise<User>;
}
```

Git diff shows implementation. Verify compliance.
"""
        }
    }

    ok, reason = run_validation_hook(tool_call)
    assert ok, f"Small snippet should pass, got: {reason}"
    print("  [PASS] Small snippet allowed")


def test_phase_a_reference():
    """Test 5: Reference to Phase A should block."""
    print("Test 5: Phase A reference...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "review-agent",
            "prompt": """Phase A implementation is complete.

Review the code for security issues.
"""
        }
    }

    ok, reason = run_validation_hook(tool_call)
    assert not ok, "Should block Phase A reference"
    assert "phase a" in reason.lower(), f"Should mention Phase A, got: {reason}"
    print(f"  [PASS] Blocked: {reason}")


def test_developer_agent_reference():
    """Test 6: Reference to developer agent should block."""
    print("Test 6: Developer agent reference...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "review-agent",
            "prompt": """The developer agent has implemented the feature.

Review the implementation for compliance.
"""
        }
    }

    ok, reason = run_validation_hook(tool_call)
    assert not ok, "Should block developer agent reference"
    assert "developer" in reason.lower() or "implementer" in reason.lower(), f"Should mention developer/implementer, got: {reason}"
    print(f"  [PASS] Blocked: {reason}")


def test_non_review_subagent_allowed():
    """Test 7: Non-review subagent (e.g., web-researcher) should pass without validation."""
    print("Test 7: Non-review subagent...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "web-researcher",
            "prompt": """Research best practices for src/services/UserService.ts implementation.

Include code examples and file paths.
"""
        }
    }

    ok, reason = run_validation_hook(tool_call)
    assert ok, f"Non-review subagent should pass, got: {reason}"
    print("  [PASS] Non-review subagent bypasses validation")


def test_qa_engineer_also_validated():
    """Test 8: QA engineer subagent should also be validated."""
    print("Test 8: QA engineer validation...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "qa-engineer",
            "prompt": """Phase A implementation complete. Write integration tests."""
        }
    }

    ok, reason = run_validation_hook(tool_call)
    assert not ok, "Should block Phase A reference in qa-engineer spawn"
    assert "phase a" in reason.lower(), f"Should mention Phase A, got: {reason}"
    print(f"  [PASS] QA engineer also validated")


def test_test_file_paths_allowed():
    """Test 9: Test file paths should be allowed (not implementation)."""
    print("Test 9: Test file paths...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "review-agent",
            "prompt": """Review the test coverage in src/services/UserService.test.ts.

Check if acceptance criteria are covered.
"""
        }
    }

    ok, reason = run_validation_hook(tool_call)
    assert ok, f"Test file paths should pass, got: {reason}"
    print("  [PASS] Test file paths allowed")


def test_tdd_reviewer_validated():
    """Test 10: tdd-reviewer should be validated — impl context must be blocked."""
    print("Test 10: tdd-reviewer validation...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "tdd-reviewer",
            "prompt": """Phase A implementation is complete. Review the TDD for compliance."""
        }
    }

    ok, reason = run_validation_hook(tool_call)
    assert not ok, "Should block Phase A reference in tdd-reviewer spawn"
    assert "phase a" in reason.lower(), f"Should mention Phase A, got: {reason}"
    print(f"  [PASS] tdd-reviewer validated: {reason}")


def test_prd_reviewer_validated():
    """Test 11: prd-reviewer should be validated — impl context must be blocked."""
    print("Test 11: prd-reviewer validation...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "prd-reviewer",
            "prompt": """The developer agent has completed implementation. Review the PRD."""
        }
    }

    ok, reason = run_validation_hook(tool_call)
    assert not ok, "Should block developer agent reference in prd-reviewer spawn"
    assert "developer" in reason.lower() or "implementer" in reason.lower(), f"Got: {reason}"
    print(f"  [PASS] prd-reviewer validated: {reason}")


def test_tdd_reviewer_clean_prompt_allowed():
    """Test 12: Clean tdd-reviewer prompt (TDD + diff only) should pass."""
    print("Test 12: tdd-reviewer clean prompt...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "tdd-reviewer",
            "prompt": """Review the TDD for completeness and PRD traceability.

TDD Section 3 (Interfaces):
- UserService.createUser(email, name): Promise<User>
- Returns: User{id, email, name}

Git Diff:
+++ src/services/UserService.ts
+ export class UserService { ... }

Verify all TDD interfaces are implemented.
"""
        }
    }

    ok, reason = run_validation_hook(tool_call)
    assert ok, f"Clean tdd-reviewer prompt should pass, got: {reason}"
    print("  [PASS] tdd-reviewer clean prompt allowed")


def test_kotlin_impl_path_blocked():
    """Test 13: Kotlin implementation file path should block."""
    print("Test 13: Kotlin impl path...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "review-agent",
            "prompt": "Review the implementation in src/main/UserService.kt for security issues.",
        },
    }

    ok, reason = run_validation_hook(tool_call)
    assert not ok, "Should block Kotlin impl path"
    print(f"  [PASS] Blocked: {reason}")


def test_csharp_impl_path_blocked():
    """Test 14: C# implementation file path should block."""
    print("Test 14: C# impl path...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "review-agent",
            "prompt": "Check src/Services/UserService.cs for OWASP issues.",
        },
    }

    ok, reason = run_validation_hook(tool_call)
    assert not ok, "Should block C# impl path"
    print(f"  [PASS] Blocked: {reason}")


def test_rust_impl_path_blocked():
    """Test 15: Rust implementation file path should block."""
    print("Test 15: Rust impl path...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "review-agent",
            "prompt": "Review the implementation at src/user_service.rs.",
        },
    }

    ok, reason = run_validation_hook(tool_call)
    assert not ok, "Should block Rust impl path"
    print(f"  [PASS] Blocked: {reason}")


def test_swift_impl_path_blocked():
    """Test 16: Swift implementation file path should block."""
    print("Test 16: Swift impl path...")

    tool_call = {
        "name": "Agent",
        "parameters": {
            "subagent_type": "review-agent",
            "prompt": "See src/UserService.swift for the implementation details.",
        },
    }

    ok, reason = run_validation_hook(tool_call)
    assert not ok, "Should block Swift impl path"
    print(f"  [PASS] Blocked: {reason}")


if __name__ == "__main__":
    print("Running pre-spawn validation tests (FIX-019)...\n")

    try:
        test_clean_prompt()
        test_implementation_file_path()
        test_large_code_block()
        test_small_code_snippet_allowed()
        test_phase_a_reference()
        test_developer_agent_reference()
        test_non_review_subagent_allowed()
        test_qa_engineer_also_validated()
        test_test_file_paths_allowed()
        test_tdd_reviewer_validated()
        test_prd_reviewer_validated()
        test_tdd_reviewer_clean_prompt_allowed()
        test_kotlin_impl_path_blocked()
        test_csharp_impl_path_blocked()
        test_rust_impl_path_blocked()
        test_swift_impl_path_blocked()

        print("\n" + "="*60)
        print("[PASS] FIX-019: All pre-spawn validation tests passed")
        print("="*60)

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        raise
