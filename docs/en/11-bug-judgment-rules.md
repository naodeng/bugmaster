# Bug Judgment: Patterns → Oracles → Evidence Gates

[中文版](../zh-CN/11-bug-judgment-rules.md) · [Product](../../PRODUCT.md)

## Decision layers
1. **Pattern** chooses a falsifiable defect hypothesis; matching a Pattern is not confirming a bug.
2. **Oracle** captures a source-backed expected behavior (OpenAPI contract, approved requirement, business invariant, state machine) and checks whether actual observations violate it. Undocumented behavior is a hypothesis, not an authoritative Oracle.
3. **Evidence gate** requires real authorized tool execution and provenance, attributable state observations, valid Oracle, causal/environment checks and policy review. A self-described or inferred execution never establishes E3.

## Domains
| Domain | Candidate defects | Required evidence |
|---|---|---|
| REST API | contract mismatch, missing/null, input boundary, idempotency, state and durable outcome | contract revision, request/response, authoritative state if relevant |
| Browser UI | form feedback, navigation, stale state, duplicate interaction, UI/API inconsistency | visible page/DOM, browser action trace, correlated network/API state |
| Business | amounts/rounding, forbidden transitions, coupon reuse, policy conflicts | approved business rules, controlled experiment, post-state |
| Mobile | classification only in v0.1 | not executable within v0.1 |

## Verdict
`confirmed` requires validated Oracle and E3+ authentic evidence; otherwise `suspected`/`needs_review`. A violation found in Browser does not automatically mean root cause is frontend. Record observed surface separately from suspected layer and actual root-cause verification.

## Rule discovery
Machine-readable rules live in `patterns/<domain>/<BP-ID>/pattern.json`, indexing in `patterns/taxonomy.json` and `registry/capabilities.json`. They are **candidate skeletons** requiring applicability, exclusions, evaluator, false-positive branches, a positive case and a correct-implementation negative case for release.
