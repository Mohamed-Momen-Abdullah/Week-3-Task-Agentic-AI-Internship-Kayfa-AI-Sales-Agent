# paste this into a verify_users.py and run it once
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.mongo import db

users = list(db.users.find({}, {"_id": 0, "password_hash": 0}))  # hides the hash
if not users:
    print("❌ No users found — did the seed script run successfully?")
else:
    print(f"✅ Found {len(users)} user(s):\n")
    for u in users:
        print(f"  [{u['role']}] {u['username']} — created {u.get('created_at', 'N/A')[:10]}")
