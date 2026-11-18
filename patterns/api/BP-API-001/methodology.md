# BP-API-001 — Retry unexpectedly creates duplicate resources

Status: **candidate**, not independently verified.

Hypothesis: Retry unexpectedly creates duplicate resources.

Before testing, obtain a valid business-invariant oracle and confirm applicability.

For validation: capture actual tool results and authoritative business state; rule out expected behavior, async windows and environment artifacts.

Never classify this as a confirmed defect solely because the pattern matched.
