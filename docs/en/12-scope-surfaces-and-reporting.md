# Discovery Scope, Surface Routing, Deduplication and Reporting

[中文版](../zh-CN/12-scope-surfaces-and-reporting.md)

## Three separate ledgers
- **Discovered Inventory**: features/routes/endpoints actually observed with evidence and confidence; discovery is not coverage.
- **Authorization Scope**: approved targets, environment, identity, allowed risk/action budget, explicit exclusions and pending approval; a URL alone is not authorization.
- **Execution Ledger**: real action IDs, feature IDs, Oracle refs and tool evidence; status `planned/explored/partially_explored/blocked/not_explored`.

The current local CLI reads an OpenAPI 3 JSON file and emits one stable feature ID per declared operation, with JSON Pointer references to the operation, parameters, request body, responses and effective security declaration. Run `python scripts/discover_openapi.py examples/openapi/orders.json --source-ref examples/openapi/orders.json`. This records what the specification declares; it does not fetch the document, confirm a live endpoint, authorize access or execute a request. URL and Browser discovery remain unimplemented.

## Surfaces
v0.1 executable: `api` (REST/JSON/OpenAPI) and `web` (basic browser). Classified but not executable: `android`, `ios`. Unknown must remain unknown rather than auto-route to Browser. UI/API joint observations must be correlated by trace IDs, workflow state and authoritative records where available.

## Risk selection
Rank candidates by business impact, failure risk, complexity, observability and uncertainty (provisional weights 0.30/0.25/0.20/0.15/0.10); these scores guide selection, not bug probability. Unknown Oracle implies discovery/review before possible confirmation.

## Attribution and dedup
Store independent fields `testSurface`, `observedLayer`, `failureType`, `rootCauseStatus`, `evidenceRefs` and optional stable cross-surface cluster ID. Cluster only where there is observed matching operation/state/causal evidence, otherwise keep separate suspected findings. Never assert identical root cause solely based on similar error messages.

## Session report sections
Overview, discovered functional map, selected/excluded scope and reasons, explored/partly/blocked/untested features, execution methods and Action IDs, deduplicated Confirmed/Suspected/Rejected findings, individual evidence-linked defect reports, uncovered risks, and regression recommendations only. `no observed bug` ≠ `tested fully` or `passed`.

## Blind-scope Eval
URL-only Browser discovery; OpenAPI-only API discovery; forbidden URL traversal; discovery of new related feature and plan update; no executable mobile scope. All must have independent oracle/ground truth and recorded runs before release.
