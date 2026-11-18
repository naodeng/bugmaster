# Contract Schemas

Schemas use JSON Schema Draft 2020-12. Contract tests check both the schema itself and representative documents.

## Implemented

- `scope.schema.json`: validates the versioned Scope document, per-target authorization decision, known surfaces and risks, approval-reference presence for in-scope targets, and finite action budgets.
- `feature-inventory.schema.json`: validates the source-linked Feature Inventory emitted by the local OpenAPI CLI while keeping authorization and execution ledgers separate.
- `approval.schema.json`: validates scope or action approval records, exact scope revision and target binding, source/approver references, expiry fields, and the action intent fields required for R2.
- `action.schema.json`: validates the normalized action intent and lifecycle state, R0/R2 mutation constraints, R2 approval references, R1 mutation enforcement references, and non-executable mobile/unknown surfaces.
- `event.schema.json`: validates the versioned Action Journal event envelope and the four prepared/dispatched/outcome/reconciled payloads. The runtime additionally checks sequence, transition order, session identity, RFC3339 time, and the SHA-256 event chain.

`approvalRef` and `enforcementRef` are structural references only. Validation does not establish who approved a scope, whether the record is authentic, current, unexpired, or bound to this exact scope revision. The trusted authorization gateway must verify those properties before dispatch. R2 also needs action-level approval and enforceable controls; R3 remains subject to separate security policy.

The local Action Journal uses restrictive file permissions, a single-operation POSIX file lock, append + `fsync`, and conservative recovery states. Its event hashes do not prove provenance or truth. A prepared/dispatched action without a result remains blocked after restart. Caller-supplied read-only observations are stored only as unverified reconciliation claims and never unlock dispatch; R1/R2 failed outcomes also remain blocked. A trusted read-only verifier is not implemented yet.

## Remaining contracts

Skill Manifest, Pattern, Catalog, Capability Registry, Session, Checkpoint, Recovery Decision, Oracle, Evidence, Finding, Review, Report, Regression Recommendation, Eval Manifest, and Release Manifest remain unimplemented. Existing status and identity guidance in `docs/en/03-contracts.md` and `docs/zh-CN/03-contracts.md` is the starting point. Do not treat this partial schema set as a passing complete contract suite.

Scope, Feature Inventory, Approval, Action, and Event schemas are exercised by the corresponding tests in `tests/contracts/`. Feature Inventory tests validate the actual CLI output generated from `examples/openapi/orders.json`; event tests validate actual journal output, including R2 approval binding. CI installs the pinned test validator and runs the contract suite. To run it locally, use Python 3.12 and install `jsonschema[format-nongpl]==4.26.0`; the optional format validators make RFC3339 timestamp checks executable. This is a test-only dependency and is not a BugMaster runtime dependency. Python versions below 3.10 need to use the repository's Python 3.12 CI runtime or an equivalent compatible environment.
