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
| Oracle | `.bugmaster/oracles/<id>/revisions/` | ID + revision + digest | approved/validated where required |
| Evidence | metadata and content-addressed artifacts | EV ID + artifact SHA-256 | hash proves integrity, not authenticity |
| Finding | immutable revisions + current pointer | Finding ID + revision | report and indexes are generated |
| Review | signed-off/host-attested review record | review ID + bound revision/digest | model cannot approve itself |
| Session | revisions + `journal.jsonl` + checkpoint | session ID + revision | one local writer; safe resume gate |
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

## Approval invariant

Approve a normalized action intent: target, method, parameter digest, environment, scope revision, risk, count and expiry. Approval must originate in a trusted human/host event; a document claim is only advisory. R2 mutating actions require explicit authorization and enforceable controls; R3 blocked by default. Q9 recommendation approval never authorizes test code modifications.

The Scope JSON Schema records a per-target decision (`in_scope`, `pending_authorization`, or `out_of_scope`), a non-secret identity and environment reference, risk ceiling, finite action budget, and an approval reference for each `in_scope` target. The reference is not proof: the authorization gateway must verify the trusted record and its binding to the current scope revision before dispatch. Android, iOS, and unknown surfaces cannot be marked executable in v0.1.

The Approval and Action schemas capture scope/action references, scope revision, target, environment, normalized method and parameter digest, risk, count, expiry and lifecycle status. Their reference fields remain untrusted data until the host verifies the originating event and action binding. R2 is blocked by the current helper until that trusted gateway exists; R3 cannot enter a dispatched or completed state.

Action Journal event schema v1.1 binds every event to both `sessionId` and `journalId`; a reader rejects an event stream whose identities do not match its configured Session and Journal. v1.0 logs are rejected without modification because their events do not carry a Journal ID; no migration is implemented. This local binding and the hash chain do not establish event provenance or external truth.

## Checkpoint invariant

Persist action intent before dispatch, append journal events, and reconcile unknown effects with authoritative read-only state before allowing any replay. A prepared event without dispatched event does **not** prove non-execution. Do not promise exactly-once effects for external systems. Session recovery cannot reset budgets or approvals.

## Contract build order

1. Define canonical schemas for Skill manifest, Pattern, Registry, Scope, Action, Approval, Oracle, Evidence, Finding, Session, Checkpoint, Review, Recommendation, Eval.
2. Generate language types/validators from JSON Schema where practical; never manually maintain contradictory enums.
3. Validate cross-document references and ID collisions, not only individual files.
4. Validate structural relationships and semantic gates separately; LLM review never replaces deterministic integrity checks.
