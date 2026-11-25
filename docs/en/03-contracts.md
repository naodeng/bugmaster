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
| Candidate Assessment | embedded in a Candidate revision | Candidate ID + revision | screening only; never `confirmed`; rejection requires trusted counter-evidence review |
| Candidate | `<root>/candidates/<sha256(candidateId)>/revisions/` | Candidate ID + revision | local immutable metadata; assessment stays provisional |
| Finding | `<root>/findings/<sha256(findingId)>/revisions/` + `metadata.head` | Finding ID + revision | local metadata only; reports and indexes are not generated |
| Review | signed-off/host-attested review record | review ID + bound revision/digest | model cannot approve itself |
| Session | immutable revisions + `ActionJournalStore` + checkpoints | session ID + revision | deterministic local Journal identity mapping; safe resume gate remains separate |
| Regression Recommendation | immutable revisions | REG ID + revision | no test code writes |
| Eval Run | immutable run manifest | Run ID + dataset digest | private ground truth isolated |

## Schema registry and compatibility

The repository schema bundle uses JSON Schema Draft 2020-12. Every schema has a unique absolute, fragment-free `$id` and requires a pinned `schemaVersion` in `major.minor` form. ID and reference matching normalize scheme/host case and remove the standard HTTP/HTTPS default port. For a non-literal reference spelling, the loader adds an exact registry alias only when it maps to a known local schema resource. `bugmaster_core.schema_registry` loads schemas into a closed local registry, validates each schema, and resolves every `$ref` and `$dynamicRef` from the effective base URI, including nested `$id` values, before returning a validator. Each reference target must itself be a valid object or boolean schema. It traverses schema-bearing keywords, not object-shaped data under keywords such as `default`. Missing local references, non-schema targets, and unregistered external references fail closed; the loader does not retrieve schemas over the network.

A schema accepts only its declared `schemaVersion`. There is no implicit migration or backward-compatibility claim: supporting another version requires an explicit schema and migration decision. This registry check validates schema definitions and their `$ref` graph; it does not prove that runtime records named by domain references exist or are authentic. Existing stores and contract validators keep their separate record-level binding checks.

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

The Candidate/Finding schemas describe the full future status vocabulary. The current local store only accepts Candidate decisions `candidate`, `needs_review`, and provisional `duplicate`, and Finding statuses `hypothesis`, `observed`, `suspected`, and `needs_review`. It blocks Candidate `rejected` and Finding `confirmed`, `rejected`, `duplicate`, `resolved`, and `reopened` until trusted verification and required human review are integrated.

## Confirmation invariant

`confirmed` requires valid applicable Oracle, authentic independently attributable execution artifact(s), observable violation, sufficiently checked environment and causality, no blocking contradiction, >=E3 gate assessment, and bound human review when policy requires. E4 independent review is optional. Non-reproduction does not automatically invalidate original credible evidence. Confidence and severity are independent of maturity.

## Candidate screening and feedback

The Candidate Assessment schema reserves `rejected` for a future trusted-host verification flow; the current `assess_candidate()` helper emits only `candidate`, `needs_review`, or `duplicate`, and does not accept caller-supplied verifier callbacks. Until a trusted host verifier is integrated, structurally valid counter-evidence stays `needs_review` with unverified-provenance reasons. Self-asserted `validated` or provenance flags do not qualify for automatic rejection. A model opinion alone cannot reject. Conflicting E3+ violation and counter-evidence stays `needs_review`. The `candidate-assessment-rejected.json` file is a schema-only fixture, not a runtime assessment.

`candidate` and `duplicate` are provisional local screening results based on supplied records. The helper does not authenticate provenance flags or verify `duplicateOf` against canonical storage. A Host must verify source provenance and the referenced candidate before treating these results as authoritative or suppressing/aggregating records. Candidate Assessment remains blocked from the Confirmed Gate.

Cross-surface deduplication links only candidates with the same target, business object, operation, Oracle, and violation signature. The observed surface is omitted from that identity so an API and browser observation can link without counting twice. Review feedback is an append-only event list bound to a candidate revision and evidence references. The helper still returns an updated in-memory value; the metadata store is a separate API and is not wired into assessment, deduplication, or reporting. The local binding checker below is also not integrated into Candidate assessment.

## Candidate and Finding metadata persistence

`CandidateStore` and `FindingStore` validate their JSON Schema by default and append immutable revision files under a configured private root. Hashed IDs select per-record directories. Each record has a POSIX file lock, a current head containing the latest revision and history digests, and optimistic `expected_revision` checks. Revision and head writes use private temporary files, `fsync`, and no-replace publication for immutable revisions. Reads revalidate the entire history and fail closed on missing or orphan revisions, unknown directory entries, symlinks, hard links, unsafe owners, non-private existing file permissions, detectable extended ACLs, non-canonical JSON, schema failures, or digest mismatches. A missing configured root is created with owner-only access; an existing root must already be private and is never permission-repaired. Record directories may be repaired to owner-only access after ownership and ACL checks. Reads reject non-private directory permissions, and existing files with unsafe permissions are always rejected without modification.

Candidate revisions embed a Candidate Assessment and require its ID, revision, surface, Pattern, Oracle reference, evidence references, false-positive checks, review-required flag, and optional deduplication identity to match. Each review event must reference the same Candidate and an existing revision; event IDs must be unique and event evidence references must exist in the exact revision named by the event. A Candidate cannot reference itself as a duplicate. This binding does not authenticate the reviewer or prove that a human performed the review. Identity fields are stable across revisions; evidence references, false-positive checks, and review events cannot be removed or reordered. Finding references to Candidates, surfaces, Actions, and Evidence are also append-only. Candidate evidence references contain Evidence IDs; Finding evidence references also contain SHA-256 digests and byte lengths. The store does not read or write Evidence bytes, verify referenced records, authenticate source or reviewer claims, verify the human identity represented by a review event, suppress duplicates, or connect any state to the Confirmed Gate. A persisted reviewer ID or decision is an unverified statement, not proof that a person reviewed the record. Interrupted publication is not automatically recovered; the next read fails closed until an operator resolves the orphan/temporary entry. Windows behavior is not verified.

The digest chain detects partial or inconsistent edits, not a local actor with write access to the entire root who can recompute all digests or roll back the complete directory. Callers must keep raw or Base64-encoded Evidence content out of descriptive free-text fields. The store treats those fields as opaque text and does not inspect embedded content.

Finding evidence references must use a unique Evidence ID within each revision, even when duplicate IDs carry different digests or byte lengths.

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
