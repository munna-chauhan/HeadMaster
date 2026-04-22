#!/usr/bin/env python3
"""
Jira Operations - Python Implementation
Purpose: Full Jira automation with permission controls
Usage: python3 scripts/jira_ops.py <action> [args...]
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import requests
    import yaml
except ImportError:
    print("[ERROR] Missing dependencies. Install with:")
    print("  pip install requests pyyaml")
    sys.exit(1)



class JiraClient:
    """Jira REST API client with permission controls"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = self._find_config(config_path)
        self.config = self._load_config()
        self._validate_config()
        self._setup_client()

    def _find_config(self, config_path: Optional[str]) -> Path:
        """Find resolved config file"""
        if config_path:
            path = Path(config_path).resolve()
            allowed_base = Path.cwd().resolve()
            try:
                path.relative_to(allowed_base)
            except ValueError:
                raise ValueError(f"Access denied: {config_path} is outside allowed directory")
            if not path.exists():
                raise FileNotFoundError(f"Config not found: {config_path}")
            if not path.is_file():
                raise ValueError(f"Not a file: {config_path}")
            if path.suffix.lower() not in ['.yml', '.yaml']:
                raise ValueError(f"Invalid config file type: {path.suffix}")
            return path

        # Use config.yml (single config file)
        config = Path(__file__).parent.parent / "config.yml"
        if config.exists():
            return config

        raise FileNotFoundError(
            "No config found. Create config.yml with project_key, jira_push, max_loops, parallel."
        )

    def _load_config(self) -> Dict:
        """Load YAML config"""
        with open(self.config_path) as f:
            return yaml.safe_load(f)

    def _validate_config(self):
        """Validate Jira config from flat config.yml structure."""
        # Check jira_push flag (flat key in config.yml)
        if not self.config.get("jira_push", False):
            raise ValueError(
                "Jira push is disabled. Set jira_push: true in config.yml to enable."
            )

        # Load environment variables
        self.domain = os.getenv("ATLASSIAN_DOMAIN")
        self.user = os.getenv("JIRA_USER_EMAIL")
        self.token = os.getenv("JIRA_API_TOKEN")

        if not all([self.domain, self.user, self.token]):
            raise ValueError(
                "Jira credentials not set. Required env vars:\n"
                "  - ATLASSIAN_DOMAIN\n"
                "  - JIRA_USER_EMAIL\n"
                "  - JIRA_API_TOKEN"
            )

        # Load project settings from flat config
        self.project_key = self.config.get("project_key", "")

        # Permissions: all enabled except delete
        self.permissions = {
            "read": True,
            "create": True,
            "update": True,
            "transition": True,
            "delete": False,
        }

        # Custom fields (story points field ID varies by Jira instance)
        self.custom_fields = {
            "story_points": os.getenv("JIRA_STORY_POINTS_FIELD", "customfield_10016"),
            "epic_link": os.getenv("JIRA_EPIC_LINK_FIELD", "customfield_10014"),
        }

        self.workflow = {}

    def _setup_client(self):
        """Setup HTTP client"""
        self.base_url = f"https://{self.domain}/rest/api/3"
        self.agile_base_url = f"https://{self.domain}/rest/agile/1.0"
        auth_string = f"{self.user}:{self.token}"
        auth_bytes = auth_string.encode("utf-8")
        auth_b64 = base64.b64encode(auth_bytes).decode("utf-8")

        self.headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _check_permission(self, operation: str):
        """Check if operation is permitted"""
        if operation not in self.permissions:
            raise ValueError(f"Unknown permission: {operation}")

        if not self.permissions[operation]:
            raise PermissionError(
                f"Operation '{operation}' is disabled in config\n"
                f"Enable in config.yml: jira_push: true"
            )

    def _log(self, level: str, message: str):
        """Log message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = {
            "INFO": "[INFO]",
            "SUCCESS": "[OK]",
            "WARN": "[WARN]",
            "ERROR": "[ERROR]",
        }.get(level, "[LOG]")

        print(f"{prefix} {message}")

    def _request(
            self,
            method: str,
            endpoint: str,
            data: Optional[Dict] = None,
            params: Optional[Dict] = None,
            max_retries: int = 3,
            use_agile_api: bool = False,
    ) -> Dict:
        """Make API request with retry"""
        base = self.agile_base_url if use_agile_api else self.base_url
        url = f"{base}{endpoint}"

        for attempt in range(max_retries):
            try:
                if method == "GET":
                    response = self.session.get(url, params=params, timeout=30)
                elif method == "POST":
                    response = self.session.post(url, json=data, timeout=30)
                elif method == "PUT":
                    response = self.session.put(url, json=data, timeout=30)
                elif method == "DELETE":
                    response = self.session.delete(url, timeout=30)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                # Handle response
                if response.status_code in [200, 201, 204]:
                    if response.content:
                        return response.json()
                    return {}

                # Handle errors
                if response.status_code == 400:
                    error = response.json() if response.content else {}
                    raise ValueError(f"Bad Request: {error.get('errorMessages', response.text)}")
                elif response.status_code == 401:
                    raise PermissionError("Authentication failed. Check credentials.")
                elif response.status_code == 403:
                    raise PermissionError("Forbidden. Check Jira permissions.")
                elif response.status_code == 404:
                    raise ValueError(f"Not Found: {endpoint}")
                else:
                    if attempt < max_retries - 1:
                        self._log("WARN", f"Request failed (attempt {attempt + 1}/{max_retries}), retrying...")
                        continue
                    response.raise_for_status()

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    self._log("WARN", f"Network error (attempt {attempt + 1}/{max_retries}), retrying...")
                    continue
                raise ConnectionError(f"API request failed: {e}")

        raise ConnectionError("Max retries exceeded")

    # ============================================================================
    # CORE OPERATIONS
    # ============================================================================

    def fetch_issue(self, issue_key: str) -> Dict:
        """Fetch issue details"""
        self._check_permission("read")
        self._log("INFO", f"Fetching issue: {issue_key}")

        data = self._request("GET", f"/issue/{issue_key}", params={"expand": "renderedFields,transitions"})
        self._log("SUCCESS", f"Fetched issue: {issue_key}")
        return data

    def create_issue(
            self,
            summary: str,
            description: str = "",
            issue_type: str = "Story",
            story_points: Optional[int] = None,
            epic_link: Optional[str] = None,
    ) -> Dict:
        """Create new issue"""
        self._check_permission("create")
        self._log("INFO", f"Creating issue: {summary}")

        # Build payload
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "issuetype": {"name": issue_type},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}],
                        }
                    ],
                },
            }
        }

        # Add epic link — must be passed explicitly by caller (per-feature, not global config)
        if epic_link and self.custom_fields.get("epic_link"):
            payload["fields"][self.custom_fields["epic_link"]] = epic_link

        # Add story points
        if story_points is not None and self.custom_fields.get("story_points"):
            payload["fields"][self.custom_fields["story_points"]] = story_points

        data = self._request("POST", "/issue", data=payload)
        issue_key = data.get("key")
        self._log("SUCCESS", f"Created issue: {issue_key}")
        return data

    def update_issue(self, issue_key: str, fields: Dict) -> Dict:
        """Update issue fields"""
        self._check_permission("update")
        self._log("INFO", f"Updating issue: {issue_key}")

        payload = {"fields": fields}
        data = self._request("PUT", f"/issue/{issue_key}", data=payload)
        self._log("SUCCESS", f"Updated issue: {issue_key}")
        return data

    def add_comment(self, issue_key: str, comment_text: str) -> Dict:
        """Add comment to issue"""
        self._check_permission("update")
        self._log("INFO", f"Adding comment to: {issue_key}")

        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment_text}],
                    }
                ],
            }
        }

        data = self._request("POST", f"/issue/{issue_key}/comment", data=payload)
        self._log("SUCCESS", f"Added comment to: {issue_key}")
        return data

    def transition_issue(self, issue_key: str, target_status: str) -> Dict:
        """Transition issue to new status"""
        self._check_permission("transition")
        self._log("INFO", f"Transitioning {issue_key} to: {target_status}")

        # Get available transitions
        transitions_data = self._request("GET", f"/issue/{issue_key}/transitions")
        transitions = transitions_data.get("transitions", [])

        # Find transition ID
        transition_id = None
        for t in transitions:
            if t.get("to", {}).get("name") == target_status:
                transition_id = t.get("id")
                break

        if not transition_id:
            available = [t.get("to", {}).get("name") for t in transitions]
            raise ValueError(
                f"Transition '{target_status}' not available for {issue_key}\n"
                f"Available transitions: {', '.join(available)}"
            )

        payload = {"transition": {"id": transition_id}}
        self._request("POST", f"/issue/{issue_key}/transitions", data=payload)
        self._log("SUCCESS", f"Transitioned {issue_key} to: {target_status}")
        return {}

    def search_issues(self, jql: str, max_results: int = 50, fields: Optional[List[str]] = None) -> List[Dict]:
        """Search issues with JQL"""
        self._check_permission("read")
        self._log("INFO", f"Searching: {jql}")

        params = {
            "jql": jql,
            "maxResults": max_results,
        }

        if fields:
            params["fields"] = ",".join(fields)

        data = self._request("GET", "/search", params=params)
        issues = data.get("issues", [])
        self._log("SUCCESS", f"Found {len(issues)} issues")
        return issues

    def link_issues(self, blocking_key: str, blocked_key: str) -> Dict:
        """Create issue link (blocking relationship)"""
        self._check_permission("update")
        self._log("INFO", f"Linking {blocking_key} blocks {blocked_key}")

        payload = {
            "type": {"name": "Blocks"},
            "inwardIssue": {"key": blocked_key},
            "outwardIssue": {"key": blocking_key},
        }

        data = self._request("POST", "/issueLink", data=payload)
        self._log("SUCCESS", f"Linked issues: {blocking_key} blocks {blocked_key}")
        return data

    # ============================================================================
    # AUTO-TRANSITION (WORKFLOW AUTOMATION)
    # ============================================================================

    def auto_transition(self, issue_key: str, trigger: str) -> Dict:
        """Auto-transition based on trigger event"""
        self._check_permission("transition")
        self._log("INFO", f"Auto-transition {issue_key} based on trigger: {trigger}")

        # Check if auto-transition is enabled
        if not self.workflow.get("auto_transition", False):
            self._log("WARN", "Auto-transition is disabled in config")
            return {}

        # Map trigger to target status
        transitions_map = self.workflow.get("transitions", {})
        trigger_mapping = {
            "build_passed": "code_complete",
            "code_complete": "code_complete",
            "review_approved": "review_approved",
            "qa_passed": "qa_passed",
            "blocked": "blocked",
        }

        config_key = trigger_mapping.get(trigger)
        if not config_key:
            raise ValueError(f"Unknown trigger: {trigger}")

        target_status = transitions_map.get(config_key)
        if not target_status:
            raise ValueError(f"No transition configured for trigger: {trigger}")

        return self.transition_issue(issue_key, target_status)

    # ============================================================================
    # UTILITY OPERATIONS
    # ============================================================================

    def health_check(self) -> bool:
        """Check Jira connectivity"""
        try:
            self._log("INFO", "Running Jira health check...")

            # Test authentication
            data = self._request("GET", "/myself")
            username = data.get("displayName", "Unknown")
            self._log("SUCCESS", f"Authenticated as: {username}")

            # Test project access
            project_data = self._request("GET", f"/project/{self.project_key}")
            project_name = project_data.get("name", "Unknown")
            self._log("SUCCESS", f"Project accessible: {project_name}")

            return True

        except Exception as e:
            self._log("ERROR", f"Health check failed: {e}")
            return False

    def get_issue_summary(self, issue_key: str) -> str:
        """Get brief issue summary"""
        data = self.fetch_issue(issue_key)
        fields = data.get("fields", {})

        summary = fields.get("summary", "")
        status = fields.get("status", {}).get("name", "")
        assignee = fields.get("assignee", {}).get("displayName", "Unassigned")

        return f"{issue_key}: {summary} [{status}] (Assignee: {assignee})"


# ============================================================================
# CLI INTERFACE
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="Jira Operations CLI")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("action", help="Action to perform")
    parser.add_argument("args", nargs="*", help="Action arguments")

    args = parser.parse_args()

    try:
        client = JiraClient(config_path=args.config)

        # Dispatch action
        if args.action == "fetch":
            if not args.args:
                print("Usage: jira_ops.py fetch <issue-key>")
                sys.exit(1)
            result = client.fetch_issue(args.args[0])
            print(json.dumps(result, indent=2))

        elif args.action == "create":
            if not args.args:
                print("Usage: jira_ops.py create <summary> [description] [type] [points]")
                sys.exit(1)
            summary = args.args[0]
            description = args.args[1] if len(args.args) > 1 else ""
            issue_type = args.args[2] if len(args.args) > 2 else "Story"
            points = int(args.args[3]) if len(args.args) > 3 else None
            result = client.create_issue(summary, description, issue_type, points)
            print(json.dumps(result, indent=2))

        elif args.action == "comment":
            if len(args.args) < 2:
                print("Usage: jira_ops.py comment <issue-key> <comment-text>")
                sys.exit(1)
            result = client.add_comment(args.args[0], args.args[1])
            print(json.dumps(result, indent=2))

        elif args.action == "transition":
            if len(args.args) < 2:
                print("Usage: jira_ops.py transition <issue-key> <target-status>")
                sys.exit(1)
            result = client.transition_issue(args.args[0], args.args[1])
            print("Transition successful")

        elif args.action == "search":
            if not args.args:
                print("Usage: jira_ops.py search <jql> [max-results]")
                sys.exit(1)
            jql = args.args[0]
            max_results = int(args.args[1]) if len(args.args) > 1 else 50
            results = client.search_issues(jql, max_results)
            print(json.dumps(results, indent=2))

        elif args.action == "link":
            if len(args.args) < 2:
                print("Usage: jira_ops.py link <blocking-key> <blocked-key>")
                sys.exit(1)
            result = client.link_issues(args.args[0], args.args[1])
            print("Issues linked successfully")

        elif args.action == "auto-transition":
            if len(args.args) < 2:
                print("Usage: jira_ops.py auto-transition <issue-key> <trigger>")
                sys.exit(1)
            result = client.auto_transition(args.args[0], args.args[1])
            print("Auto-transition successful")

        elif args.action == "health":
            client.health_check()

        elif args.action == "summary":
            if not args.args:
                print("Usage: jira_ops.py summary <issue-key>")
                sys.exit(1)
            summary = client.get_issue_summary(args.args[0])
            print(summary)

        else:
            print(f"Unknown action: {args.action}")
            print("\nAvailable actions:")
            print("  fetch <issue-key>")
            print("  create <summary> [description] [type] [points]")
            print("  comment <issue-key> <text>")
            print("  transition <issue-key> <status>")
            print("  search <jql> [max-results]")
            print("  link <blocking-key> <blocked-key>")
            print("  auto-transition <issue-key> <trigger>")
            print("  health")
            print("  summary <issue-key>")
            sys.exit(1)

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
