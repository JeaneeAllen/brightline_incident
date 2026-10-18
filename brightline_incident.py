from pathlib import Path
from datetime import date, timedelta
from collections import Counter
import csv
import json
import sqlite3


# All data, timestamps, and costs are synthetic.
OUTPUT = Path("output")
OUTPUT.mkdir(exist_ok=True)

INCIDENT_DATE = date(2026, 10, 15)


def save_csv(filename, rows):
    """Save a nonempty list of dictionaries as a CSV."""
    with (OUTPUT / filename).open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_text(filename, text):
    (OUTPUT / filename).write_text(text.strip() + "\n")


def make_claims():
    """Generate 1,000 unique closed claims."""
    return [
        {
            "claim_id": f"CLM{i:04d}",
            "policy_reference": f"POL{i:04d}",
            "status": "Closed",
            "severity": "High" if i <= 380 else "Standard",
            "severity_score": 8 if i <= 380 else 3,
        }
        for i in range(1, 1001)
    ]


def make_policy_feed(claims, changed=False):
    """
    The specialty feed changes policy_id to policy_key.
    The standard feed keeps policy_id.
    """
    rows = []

    for claim in claims:
        specialty = claim["severity"] == "High"
        key_name = "policy_key" if changed and specialty else "policy_id"

        rows.append({
            "feed": "specialty" if specialty else "standard",
            key_name: claim["policy_reference"],
        })

    return rows


def load_policy_staging(connection, feed, corrected=False):
    """
    Flexible ingestion accepts either source field.
    The faulty version leaves policy_id null for renamed records.
    """
    connection.execute("DELETE FROM policy_staging")

    records = []
    for row in feed:
        policy_id = row.get("policy_id")

        if corrected and policy_id is None:
            policy_id = row.get("policy_key")

        records.append((row["feed"], policy_id, row.get("policy_key")))

    connection.executemany(
        "INSERT INTO policy_staging VALUES (?, ?, ?)",
        records,
    )


def build_mart(connection):
    connection.execute("DROP TABLE IF EXISTS claims_mart")

    connection.execute("""
        CREATE TABLE claims_mart AS
        SELECT c.*
        FROM claims_staging AS c
        INNER JOIN policy_staging AS p
            ON c.policy_reference = p.policy_id
        WHERE c.status = 'Closed'
    """)


def profile(connection, table, run):
    rows = connection.execute(
        f"SELECT severity, severity_score FROM {table}"
    ).fetchall()

    categories = Counter(row[0] for row in rows)
    total = len(rows)

    return {
        "run": run,
        "table": table,
        "row_count": total,
        "severity_null_rate": (
            sum(row[0] is None for row in rows) / total
        ),
        "severity_cardinality": len(categories),
        "high_count": categories["High"],
        "high_share": categories["High"] / total,
        "standard_count": categories["Standard"],
        "standard_share": categories["Standard"] / total,
        "mean_severity": round(
            sum(row[1] for row in rows) / total, 2
        ),
    }


def unmatched_keys(connection):
    return connection.execute("""
        SELECT COUNT(*)
        FROM claims_staging AS c
        LEFT JOIN policy_staging AS p
            ON c.policy_reference = p.policy_id
        WHERE p.policy_id IS NULL
    """).fetchone()[0]


def count_rows(connection, table):
    return connection.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]


claims = make_claims()
old_feed = make_policy_feed(claims)
changed_feed = make_policy_feed(claims, changed=True)

save_csv("claims_source.csv", claims)
save_text("policy_feed_before.json", json.dumps(old_feed, indent=2))
save_text("policy_feed_incident.json", json.dumps(changed_feed, indent=2))

connection = sqlite3.connect(":memory:")

connection.executescript("""
    CREATE TABLE claims_staging (
        claim_id TEXT PRIMARY KEY,
        policy_reference TEXT,
        status TEXT,
        severity TEXT,
        severity_score INTEGER
    );

    CREATE TABLE policy_staging (
        feed TEXT,
        policy_id TEXT,
        policy_key TEXT
    );
""")

