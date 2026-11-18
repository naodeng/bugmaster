[中文版](../zh-CN/07-release.md)

# MVP / v1.0 Roadmap, Gates and Rollback

## One full MVP release (Q14=A)

MVP v0.1 is a complete-scope target: 11 Skills, 16 Patterns, 50 cases, both host validation, API + Browser Basic, evidence/approval/session persistence, reporting/regression recommendations, and release gates. VS-01 is a developer integration checkpoint only.

## Candidate Go/No-Go

1. Zero failing required static/contract/safety fixture tests.
2. Every published Skill can be installed alone with required Pattern closure; packaged assets match manifest digests.
3. Every stable/verified Pattern has expected provenance and positive/negative Eval; candidates visibly labeled.
4. Correct and faulty Order Demo fixtures both verified by independent reference tests.
5. At least one real API and one real Browser finding workflow is exercised; no fabricated execution accepted.
6. Q7 E3 confirmation and review gate, Q8 filesystem crash recovery, Q13 unknown-outcome safe resume pass.
7. Codex and Claude Code compatibility claims backed by actual run IDs; no silent downgrade.
8. 50-case eval report and G0–G3 comparisons exist; provisional discovery thresholds calibrated and signed off.
9. Human release approval, immutable source commit, checksums, license and attribution checks, English and Chinese docs complete.
10. Rollback rehearsal preserves `.bugmaster/` records and refuses incompatible data writes.

A critical blocker means No-Go; do not quietly ship a reduced MVP against Q14. Escalate a revised decision if scope/time/resources are incompatible.

## Later versions (subject to later decisions)

v0.2 concurrency and data integrity; v0.3 richer browser exploration; v0.4 pattern contribution quality; v0.5 reproduction refinements; v0.6 PR change-risk discovery; v0.7 AI/RAG/agent systems; v0.8 broader host/model comparison; v0.9 optional data exchange; v1.0 stable public contracts and maturity benchmarks. None silently overrides Q9's recommendation-only rule.

## Rollback

Disable unsafe adapter or release, restore last known good verified bundle and compatible schemas; preserve user sessions, findings and evidence. Never assume downgrading a file schema is reversible. If old software cannot read new data, open read-only or refuse writes. Record advisory and rebuild release from pinned commit.
