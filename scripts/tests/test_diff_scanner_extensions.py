#!/usr/bin/env python
"""
Unit tests for diff_scanner.py extensions:
  - scan_iac
  - scan_licenses
  - scan_auth_routes
  - main() verdict integration

Run: python -m pytest scripts/tests/test_diff_scanner_extensions.py -v
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / ".claude" / "skills" / "security-scan" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import diff_scanner as ds  # noqa: E402


# ─────────────────────────────────────────────────────────────
# scan_iac
# ─────────────────────────────────────────────────────────────

def test_iac_no_iac_files_in_diff():
    result = ds.scan_iac(["src/app.py", "README.md"], str(ROOT))
    assert result["skipped_reason"] == "no IaC files in diff"
    assert result["findings"] == []
    assert result["files_scanned"] == 0


def test_iac_no_tool_available(tmp_path):
    tf = tmp_path / "main.tf"
    tf.write_text('resource "aws_s3_bucket" "b" {}\n')
    with patch.object(ds, "_tool_available", return_value=False):
        result = ds.scan_iac(["main.tf"], str(tmp_path))
    assert result["skipped_reason"] == "no IaC tool available"
    assert result["findings"] == []


def test_iac_checkov_critical_finding(tmp_path):
    tf = tmp_path / "main.tf"
    tf.write_text('resource "aws_s3_bucket" "b" {}\n')

    checkov_out = json.dumps({
        "results": {
            "failed_checks": [{
                "check_id": "CKV_AWS_19",
                "check_name": "S3 bucket has encryption",
                "severity": "CRITICAL",
                "file_line_range": [1, 1],
            }]
        }
    })

    def fake_tool(name):
        return name == "checkov"

    with patch.object(ds, "_tool_available", side_effect=fake_tool), \
         patch.object(ds, "run", return_value=(0, checkov_out, "")):
        result = ds.scan_iac(["main.tf"], str(tmp_path))

    assert result["files_scanned"] == 1
    assert len(result["findings"]) == 1
    assert result["findings"][0]["severity"] == "CRITICAL"
    assert result["findings"][0]["tool"] == "checkov"


def test_iac_yaml_without_kind_marker_skipped(tmp_path):
    y = tmp_path / "config.yaml"
    y.write_text("name: foo\nvalue: 1\n")
    result = ds.scan_iac(["config.yaml"], str(tmp_path))
    assert result["skipped_reason"] == "no IaC files in diff"


def test_iac_k8s_yaml_detected(tmp_path):
    y = tmp_path / "deploy.yaml"
    y.write_text("apiVersion: v1\nkind: Deployment\nmetadata:\n  name: x\n")
    with patch.object(ds, "_tool_available", return_value=False):
        result = ds.scan_iac(["deploy.yaml"], str(tmp_path))
    assert result["skipped_reason"] == "no IaC tool available"


# ─────────────────────────────────────────────────────────────
# scan_licenses
# ─────────────────────────────────────────────────────────────

def test_licenses_no_dep_file_changes():
    diff = """diff --git a/src/app.py b/src/app.py
+++ b/src/app.py
@@ -1,1 +1,2 @@
+print("hi")
"""
    result = ds.scan_licenses(diff, str(ROOT))
    assert result["skipped_reason"] == "no dep file changes in diff"
    assert result["packages_checked"] == 0


def test_licenses_gpl_blocks(tmp_path):
    diff = """diff --git a/requirements.txt b/requirements.txt
+++ b/requirements.txt
@@ -0,0 +1,1 @@
+somepkg==1.0.0
"""
    with patch.object(ds, "_tool_available", return_value=False), \
         patch.object(ds, "_pypi_license", return_value="GPL-3.0"):
        result = ds.scan_licenses(diff, str(tmp_path))

    assert result["packages_checked"] == 1
    assert result["findings"][0]["verdict"] == "BLOCKED"
    assert result["findings"][0]["license"] == "GPL-3.0"


def test_licenses_mit_ok(tmp_path):
    diff = """diff --git a/requirements.txt b/requirements.txt
+++ b/requirements.txt
@@ -0,0 +1,1 @@
+okpkg==2.0
"""
    with patch.object(ds, "_tool_available", return_value=False), \
         patch.object(ds, "_pypi_license", return_value="MIT"):
        result = ds.scan_licenses(diff, str(tmp_path))
    assert result["findings"][0]["verdict"] == "OK"


def test_licenses_tool_unavailable_gracefully(tmp_path):
    diff = """diff --git a/requirements.txt b/requirements.txt
+++ b/requirements.txt
@@ -0,0 +1,1 @@
+mystery==0.1
"""
    with patch.object(ds, "_tool_available", return_value=False), \
         patch.object(ds, "_pypi_license", return_value=""):
        result = ds.scan_licenses(diff, str(tmp_path))
    # Package still reported, license UNKNOWN, verdict WARNING
    assert result["packages_checked"] == 1
    assert result["findings"][0]["license"] == "UNKNOWN"
    assert result["findings"][0]["verdict"] == "WARNING"


# ─────────────────────────────────────────────────────────────
# scan_auth_routes
# ─────────────────────────────────────────────────────────────

def test_auth_empty_diff():
    result = ds.scan_auth_routes("", tech_stack="django")
    assert result["routes_checked"] == 0
    assert result["findings"] == []
    assert result["skipped_reason"] == "empty diff"


def test_auth_django_new_view_without_login_required():
    diff = """diff --git a/app/views.py b/app/views.py
