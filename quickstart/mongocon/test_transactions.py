import os
import sys
from pymongo import MongoClient
from django_mongodb_backend import transaction # USE THIS

# Add parent directory to sys.path for module resolution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Use replica-mode settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings_mongoenv')

import django
from django.conf import settings

django.setup()

from mongocon.models import Bot2

def retrieve_all_bots():
    print("\n[FINAL VIEW] All objects currently in Bot2 collection:")
    all_docs = Bot2.objects.all()
    
    if not all_docs.exists():
        print("  The collection is empty.")
    else:
        for doc in all_docs:
            # We use __dict__ to see exactly what MongoDB stored
            print(f"  ID: {doc.id} | Name: {doc.name} (Type: {type(doc.name).__name__}) | Status: {doc.status}")

def test_transactions():
    print("\n[TEST] Transactions (MongoDB Backend API):")
    try:
        with transaction.atomic():
            b1 = Bot2.objects.create(name="Trans1", status="t1")
            b2 = Bot2.objects.create(name="Trans2", status="t2")
            print(f"  Created: {b1.id}, {b2.id}")
            raise Exception("Trigger rollback!")
    except Exception as e:
        print("  Exception raised, should rollback:", e)
    # Check if objects exist
    exists = Bot2.objects.filter(name__in=["Trans1", "Trans2"]).exists()
    print("  Objects exist after rollback?", exists)

    # Test on_commit callback
    def after_commit():
        print("  [on_commit] Transaction committed!")
    with transaction.atomic():
        Bot2.objects.create(name="TransCommit", status="ok")
        transaction.on_commit(after_commit)

def test_transaction_with_corrupt():
    print("\n[TEST] Transaction with One Valid and One Faulty Object (Backend Docs Style):")
    try:
        with transaction.atomic():
            Bot2.objects.create(name="TransGood", status="ok")
            # Insert with a type error: name expects a string, give an int
            Bot2.objects.create(name=123, status="ok")
        print("  Transaction committed successfully.")
    except Exception as e:
        print("  Exception during transaction:", e)
    objs = list(Bot2.objects.filter(name__in=["TransGood", 123]))
    for obj in objs:
        print(f"  DB fetch after transaction: {{'name': {obj.name}, 'status': {obj.status}}}")


def test_1_two_valid_documents():
    print("\n[TEST 1] Two Valid Documents (Should Commit):")
    try:
        with transaction.atomic():
            b1 = Bot2.objects.create(name=123, status="active")
            b2 = Bot2.objects.create(name=456, status="active")
            print(f"  Staged: {b1.name} and {b2.name}")
        print("  ✅ Transaction committed successfully.")
    except Exception as e:
        print(f"  ❌ Unexpected Error: {e}")

    print(f"  Verification:")
    retrieve_all_bots()


def test_2_json_instead_of_string():
    print("\n[TEST 2] JSON Object in String Field (The 'Crazy' Test):")
    crazy_payload = {"key": "value", "nested": [1, 2, 3]}
    try:
        with transaction.atomic():
            # Object 1: Normal
            Bot2.objects.create(name="Normal_Doc", status="active")
            # Object 2: Passing a DICT into a field defined as CharField/TextField
            print(f"  Attempting to insert JSON into 'name' field...")
            Bot2.objects.create(name=crazy_payload, status="crazy")
        print("  ✅ Transaction committed successfully (Wait, what?!)")
    except Exception as e:
        print(f"  🛑 Transaction Rolled Back! Error: {e}")

    print(f"  Verification:")
    retrieve_all_bots()

def wipe_bot2_collection():
    """Wipe the Bot2 collection using a replica-set-aware MongoClient."""
    client = MongoClient("mongodb://localhost:27017/?replicaSet=rs0")
    db = client['test']
    db['mongocon_bot2'].delete_many({})
    print('[INFO] Wiped mongocon_bot2 collection (replica mode).')


if __name__ == '__main__':
    wipe_bot2_collection()
    test_1_two_valid_documents()
    wipe_bot2_collection()
    test_2_json_instead_of_string()
