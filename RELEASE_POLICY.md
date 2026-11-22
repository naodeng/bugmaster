# BugMaster Release Policy (Q14–Q16)

**State:** Design approved; not implemented. **Q14=A:** one complete v0.1 MVP; no partial public MVP.

**Scope:** 11 canonical Skills, 16 Patterns, 50 benchmark scenarios, Codex + Claude Code verified core paths, API + Browser Basic, evidence/Oracle/approval, Safe Resume, Finding + Evidence Bundle, regression recommendations only, and quality governance.

**PR scans and merge:** Q15=D, amended by the project owner on 2026-11-22. Codex runs a code scan for every PR and a security scan for R2/R3 changes. The project owner reviews the results and merges manually. No independent human Q15 review or signature is required; do not auto-merge. If later evidence suggests this decision creates a material problem, Codex explains the evidence and impact, then discusses it with the owner or asks the owner to choose.

**Release approval:** Q16=B. Release Initiator and Independent Release Reviewer must be two different authenticated humans. Release approval binds to one immutable release manifest digest and exact source commit, tested artifacts, benchmark digest, and evidence runs. A changed artifact or source invalidates approval.

**GitHub enforcement (to be configured and tested):** Protected `release-production` Environment with Required reviewers and Prevent self-review, no admin bypass where supported, protected `main` and `v*` tags, immutable releases if available; least-privilege build and publish jobs, SHA-pinned Actions and artifact provenance attestations.

**No-Go:** Any missing full MVP acceptance, failed safety/evidence/recovery/host gate, missing required Q15 scan evidence, unavailable second Q16 release approver, unreliable provenance, or unverified tag/release protections. No discretionary override of critical safety gates. Q15 scans and owner merge do not replace Q16 release authorization.

**Rollback:** Publish a new corrected release/advisory rather than mutating immutable released artifacts. Preserve `.bugmaster/` user data; incompatible older writers must operate read-only or refuse writes.

**Normative details:** `docs/en/09-release-authorization.md`, `docs/zh-CN/09-release-authorization.md`, and `docs/development/ADR-016-two-person-release-authorization.md`.
