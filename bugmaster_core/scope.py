"""Deterministic test-surface classification and conservative action gate."""

SUPPORTED = frozenset({"api", "web"})
KNOWN = SUPPORTED | frozenset({"android", "ios"})


def classify_surface(surface: str) -> dict:
    """Classify a surface without implying execution support for unknown input."""
    if not isinstance(surface, str) or surface not in KNOWN:
        return {
            "surface": "unknown",
            "executable": False,
            "reason": "unrecognized-surface",
        }
    if surface not in SUPPORTED:
        return {"surface": surface, "executable": False, "reason": "future-only"}
    return {"surface": surface, "executable": True, "reason": "supported-surface"}


def action_allowed(
    scope_approved: bool,
    surface: str,
    risk: str,
    enforced: bool,
    *,
    operation_mutates: bool,
) -> bool:
    """Allow only explicitly approved, supported, read-only or isolated actions.

    R2 requires a separate action-level authorization gateway. R3 remains denied.
    """
    if scope_approved is not True or not isinstance(operation_mutates, bool):
        return False
    if not classify_surface(surface)["executable"]:
        return False
    if risk == "R0":
        return operation_mutates is False
    if risk == "R1":
        return enforced is True
    return False
