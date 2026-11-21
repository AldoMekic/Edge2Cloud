
"""Aggregate completed Step 10 benchmark repetitions."""

import csv
import json
import math
import statistics

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results" / "step10"


def confidence_interval_95(values):
    """Normal-approximation CI for descriptive screening.

    For final publication, prefer bootstrap or
    an appropriate repeated-measures method.
    """
    if len(values) < 2:
        return None

    mean = statistics.mean(values)
    se = statistics.stdev(values) / math.sqrt(len(values))

    return [
        mean - 1.96 * se,
        mean + 1.96 * se
    ]


def main():
    files = sorted(
        RESULTS.glob("*/results.json")
    )

    completed = []

    for path in files:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )

        if data.get("error") is None:
            completed.append({
                "run": path.parent.name,
                "phases": data["phases"]
            })

    print("=" * 70)
    print("EDGE2CLOUD STEP 10 AGGREGATE RESULTS")
    print("=" * 70)

    print("Completed benchmark runs:", len(completed))

    if not completed:
        print("No completed experiments found.")
        return

    records = []

    for run in completed:
        phases = run["phases"]

        for cohort in ("cold", "warm"):
            cache = phases.get("cache", {}).get(
                cohort, {}
            )

            if cache.get("median_ms") is not None:
                records.append({
                    "run": run["run"],
                    "metric": f"cache_{cohort}_median_ms",
                    "value": cache["median_ms"]
                })

        for workers, metrics in phases.get(
            "load", {}
        ).items():
            for key in (
                "throughput_rps",
                "median_ms",
                "p95_ms",
                "p99_ms"
            ):
                value = metrics.get(key)

                if value is not None:
                    records.append({
                        "run": run["run"],
                        "metric": f"pdp_w{workers}_{key}",
                        "value": value
                    })

        revocation = phases.get("revocation", {})

        if revocation.get(
            "deny_observed_from_start_ms"
        ) is not None:
            records.append({
                "run": run["run"],
                "metric": "revocation_client_to_deny_ms",
                "value": revocation[
                    "deny_observed_from_start_ms"
                ]
            })

    grouped = {}

    for record in records:
        grouped.setdefault(
            record["metric"], []
        ).append(record["value"])

    output = []

    print()
    print(
        f"{'Metric':40} {'N':>4} "
        f"{'Mean':>12} {'Std Dev':>12}"
    )
    print("-" * 70)

    for metric in sorted(grouped):
        values = grouped[metric]

        mean = statistics.mean(values)
        stdev = (
            statistics.stdev(values)
            if len(values) > 1 else 0.0
        )

        ci = confidence_interval_95(values)

        result = {
            "metric": metric,
            "n": len(values),
            "mean": round(mean, 5),
            "std_dev": round(stdev, 5),
            "ci95_lower": (
                round(ci[0], 5) if ci else ""
            ),
            "ci95_upper": (
                round(ci[1], 5) if ci else ""
            )
        }

        output.append(result)

        print(
            f"{metric:40} {len(values):>4} "
            f"{mean:>12.4f} {stdev:>12.4f}"
        )

    target = RESULTS / "aggregate_summary.csv"

    with target.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "metric",
                "n",
                "mean",
                "std_dev",
                "ci95_lower",
                "ci95_upper"
            ]
        )

        writer.writeheader()
        writer.writerows(output)

    print()
    print("Saved:", target)
    print(
        "Confidence intervals are preliminary "
        "normal approximations."
    )


if __name__ == "__main__":
    main()
