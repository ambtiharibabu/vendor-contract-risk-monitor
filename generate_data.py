import sqlite3
import pandas as pd
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker()
random.seed(42)  # ensures same data every run — good for reproducibility

# --- CONFIG ---
NUM_VENDORS = 120        # unique vendor companies
NUM_CONTRACTS = 300      # some vendors will have multiple contracts
SERVICE_TYPES = ["IT", "Logistics", "Legal", "Data"]
REGIONS = ["Midwest", "Southeast", "Northeast", "West", "Southwest"]

# --- BUILD VENDOR POOL ---
vendor_pool = []
for _ in range(NUM_VENDORS):
    vendor_pool.append({
        "vendor_id": fake.unique.bothify(text="VND-####"),  # e.g. VND-4821
        "vendor_name": fake.company()
    })

# --- BUILD CONTRACT ROWS ---
rows = []
today = datetime.today()

for i in range(NUM_CONTRACTS):
    vendor = random.choice(vendor_pool)  # allows duplicate vendors → multiple contracts

    # contract start: anywhere from 3 years ago to 6 months ago
    start_offset = random.randint(180, 1095)
    contract_start = today - timedelta(days=start_offset)

    # contract length: 1 to 3 years
    contract_length = random.randint(365, 1095)
    contract_end = contract_start + timedelta(days=contract_length)

    # cert expiry: randomly within ±60 days of contract end (realistic overlap)
    cert_offset = random.randint(-60, 60)
    cert_expiry = contract_end + timedelta(days=cert_offset)

    # days until contract ends (negative = already expired)
    days_to_expiry = (contract_end - today).days

    # assign status bucket
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
        "renewal_lead_days": random.choice([30, 45, 60, 90]),  # how early to start renewal
        "sla_score": random.randint(45, 100),       # 0–100; lower = riskier
        "data_issue_flags": random.randint(0, 12),  # count of logged data problems
        "cert_expiry_date": cert_expiry.strftime("%Y-%m-%d"),
        "status": status,
        "region": random.choice(REGIONS)
    })

# --- SAVE TO SQLITE ---
df = pd.DataFrame(rows)

conn = sqlite3.connect("vendor_contracts.db")  # creates the .db file if it doesn't exist
df.to_sql("vendor_contracts", conn, if_exists="replace", index=False)  # writes as a table
conn.close()

print(f"✅ Done. {len(df)} contracts written to vendor_contracts.db")
print(df["status"].value_counts())  # quick sanity check on status distribution