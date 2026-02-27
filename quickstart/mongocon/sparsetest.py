import os
import sys
import time
import gc
import django
from django.conf import settings
from django.db import connections

# --- 1. DJANGO INITIALIZATION ---

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

DATABASES = {
    'default': {
        'ENGINE': 'django_mongodb_backend',
        'NAME': 'perf_test_regular',
        'HOST': 'mongodb://localhost:27017',
    },
    'reg_db': {
        'ENGINE': 'django_mongodb_backend',
        'NAME': 'perf_test_regular',
        'HOST': 'mongodb://localhost:27017',
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'maxPoolSize': 15,
            'minPoolSize': 10,
            'directConnection': True,
        },
    },
    'spr_db': {
        'ENGINE': 'django_mongodb_backend',
        'NAME': 'perf_test_sparse',
        'HOST': 'mongodb://localhost:27017',
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'maxPoolSize': 15,
            'minPoolSize': 10,
            'directConnection': True,
        },
    }
}

if not settings.configured:
    settings.configure(
        DEBUG=False,
        DATABASES=DATABASES,
        INSTALLED_APPS=[
            'mongocon.apps.MongoenvConfig', 
            'django.contrib.contenttypes',
        ],
        USE_TZ=True,
    )

django.setup()

# Models must be imported after setup
from mongocon.models import Bot, Bot2, InfoNode

print("--- Environment Initialized & Heavyweight Test Ready ---")

# --- 2. UTILITIES ---

def reset_and_verify(alias, model_class):
    """Drops DB and ensures fresh storage state for each run."""
    conn = connections[alias]
    conn.ensure_connection() 
    db_name = conn.settings_dict['NAME']
    
    with conn.cursor():
        client = conn.connection 
        db = client.get_database(db_name) 
        client.drop_database(db_name)
        
        from django.core.management import call_command
        call_command('migrate', database=alias, verbosity=0)
        
        coll = db[model_class._meta.db_table]
        print(f"[{alias}] Physical DB reset. Ready for Heavyweight ingestion.")

def get_physical_metrics(alias, model_class, total_time, count):
    conn = connections[alias]
    conn.ensure_connection()
    db_name = conn.settings_dict['NAME']
    
    with conn.cursor():
        client = conn.connection
        db = client.get_database(db_name)
        stats = db.command("collStats", model_class._meta.db_table)
    
    return {
        "total_time": total_time,
        "avg_ms": (total_time / count) * 1000,
        "logical_size_kb": stats["size"] / 1024,
        "physical_storage_kb": stats["storageSize"] / 1024,
        "avg_obj": stats["avgObjSize"]
    }

def get_payload(i):
    # ~3.5KB of text to simulate a healthy 'description' or 'comment'
    medium_mass = "x" * 3500 
    
    # One populated Embedded Model
    primary = InfoNode(
        label=f"Node_{i}", 
        data_blob=medium_mass, 
        flag=True
    )
    
    # An array with some empty slots to tempt the Sparse logic
    history = [
        InfoNode(label="Old_Node", data_blob="Some history", flag=False),
        InfoNode(label=None, data_blob=None, flag=None) # SPARSIFY ME
    ]

    return {
        "name": i,
        "main_node": primary,
        "node_history": history,
        "client_id": f"client_{i % 100}",
        "description": "Short bio here",
        "tags": ["testing", "4kb", "embedded"],
        "status": "active",
        # Leave 10+ other model fields as None
    }

# --- 3. THE BENCHMARK RUNNER ---

def run_isolated_test(model_class, db_alias, count):
    reset_and_verify(db_alias, model_class)
    
    # --- PHASE A: WARMUP ---
    WARMUP_COUNT = 50 # 50 records @ 500KB = 25MB warmup
    print(f"Pre-heating {db_alias} with {WARMUP_COUNT} heavy records...")
    for i in range(WARMUP_COUNT):
        model_class(**get_payload(i)).save(using=db_alias)
    gc.collect()

    # --- PHASE B: MEASURED TEST ---
    print(f"Generating {count} heavy payloads (~500MB total)...")
    payloads = [get_payload(i) for i in range(count)]
    
    print(f"Starting timed loop for {db_alias} (Throughput Phase)...")
    start_time = time.perf_counter()
    for p in payloads:
        obj = model_class(**p)
        obj.save(using=db_alias)
    end_time = time.perf_counter()
    
    # --- PHASE C: SETTLE & MEASURE ---
    print("Loop finished. Allowing WiredTiger to flush to disk...")
    time.sleep(3) 
    del payloads
    gc.collect()
    
    return get_physical_metrics(db_alias, model_class, end_time - start_time, count)

# --- 4. MAIN ---

def main():
    TEST_COUNT = 100000 #total per suite
    print("\n" + "="*80)
    print("SCIENTIFIC SPARSITY BENCHMARK: HEAVYWEIGHT THROUGHPUT TEST")
    print("="*80)
    print(f"Test Volume: {TEST_COUNT} records (~4kB each) per suite")

    
    # Run Sparse
    spr_res = run_isolated_test(Bot, 'spr_db', TEST_COUNT)
    print(f"Sparse Suite Complete.")


    # Run Regular
    reg_res = run_isolated_test(Bot2, 'reg_db', TEST_COUNT)
    print(f"Regular Suite Complete.")

    # --- FINAL REPORT ---
    print("\n" + "="*80)
    print(f"{'METRIC':<25} | {'REGULAR (Bot2)':<22} | {'SPARSE (Bot)':<22}")
    print("-" * 80)
    print(f"{'Total Time':<25} | {reg_res['total_time']:>18.4f}s | {spr_res['total_time']:>18.4f}s")
    print(f"{'Avg Insert':<25} | {reg_res['avg_ms']:>18.4f}ms | {spr_res['avg_ms']:>18.4f}ms")
    print(f"{'Logical Size (Data)':<25} | {reg_res['logical_size_kb']:>15.2f} KB | {spr_res['logical_size_kb']:>15.2f} KB")
    print(f"{'Physical Size (Disk)':<25} | {reg_res['physical_storage_kb']:>15.2f} KB | {spr_res['physical_storage_kb']:>15.2f} KB")
    print(f"{'Avg Obj Size':<25} | {reg_res['avg_obj']:>17.1f} b  | {spr_res['avg_obj']:>17.1f} b")
    print("="*80)

    # Efficiency Summary
    s_saved = 100 - (spr_res['physical_storage_kb'] / reg_res['physical_storage_kb'] * 100)
    t_over = (spr_res['total_time'] / reg_res['total_time'] * 100) - 100
    
    print(f"RESULT: Sparse saved {s_saved:.2f}% Physical Space with {t_over:+.2f}% Time Overhead.")
    print("="*80)

if __name__ == "__main__":
    main()