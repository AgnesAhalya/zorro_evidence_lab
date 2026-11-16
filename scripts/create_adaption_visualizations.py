#!/usr/bin/env python3
"""Create publication-ready PNG figures from an Adaption merged run summary."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "adaption_github_results"
SUMMARY_PATH = RESULTS / "run_summary.json"

BLUE = "#2f6fbb"
YELLOW = "#d69e2e"
GREEN = "#438b65"
RED = "#c45151"
INK = "#1f2937"
MUTED = "#5f6b7a"
GRID = "#d7dde6"


def percent(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def points(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def configure() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.labelsize": 10,
        "axes.edgecolor": "#aab4c0",
        "axes.labelcolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "text.color": INK,
        "figure.dpi": 150,
        "savefig.dpi": 300,
    })


def finish(fig: plt.Figure, title: str, note: str, filename: str) -> None:
    fig.suptitle(title, x=0.08, y=0.98, ha="left", fontsize=16, fontweight="bold")
    fig.text(0.08, 0.015, note, ha="left", va="bottom", fontsize=8.5, color=MUTED)
    # Reserve distinct regions for the title, axes/legends, and the explanatory note.
    # This keeps annotations readable when the PNG is placed directly in a paper.
    fig.tight_layout(rect=(0.03, 0.09, 0.98, 0.90))
    fig.savefig(RESULTS / filename, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def annotate(ax, bars, labels, color=INK, rotation=0) -> None:
    for bar, label in zip(bars, labels):
        value = bar.get_height()
        ax.annotate(
            label,
            xy=(bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 4 if value >= 0 else 6),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
            color=color,
            rotation=rotation,
        )


def base_axes(ax) -> None:
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)


def epistemic_balance(data: dict) -> None:
    conditions = data["metrics"]["conditions"]
    authority = data["metrics"]["epistemic_balance"]
    names = ["Negative pressure", "Positive pressure"]
    alignment = [conditions[c]["suggestion_adoption_rate"] * 100 for c in ("negative_pressure", "positive_pressure")]
    directional = [
        authority["negative_harmful_transition_rate"] * 100,
        authority["positive_corrective_transition_rate"] * 100,
    ]
    x = np.arange(2)
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    width = 0.34
    bars_a = ax.bar(x - width / 2, alignment, width, color=BLUE, label="Investigator-preference alignment")
    bars_b = ax.bar(x + width / 2, directional, width, color=GREEN, label="Directional accuracy transition")
    labels_a = [
        f"{conditions['negative_pressure']['suggestion_adoption_count']}/{conditions['negative_pressure']['suggestion_adoption_total']}\n{alignment[0]:.1f}%",
        f"{conditions['positive_pressure']['suggestion_adoption_count']}/{conditions['positive_pressure']['suggestion_adoption_total']}\n{alignment[1]:.1f}%",
    ]
    labels_b = [
        f"{conditions['negative_pressure']['correct_to_incorrect_count']}/{conditions['negative_pressure']['correct_to_incorrect_total']}\n{directional[0]:.1f}%",
        f"{conditions['positive_pressure']['incorrect_to_correct_count']}/{conditions['positive_pressure']['incorrect_to_correct_total']}\n{directional[1]:.1f}%",
    ]
    annotate(ax, bars_a, labels_a)
    annotate(ax, bars_b, labels_b)
    ax.set_ylim(0, 112)
    ax.set_ylabel("Rate (%)")
    ax.set_xticks(x, names)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.set_title("EpistemicBalance: directional responsiveness", loc="left", color=INK)
    ax.legend(frameon=False, loc="upper left", ncols=1)
    base_axes(ax)
    finish(fig, "EpistemicBalance", "Counts are valid paired responses. Positive alignment is not evidence of independent reasoning.", "epistemic_balance.png")


def accuracy_transitions(data: dict) -> None:
    conditions = data["metrics"]["conditions"]
    names = ["Negative pressure", "Positive pressure"]
    initial = [conditions[c]["initial_accuracy"] * 100 for c in ("negative_pressure", "positive_pressure")]
    post = [conditions[c]["post_pressure_accuracy"] * 100 for c in ("negative_pressure", "positive_pressure")]
    x = np.arange(2)
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.7), gridspec_kw={"width_ratios": [1, 1.15]})
    width = 0.34
    bars_a = axes[0].bar(x - width / 2, initial, width, color=BLUE, label="Initial accuracy")
    bars_b = axes[0].bar(x + width / 2, post, width, color=YELLOW, label="Post-pressure accuracy")
    annotate(axes[0], bars_a, [f"{v:.1f}%" for v in initial])
    annotate(axes[0], bars_b, [f"{v:.1f}%" for v in post])
    axes[0].set_ylim(0, 112)
    axes[0].set_ylabel("Accuracy (%)")
    axes[0].set_xticks(x, names)
    axes[0].set_yticks(np.arange(0, 101, 20))
    axes[0].set_title("Initial vs post-pressure", loc="left")
    base_axes(axes[0])

    harmful = [conditions["negative_pressure"]["correct_to_incorrect_count"], 0]
    corrective = [0, conditions["positive_pressure"]["incorrect_to_correct_count"]]
    bars_c = axes[1].bar(x - width / 2, harmful, width, color=RED, label="Correct → incorrect")
    bars_d = axes[1].bar(x + width / 2, corrective, width, color=GREEN, label="Incorrect → correct")
    annotate(axes[1], bars_c, ["166/942", "0/949"])
    annotate(axes[1], bars_d, ["0/148", "143/149"])
    axes[1].set_ylim(0, 190)
    axes[1].set_ylabel("Transition count")
    axes[1].set_xticks(x, names)
    axes[1].set_title("Directional transitions", loc="left")
    base_axes(axes[1])
    finish(
        fig,
        "Accuracy transitions under investigative pressure",
        "Blue = initial accuracy; gold = post-pressure accuracy. Red = correct → incorrect; green = incorrect → correct.\n"
        "Numerators and denominators are shown directly; denominators are valid paired responses.",
        "accuracy_transitions.png",
    )


def confidence_changes(data: dict) -> None:
    conditions = data["metrics"]["conditions"]
    values = [conditions[c]["mean_confidence_change_all"] for c in ("negative_pressure", "positive_pressure")]
    counts = [
        (conditions[c]["confidence_changed_count"], conditions[c]["confidence_change_observation_count"])
        for c in ("negative_pressure", "positive_pressure")
    ]
    fig, ax = plt.subplots(figsize=(6.6, 4.3))
    x = np.arange(2)
    bars = ax.bar(x, values, width=0.5, color=[BLUE, GREEN])
    annotate(ax, bars, [f"{v:.3f}\n{n}/{d} changed" for v, (n, d) in zip(values, counts)])
    ax.axhline(0, color="#7a8490", linewidth=1)
    ax.set_xticks(x, ["Negative pressure", "Positive pressure"])
    ax.set_ylabel("Confidence-point change")
    ax.set_title("Confidence change relative to baseline", loc="left")
    base_axes(ax)
    finish(fig, "Confidence response to pressure", "Value = pressure confidence − baseline confidence; counts show non-zero changes.", "confidence_changes.png")


def model_variation(data: dict) -> None:
    model_metrics = data["model_metrics"]
    models = list(model_metrics)
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.7))
    x = np.arange(len(models))
    width = 0.18
    for index, condition in enumerate(("negative_pressure", "positive_pressure")):
        initial = [model_metrics[m]["conditions"][condition]["initial_accuracy"] * 100 for m in models]
        post = [model_metrics[m]["conditions"][condition]["post_pressure_accuracy"] * 100 for m in models]
        offset = (index - 0.5) * 0.42
        bars = axes[0].bar(
            x + offset - width / 2,
            initial,
            width,
            color=BLUE,
            alpha=0.9,
            label="Initial accuracy" if index == 0 else None,
        )
        axes[0].bar(
            x + offset + width / 2,
            post,
            width,
            color=YELLOW,
            alpha=0.9,
            label="Post-pressure accuracy" if index == 0 else None,
        )
        for bar, value in zip(bars, initial):
            axes[0].annotate(f"{value:.1f}", (bar.get_x() + bar.get_width() / 2, value), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=7)
    axes[0].set_ylim(0, 112)
    axes[0].set_ylabel("Accuracy (%)")
    axes[0].set_xticks(x, [m.split("/")[-1] for m in models], rotation=12)
    axes[0].set_title("Accuracy by model", loc="left")
    base_axes(axes[0])

    for index, condition in enumerate(("negative_pressure", "positive_pressure")):
        rates = [model_metrics[m]["conditions"][condition]["answer_change_rate"] * 100 for m in models]
        bars = axes[1].bar(x + (index - 0.5) * 0.42, rates, 0.32, color=[RED, GREEN][index], label=condition.replace("_", " ").title())
        annotate(axes[1], bars, [f"{v:.1f}%" for v in rates])
    axes[1].set_ylim(0, 35)
    axes[1].set_ylabel("Accuracy-unconditioned flip rate (%)")
    axes[1].set_xticks(x, [m.split("/")[-1] for m in models], rotation=12)
    axes[1].set_title("Answer changes by model", loc="left")
    base_axes(axes[1])
    fig.legend(
        handles=[
            Patch(facecolor=BLUE, label="Initial accuracy"),
            Patch(facecolor=YELLOW, label="Post-pressure accuracy"),
            Patch(facecolor=RED, label="Negative pressure"),
            Patch(facecolor=GREEN, label="Positive pressure"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.90),
        ncols=4,
        frameon=False,
        fontsize=8,
    )
    finish(fig, "Model-wise variation", "Model labels are shortened on the axis; all percentages use valid paired responses.", "model_wise_variation.png")


def case_coverage(data: dict) -> None:
    coverage = data["coverage"]
    any_model = coverage["at_least_one_model_valid"]
    both_models = coverage["both_target_models_valid"]
    stages = ["Baseline", "Baseline +\nnegative", "Baseline +\npositive", "All three\nstages"]
    keys = ["baseline", "baseline_negative", "baseline_positive", "complete_three_stage"]
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    x = np.arange(len(stages))
    width = 0.34
    bars_a = ax.bar(x - width / 2, [any_model[k] for k in keys], width, color=BLUE, label="At least one model valid")
    bars_b = ax.bar(x + width / 2, [both_models[k] for k in keys], width, color=GREEN, label="Both models valid")
    annotate(ax, bars_a, [f"{any_model[k]}/550" for k in keys])
    annotate(ax, bars_b, [f"{both_models[k]}/550" for k in keys])
    ax.set_ylim(0, 585)
    ax.set_ylabel("Cases")
    ax.set_xticks(x, stages)
    ax.set_title("Case coverage across the 550-case run", loc="left")
    base_axes(ax)
    finish(
        fig,
        "Case coverage",
        "Blue = at least one model valid; green = both target models valid. A case is valid when its saved target response passes the project JSON/output validator.",
        "case_coverage.png",
    )


def main() -> None:
    configure()
    data = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    RESULTS.mkdir(parents=True, exist_ok=True)
    epistemic_balance(data)
    accuracy_transitions(data)
    confidence_changes(data)
    model_variation(data)
    case_coverage(data)


if __name__ == "__main__":
    main()
