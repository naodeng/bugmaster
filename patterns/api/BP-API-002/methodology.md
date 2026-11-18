# BP-API-002 — Same idempotency key causes duplicate side effects

Status: **candidate**, not independently verified.

Hypothesis: Same idempotency key causes duplicate side effects.

Before testing, obtain a valid business-invariant oracle and confirm applicability.

For validation: capture actual tool results and authoritative business state; rule out expected behavior, async windows and environment artifacts.

Never classify this as a confirmed defect solely because the pattern matched.
