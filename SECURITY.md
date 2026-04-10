# Security Policy

## Reporting a Vulnerability

Please report suspected vulnerabilities privately.

1. Use GitHub Private Vulnerability Reporting:
   - https://github.com/NightHawkATL/ntp-dashboard/security/advisories/new
2. Include as much detail as possible so the issue can be reproduced quickly:
   - A clear description of the vulnerability
   - Affected versions, tags, or commit SHAs
   - Reproduction steps or proof-of-concept
   - Impact assessment (what an attacker could do)
   - Suggested remediation (if available)

If private reporting is unavailable for any reason, open a minimal public issue asking for a secure contact path and avoid posting exploit details publicly.

## Please Do Not

- Do not open public issues with exploit details before a fix is available.
- Do not run disruptive tests against systems you do not own or have explicit permission to test.

## What to Expect

- Initial triage acknowledgment target: within 7 days
- Follow-up after validation: severity and remediation plan will be shared when confirmed
- Coordinated disclosure: we will aim to publish a fix before full public details

Response times may vary based on maintainer availability.

## Supported Versions

Security fixes are primarily targeted to:

- The latest release
- The staging branch (pre-update-release)
- The default branch (main)

Older releases may not receive backported fixes.

Security remediations may be applied to pre-update-release before they are merged into main and included in a release.

## Scope

This policy applies to this repository and its published container images.
