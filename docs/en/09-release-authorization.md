[中文版](../zh-CN/09-release-authorization.md)

# Q16 — Two-person Release Authorization and Supply-chain Assurance

> ADR-016 · Accepted architecture decision, not implemented · 2026-11-18. Q15 amended to D on 2026-11-22; Q16=B. Q14=A: a single complete MVP release.

## Decision
Q1–Q16: **A,A,B,B,B,B,B,B,A,B,B,B,B,A,D,B**. Q15 requires a Codex code scan for every PR and a security scan for R2/R3 changes; the project owner reviews results and merges manually. No independent human Q15 signature is required. Q16 public release authorization remains separate: the release initiator (RI) and independent release reviewer (IRR) are two distinct real people. Without a second authorized human, publishing is **No-Go**.

## Trust boundaries
- **RI** requests a release candidate from a fixed, reviewed Git SHA and a frozen release-manifest digest.
- **IRR** independently checks the same SHA, artifact digests, full-scope acceptance (11 Skills, 16 Patterns, 50 benchmark cases, Codex and Claude Code), BLK-01..07, W0..W11, Q15 scan evidence, Eval results, rollback rehearsal, and signs off the exact manifest.
- **Codex Q15 scans** cover every PR for code issues and R2/R3 changes for security issues. The project owner reviews the results and merges manually; these scans do not replace Q16 authorization.
- **Publisher** is a least-privilege, protected GitHub Actions job, not an unrestricted human PAT.

## GitHub controls to configure and VERIFY
1. Use a `release-production` Environment with Required reviewers, **Prevent self-review**, no admin bypass where supported, and deployment branch/tag restrictions. Availability of specific protection rules varies by plan and repository visibility.
2. GitHub's required reviewers gate generally requires **one** of the listed reviewers, not unanimous approval. Two-person Q16 is **initiator + different approving reviewer**. Two independent reviewer signatures would require an additional explicit gate.
3. Protect `main` and `v*` tags with Rulesets. Enable **Immutable Releases** if supported; do not re-point tags or overwrite published release assets.
4. Test the actual protections in a disposable repository before any public release. Settings documentation alone does not prove enforcement.

## Build and publish separation
```
Reviewed source SHA -> unprivileged build/test -> reproducible artifacts + hashes + provenance attestation
-> frozen release manifest -> RI requests deployment -> IRR approves same manifest
-> protected publish job re-verifies SHA, signatures and hashes -> protected tag / release
-> download and post-publish verification
```

Fork PR workflows must not get release secrets or write-scoped tokens. Pin actions by full commit SHA; minimize per-job `GITHUB_TOKEN` permissions. Build and test untrusted code outside privileged publish jobs. Prefer OIDC-based GitHub Artifact Attestations, with `gh attestation verify <file> -R <owner/repo>` and verification of expected repository and workflow identity. An attestation is not a human approval or a signed Git tag, and only establishes claimed build provenance—not code correctness.

## Release manifest (minimum)
Record source SHA/tree digest, bundle version, all component versions, benchmark dataset digest, Run IDs, Host compatibility evidence, artifact SHA-256 list, SBOM/dependency manifest, provenance attestations, blocking-spike evidence, Q15 code/security scan records, RI identity, IRR identity, approved manifest digest, publication tag, and post-release verification. Any approved content/metadata change invalidates the approval and requires a new review.

## Go/No-Go
GO only with complete Q14 MVP; W0–W11 acceptance; Q15 code/security scan records and project-owner merge evidence; BLK-01..07 closure; actual API/Browser and dual-host runs; valid Oracle/Evidence, approvals, recovery and safety controls; comparative G0–G3 Eval; reviewed documentation/licenses; verified reproducible release artifacts; two distinct authorized humans; and successful protected publish dry run. Otherwise **No-Go**, including when the project has only one maintainer available.

## Rollback
Do not rewrite immutable released assets or reuse an already-published tag for different bytes. Revoke/disable unsafe capabilities, publish a security advisory and fixed replacement version, and guide users to a previously verified compatible release. Preserve local Finding, Evidence and Session files; incompatible schemas must be read-only or reject writes, not silently downgrade.

## TDD / Eval
The 16 required scenarios `RELAUTH-001..016` defined in the Chinese decision document cover self-review prevention, missing approvals, manifest drift, source/asset mismatch, attestation validation, fork secret isolation, tag protection, missing Q15 scan evidence, immutable release behavior, rollback safety, permissions and re-evaluation. Perform an end-to-end protected-environment dry run using actual GitHub settings. These are planned tests, not results.

## Execution handoff
Q16 closes the non-blocking architecture decision sequence. Begin repository setup, the 27 W0–W11 tasks, risk spikes, TDD and full MVP implementation without splitting the public release.
