
"""Train the Edge2Cloud predictive prefetch model.

The dataset is SYNTHETIC and intended only for
functional validation of the MVP.

Target: next likely authorization action.
The model does not predict or decide access rights.
"""

import json
import random

from pathlib import Path

import joblib
import numpy as np

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report
)
from sklearn.model_selection import train_test_split


MODEL_PATH = Path("/app/model.joblib")
REPORT_PATH = Path("/app/training_report.json")

RANDOM_SEED = 42
NUM_SAMPLES = 6000

ACTIONS = [
    "edge:read",
    "edge:start",
    "edge:maintain"
]

# Synthetic user categories, not authoritative roles.
USER_HINTS = {
    "operator": 0,
    "technician": 1,
    "viewer": 2
}

ACTION_CODES = {
    name: index
    for index, name in enumerate(ACTIONS)
}


def synthetic_next_action(role, action, decision, rng):
    """Simulate plausible access-request transitions."""

    if decision == "DENY":
        return rng.choices(
            ACTIONS,
            weights=[85, 8, 7]
        )[0]

    if role == "operator":
        if action == "edge:read":
            weights = [20, 75, 5]
        else:
            weights = [85, 10, 5]

    elif role == "technician":
        if action == "edge:read":
            weights = [20, 5, 75]
        else:
            weights = [85, 5, 10]

    else:
        weights = [90, 5, 5]

    return rng.choices(
        ACTIONS,
        weights=weights
    )[0]


def generate_dataset():
    rng = random.Random(RANDOM_SEED)

    features = []
    labels = []

    for _ in range(NUM_SAMPLES):
        role = rng.choice(list(USER_HINTS))
        action = rng.choice(ACTIONS)

        decision = rng.choices(
            ["ALLOW", "DENY"],
            weights=[80, 20]
        )[0]

        hour = rng.randrange(24)

        next_action = synthetic_next_action(
            role, action, decision, rng
        )

        features.append([
            USER_HINTS[role],
            ACTION_CODES[action],
            1 if decision == "ALLOW" else 0,
            hour
        ])

        labels.append(ACTION_CODES[next_action])

    return (
        np.asarray(features, dtype=np.float64),
        np.asarray(labels, dtype=np.int64)
    )


def main():
    X, y = generate_dataset()

    X_train, X_test, y_train, y_test = (
        train_test_split(
            X,
            y,
            test_size=0.25,
            random_state=RANDOM_SEED,
            stratify=y
        )
    )

    model = HistGradientBoostingClassifier(
        max_iter=100,
        max_depth=4,
        min_samples_leaf=15,
        learning_rate=0.08,
        random_state=RANDOM_SEED
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    accuracy = accuracy_score(
        y_test, predictions
    )

    balanced_accuracy = balanced_accuracy_score(
        y_test, predictions
    )

    majority_class = np.bincount(y_train).argmax()

    baseline_accuracy = float(
        np.mean(y_test == majority_class)
    )

    report = {
        "dataset": "synthetic",
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "algorithm": "HistGradientBoostingClassifier",
        "target": "next_authorization_action",
        "accuracy": float(accuracy),
        "balanced_accuracy": float(balanced_accuracy),
        "majority_baseline_accuracy": baseline_accuracy,
        "class_names": ACTIONS,
        "classification_report": classification_report(
            y_test,
            predictions,
            target_names=ACTIONS,
            zero_division=0,
            output_dict=True
        )
    }

    joblib.dump(
        {
            "model": model,
            "actions": ACTIONS,
            "user_hints": USER_HINTS,
            "action_codes": ACTION_CODES
        },
        MODEL_PATH
    )

    REPORT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print("=" * 60)
    print("EDGE2CLOUD AI PREFETCH TRAINING")
    print("=" * 60)
    print(f"Dataset: SYNTHETIC ({NUM_SAMPLES} samples)")
    print(f"Training samples: {len(X_train)}")
    print(f"Test samples: {len(X_test)}")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Balanced accuracy: {balanced_accuracy:.4f}")
    print(f"Majority baseline: {baseline_accuracy:.4f}")
    print(f"Model saved to: {MODEL_PATH}")


if __name__ == "__main__":
    main()
