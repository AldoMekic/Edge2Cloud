
"""Restricted ODRL policy evaluator for Edge2Cloud."""

from datetime import datetime, timezone

CONTEXT = "http://www.w3.org/ns/odrl.jsonld"
PROFILE = "https://example.org/edge2cloud/odrl-profile/v1"
EDGE_NS = "https://example.org/edge2cloud/odrl#"

OPERATORS = {"eq", "lt", "lteq", "gt", "gteq"}

RULE_KEYS = {
    "target",
    "action",
    "edge:requiredRelation",
    "edge:requiredContext",
    "constraint"
}

TOP_KEYS = {
    "@context",
    "@type",
    "uid",
    "profile",
    "edge:version",
    "permission",
    "prohibition"
}


class PolicyError(ValueError):
    pass


def parse_instant(value):
    if not isinstance(value, str):
        raise PolicyError("dateTime must be a string")

    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise PolicyError("Invalid ISO 8601 dateTime") from exc

    if dt.tzinfo is None:
        raise PolicyError("dateTime requires timezone")

    return dt.astimezone(timezone.utc)


def validate_constraint(constraint):
    if (
        not isinstance(constraint, dict)
        or set(constraint) != {
            "leftOperand", "operator", "rightOperand"
        }
    ):
        raise PolicyError("Unsupported temporal constraint")

    if (
        constraint["leftOperand"] != "dateTime"
        or constraint["operator"] not in OPERATORS
    ):
        raise PolicyError("Unsupported operand/operator")

    right = constraint["rightOperand"]

    if (
        not isinstance(right, dict)
        or set(right) != {"@value", "@type"}
        or right["@type"] != "xsd:dateTime"
    ):
        raise PolicyError("Expected typed dateTime value")

    parse_instant(right["@value"])


def validate_context_requirements(requirements):
    if not isinstance(requirements, list) or not requirements:
        raise PolicyError("Context requirements must be nonempty")

    for requirement in requirements:
        if (
            not isinstance(requirement, dict)
            or set(requirement) != {
                "attribute", "operator", "value"
            }
        ):
            raise PolicyError("Unsupported context requirement")

        attribute = requirement["attribute"]
        operator = requirement["operator"]
        value = requirement["value"]

        if attribute == "state":
            if operator != "eq" or value not in (
                "IDLE", "RUNNING", "STOPPED", "FAULT"
            ):
                raise PolicyError("Invalid state requirement")

        elif attribute == "temperature":
            if (
                operator not in OPERATORS
                or type(value) not in (int, float)
            ):
                raise PolicyError("Invalid temperature requirement")

        else:
            raise PolicyError("Unknown Digital Twin attribute")


def validate_policy(policy):
    if (
        not isinstance(policy, dict)
        or set(policy) - TOP_KEYS
    ):
        raise PolicyError("Unsupported top-level construct")

    context = policy.get("@context")

    if (
        not isinstance(context, list)
        or len(context) != 2
        or context[0] not in (
            CONTEXT, CONTEXT.replace("http:", "https:")
        )
        or context[1] != {"edge": EDGE_NS}
    ):
        raise PolicyError("Unexpected JSON-LD context")

    if (
        policy.get("@type") != "Set"
        or policy.get("profile") != PROFILE
    ):
        raise PolicyError("Unsupported policy type/profile")

    if not isinstance(policy.get("uid"), str) or not policy["uid"]:
        raise PolicyError("Policy UID required")

    if (
        not isinstance(policy.get("edge:version"), str)
        or not policy["edge:version"]
    ):
        raise PolicyError("Policy version required")

    for kind in ("permission", "prohibition"):
        rules = policy.get(kind, [])

        if not isinstance(rules, list):
            raise PolicyError("Rules must be arrays")

        for rule in rules:
            if (
                not isinstance(rule, dict)
                or set(rule) - RULE_KEYS
            ):
                raise PolicyError("Unsupported ODRL rule")

            if (
                not isinstance(rule.get("target"), str)
                or not rule["target"]
            ):
                raise PolicyError("Target required")

            if (
                not isinstance(rule.get("action"), str)
                or not rule["action"].startswith("edge:")
            ):
                raise PolicyError("Unsupported action")

            relation = rule.get("edge:requiredRelation")

            if kind == "permission":
                if (
                    not isinstance(relation, str)
                    or not relation.startswith("can_")
                ):
                    raise PolicyError("ReBAC relation required")

            elif relation is not None:
                raise PolicyError(
                    "Relationship-dependent prohibition unsupported"
                )

            if "edge:requiredContext" in rule:
                if kind != "permission":
                    raise PolicyError(
                        "Context-dependent prohibition unsupported"
                    )

                validate_context_requirements(
                    rule["edge:requiredContext"]
                )

            constraints = rule.get("constraint", [])

            if not isinstance(constraints, list):
                raise PolicyError("Constraints must be arrays")

            for constraint in constraints:
                validate_constraint(constraint)

    if not (policy.get("permission") or policy.get("prohibition")):
        raise PolicyError("At least one rule required")

    return policy


def constraints_satisfied(rule, now):
    for constraint in rule.get("constraint", []):
        target = parse_instant(
            constraint["rightOperand"]["@value"]
        )

        comparisons = {
            "eq": now == target,
            "lt": now < target,
            "lteq": now <= target,
            "gt": now > target,
            "gteq": now >= target
        }

        if not comparisons[constraint["operator"]]:
            return False

    return True


def applicable_rules(policy, kind, resource, action, now):
    return [
        rule
        for rule in policy.get(kind, [])
        if (
            rule["target"] == resource
            and rule["action"] == action
            and constraints_satisfied(rule, now)
        )
    ]


def select_requirement(policy, resource, action, now):
    validate_policy(policy)

    prohibitions = applicable_rules(
        policy, "prohibition", resource, action, now
    )

    if prohibitions:
        return "DENY", "EXPLICIT_PROHIBITION", None

    permissions = applicable_rules(
        policy, "permission", resource, action, now
    )

    if not permissions:
        return "DENY", "NO_APPLICABLE_PERMISSION", None

    relations = {
        rule["edge:requiredRelation"]
        for rule in permissions
    }

    if len(relations) != 1:
        raise PolicyError(
            "Ambiguous permission relationships"
        )

    return None, "RELATIONSHIP_REQUIRED", next(iter(relations))


def evaluate_context_requirements(requirements, observation):
    """
    Return True if all known context requirements hold.

    Invalid or missing evidence is an error, not a
    successful comparison.
    """
    for requirement in requirements:
        attribute = requirement["attribute"]
        operator = requirement["operator"]
        expected = requirement["value"]

        actual = observation.get(attribute)

        if attribute == "state":
            if not isinstance(actual, str):
                raise ValueError("Invalid state evidence")

        elif attribute == "temperature":
            if type(actual) not in (int, float):
                raise ValueError("Invalid temperature evidence")

        comparisons = {
            "eq": actual == expected,
            "lt": actual < expected if attribute == "temperature" else False,
            "lteq": actual <= expected if attribute == "temperature" else False,
            "gt": actual > expected if attribute == "temperature" else False,
            "gteq": actual >= expected if attribute == "temperature" else False
        }

        if not comparisons[operator]:
            return False

    return True
