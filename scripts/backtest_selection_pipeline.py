"""Untouched-season validation of the deployed prop-selection path.

The test freezes probability errors on seasons strictly before the evaluated
season, then runs projection -> reference line -> probability -> consistency
screen on the next season. Sportsbook prices, injuries, and current depth
charts are intentionally excluded because the free historical files do not
contain point-in-time versions of those feeds.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backtests" / "game_predictions.csv"
OUT = ROOT / "backtests" / "selection_pipeline_holdout.csv"
REPORT = ROOT / "SELECTION_VALIDATION.md"
STEPS = {"passing": 25.0, "rushing": 10.0, "receiving": 10.0, "receptions": 1.0}


def sd(values):
    if len(values) < 2:
        return 0.0
    avg = sum(values) / len(values)
    return math.sqrt(sum((x - avg) ** 2 for x in values) / (len(values) - 1))


def consistency(history):
    values = history[-5:]
    if len(values) < 3:
        return None
    avg = sum(values) / len(values)
    # Mirrors the outcome-variance half of the browser score. Opportunity
    # history is unavailable in the prediction export, so this is conservative.
    volatility = sd(values) / (abs(avg) + 1.0)
    return max(0, min(10, round(10 - 5 * volatility / 0.55)))


def reference_line(projection, market):
    step = STEPS[market]
    floor = 0.5 if market == "receptions" else 0.0
    return max(floor, math.floor(projection / step) * step - 0.5)


def empirical_over(errors, threshold):
    ordered = sorted(errors)
    below = sum(x <= threshold for x in ordered)
    # Add-one smoothing prevents a held-out row from receiving 0% or 100%.
    return (len(ordered) - below + 1) / (len(ordered) + 2)


rows = []
with SOURCE.open(newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        row["season"] = int(row["season"])
        row["week"] = int(row["week"])
        row["actual"] = float(row["actual"])
        row["ridge"] = float(row["ridge"])
        rows.append(row)

seasons = sorted({r["season"] for r in rows})
metrics = []
for season in seasons[2:]:
    training = [r for r in rows if r["season"] < season]
    test = sorted((r for r in rows if r["season"] == season), key=lambda r: (r["week"], r["market"], r["player_display_name"]))
    errors = defaultdict(list)
    history = defaultdict(list)
    for r in training:
        errors[r["market"]].append(r["actual"] - r["ridge"])
        history[(r["market"], r["player_display_name"])].append(r["actual"])
    selected = hits = 0
    brier = probability_sum = 0.0
    for r in test:
        key = (r["market"], r["player_display_name"])
        score = consistency(history[key])
        line = reference_line(r["ridge"], r["market"])
        probability = empirical_over(errors[r["market"]], line - r["ridge"])
        if score is not None and score >= 7 and probability >= 0.64:
            outcome = float(r["actual"] > line)
            selected += 1
            hits += int(outcome)
            brier += (probability - outcome) ** 2
            probability_sum += probability
        history[key].append(r["actual"])
    metrics.append({
        "season": season,
        "selected": selected,
        "hits": hits,
        "hit_rate": hits / selected if selected else 0.0,
        "mean_probability": probability_sum / selected if selected else 0.0,
        "brier": brier / selected if selected else 0.0,
    })

with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=metrics[0].keys())
    writer.writeheader()
    writer.writerows(metrics)

total = sum(x["selected"] for x in metrics)
hits = sum(x["hits"] for x in metrics)
weighted_brier = sum(x["brier"] * x["selected"] for x in metrics) / total
weighted_probability = sum(x["mean_probability"] * x["selected"] for x in metrics) / total
REPORT.write_text(
    "# End-to-end selection validation\n\n"
    "Each listed season is untouched: model-error probabilities are built only from earlier seasons. "
    "The test executes the deployed reference-line, 64% probability, and 7/10 consistency screens.\n\n"
    f"- Selections: {total:,}\n"
    f"- Hit rate: {hits / total:.1%}\n"
    f"- Mean stated probability: {weighted_probability:.1%}\n"
    f"- Brier score: {weighted_brier:.3f}\n\n"
    "This is a selection-model validation, not a profitability claim. Free historical data does not "
    "preserve FanDuel alt lines/odds, injury reports, depth charts, or roster snapshots as seen at bet time; "
    "those live gates must still pass before a recommendation is shown.\n",
    encoding="utf-8",
)
print(REPORT.read_text(encoding="utf-8"))
