# OWASP Top 10 Review Checklist

Every code review checks all 10 categories:

- **A01 Broken Access Control:** Missing RBAC, horizontal privilege escalation, insecure direct object refs
- **A02 Cryptographic Failures:** Hardcoded secrets, weak crypto (MD5/SHA1 for passwords), plaintext in logs
- **A03 Injection:** SQL injection (string concat), command injection, XSS
- **A04 Insecure Design:** Missing input validation, no rate limiting, no defense in depth
- **A05 Security Misconfiguration:** Default credentials, verbose errors, CORS misconfiguration
- **A06 Vulnerable Components:** Outdated dependencies with known CVEs
- **A07 Auth Failures:** Missing authentication, weak passwords, session fixation
- **A08 Software/Data Integrity:** Insecure deserialization, unsigned JWTs, missing integrity
- **A09 Logging Failures:** PII in logs, missing audit trail for auth events
- **A10 SSRF:** User-controlled URLs, unvalidated redirects
