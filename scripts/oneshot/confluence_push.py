#!/usr/bin/env python3
# LIFETIME: revision-REV-005
# Provenance: .claude/skills/publish-confluence/scripts/confluence_publish.py update
"""Push the staged REV-005 storage XML to Confluence page 7586512902.

Reads the staged body from
  memory/features/pwr/pwr-es9-migration/_confluence-storage-staged.xml
and issues a PUT to /wiki/api/v2/pages/{id} with the current version+1.

Auth: env vars ATLASSIAN_DOMAIN, JIRA_USER_EMAIL, JIRA_API_TOKEN.
"""
import json
import os
import sys
from pathlib import Path

import requests
import urllib3

# Syndigo corporate proxy injects a self-signed root into the TLS chain. This
# script runs on a trusted Syndigo workstation only.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_TLS = False

PAGE_ID = '7586512902'
TITLE = 'Elasticsearch Datagroup API (Control Plane) - v1'
# Fixed: path now resolves from repo root (scripts/oneshot/ is 2 levels deep)
BODY_PATH = Path(__file__).parent.parent.parent / 'memory/features/pwr/pwr-es9-migration/_confluence-storage-staged.xml'


def main() -> int:
    domain = os.environ.get('ATLASSIAN_DOMAIN')
    email = os.environ.get('JIRA_USER_EMAIL')
    token = os.environ.get('JIRA_API_TOKEN')
    if not (domain and email and token):
        print('[ERR] Missing ATLASSIAN_DOMAIN / JIRA_USER_EMAIL / JIRA_API_TOKEN', file=sys.stderr)
        return 2

    body = BODY_PATH.read_text(encoding='utf-8')
    print(f'Body: {len(body):,} chars from {BODY_PATH.name}')

    base = f'https://{domain}'
    auth = (email, token)
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

    r = requests.get(f'{base}/wiki/api/v2/pages/{PAGE_ID}', auth=auth, headers=headers, timeout=30, verify=VERIFY_TLS)
    if r.status_code != 200:
        print(f'[ERR] GET page failed: HTTP {r.status_code}\n{r.text[:500]}', file=sys.stderr)
        return 3
    cur_version = r.json()['version']['number']
    print(f'Current page version: {cur_version}')

    payload = {
        'id': PAGE_ID,
        'status': 'current',
        'title': TITLE,
        'body': {'representation': 'storage', 'value': body},
        'version': {
            'number': cur_version + 1,
            'message': 'TDD design update -- TierShardConfig + ShardDefaults + per-row capacity + docTypeOverrides + property-driven shard target',
        },
    }
    r = requests.put(
        f'{base}/wiki/api/v2/pages/{PAGE_ID}',
        auth=auth, headers=headers, data=json.dumps(payload), timeout=60, verify=VERIFY_TLS,
    )
    if r.status_code not in (200, 204):
        print(f'[ERR] PUT page failed: HTTP {r.status_code}\n{r.text[:1500]}', file=sys.stderr)
        return 4
    result = r.json()
    new_version = result.get('version', {}).get('number')
    web_url = result.get('_links', {}).get('webui')
    print(f'[OK] Updated to v{new_version}: {base}/wiki{web_url}' if web_url else f'[OK] Updated to v{new_version}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