connection.executemany(
    "INSERT INTO claims_staging VALUES (?, ?, ?, ?, ?)",
    [
        (
            row["claim_id"],
            row["policy_reference"],
            row["status"],
            row["severity"],
            row["severity_score"],
        )
        for row in claims
    ],
)

# Baseline: old policy feed and original mapping.
load_policy_staging(connection, old_feed)
build_mart(connection)
baseline = profile(connection, "claims_mart", "baseline")

# Incident: new feed, but original mapping and SQL.
load_policy_staging(connection, changed_feed)
build_mart(connection)

incident = profile(connection, "claims_mart", "incident")
incident_unmatched = unmatched_keys(connection)

incident_rows = [
    dict(zip(
        ["claim_id", "policy_reference", "status",
         "severity", "severity_score"],
        row,
    ))
    for row in connection.execute("SELECT * FROM claims_mart")
]
save_csv("incident_mart.csv", incident_rows)

# Counterfactual: same input and SQL, corrected mapping only.
load_policy_staging(connection, changed_feed, corrected=True)
build_mart(connection)

corrected = profile(connection, "claims_mart", "corrected")
corrected_unmatched = unmatched_keys(connection)

corrected_rows = [
    dict(zip(
        ["claim_id", "policy_reference", "status",
         "severity", "severity_score"],
        row,
    ))
    for row in connection.execute("SELECT * FROM claims_mart")
]
save_csv("corrected_mart.csv", corrected_rows)

save_csv("distribution_profiles.csv", [baseline, incident, corrected])

# Fourteen normal runs, followed by the incident.
history = []
for offset in range(14, 0, -1):
    run_date = INCIDENT_DATE - timedelta(days=offset)
    history.append({
        "run_date": str(run_date),
        "source_rows": 1000,
        "staging_rows": 1000,
        "mart_rows": 1000,
        "run_status": "success",
    })

history.append({
    "run_date": str(INCIDENT_DATE),
    "source_rows": 1000,
    "staging_rows": 1000,
    "mart_rows": incident["row_count"],
    "run_status": "success",
})
save_csv("volume_history.csv", history)

save_csv("freshness.csv", [
    {
        "asset": "claims_source",
        "completed_at": "2026-10-15T03:00:00-05:00",
        "business_date": "2026-10-14",
        "status": "success",
    },
    {
        "asset": "claims_staging",
        "completed_at": "2026-10-15T03:20:00-05:00",
        "business_date": "2026-10-14",
        "status": "success",
    },
    {
        "asset": "claims_mart",
        "completed_at": "2026-10-15T03:30:00-05:00",
        "business_date": "2026-10-14",
        "status": "success",
    },
    {
        "asset": "claims_dashboard",
        "completed_at": "2026-10-15T03:40:00-05:00",
        "business_date": "2026-10-14",
        "status": "success",
    },
])

save_csv("schema_changes.csv", [{
    "deployed_at": "2026-10-15T01:50:00-05:00",
    "asset": "specialty_policy_feed",
    "change": "policy_id renamed to policy_key",
    "compatibility": "breaking for the existing mapping",
    "ingestion_behavior": "accept new field; old field becomes null",
    "notification": "no downstream notification",
}])

save_csv("join_checks.csv", [
    {
        "run": "incident",
        "unmatched_claims": incident_unmatched,
        "policy_id_null_rate": 0.38,
    },
    {
        "run": "corrected",
        "unmatched_claims": corrected_unmatched,
        "policy_id_null_rate": 0.0,
    },
])

save_text("lineage.md", """
# Synthetic lineage graph

```mermaid
flowchart TD
    A["Claims source"] --> C["Claims staging"]
    B["Policy feeds"] --> D["Policy staging"]
    C --> E["Claims mart"]
    D --> E
    E --> F["Severity dashboard"]
    F --> G["Staffing decision"]
```
""")
