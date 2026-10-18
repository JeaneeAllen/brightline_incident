from pathlib import Path
import csv
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


# Paths work even when you run the script from another folder.
BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "output"
VISUALS = OUTPUT / "visuals"
VISUALS.mkdir(parents=True, exist_ok=True)

DARK = "#333333"
GRAY = "#777777"
LIGHT = "#EEEEEE"
RED = "#B83232"

plt.rcParams.update({
    "font.size": 12,
    "axes.titlesize": 18,
    "axes.labelsize": 12,
    "figure.facecolor": "white",
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def read_csv(filename):
    path = OUTPUT / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run brightline_incident.py first."
        )

    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def save_figure(fig, filename, footer):
    fig.text(
        0.5, 0.025, footer,
        ha="center", fontsize=10, color=GRAY,
    )
    path = VISUALS / filename
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def add_box(ax, x, y, width, height, text, highlight=False):
    box = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.012",
        facecolor="#FCEDED" if highlight else LIGHT,
        edgecolor=RED if highlight else DARK,
        linewidth=1.7,
        zorder=2,
    )
    ax.add_patch(box)

    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center", va="center",
        fontsize=12,
        color=DARK,
        zorder=3,
    )


def connect(ax, start, end, highlight=False):
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "->",
            "color": RED if highlight else GRAY,
            "lw": 2,
            "shrinkA": 3,
            "shrinkB": 3,
        },
        zorder=1,
    )


# ----------------------------------------------------------
# 1. VOLUME HISTORY
# ----------------------------------------------------------
history = read_csv("volume_history.csv")

dates = [
    datetime.strptime(row["run_date"], "%Y-%m-%d")
    for row in history
]
source = [int(row["source_rows"]) for row in history]
staging = [int(row["staging_rows"]) for row in history]
mart = [int(row["mart_rows"]) for row in history]

fig, ax = plt.subplots(figsize=(11, 5.5))

# Source and staging overlap in this synthetic dataset.
ax.plot(
    dates, source,
    color=DARK, linewidth=4,
    label="Source",
)
ax.plot(
    dates, staging,
    color="white", linestyle=":", linewidth=2,
)
# Separate legend handle makes the overlap easy to explain.
ax.plot(
    [], [],
    color=GRAY, linestyle=":", linewidth=2,
    label="Staging: same counts as source",
)
ax.plot(
    dates, mart,
    color=RED, linestyle="--",
    marker="o", markersize=5,
    linewidth=2, label="Reporting mart",
)

expected = source[-1]
actual = mart[-1]
drop = (expected - actual) / expected * 100

ax.annotate(
    f"Incident: {actual:,} claims\n{drop:.0f}% below source",
    xy=(dates[-1], actual),
    xytext=(-170, 45),
    textcoords="offset points",
    arrowprops={"arrowstyle": "->", "color": RED},
    color=RED,
    fontsize=12,
)

tick_positions = list(range(0, len(dates), 3))
if len(dates) - 1 not in tick_positions:
    tick_positions.append(len(dates) - 1)

ax.set_xticks([dates[i] for i in tick_positions])
ax.set_xticklabels([
    dates[i].strftime("%b %d") for i in tick_positions
])

ax.set_title("Volume History: Loss Appears in the Reporting Mart")
ax.set_ylabel("Closed-claim rows")
ax.set_xlabel("Run date")
ax.set_ylim(0, max(source + staging + mart) * 1.2)
ax.grid(axis="y", alpha=0.2)
ax.legend(loc="lower left", frameon=False)

fig.tight_layout(rect=[0, 0.08, 1, 1])
save_figure(
    fig,
    "01_volume_history.png",
    "Synthetic incident data | Source and staging overlap at 1,000 rows",
)


# ----------------------------------------------------------
# 2. FRESHNESS
# ----------------------------------------------------------
freshness = read_csv("freshness.csv")

table_rows = []
for row in freshness:
    completed = datetime.fromisoformat(row["completed_at"])
    table_rows.append([
        row["asset"],
        completed.strftime("%I:%M %p").lstrip("0"),
        row["business_date"],
        row["status"].capitalize(),
    ])

fig, ax = plt.subplots(figsize=(11, 4.8))
ax.axis("off")

ax.set_title(
    "Freshness: Jobs Completed for the Expected Business Date",
    pad=20,
)

