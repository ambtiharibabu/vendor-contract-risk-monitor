# =============================================================
# generate_data.py
# Generates 300 synthetic vendor contracts and saves to SQLite.
# Can be run directly (python generate_data.py) or imported
# and called as a function by app.py on cloud deploy.
# =============================================================

import sqlite3
import pandas as pd
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker()

def generate_and_save(db_path="vendor_contracts.db"):
    """Generate synthetic vendor data and write to SQLite database."""

    random.seed(42)
    fake.unique.clear()  # reset unique tracker in case function is called again

    NUM_VENDORS = 120
    NUM_CONTRACTS = 300
    SERVICE_TYPES = ["IT", "Logistics", "Legal", "Data"]
    REGIONS = ["Midwest", "Southeast", "Northeast", "West", "Southwest"]

    vendor_pool = []
    for _ in range(NUM_VENDORS):
        vendor_pool.append({
            "vendor_id": fake.unique.bothify(text="VND-####"),
            "vendor_name": fake.company()
        })

    rows = []
    today = datetime.today()

    for i in range(NUM_CONTRACTS):
        vendor = random.choice(vendor_pool)

        start_offset = random.randint(180, 1095)
        contract_start = today - timedelta(days=start_offset)

        contract_length = random.randint(365, 1095)
        contract_end = contract_start + timedelta(days=contract_length)

        cert_offset = random.randint(-60, 60)
        cert_expiry = contract_end + timedelta(days=cert_offset)

        days_to_expiry = (contract_end - today).days

        if days_to_expiry < 0:
            status = "Expired"
        elif days_to_expiry <= 90:
            status = "Expiring"
        else:
            status = "Active"

        rows.append({
            "vendor_id": vendor["vendor_id"],
            "vendor_name": vendor["vendor_name"],
            "service_type": random.choice(SERVICE_TYPES),
            "contract_start": contract_start.strftime("%Y-%m-%d"),
            "contract_end": contract_end.strftime("%Y-%m-%d"),
            "renewal_lead_days": random.choice([30, 45, 60, 90]),
            "sla_score": random.randint(45, 100),
            "data_issue_flags": random.randint(0, 12),
            "cert_expiry_date": cert_expiry.strftime("%Y-%m-%d"),
            "status": status,
            "region": random.choice(REGIONS)
        })

    df = pd.DataFrame(rows)
    conn = sqlite3.connect(db_path)
    df.to_sql("vendor_contracts", conn, if_exists="replace", index=False)
    conn.close()
    print(f"✅ Done. {len(df)} contracts written to {db_path}")

# Allows both: python generate_data.py  AND  from generate_data import generate_and_save
if __name__ == "__main__":
    generate_and_save()