+++ b/app/views.py
@@ -10,3 +10,6 @@
+def my_view(request):
+    return HttpResponse("hi")
+
"""
    result = ds.scan_auth_routes(diff, tech_stack="django")
    warnings = [f for f in result["findings"] if f["severity"] == "WARNING"]
    assert len(warnings) >= 1
    assert warnings[0]["framework"] == "django"


def test_auth_django_login_required_removed():
    diff = """diff --git a/app/views.py b/app/views.py
+++ b/app/views.py
@@ -10,5 +10,4 @@
-@login_required
 def existing(request):
     return HttpResponse("x")
"""
    result = ds.scan_auth_routes(diff, tech_stack="django")
    blocked = [f for f in result["findings"] if f["severity"] == "BLOCKED"]
    assert len(blocked) >= 1
    assert "@login_required" in blocked[0]["route"]


def test_auth_fastapi_new_route_without_depends():
    diff = """diff --git a/api.py b/api.py
+++ b/api.py
@@ -5,3 +5,6 @@
+@router.get("/items")
+def list_items():
+    return []
"""
    result = ds.scan_auth_routes(diff, tech_stack="fastapi")
    warnings = [f for f in result["findings"] if f["severity"] == "WARNING"]
    assert len(warnings) >= 1


def test_auth_spring_preauthorize_removed():
    diff = """diff --git a/C.java b/C.java
+++ b/C.java
@@ -3,3 +3,2 @@
-    @PreAuthorize("hasRole('ADMIN')")
     @GetMapping("/admin")
     public String admin() { return "x"; }
"""
    result = ds.scan_auth_routes(diff, tech_stack="spring")
    blocked = [f for f in result["findings"] if f["severity"] == "BLOCKED"]
    assert len(blocked) >= 1


def test_auth_unknown_framework_low_confidence():
    diff = """diff --git a/mystery.xyz b/mystery.xyz
+++ b/mystery.xyz
@@ -1,3 +1,6 @@
+def handleRequest():
+    do_stuff()
+    return "ok"
"""
    result = ds.scan_auth_routes(diff, tech_stack="cobol")
    low = [f for f in result["findings"] if f.get("confidence") == "low"]
    assert len(low) >= 1
    assert "framework-unknown" in low[0]["issue"]


# ─────────────────────────────────────────────────────────────
# main() verdict integration
# ─────────────────────────────────────────────────────────────

def _run_main_with_mocks(*, secrets=None, sast=None, deps=None,
                        iac=None, licenses=None, auth=None,
                        changed=None, diff_text=""):
    """Invoke main() with mocks; return parsed JSON from stdout + exit code."""
    import io
    secrets = secrets or []
    sast = sast or []
    deps = deps or []
    iac = iac or {"findings": [], "skipped_reason": None, "files_scanned": 0}
    licenses = licenses or {"findings": [], "skipped_reason": None, "packages_checked": 0}
    auth = auth or {"findings": [], "framework_detected": None,
                    "skipped_reason": None, "routes_checked": 0}
    changed = changed or ["src/x.py"]

    argv = ["diff_scanner", "--branch", "b", "--base", "main", "--repo", str(ROOT)]
    buf = io.StringIO()
    exit_code = None

    with patch.object(sys, "argv", argv), \
         patch.object(ds, "get_changed_files", return_value=changed), \
         patch.object(ds, "get_diff_text", return_value=diff_text), \
         patch.object(ds, "scan_secrets", return_value=secrets), \
         patch.object(ds, "scan_sast", return_value=sast), \
         patch.object(ds, "scan_deps", return_value=deps), \
         patch.object(ds, "scan_iac", return_value=iac), \
         patch.object(ds, "scan_licenses", return_value=licenses), \
         patch.object(ds, "scan_auth_routes", return_value=auth), \
         patch("sys.stdout", buf):
        try:
            ds.main()
        except SystemExit as e:
            exit_code = e.code

    return json.loads(buf.getvalue()), exit_code


def test_main_iac_critical_blocks():
    result, code = _run_main_with_mocks(
        iac={"findings": [{"severity": "CRITICAL", "file": "m.tf", "line": 1,
                           "rule": "X", "message": "bad", "tool": "checkov"}],
             "skipped_reason": None, "files_scanned": 1}
    )
    assert result["verdict"] == "BLOCKED"
    assert code == 1


def test_main_license_blocked_propagates():
    result, code = _run_main_with_mocks(
        licenses={"findings": [{"package": "p", "version": "1", "license": "GPL-3.0",
                                "verdict": "BLOCKED", "source": "pypi-api"}],
                  "skipped_reason": None, "packages_checked": 1}
    )
    assert result["verdict"] == "BLOCKED"


def test_main_auth_blocked_propagates():
    result, code = _run_main_with_mocks(
        auth={"findings": [{"file": "v.py", "line": 1, "route": "x",
                            "issue": "removed", "severity": "BLOCKED",
                            "framework": "django", "confidence": "high"}],
              "framework_detected": "django", "skipped_reason": None,
              "routes_checked": 1}
    )
    assert result["verdict"] == "BLOCKED"


def test_main_warning_only_from_new_scans():
    result, code = _run_main_with_mocks(
        iac={"findings": [{"severity": "HIGH", "file": "m.tf", "line": 1,
                           "rule": "X", "message": "meh", "tool": "checkov"}],
             "skipped_reason": None, "files_scanned": 1}
    )
    assert result["verdict"] == "WARNING"
    assert code == 0
