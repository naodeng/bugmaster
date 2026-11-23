[中文版](../zh-CN/03-contracts.md)

# Unified Contracts and State Machines

## Source-of-truth table

| Entity | Canonical location | Identity / revision | Rules |
|---|---|---|---|
| Skill | `skills/<name>/SKILL.md` | name + skill version | standalone bundle closes references |
| Pattern | `patterns/<category>/<id>/pattern.json` | stable ID + revision | canonical catalog, provenance, positive/negative Eval |
| Capability | `registry/capabilities.json` | capability ID + registry version | refers to actual Skill/Pattern |
| Feature Inventory | local CLI output | source reference + stable feature ID | declared discovery only; authorization and execution are separate |
| Scope | `.bugmaster/scopes/<id>.json` | scope ID + revision | approval references require trusted gateway verification |
| Approval | Approval record referenced by Scope/Action | approval ID + Scope revision | host-authenticated source event; exact intent binding |
| Action | session journal | session ID + action ID + sequence | write-ahead intent; unknown outcomes never replayed |
| Oracle | `.bugmaster/oracles/<id>/revisions/` | ID + revision + canonical record digest | expected behavior and source fingerprint; source and author remain unauthenticated |
| Evidence | metadata and content-addressed artifacts | EV ID + artifact SHA-256 + Oracle/Journal references | local byte integrity and references are checked; authenticity remains unverified |
| Candidate Assessment | candidate revision's `candidateAssessment` | candidate ID + revision | screening only; never `confirmed`; rejection requires linked counter-evidence |
| Finding | immutable revisions + current pointer | Finding ID + revision | report and indexes are generated |
| Review | signed-off/host-attested review record | review ID + bound revision/digest | model cannot approve itself |
| Session | immutable revisions + `ActionJournalStore` + checkpoints | session ID + revision | deterministic local Journal identity mapping; safe resume gate remains separate |
| Regression Recommendation | immutable revisions | REG ID + revision | no test code writes |
| Eval Run | immutable run manifest | Run ID + dataset digest | private ground truth isolated |

## Normative canonical state enums

- Finding status: `hypothesis`, `observed`, `suspected`, `needs_review`, `confirmed`, `rejected`, `duplicate`, `resolved`, `reopened`.
- Evidence level: `E0`, `E1`, `E2`, `E3`, `E4`.
- Reproduction: `not_attempted`, `reproduced`, `not_reproduced`, `intermittent`, `blocked`, `unknown`.
- Review: `not_required`, `pending`, `approved`, `rejected`, `expired`.
- Session: `created`, `ready`, `running`, `paused`, `recovering`, `completed`, `failed`, `blocked`, `cancelled`.
- Action: `proposed`, `authorized`, `prepared`, `dispatched`, `completed`, `failed`, `outcome_unknown`, `reconciled_completed`, `reconciled_not_executed`, `needs_review`, `rejected`, `cancelled`.
- Recovery: `safe`, `restricted`, `needs_reconciliation`, `blocked`.
- Pattern: `candidate`, `reviewed`, `verified`, `deprecated`.
- Recommendation: `draft`, `needs_review`, `approved`, `rejected`, `exported`, `superseded`, `archived`.

## Confirmation invariant

`confirmed` requires valid applicable Oracle, authentic independently attributable execution artifact(s), observable violation, sufficiently checked environment and causality, no blocking contradiction, >=E3 gate assessment, and bound human review when policy requires. E4 independent review is optional. Non-reproduction does not automatically invalidate original credible evidence. Confidence and severity are independent of maturity.

## Candidate screening and feedback

The Candidate Assessment schema reserves `rejected` for a future trusted-host verification flow; the current `assess_candidate()` helper emits only `candidate`, `needs_review`, or `duplicate`, and does not accept caller-supplied verifier callbacks. Until a trusted host verifier is integrated, structurally valid counter-evidence stays `needs_review` with unverified-provenance reasons. Self-asserted `validated` or provenance flags do not qualify for automatic rejection. A model opinion alone cannot reject. Conflicting E3+ violation and counter-evidence stays `needs_review`. The `candidate-assessment-rejected.json` file is a schema-only fixture, not a runtime assessment.

`candidate` and `duplicate` are provisional local screening results based on supplied records. The helper does not authenticate provenance flags or verify `duplicateOf` against canonical storage. A Host must verify source provenance and the referenced candidate before treating these results as authoritative or suppressing/aggregating records. Candidate Assessment remains blocked from the Confirmed Gate.

Cross-surface deduplication links only candidates with the same target, business object, operation, Oracle, and violation signature. The observed surface is omitted from that identity so an API and browser observation can link without counting twice. Review feedback is an append-only event list bound to a candidate revision and evidence references. The current helper returns an updated in-memory value; durable immutable Candidate/Finding storage and trusted evidence provenance verification are not implemented. The local binding checker below is not integrated into Candidate assessment.

