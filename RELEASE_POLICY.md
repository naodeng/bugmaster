# BugMaster Release Policy (Q14–Q16)

**State:** Design approved; not implemented. **Q14=A:** one complete v0.1 MVP; no partial public MVP.

**Scope:** 11 canonical Skills, 16 Patterns, 50 benchmark scenarios, Codex + Claude Code verified core paths, API + Browser Basic, evidence/Oracle/approval, Safe Resume, Finding + Evidence Bundle, regression recommendations only, and quality governance.

**Code review:** Q15=B. R2 changes require independent quality review; R3 changes require independent security review. AI reviews cannot substitute for human reviews.

**Release approval:** Q16=B. Release Initiator and Independent Release Reviewer must be two different authenticated humans. Release approval binds to one immutable release manifest digest and exact source commit, tested artifacts, benchmark digest, and evidence runs. A changed artifact or source invalidates approval.

**GitHub enforcement (to be configured and tested):** Protected `release-production` Environment with Required reviewers and Prevent self-review, no admin bypass where supported, protected `main` and `v*` tags, immutable releases if available; least-privilege build and publish jobs, SHA-pinned Actions and artifact provenance attestations.

**No-Go:** Any missing full MVP acceptance, failed safety/evidence/recovery/host gate, missing independent Q15 review, unavailable second release approver, unreliable provenance, or unverified tag/release protections. No discretionary override of critical safety gates.

**Rollback:** Publish a new corrected release/advisory rather than mutating immutable released artifacts. Preserve `.bugmaster/` user data; incompatible older writers must operate read-only or refuse writes.

**Normative details:** `docs/en/09-release-authorization.md`, `docs/zh-CN/09-release-authorization.md`, and `docs/development/ADR-016-two-person-release-authorization.md`.
