"""
scripts/seed_users.py
─────────────────────
Standalone seed script — does NOT use st.secrets or database/mongo.py.
Connects directly to MongoDB Atlas using your URI from .env or the terminal.

Run from the project root:
    python scripts/seed_users.py
"""

import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path

# Load .env file if present (picks up MONGO_URI)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # dotenv not installed, that's fine

from pymongo import MongoClient

# ── Get URI ───────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    print("\n❌ MONGO_URI not found.")
    print("   Set it one of these ways:\n")
    print("   Option A — add it to your .env file:")
    print('   MONGO_URI="mongodb+srv://..."\n')
    print("   Option B — set it in your terminal before running:")
    print('   export MONGO_URI="mongodb+srv://..."   # Mac/Linux')
    print('   set MONGO_URI=mongodb+srv://...        # Windows\n')
    sys.exit(1)

# ── Connect directly (no st.secrets) ─────────────────────────────────────────
print(f"\n🔗 Connecting to MongoDB Atlas...")
try:
    client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")   # will raise if connection fails
    print("✅ Connected successfully.\n")
except Exception as e:
    print(f"\n❌ Could not connect to MongoDB: {e}")
    print("   Double-check your MONGO_URI and that your IP is whitelisted in Atlas.")
    sys.exit(1)

db = client.kayfa_crm

# ── Define your users ─────────────────────────────────────────────────────────
# role must be "customer" or "agent"
USERS = [
    {"username": "agent1",    "password": "0000",    "role": "agent"},
    {"username": "agent2",    "password": "0000",    "role": "agent"},
    {"username": "customer1", "password": "1234", "role": "customer"},
    {"username": "customer2", "password": "1234", "role": "customer"},
]

# ── Seed ──────────────────────────────────────────────────────────────────────
print("Seeding users into kayfa_crm.users...\n")
created = 0
skipped = 0

for u in USERS:
    username = u["username"].strip().lower()
    existing = db.users.find_one({"username": username})
    if existing:
        print(f"  ⚠️  Already exists (skipped): [{u['role']}] {username}")
        skipped += 1
    else:
        db.users.insert_one({
            "username": username,
            "password_hash": hashlib.sha256(u["password"].encode()).hexdigest(),
            "role": u["role"],
            "created_at": datetime.now().isoformat(),
        })
        print(f"  ✅ Created: [{u['role']}] {username}")
        created += 1

print(f"\n─────────────────────────────")
print(f"  Created: {created}  |  Skipped: {skipped}")
print(f"─────────────────────────────")

# ── Verify by reading back ────────────────────────────────────────────────────
print("\n📋 Current users in kayfa_crm.users:\n")
all_users = list(db.users.find({}, {"_id": 0, "password_hash": 0}))
if not all_users:
    print("  (none found — something went wrong)")
else:
    for u in all_users:
        print(f"  [{u['role']}] {u['username']} — {u.get('created_at','')[:10]}")

print("\nDone ✓")