table = ax.table(
    cellText=table_rows,
    colLabels=["Asset", "Completed", "Business date", "Job status"],
    cellLoc="center",
    colWidths=[0.34, 0.20, 0.25, 0.21],
    bbox=[0, 0.25, 1, 0.60],
)

table.auto_set_font_size(False)
table.set_fontsize(12)

for (row_index, column_index), cell in table.get_celld().items():
    cell.set_edgecolor("white")
    if row_index == 0:
        cell.set_facecolor(DARK)
        cell.set_text_props(color="white", weight="bold")
    else:
        cell.set_facecolor(LIGHT if row_index % 2 else "#FAFAFA")

ax.text(
    0.5, 0.10,
    "Successful execution does not prove complete data.",
    transform=ax.transAxes,
    ha="center", fontsize=13, color=RED,
)

save_figure(
    fig,
    "02_freshness.png",
    "Synthetic incident data | Completion times: America/Chicago",
)


# ----------------------------------------------------------
# 3. SCHEMA CHANGE
# ----------------------------------------------------------
schema = read_csv("schema_changes.csv")
change = schema[0]
deployed = datetime.fromisoformat(change["deployed_at"])
release_time = deployed.strftime("%I:%M %p").lstrip("0")

join_checks = read_csv("join_checks.csv")
incident_check = next(
    row for row in join_checks if row["run"] == "incident"
)
unmatched = int(incident_check["unmatched_claims"])

fig, ax = plt.subplots(figsize=(11, 6.5))
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

ax.set_title("Schema Change: Accepted Input, Broken Mapping", pad=15)

add_box(
    ax, 0.05, 0.68, 0.36, 0.17,
    "Before release\nSpecialty feed: policy_id",
)
add_box(
    ax, 0.59, 0.68, 0.36, 0.17,
    f"After {release_time} release\nSpecialty feed: policy_key",
    highlight=True,
)
connect(ax, (0.41, 0.765), (0.59, 0.765), highlight=True)

add_box(
    ax, 0.27, 0.38, 0.46, 0.18,
    "Original mapping still expects policy_id\n"
    "Renamed records receive NULL",
    highlight=True,
)
connect(ax, (0.77, 0.68), (0.50, 0.56), highlight=True)

add_box(
    ax, 0.27, 0.08, 0.46, 0.18,
    f"INNER JOIN cannot match {unmatched:,} claims\n"
    "Reporting output is incomplete",
    highlight=True,
)
connect(ax, (0.50, 0.38), (0.50, 0.26), highlight=True)

save_figure(
    fig,
    "03_schema_change.png",
    "Synthetic incident mechanism | Flexible ingestion allows execution to continue",
)


# ----------------------------------------------------------
# 4. LINEAGE
# ----------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 8))
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

ax.set_title("Lineage: Upstream Change and Downstream Impact", pad=15)

add_box(ax, 0.05, 0.81, 0.35, 0.11, "Claims source")
add_box(
    ax, 0.60, 0.81, 0.35, 0.11,
    "Policy feeds\nSpecialty key renamed",
    highlight=True,
)

add_box(ax, 0.05, 0.60, 0.35, 0.11, "Claims staging\n1,000 claims")
add_box(
    ax, 0.60, 0.60, 0.35, 0.11,
    f"Policy staging\n{unmatched:,} unmatched claim keys",
    highlight=True,
)

add_box(
    ax, 0.30, 0.39, 0.40, 0.11,
    f"Claims mart\n{actual:,} claims after join",
    highlight=True,
)
add_box(
    ax, 0.30, 0.21, 0.40, 0.10,
    "Severity dashboard",
    highlight=True,
)
add_box(
    ax, 0.30, 0.04, 0.40, 0.10,
    "Adjuster staffing decision",
    highlight=True,
)

connect(ax, (0.225, 0.81), (0.225, 0.71))
connect(ax, (0.775, 0.81), (0.775, 0.71), highlight=True)

connect(ax, (0.225, 0.60), (0.40, 0.50))
connect(ax, (0.775, 0.60), (0.60, 0.50), highlight=True)

connect(ax, (0.50, 0.39), (0.50, 0.31), highlight=True)
connect(ax, (0.50, 0.21), (0.50, 0.14), highlight=True)

save_figure(
    fig,
    "04_lineage.png",
    "Synthetic dependency map | Red highlights the affected path and consumers",
)

print("\nAll four visuals created successfully.")