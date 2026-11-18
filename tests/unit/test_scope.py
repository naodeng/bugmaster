import unittest

from bugmaster_core.scope import action_allowed, classify_surface


class ScopeTests(unittest.TestCase):
    def test_api_is_executable(self):
        self.assertEqual(
            classify_surface("api"),
            {"surface": "api", "executable": True, "reason": "supported-surface"},
        )

    def test_web_is_executable(self):
        self.assertIs(classify_surface("web")["executable"], True)

    def test_mobile_surfaces_are_future_only(self):
        for surface in ("android", "ios"):
            with self.subTest(surface=surface):
                self.assertEqual(classify_surface(surface)["reason"], "future-only")
                self.assertIs(
                    action_allowed(
                        True, surface, "R0", True, operation_mutates=False
                    ),
                    False,
                )

    def test_unknown_surface_is_not_executable(self):
        self.assertEqual(classify_surface("desktop")["surface"], "unknown")

    def test_non_string_surface_is_denied_without_crashing(self):
        try:
            result = classify_surface([])
        except Exception as error:
            self.fail("non-string surface raised {}".format(type(error).__name__))
        self.assertEqual(
            result,
            {"surface": "unknown", "executable": False, "reason": "unrecognized-surface"},
        )

    def test_scope_approval_must_be_boolean_true(self):
        for approval in ("approved", 1, None, False):
            with self.subTest(approval=approval):
                self.assertIs(
                    action_allowed(
                        approval, "api", "R0", False, operation_mutates=False
                    ),
                    False,
                )

    def test_r0_allows_explicitly_read_only_action(self):
        self.assertIs(
            action_allowed(True, "api", "R0", False, operation_mutates=False),
            True,
        )

    def test_r0_rejects_mutating_operation(self):
        self.assertIs(
            action_allowed(True, "api", "R0", True, operation_mutates=True),
            False,
        )

    def test_r1_requires_boolean_enforcement(self):
        for enforced in (False, "yes"):
            with self.subTest(enforced=enforced):
                self.assertIs(
                    action_allowed(
                        True, "web", "R1", enforced, operation_mutates=False
                    ),
                    False,
                )

    def test_r1_allows_enforced_isolated_action(self):
        self.assertIs(
            action_allowed(True, "web", "R1", True, operation_mutates=False),
            True,
        )

    def test_non_boolean_mutation_classification_is_denied(self):
        self.assertIs(
            action_allowed(True, "web", "R1", True, operation_mutates="no"),
            False,
        )

    def test_r2_r3_and_unknown_risk_require_higher_level_gate(self):
        for risk in ("R2", "R3", "R4"):
            with self.subTest(risk=risk):
                self.assertIs(
                    action_allowed(
                        True, "api", risk, True, operation_mutates=True
                    ),
                    False,
                )


if __name__ == "__main__":
    unittest.main()
