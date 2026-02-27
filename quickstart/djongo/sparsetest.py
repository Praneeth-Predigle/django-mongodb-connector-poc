import os
import sys
import time
import gc
import django
import uuid

# --- 1. PATH & DJANGO SETUP ---
# Ensure we can find the 'bots' module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

from django.conf import settings
from django.db import connections

DATABASES = {
    'default': {
        'ENGINE': 'djongo',
        'NAME': 'perf_test_djongo',
        'CLIENT': {
            'host': 'mongodb://localhost:27017',
            'directConnection': True,
        },
    },
    'djongo_db': {
        'ENGINE': 'djongo',
        'NAME': 'perf_test_djongo',
        'CLIENT': {
            'host': 'mongodb://localhost:27017',
            'directConnection': True,
        },
    }
}

if not settings.configured:
    settings.configure(
        DEBUG=False,
        DATABASES=DATABASES,
        INSTALLED_APPS=[
            'bots',
            'django.contrib.contenttypes',
        ],
        USE_TZ=True,
    )

django.setup()

# Import the model AFTER setup
from bots.models import Bot
print("--- Djongo Heavyweight Environment Initialized ---")

# --- 2. UTILITIES ---

def reset_and_verify(alias):
    """Drops DB and ensures fresh storage state bypassing Django Migrations."""
    conn = connections[alias]
    conn.ensure_connection() 
    db_name = conn.settings_dict['NAME']
    
    # Robustly get the MongoClient
    db_obj = conn.connection 
    client = db_obj.client if hasattr(db_obj, 'client') else db_obj
        
    print(f"[{alias}] Dropping database: {db_name}...")
    client.drop_database(db_name)
    
    # Manually create collection to avoid SQL translation errors
    db = client[db_name]
    collection_name = Bot._meta.db_table
    db.create_collection(collection_name)
    
    print(f"[{alias}] Physical DB reset (Bypassed Migrations). Ready.")

def get_physical_metrics(alias, model_class, total_time, count):
    """Fetches stats using direct PyMongo commands."""
    conn = connections[alias]
    conn.ensure_connection()

    # Djongo gives you a pymongo.database.Database directly
    db = conn.connection  

    try:
        stats = db.command("collStats", model_class._meta.db_table)
        return {
            "total_time": total_time,
            "avg_ms": (total_time / count) * 1000,
            "logical_size_kb": stats.get("size", 0) / 1024,
            "physical_storage_kb": stats.get("storageSize", 0) / 1024,
            "avg_obj": stats.get("avgObjSize", 0)
        }
    except Exception as e:
        print(f"Metrics Error: {e}")
        return {
            "total_time": total_time,
            "avg_ms": (total_time / count) * 1000,
            "logical_size_kb": 0,
            "physical_storage_kb": 0,
            "avg_obj": 0
        }

def get_payload(i):
    """
    Constructs a ~4KB payload. 
    3900 bytes of 'x' plus field keys/values hits the target.
    """
    return {
        "name": i,
        "status": "active",
        "client_id": f"client_{i % 100}",
        "main_node": {
            "label": f"node_{i}",
            "data_blob": "x" * 3900, # This brings the doc to ~4KB total
            "flag": True
        }
    }

# --- 3. THE BENCHMARK RUNNER ---

def run_benchmark(count):
    ALIAS = 'djongo_db'
    reset_and_verify(ALIAS)
    
    # --- PHASE A: WARMUP ---
    WARMUP_COUNT = min(50, count)
    print(f"Pre-heating with {WARMUP_COUNT} records...")
    for i in range(WARMUP_COUNT):
        Bot(**get_payload(i)).save(using=ALIAS)
    gc.collect()

    # --- PHASE B: MEASURED TEST ---
    print(f"Generating {count} payloads in memory...")
    payloads = [get_payload(i) for i in range(count)]
    
    print(f"Starting timed loop for {count} Inserts...")
    start_time = time.perf_counter()
    for p in payloads:
        # Every save() triggers the 'Thing' inheritance and Djongo overhead
        obj = Bot(**p)
        obj.save(using=ALIAS)
    end_time = time.perf_counter()
    
    # --- PHASE C: SETTLE ---
    print("Loop finished. Settling...")
    time.sleep(2) 
    del payloads
    gc.collect()
    
    return get_physical_metrics(ALIAS, Bot, end_time - start_time, count)

# --- 4. MAIN ---

if __name__ == "__main__":
    # SET YOUR TEST COUNT HERE
    TEST_COUNT = 100000 
    
    print("\n" + "="*80)
    print("DJONGO + THING INHERITANCE PERFORMANCE TEST")
    print(f"Document Weight: ~4KB | Count: {TEST_COUNT}")
    print("="*80)
    
    results = run_benchmark(TEST_COUNT)

    print("\n" + "="*80)
    print(f"{'METRIC':<25} | {'DJONGO (py_predigle)':<22}")
    print("-" * 80)
    print(f"{'Total Time':<25} | {results['total_time']:>18.4f}s")
    print(f"{'Avg Insert':<25} | {results['avg_ms']:>18.4f}ms")
    print(f"{'Logical Size (Data)':<25} | {results['logical_size_kb']:>15.2f} KB")
    print(f"{'Physical Size (Disk)':<25} | {results['physical_storage_kb']:>15.2f} KB")
    print(f"{'Avg Obj Size':<25} | {results['avg_obj']:>17.1f} bytes")
    print("="*80)