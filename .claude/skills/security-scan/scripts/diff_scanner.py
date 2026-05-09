#!/usr/bin/env python
"""
diff_scanner.py — scan git diff for secrets, SAST issues, vulnerable deps,
IaC misconfigs, license violations, and missing auth on routes.

Usage:
    python scripts/diff_scanner.py --branch story/KEY --base feature/slug --repo /path/to/repo
    python scripts/diff_scanner.py --staged --repo /path/to/repo

Output: JSON to stdout
{
  "verdict": "PASS" | "BLOCKED" | "WARNING",
  "secrets": [...],
  "sast": [...],
  "deps": [...],
  "iac": {...},
  "licenses": {...},
  "auth": {...},
  "changed_files": [...],
  "summary": "one line"
}
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Add repo root to path so scripts.secret_scanner is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from scripts.secret_scanner import scan_file


def run(cmd: list[str], cwd: str = None) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=cwd)
        return r.returncode, r.stdout, r.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return 1, "", str(e)


def get_changed_files(branch: str, base: str, repo: str, staged: bool) -> list[str]:
    if staged:
        _, out, _ = run(["git", "diff", "--cached", "--name-only"], cwd=repo)
    else:
        _, out, _ = run(["git", "diff", "--name-only", f"{base}...{branch}"], cwd=repo)
    return [f.strip() for f in out.splitlines() if f.strip()]


def scan_secrets(files: list[str], repo: str) -> list[dict]:
    findings = []
    for f in files:
        full = str(Path(repo) / f)
        for finding in scan_file(full):
            findings.append({
                "file": f,
                "line": finding.line_num,
                "pattern": finding.pattern_name,
                "snippet": finding.snippet,
            })
    return findings


def _tool_available(name: str) -> bool:
    """Check if a CLI tool is on PATH."""
    import shutil
    return shutil.which(name) is not None


def scan_sast(files: list[str], repo: str) -> list[dict]:
    findings = []
    unavailable = []
    py_files = [f for f in files if f.endswith(".py")]
    js_files = [f for f in files if f.endswith((".js", ".ts", ".jsx", ".tsx"))]

    if py_files:
        if not _tool_available("bandit"):
            unavailable.append(("bandit (pip install bandit) — Python SAST skipped", len(py_files)))
        else:
            code, out, _ = run(["bandit", "-f", "json", "-q"] + py_files, cwd=repo)
            if out.strip():
                try:
                    data = json.loads(out)
                    for r in data.get("results", []):
                        if r.get("issue_severity") in ("HIGH", "MEDIUM"):
                            findings.append({
                                "tool": "bandit",
                                "file": r.get("filename", ""),
                                "line": r.get("line_number", 0),
                                "severity": r.get("issue_severity"),
                                "issue": r.get("issue_text", ""),
                            })
                except json.JSONDecodeError:
                    pass

    if js_files:
        if not _tool_available("npx"):
            unavailable.append(("npx/eslint (install Node.js) — JS/TS SAST skipped", len(js_files)))
        else:
            code, out, _ = run(
                ["npx", "eslint", "--format=json", "--plugin=security"] + js_files,
                cwd=repo
            )
            if out.strip():
                try:
                    for file_result in json.loads(out):
                        for msg in file_result.get("messages", []):
                            if msg.get("severity", 0) >= 2:
                                findings.append({
                                    "tool": "eslint",
                                    "file": file_result.get("filePath", ""),
                                    "line": msg.get("line", 0),
                                    "severity": "HIGH",
                                    "issue": msg.get("message", ""),
                                })
                except json.JSONDecodeError:
                    pass

    # Attach unavailable tool notices as WARNING findings with file count
    for notice, file_count in unavailable:
        findings.append({
            "tool": "unavailable",
            "severity": "WARNING",
            "issue": f"WARNING: SAST tool not found — {file_count} file(s) not scanned. {notice}",
            "file": "",
            "line": 0
        })

    return findings


def scan_deps(files: list[str], repo: str) -> list[dict]:
    findings = []
    unavailable = []
    dep_files = {Path(f).name for f in files}

    if "requirements.txt" in dep_files or "setup.py" in dep_files:
        if not _tool_available("pip-audit"):
            unavailable.append(("pip-audit (pip install pip-audit) — Python dep scan skipped", 1))
        else:
            code, out, _ = run(["pip-audit", "--format=json", "-r", "requirements.txt"], cwd=repo)
            if out.strip():
                try:
                    for vuln in json.loads(out):
                        for v in vuln.get("vulns", []):
                            findings.append({
                                "tool": "pip-audit",
                                "package": vuln.get("name"),
                                "severity": "HIGH",
                                "issue": v.get("id", "") + ": " + v.get("description", "")[:100],
                            })
                except json.JSONDecodeError:
                    pass

    if "package.json" in dep_files:
        if not _tool_available("npm"):
            unavailable.append(("npm (install Node.js) — JS dep scan skipped", 1))
        else:
            code, out, _ = run(["npm", "audit", "--json"], cwd=repo)
            if out.strip():
                try:
                    data = json.loads(out)
                    vulns = data.get("vulnerabilities", {})
                    for name, info in vulns.items():
                        sev = info.get("severity", "").upper()
                        if sev in ("CRITICAL", "HIGH"):
                            findings.append({
                                "tool": "npm-audit",
                                "package": name,
                                "severity": sev,
                                "issue": info.get("title", ""),
                            })
                except json.JSONDecodeError:
                    pass

    if "pom.xml" in dep_files or "build.gradle" in dep_files:
        if not _tool_available("mvn"):
            unavailable.append(("mvn/owasp-dependency-check (install Maven) — Java dep scan skipped", 1))
        else:
            code, out, _ = run(
                ["mvn", "-q", "org.owasp:dependency-check-maven:check",
                 "-DfailBuildOnCVSS=7", "-Dformat=JSON"],
                cwd=repo
            )
            report = Path(repo) / "target" / "dependency-check-report.json"
            if report.exists():
                try:
                    data = json.loads(report.read_text())
                    for dep in data.get("dependencies", []):
                        for vuln in dep.get("vulnerabilities", []):
                            if vuln.get("cvssv3", {}).get("baseScore", 0) >= 7:
                                findings.append({
                                    "tool": "owasp-dc",
                                    "package": dep.get("fileName", ""),
                                    "severity": "HIGH",
                                    "issue": vuln.get("name", "") + " CVSS:" + str(
                                        vuln.get("cvssv3", {}).get("baseScore")),
                                })
                except (json.JSONDecodeError, Exception):
                    pass

    for notice, file_count in unavailable:
        findings.append({
            "tool": "unavailable",
            "severity": "WARNING",
            "issue": f"WARNING: Dependency scan tool not found — {file_count} file(s) not scanned. {notice}",
            "package": ""
        })

    return findings


def get_diff_text(branch: str, base: str, repo: str, staged: bool) -> str:
    if staged:
        _, out, _ = run(["git", "diff", "--cached"], cwd=repo)
    else:
        _, out, _ = run(["git", "diff", f"{base}...{branch}"], cwd=repo)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# IaC scan
# ─────────────────────────────────────────────────────────────────────────────

def _is_iac_file(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith(".tf"):
        return True
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    if name.endswith((".yaml", ".yml")):
        return "kind:" in text or "AWSTemplateFormatVersion" in text
    if name.endswith(".json"):
        return "AWSTemplateFormatVersion" in text
    return False


def scan_iac(diff_files: list, repo_root: str) -> dict:
    result = {"findings": [], "skipped_reason": None, "files_scanned": 0}
    candidates = []
    for f in diff_files:
        if not f.endswith((".tf", ".yaml", ".yml", ".json")):
            continue
        full = Path(repo_root) / f
        if full.exists() and _is_iac_file(full):
            candidates.append(f)

    if not candidates:
        result["skipped_reason"] = "no IaC files in diff"
        return result

    tool = None
    for name in ("checkov", "tfsec"):
        if _tool_available(name):
            tool = name
            break
    if tool is None:
        result["skipped_reason"] = "no IaC tool available"
        return result

    for f in candidates:
        result["files_scanned"] += 1
        if tool == "checkov":
            _, out, _ = run(["checkov", "-f", f, "-o", "json", "--quiet"], cwd=repo_root)
            if not out.strip():
                continue
            try:
                data = json.loads(out)
                checks = []
                if isinstance(data, list):
                    for entry in data:
                        checks.extend(entry.get("results", {}).get("failed_checks", []))
                else:
                    checks = data.get("results", {}).get("failed_checks", [])
                for c in checks:
                    sev = (c.get("severity") or "MEDIUM").upper()
                    line = c.get("file_line_range", [0, 0])
                    result["findings"].append({
                        "file": f,
                        "line": line[0] if line else 0,
                        "rule": c.get("check_id", ""),
                        "severity": sev,
                        "message": c.get("check_name", ""),
                        "tool": "checkov",
                    })
            except json.JSONDecodeError:
                pass
        else:  # tfsec
            _, out, _ = run(["tfsec", f, "--format", "json"], cwd=repo_root)
            if not out.strip():
                continue
            try:
                data = json.loads(out)
                for r in data.get("results", []):
                    sev = (r.get("severity") or "MEDIUM").upper()
                    if sev == "ERROR":
                        sev = "HIGH"
                    result["findings"].append({
                        "file": f,
                        "line": r.get("location", {}).get("start_line", 0),
                        "rule": r.get("rule_id", ""),
                        "severity": sev,
                        "message": r.get("description", ""),
                        "tool": "tfsec",
                    })
            except json.JSONDecodeError:
                pass

    return result


# ─────────────────────────────────────────────────────────────────────────────
# License scan
# ─────────────────────────────────────────────────────────────────────────────

LICENSE_BLOCKED = {"GPL-2.0", "GPL-3.0", "AGPL-3.0", "SSPL-1.0"}
LICENSE_WARNING = {"LGPL-2.0", "LGPL-2.1", "LGPL-3.0", "EUPL-1.2"}
LICENSE_OK = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MPL-2.0", "CC0-1.0"}


def _classify_license(license_str: str) -> str:
    if not license_str:
        return "WARNING"
    ls = license_str.strip()
    up = ls.upper()
    for b in LICENSE_BLOCKED:
        if b.upper() in up:
            return "BLOCKED"
    for w in LICENSE_WARNING:
        if w.upper() in up:
            return "WARNING"
    for o in LICENSE_OK:
        if o.upper() in up:
            return "OK"
    return "WARNING"


def _added_py_deps(diff_text: str) -> list:
    pkgs = []
    for line in diff_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:].strip()
        if not body or body.startswith("#"):
            continue
        # requirements.txt style: pkg==1.0 or pkg>=1.0 or bare pkg
        import re
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*([=<>!~]=?\s*([A-Za-z0-9_.\-]+))?", body)
        if m and ("==" in body or ">=" in body or "<=" in body or
                  re.match(r"^[A-Za-z0-9_.\-]+$", body)):
            name = m.group(1)
            ver = m.group(3) or ""
            if name.lower() not in ("name", "version", "dependencies"):
                pkgs.append((name, ver))
    return pkgs


def _added_npm_deps(diff_text: str) -> list:
    pkgs = []
    import re
    in_deps = False
    for line in diff_text.splitlines():
        if '"dependencies"' in line or '"devDependencies"' in line:
            in_deps = True
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:].strip().rstrip(",")
        m = re.match(r'"([^"]+)"\s*:\s*"([^"]+)"', body)
        if m and in_deps:
            pkgs.append((m.group(1), m.group(2).lstrip("^~")))
    return pkgs


def _added_go_deps(diff_text: str) -> list:
    pkgs = []
    import re
    for line in diff_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:].strip()
        m = re.match(r"^([a-zA-Z0-9_./\-]+)\s+(v[0-9][^\s]*)", body)
        if m:
            pkgs.append((m.group(1), m.group(2)))
    return pkgs


def _pypi_license(pkg: str) -> str:
    import urllib.request
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=5) as r:
            data = json.loads(r.read())
        info = data.get("info", {})
        lic = info.get("license") or ""
        if not lic:
            for cls in info.get("classifiers", []):
                if cls.startswith("License ::"):
                    lic = cls.split("::")[-1].strip()
                    break
        return lic
    except Exception:
        return ""


def _npm_license(pkg: str) -> str:
    import urllib.request, urllib.parse
    try:
        url = f"https://registry.npmjs.org/{urllib.parse.quote(pkg, safe='/@')}/latest"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        lic = data.get("license") or ""
        if isinstance(lic, dict):
            lic = lic.get("type", "")
        return lic
    except Exception:
        return ""


def scan_licenses(diff_text: str, repo_root: str) -> dict:
    result = {"findings": [], "skipped_reason": None, "packages_checked": 0}

    # Detect which dep files changed by scanning diff header lines
    py_changed = False
    npm_changed = False
    go_changed = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git") or line.startswith("+++"):
            low = line.lower()
            if "requirements.txt" in low or "pyproject.toml" in low:
                py_changed = True
            if "package.json" in low:
                npm_changed = True
            if "go.mod" in low:
                go_changed = True

    if not (py_changed or npm_changed or go_changed):
        result["skipped_reason"] = "no dep file changes in diff"
        return result

    pkgs = []  # (name, version, ecosystem)
    if py_changed:
        for n, v in _added_py_deps(diff_text):
            pkgs.append((n, v, "py"))
    if npm_changed:
        for n, v in _added_npm_deps(diff_text):
            pkgs.append((n, v, "npm"))
    if go_changed:
        for n, v in _added_go_deps(diff_text):
            pkgs.append((n, v, "go"))

    if not pkgs:
        result["skipped_reason"] = "no new packages added"
        return result

    any_success = False
    for name, ver, eco in pkgs:
        lic = ""
        source = ""
        if eco == "py":
            if _tool_available("pip-licenses"):
                _, out, _ = run(["pip-licenses", "--format=json", "--packages", name], cwd=repo_root)
                try:
                    data = json.loads(out)
                    if data:
                        lic = data[0].get("License", "")
                        source = "pip-licenses"
                except (json.JSONDecodeError, IndexError):
                    pass
            if not lic:
                lic = _pypi_license(name)
                if lic:
                    source = "pypi-api"
        elif eco == "npm":
            lic = _npm_license(name)
            if lic:
                source = "npmjs-api"
        elif eco == "go":
            # No easy offline lookup; note as unknown
            source = "unavailable"

        if lic:
            any_success = True
        verdict = _classify_license(lic)
        result["packages_checked"] += 1
        result["findings"].append({
            "package": name,
            "version": ver,
            "license": lic or "UNKNOWN",
            "verdict": verdict,
            "source": source or "unavailable",
        })

    if not any_success and result["packages_checked"] == 0:
        result["skipped_reason"] = "license check tools unavailable"

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Auth-route scan
# ─────────────────────────────────────────────────────────────────────────────

def _detect_framework(repo_root: str) -> str:
    root = Path(repo_root)
    reqs = root / "requirements.txt"
    pyproj = root / "pyproject.toml"
    pkgjson = root / "package.json"
    pom = root / "pom.xml"
    gemfile = root / "Gemfile"
    gomod = root / "go.mod"
    manage = root / "manage.py"

    py_text = ""
    for p in (reqs, pyproj):
        if p.exists():
            try:
                py_text += p.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                pass
    if manage.exists() or "django" in py_text:
        return "django"
    if "fastapi" in py_text:
        return "fastapi"
    if pom.exists():
        try:
            if "spring-boot" in pom.read_text(encoding="utf-8", errors="ignore").lower():
                return "spring"
        except Exception:
            pass
    if pkgjson.exists():
        try:
            if "express" in pkgjson.read_text(encoding="utf-8", errors="ignore").lower():
                return "express"
        except Exception:
            pass
    if gemfile.exists():
        try:
            if "rails" in gemfile.read_text(encoding="utf-8", errors="ignore").lower():
                return "rails"
        except Exception:
            pass
    if gomod.exists():
        try:
            text = gomod.read_text(encoding="utf-8", errors="ignore").lower()
            if "gin-gonic/gin" in text or "labstack/echo" in text or "gofiber/fiber" in text:
                return "go-http"
        except Exception:
            pass
    return ""


def _iter_diff_hunks(diff_text: str):
    """Yield (file, hunk_start_line, added_lines, removed_lines) per hunk."""
    import re
    current_file = None
    hunk_start = 0
    added = []
    removed = []

    def flush():
        if current_file is not None and (added or removed):
            yield_val = (current_file, hunk_start, added[:], removed[:])
            return yield_val
        return None

    results = []
    added = []
    removed = []
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            # Flush previous
            if current_file is not None and (added or removed):
                results.append((current_file, hunk_start, added[:], removed[:]))
            current_file = line[6:].strip()
            added = []
            removed = []
            hunk_start = 0
        elif line.startswith("@@"):
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if current_file is not None and (added or removed):
                results.append((current_file, hunk_start, added[:], removed[:]))
                added = []
                removed = []
            if m:
                hunk_start = int(m.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])
    if current_file is not None and (added or removed):
        results.append((current_file, hunk_start, added[:], removed[:]))
    return results


FRAMEWORK_CONFIG = {
    "django": {
        "auth_markers": ["@login_required", "@permission_required", "@user_passes_test"],
        "route_markers": [r"def\s+\w+\s*\([^)]*request", r"class\s+\w+\(.*View.*\)"],
        "extensions": (".py",),
    },
    "fastapi": {
        "auth_markers": ["Depends(", "Security("],
        "route_markers": [r"@\w+\.(get|post|put|delete|patch|options|head)\("],
        "extensions": (".py",),
    },
    "spring": {
        "auth_markers": ["@PreAuthorize", "@Secured", "@RolesAllowed"],
        "route_markers": [r"@(RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)"],
        "extensions": (".java", ".kt"),
    },
    "express": {
        "auth_markers": ["authMiddleware", "authenticate", "passport.authenticate", "requireAuth"],
        "route_markers": [r"(app|router)\.(get|post|put|delete|patch|use)\s*\("],
        "extensions": (".js", ".ts", ".mjs"),
    },
    "rails": {
        "auth_markers": ["before_action :authenticate_user!", "before_action :require_login", "before_action :authenticate"],
        "route_markers": [r"def\s+\w+"],
        "extensions": (".rb",),
    },
    "go-http": {
        "auth_markers": ["AuthRequired", "JWTMiddleware", "middleware.Auth"],
        "route_markers": [r"\.(GET|POST|PUT|DELETE|PATCH|Handle)\("],
        "extensions": (".go",),
    },
}


def _has_marker(lines: list, markers: list) -> bool:
    blob = "\n".join(lines)
    return any(m in blob for m in markers)


def scan_auth_routes(diff_text: str, tech_stack=None, repo_root: str = ".") -> dict:
    import re
    result = {
        "findings": [],
        "framework_detected": None,
        "skipped_reason": None,
        "routes_checked": 0,
    }

    fw = tech_stack or _detect_framework(repo_root)
    result["framework_detected"] = fw or None

    if not diff_text.strip():
        result["skipped_reason"] = "empty diff"
        return result

    hunks = _iter_diff_hunks(diff_text)
    if not hunks:
        result["skipped_reason"] = "no hunks parsed"
        return result

    if fw and fw in FRAMEWORK_CONFIG:
        cfg = FRAMEWORK_CONFIG[fw]
        route_res = [re.compile(p) for p in cfg["route_markers"]]
        exts = cfg["extensions"]
        auth_markers = cfg["auth_markers"]

        for file, start_line, added, removed in hunks:
            if not file.endswith(exts):
                continue

            # Check for auth decorators/middleware removed
            added_blob = "\n".join(added)
            removed_blob = "\n".join(removed)
            for marker in auth_markers:
                if marker in removed_blob and marker not in added_blob:
                    result["findings"].append({
                        "file": file,
                        "line": start_line,
                        "route": marker,
                        "issue": f"auth marker removed: {marker}",
                        "severity": "BLOCKED",
                        "framework": fw,
                        "confidence": "high",
                    })

            # Check new routes for missing auth
            for idx, line in enumerate(added):
                for rx in route_res:
                    if rx.search(line):
                        result["routes_checked"] += 1
                        # Look within ±10 added lines for auth markers
                        window_start = max(0, idx - 10)
                        window_end = min(len(added), idx + 11)
                        window = added[window_start:window_end]
                        if not _has_marker(window, auth_markers):
                            result["findings"].append({
                                "file": file,
                                "line": start_line + idx,
                                "route": line.strip()[:120],
                                "issue": "new route without auth marker",
                                "severity": "WARNING",
                                "framework": fw,
                                "confidence": "high",
                            })
                        break
    else:
        # Unknown framework — generic heuristic
        generic_route = re.compile(r"(def|function|func)\s+(handle\w*|Handle\w*|\w*Controller\w*|\w*Route\w*)")
        generic_auth = re.compile(r"(auth|Auth|login|Login|jwt|JWT|token|Token|permission|Permission)")
        for file, start_line, added, _removed in hunks:
            for idx, line in enumerate(added):
                if generic_route.search(line):
                    result["routes_checked"] += 1
                    window = added[max(0, idx - 10):idx + 11]
                    if not any(generic_auth.search(w) for w in window):
                        result["findings"].append({
                            "file": file,
                            "line": start_line + idx,
                            "route": line.strip()[:120],
                            "issue": "framework-unknown — manual review recommended",
                            "severity": "WARNING",
                            "framework": "unknown",
                            "confidence": "low",
                        })

    return result


def get_all_files(repo: str) -> list[str]:
    """Get all tracked files in repo for full scan mode."""
    _, out, _ = run(["git", "ls-files"], cwd=repo)
    return [f.strip() for f in out.splitlines() if f.strip()]


def get_full_diff_text(repo: str) -> str:
    """Get full file contents as pseudo-diff for license/auth scanning in full mode."""
    _, out, _ = run(["git", "diff", "--no-index", "/dev/null", "."], cwd=repo)
    if not out:
        # Fallback: read all tracked files and format as added lines
        files = get_all_files(repo)
        lines = []
        for f in files:
            full = Path(repo) / f
            if full.exists() and full.stat().st_size < 500_000:
                try:
                    content = full.read_text(encoding="utf-8", errors="ignore")
                    lines.append(f"+++ b/{f}")
                    for line in content.splitlines():
                        lines.append(f"+{line}")
                except Exception:
                    pass
        out = "\n".join(lines)
    return out


def main():
    parser = argparse.ArgumentParser(description="Scan git diff or full repo for security issues")
    parser.add_argument("--branch", help="Story branch")
    parser.add_argument("--base", help="Base branch")
    parser.add_argument("--repo", required=True, help="Repo path")
    parser.add_argument("--staged", action="store_true", help="Scan staged files")
    parser.add_argument("--full", action="store_true", help="Scan all tracked files in repo")
    parser.add_argument("--deps-only", action="store_true", help="Run dependency audit only")
    parser.add_argument("--iac-only", action="store_true", help="Run IaC scan only")
    args = parser.parse_args()

    if not args.full and not args.staged and not (args.branch and args.base):
        print(json.dumps({"verdict": "ERROR", "summary": "--branch/--base, --staged, or --full required"}))
        sys.exit(1)

    repo = str(Path(args.repo).resolve())

    # Determine file list based on mode
    if args.full:
        changed = get_all_files(repo)
    else:
        changed = get_changed_files(args.branch, args.base, repo, args.staged)

    if not changed:
        print(json.dumps({
            "verdict": "PASS",
            "secrets": [], "sast": [], "deps": [],
            "changed_files": [],
            "summary": "No files to scan"
        }))
        sys.exit(0)

    # Focused modes
    if args.deps_only:
        deps = scan_deps(changed, repo)
        diff_text = get_full_diff_text(repo) if args.full else get_diff_text(args.branch, args.base, repo, args.staged)
        licenses = scan_licenses(diff_text, repo)
        real_deps = [d for d in deps if d.get("severity") != "WARNING"]
        if any(d.get("severity") == "CRITICAL" for d in real_deps) or any(f.get("verdict") == "BLOCKED" for f in licenses["findings"]):
            verdict = "BLOCKED"
        elif any(d.get("severity") == "HIGH" for d in real_deps) or any(f.get("verdict") == "WARNING" for f in licenses["findings"]):
            verdict = "WARNING"
        else:
            verdict = "PASS"
        print(json.dumps({"verdict": verdict, "deps": deps, "licenses": licenses, "changed_files": changed, "summary": f"{verdict}: {len(real_deps)} dep issues, {len(licenses['findings'])} licenses"}, indent=2))
        sys.exit(0 if verdict in ("PASS", "WARNING") else 1)

    if args.iac_only:
        iac = scan_iac(changed, repo)
        iac_critical = any(f.get("severity") == "CRITICAL" for f in iac["findings"])
        iac_high = any(f.get("severity") == "HIGH" for f in iac["findings"])
        verdict = "BLOCKED" if iac_critical else "WARNING" if iac_high else "PASS"
        print(json.dumps({"verdict": verdict, "iac": iac, "changed_files": changed, "summary": f"{verdict}: {len(iac['findings'])} IaC findings"}, indent=2))
        sys.exit(0 if verdict in ("PASS", "WARNING") else 1)

    # Full scan — all checks
    secrets = scan_secrets(changed, repo)
    sast = scan_sast(changed, repo)
    deps = scan_deps(changed, repo)
    if args.full:
        diff_text = get_full_diff_text(repo)
    else:
        diff_text = get_diff_text(args.branch, args.base, repo, args.staged)
    iac = scan_iac(changed, repo)
    licenses = scan_licenses(diff_text, repo)
    auth = scan_auth_routes(diff_text, tech_stack=None, repo_root=repo)

    # Determine verdict — WARNING findings (unavailable tools) never affect verdict
    real_secrets = secrets
    real_sast = [s for s in sast if s.get("severity") != "WARNING"]
    real_deps = [d for d in deps if d.get("severity") != "WARNING"]
    warning_notices = (
            [s["issue"] for s in sast if s.get("severity") == "WARNING"] +
            [d["issue"] for d in deps if d.get("severity") == "WARNING"]
    )

    iac_critical = any(f.get("severity") == "CRITICAL" for f in iac["findings"])
    iac_high = any(f.get("severity") == "HIGH" for f in iac["findings"])
    lic_blocked = any(f.get("verdict") == "BLOCKED" for f in licenses["findings"])
    lic_warning = any(f.get("verdict") == "WARNING" for f in licenses["findings"])
    auth_blocked = any(f.get("severity") == "BLOCKED" for f in auth["findings"])
    auth_warning = any(f.get("severity") == "WARNING" for f in auth["findings"])

    if (real_secrets or any(d.get("severity") == "CRITICAL" for d in real_deps)
            or iac_critical or lic_blocked or auth_blocked):
        verdict = "BLOCKED"
    elif (any(s.get("severity") == "HIGH" for s in real_sast)
          or any(d.get("severity") == "HIGH" for d in real_deps)
          or iac_high or lic_warning or auth_warning):
        verdict = "WARNING"
    else:
        verdict = "PASS"

    summary = (
        f"{verdict}: {len(changed)} files, {len(real_secrets)} secrets, "
        f"{len(real_sast)} SAST, {len(real_deps)} dep issues, "
        f"{len(iac['findings'])} IaC, {len(licenses['findings'])} licenses, "
        f"{len(auth['findings'])} auth"
    )
    if warning_notices:
        summary += f" | SKIPPED: {'; '.join(warning_notices)}"

    print(json.dumps({
        "verdict": verdict,
        "secrets": secrets,
        "sast": sast,
        "deps": deps,
        "iac": iac,
        "licenses": licenses,
        "auth": auth,
        "changed_files": changed,
        "summary": summary,
        "tools_unavailable": warning_notices,
    }, indent=2))

    sys.exit(0 if verdict in ("PASS", "WARNING") else 1)


if __name__ == "__main__":
    main()
