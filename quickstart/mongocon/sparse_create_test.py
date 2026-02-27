import os
import sys
import django
from django.conf import settings
from pymongo import MongoClient

# 1. --- PATH SETUP ---
# Make project root importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 2. --- DJANGO INITIALIZATION ---
# This MUST happen before you import your models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            "default": {
                "ENGINE": "django_mongodb_backend",
                "NAME": "mongoenv_sparse_test",
                "HOST": "mongodb://localhost:27017",
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'mongocon',  # This tells Django 'Bot' belongs to the 'mongocon' app
        ],
        USE_TZ=True,
    )

django.setup()

# 3. --- MODEL IMPORTS ---
# Import only AFTER django.setup()
from mongocon.models import Bot

# 4. --- TEST LOGIC ---

def run_sparse_experiment():
    """Wipes the collection and tests the custom sparse save logic."""
    
    # Setup raw Mongo client for inspection
    client = MongoClient("mongodb://localhost:27017")
    db = client["mongoenv_sparse_test"]
    collection = db["mongocon_bot"] # Ensure this matches Bot._meta.db_table
    
    print(f"[INFO] Wiping collection 'mongocon_bot' in DB 'mongoenv_sparse_test'...")
    collection.delete_many({})

    # BOT 1: Provide 'type', omit 'deleted_status'
    print("\n[TEST] Creating Bot 1 (omitting deleted_status):")
    bot1 = Bot(
        name=500,
        description='Bot 1 description',
        client_id='C1',
        slug='S1',
        status='active',
        type='type_a',
        tags=['t1']
    )
    bot1.save()

    # BOT 2: Provide 'deleted_status', omit 'type'
    print("[TEST] Creating Bot 2 (omitting type):")
    bot2 = Bot(
        name=501,
        description='Bot 2 description',
        client_id='C2',
        slug='S2',
        status='inactive',
        deleted_status='N',
        tags=['t2']
    )
    bot2.save()

    # --- VERIFICATION ---
    print("\n[RESULT] Verifying BSON keys in MongoDB:")
    all_docs = list(collection.find())
    
    for d in all_docs:
        name = d.get('name')
        keys = list(d.keys())
        print(f"\n- Bot Name: {name}")
        print(f"  Keys present: {keys}")
        
        if name == 500:
            if 'deleted_status' not in d:
                print("  ✅ SUCCESS: 'deleted_status' is missing from BSON.")
            else:
                print("  ❌ FAILURE: 'deleted_status' exists as null.")
                
        if name == 501:
            if 'type' not in d:
                print("  ✅ SUCCESS: 'type' is missing from BSON.")
            else:
                print("  ❌ FAILURE: 'type' exists as null.")

    client.close()

if __name__ == '__main__':
    run_sparse_experiment()
    print("\nExperiment finished.")