
import sys
import unittest

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "edge" / "pdp"))

from policy_engine import (
    evaluate_context_requirements,
    validate_context_requirements
)


REQUIREMENTS = [
    {
        "attribute": "state",
        "operator": "eq",
        "value": "IDLE"
    },
    {
        "attribute": "temperature",
        "operator": "lt",
        "value": 70
    }
]


class TestDigitalTwinContext(unittest.TestCase):

    def test_safe_context(self):
        observation = {
            "state": "IDLE",
            "temperature": 42.5
        }

        self.assertTrue(
            evaluate_context_requirements(
                REQUIREMENTS, observation
            )
        )

    def test_unsafe_temperature(self):
        observation = {
            "state": "IDLE",
            "temperature": 85
        }

        self.assertFalse(
            evaluate_context_requirements(
                REQUIREMENTS, observation
            )
        )

    def test_unsafe_state(self):
        observation = {
            "state": "RUNNING",
            "temperature": 42.5
        }

        self.assertFalse(
            evaluate_context_requirements(
                REQUIREMENTS, observation
            )
        )

    def test_invalid_context(self):
        observation = {
            "state": "IDLE"
        }

        with self.assertRaises(ValueError):
            evaluate_context_requirements(
                REQUIREMENTS, observation
            )

    def test_invalid_policy_attribute(self):
        requirements = [
            {
                "attribute": "unknown",
                "operator": "eq",
                "value": 1
            }
        ]

        with self.assertRaises(ValueError):
            validate_context_requirements(
                requirements
            )


if __name__ == "__main__":
    unittest.main()
