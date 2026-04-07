# =============================================================
# risk_engine.py
# Reads vendor contracts from SQLite, calculates risk metrics,
# and returns an enriched DataFrame ready for the dashboard.
# =============================================================

import sqlite3
import pandas as pd
from datetime import datetime

# ------------------------------------------------------------------
# LOAD DATA
# ------------------------------------------------------------------

def load_contracts(db_path="vendor_contracts.db"):
    """Pull the vendor_contracts table from SQLite into a DataFrame."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM vendor_contracts", conn)
    conn.close()
    return df


# ------------------------------------------------------------------
# RISK CALCULATIONS
# ------------------------------------------------------------------

def calculate_risk(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived columns:
      - days_to_expiry     : calendar days until contract_end
      - expiry_window      : '30 Days', '60 Days', '90 Days', or 'OK'
      - risk_score         : composite 0–100 score (lower = riskier)
      - risk_tier          : 'High' / 'Medium' / 'Low' based on risk_score
      - root_cause_tags    : comma-separated reasons why a vendor is flagged
      - renewal_due_date   : the date by which renewal action should start
    """

    today = datetime.today()

    # Convert date strings to real datetime objects so we can do math on them
    df["contract_end"]   = pd.to_datetime(df["contract_end"])
    df["contract_start"] = pd.to_datetime(df["contract_start"])
    df["cert_expiry_date"] = pd.to_datetime(df["cert_expiry_date"])

    # Integer count of days remaining (negative = already expired)
    df["days_to_expiry"] = (df["contract_end"] - today).dt.days

    # ---- EXPIRY WINDOW ----
    # Bucket contracts into renewal urgency windows
    def assign_window(days):
        if days < 0:
            return "Expired"
        elif days <= 30:
            return "30 Days"
        elif days <= 60:
            return "60 Days"
        elif days <= 90:
            return "90 Days"
        else:
            return "OK"

    df["expiry_window"] = df["days_to_expiry"].apply(assign_window)

    # ---- RISK SCORE ----
    # Composite score = weighted blend of three signals.
    # All three components are normalized to 0–100 before weighting,
    # so no single signal dominates just because its raw range is larger.

    # Component 1: SLA score — already 0–100; higher is better, so we invert
    # (a vendor with sla_score=95 gets sla_risk=5; one with 50 gets sla_risk=50)
    sla_risk = 100 - df["sla_score"]

    # Component 2: Data issue flags — normalize by dividing by max observed value
    # so a vendor with the most flags gets 100, others scale proportionally
    max_flags = df["data_issue_flags"].max() if df["data_issue_flags"].max() > 0 else 1
    data_risk = (df["data_issue_flags"] / max_flags) * 100

    # Component 3: Expiry urgency — how close to expiry, mapped to 0–100
    # Contracts expiring in ≤90 days get higher urgency; already expired = max urgency
    def expiry_urgency(days):
        if days < 0:
            return 100       # expired = maximum urgency
        elif days <= 90:
            # linear scale: 0 days left → 100 urgency, 90 days left → 0 urgency
            return round((1 - days / 90) * 100, 1)
        else:
            return 0         # more than 90 days out = no urgency signal

    urgency_risk = df["days_to_expiry"].apply(expiry_urgency)

    # Weighted average: expiry urgency weighted heaviest for a compliance use case
    df["risk_score"] = (
        sla_risk    * 0.30 +   # 30% weight — ongoing performance signal
        data_risk   * 0.25 +   # 25% weight — data quality / operational signal
        urgency_risk * 0.45    # 45% weight — time pressure signal
    ).round(1)

    # ---- RISK TIER ----
    def assign_tier(score):
        if score >= 65:
            return "High"
        elif score >= 35:
            return "Medium"
        else:
            return "Low"

    df["risk_tier"] = df["risk_score"].apply(assign_tier)

    # ---- ROOT CAUSE TAGS ----
    # Each flag is an independent check; a vendor can carry multiple tags.
    # Tags feed the bar chart on the dashboard.

    def build_root_cause(row):
        tags = []

        if row["sla_score"] < 70:
            tags.append("SLA Breach")

        if row["data_issue_flags"] >= 5:
            tags.append("Data Issues")

        # Cert expiry within 30 days of today (separate from contract expiry)
        cert_days = (row["cert_expiry_date"] - today).days
        if cert_days <= 30:
            tags.append("Expired Cert")

        if row["days_to_expiry"] <= 30 and row["days_to_expiry"] >= 0:
            tags.append("Expiring Soon")

        if row["days_to_expiry"] < 0:
            tags.append("Contract Expired")

        # Vendor hasn't left enough lead time to renew before expiry
        if 0 <= row["days_to_expiry"] < row["renewal_lead_days"]:
            tags.append("Renewal Overdue")

        # Vendor with no flags is clean
        return ", ".join(tags) if tags else "No Issues"

    df["root_cause_tags"] = df.apply(build_root_cause, axis=1)  # axis=1 = apply row by row

    # ---- RENEWAL DUE DATE ----
    # The date an analyst should have started the renewal conversation
    df["renewal_due_date"] = (
        df["contract_end"] - pd.to_timedelta(df["renewal_lead_days"], unit="D")
    )

    return df


# ------------------------------------------------------------------
# QUICK TEST — run this file directly to verify output
# ------------------------------------------------------------------

if __name__ == "__main__":
    df = load_contracts()
    df = calculate_risk(df)

    print("\n--- SAMPLE (5 rows) ---")
    print(df[["vendor_name", "days_to_expiry", "expiry_window",
              "risk_score", "risk_tier", "root_cause_tags"]].head())

    print("\n--- RISK TIER DISTRIBUTION ---")
    print(df["risk_tier"].value_counts())

    print("\n--- EXPIRY WINDOW DISTRIBUTION ---")
    print(df["expiry_window"].value_counts())

    print("\n--- TOP 5 ROOT CAUSE TAGS ---")
    # Explode comma-separated tags into individual rows for counting
    tag_series = df["root_cause_tags"].str.split(", ").explode()
    print(tag_series.value_counts().head())