from pathlib import Path
import csv
import matplotlib.pyplot as plt

# Locate the output folder beside this script.
output = Path(__file__).resolve().parent / "output"
# Locate the visuals folder inside the output folder.
visuals = output / "visuals"

with (output / "claims_source.csv").open(newline="") as file:
    source = list(csv.DictReader(file))

with (output / "incident_mart.csv").open(newline="") as file:
    incident = list(csv.DictReader(file))

# Identify missing claims by ID, rather than only subtracting counts.
reported_ids = {row["claim_id"] for row in incident}

missing = [
    row for row in source
    if row["claim_id"] not in reported_ids
]

included_count = len(reported_ids)
missing_count = len(missing)
missing_percent = missing_count / len(source) * 100

fig, ax = plt.subplots(figsize=(8, 5))

bars = ax.bar(
    ["Included in dashboard", "Missing from dashboard"],
    [included_count, missing_count],
    color=["#555555", "#C0392B"],
    width=0.55,
)

ax.bar_label(bars, padding=6, fontsize=14)
ax.set_ylabel("Number of closed claims")
ax.set_title(
    f"Missing Claims During the Incident\n"
    f"{missing_count:,} of {len(source):,} claims excluded "
    f"({missing_percent:.0f}%)"
)
ax.set_ylim(0, max(included_count, missing_count) * 1.2)
ax.spines[["top", "right"]].set_visible(False)

fig.text(
    0.5, 0.02,
    "Synthetic Brightline Insurance incident",
    ha="center",
    fontsize=9,
    color="#555555",
)

fig.tight_layout(rect=[0, 0.05, 1, 1])

image_path = output/ visuals / "00_missing_claims_chart.png"
fig.savefig(image_path, dpi=300, bbox_inches="tight")

print(f"Missing claims: {missing_count}")
print(f"Chart saved to: {image_path}")

plt.show()