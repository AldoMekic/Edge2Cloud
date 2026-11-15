
import copy
import json
import sys
import unittest

from datetime import datetime, timezone
from pathlib import Path


# Project paths
ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(
    0,
    str(ROOT / "edge" / "pdp")
)

from policy_engine import (
    PolicyError,
    select_requirement,
    validate_policy
)


POLICY_PATH = (
    ROOT / "policies" / "odrl" /
    "actuator-v1.jsonld"
)

with open(POLICY_PATH, encoding="utf-8") as file:
    POLICY = json.load(file)


NOW = datetime(
    2026, 11, 15,
    tzinfo=timezone.utc
)


class TestODRLPolicyEngine(unittest.TestCase):

    def test_allowed_relation_selected(self):
        decision, reason, relation = select_requirement(
            POLICY,
            "device:actuator-001",
            "edge:start",
            NOW
        )

        self.assertIsNone(decision)
        self.assertEqual(
            reason,
            "RELATIONSHIP_REQUIRED"
        )
        self.assertEqual(relation, "can_start")

    def test_explicit_prohibition(self):
        decision, reason, relation = select_requirement(
            POLICY,
            "device:actuator-001",
            "edge:delete",
            NOW
        )

        self.assertEqual(decision, "DENY")
        self.assertEqual(
            reason,
            "EXPLICIT_PROHIBITION"
        )
        self.assertIsNone(relation)

    def test_no_matching_permission(self):
        decision, reason, relation = select_requirement(
            POLICY,
            "device:actuator-001",
            "edge:reset",
            NOW
        )

        self.assertEqual(decision, "DENY")
        self.assertEqual(
            reason,
            "NO_APPLICABLE_PERMISSION"
        )

    def test_expired_temporal_constraint(self):
        future = datetime(
            2100, 1, 1,
            tzinfo=timezone.utc
        )

        decision, reason, relation = select_requirement(
            POLICY,
            "device:actuator-001",
            "edge:start",
            future
        )

        self.assertEqual(decision, "DENY")
        self.assertEqual(
            reason,
            "NO_APPLICABLE_PERMISSION"
        )

    def test_unsupported_duty_is_rejected(self):
        modified = copy.deepcopy(POLICY)

        modified["obligation"] = [
            {"action": "edge:notify"}
        ]

        with self.assertRaises(PolicyError):
            validate_policy(modified)

    def test_invalid_constraint_rejected(self):
        modified = copy.deepcopy(POLICY)

        modified["permission"][1]["constraint"][0][
            "operator"
        ] = "unsupported"

        with self.assertRaises(PolicyError):
            validate_policy(modified)


if __name__ == "__main__":
    unittest.main(verbosity=2)