## Oracle and Evidence data checks

Oracle schema v1.0 records a revision, expected-behavior statement, target/feature applicability, and the SHA-256 digest and byte length of the cited source bytes. Evidence schema v1.0 records an artifact's media type, SHA-256 digest and byte length, the exact Oracle ID/revision/canonical-record digest, and the Action Journal outcome's session/journal/action IDs, result reference, sequence, and event hash. The E0–E4 level is a supplied classification; this checker does not validate that level.

`bugmaster_core.provenance.verify_provenance()` recomputes the supplied Oracle source and Evidence artifact digests, matches the canonical Oracle record digest, then asks the concrete `ActionJournal` to validate its full local event chain and return the referenced outcome. Any mismatch or unavailable outcome fails closed. The result describes local integrity and reference binding only: SHA-256 is a content fingerprint, and the Journal hash chain is not a signature. Oracle authors, evidence capture, event origin, and external facts remain unauthenticated; the result keeps source authenticity unverified and the Confirmed Finding gate blocked. This slice adds schemas and an in-memory checker, not persistence, a trusted adapter, signer identity, or Gate integration.

## Approval invariant

Approve a normalized action intent: target, method, parameter digest, environment, scope revision, risk, count and expiry. Approval must originate in a trusted human/host event; a document claim is only advisory. R2 mutating actions require explicit authorization and enforceable controls; R3 blocked by default. Q9 recommendation approval never authorizes test code modifications.

The Scope JSON Schema records a per-target decision (`in_scope`, `pending_authorization`, or `out_of_scope`), a non-secret identity and environment reference, risk ceiling, finite action budget, and an approval reference for each `in_scope` target. The reference is not proof: the authorization gateway must verify the trusted record and its binding to the current scope revision before dispatch. Android, iOS, and unknown surfaces cannot be marked executable in v0.1.

The Approval and Action schemas capture scope/action references, scope revision, target, environment, normalized method and parameter digest, risk, count, expiry and lifecycle status. Their reference fields remain untrusted data until the host verifies the originating event and action binding. R2 is blocked by the current helper until that trusted gateway exists; R3 cannot enter a dispatched or completed state.

## Checkpoint invariant

Persist action intent before dispatch, append journal events, and reconcile unknown effects with authoritative read-only state before allowing any replay. A prepared event without dispatched event does **not** prove non-execution. No trusted read-only reconciliation verifier is currently wired, so the replay helper denies all replay requests. Do not promise exactly-once effects for external systems. Session recovery cannot reset budgets or approvals.

`ActionJournal.actions_needing_reconciliation()` returns the ordered action IDs whose locally recorded states remain unresolved. It is a diagnostic view only: it neither verifies external effects nor authorizes replay, and it fails closed if the Journal is missing or cannot be validated.

Each Action Journal Event uses schema v1.1 and binds both `sessionId` and a required stable `journalId`; readers reject mismatches and ambiguous duplicate JSON keys. `ActionJournalStore` maps the pair to `<root>/journals/<sha256(sessionId)>/<sha256(journalId)>.jsonl`. It walks the configured root and ancestors with no-follow, directory-relative opens, verifies trusted ownership and private mode bits (including the filesystem root), and rejects extended ACLs on macOS. It normalizes only root-owned macOS `/tmp` and `/var` aliases with their expected targets; arbitrary ancestor symlinks fail closed. `initialize()` serializes Journal creation with Session publication using the per-Session lock. It creates and syncs a new private Journal only before a Session revision has been persisted; after a revision exists it only reopens the existing Journal and fails closed if the file or storage path is missing. It rejects unsafe existing files without changing their permissions. `open()` also requires an existing safe file and never creates or repairs paths. Returned Journal instances pin the Session-directory descriptor and recheck its ACL before every read and append. Checkpoint reference validation walks and validates the storage root's trusted ancestors, then passes the same root descriptor through the Checkpoint/Session snapshot and opens the canonical Journal relative to it before verifying its prefix. This binds local path selection to the declared IDs; it does not authenticate file content, event provenance, or external truth. v1.0 events lack `journalId` and are rejected without migration or in-place modification.

## Contract build order

1. Define canonical schemas for Skill manifest, Pattern, Registry, Scope, Action, Approval, Oracle, Evidence, Finding, Session, Checkpoint, Review, Recommendation, Eval.
2. Generate language types/validators from JSON Schema where practical; never manually maintain contradictory enums.
3. Validate cross-document references and ID collisions, not only individual files.
4. Validate structural relationships and semantic gates separately; LLM review never replaces deterministic integrity checks.
