import os
import sys
import time
import statistics
import random
import gc
import json
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

import django
from django.conf import settings
from django.db import connections, close_old_connections

if not settings.configured:
    settings.configure(
        DEBUG=False,  # FIX: Turn off DEBUG for performance
        DATABASES={
            'default': {
                'ENGINE': 'django_mongodb_backend',
                'NAME': 'mongoenv_perf_test',
                'HOST': 'mongodb://localhost:27017',
                'CONN_MAX_AGE': 400,  # 6.67 minutes - ensures connections persist during benchmarks
                'OPTIONS': {
                    'maxPoolSize': 15,  # Over-provision to ensure threads never hang
                    'minPoolSize': 10,
                    'serverSelectionTimeoutMS': 5000,
                    'directConnection': True,  # Often helps in local dev benchmarks
                },
            }
        },
        INSTALLED_APPS=[
            'mongocon.apps.MongoenvConfig',
            'django.contrib.contenttypes',
        ],
        USE_TZ=True,
    )

django.setup()

from pymongo import MongoClient

# ---------------------------------------------------------
# NUCLEAR WORKAROUND: Fix thread-local connection race condition
# ---------------------------------------------------------
from django_mongodb_backend.base import DatabaseWrapper

def patched_auto_encryption_opts(self):
    # If the thread hasn't opened the connection yet, 
    # connection is None. We return None for encryption opts.
    if self.connection is None:
        return None
    # If connection exists but _options is missing (rare)
    if not hasattr(self.connection, '_options'):
        return None
    return self.connection._options.auto_encryption_opts

# Apply the patch directly to the class method
DatabaseWrapper.auto_encryption_opts = property(patched_auto_encryption_opts)
# ---------------------------------------------------------

from mongocon.models import Bot


def time_operation(func, *args):
    close_old_connections()  # Clean up any weird thread-local state
    start = time.perf_counter()
    result = func(*args)
    end = time.perf_counter()
    return result, end - start


def run_suite(func, ids, runs=30):
    times = []
    for _ in range(runs):
        target = random.choice(ids)
        _, elapsed = time_operation(func, target)
        times.append(elapsed)
        time.sleep(0.02)

    return {
        "avg": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "stdev": statistics.stdev(times),
    }


def run_delete_suite(func, ids):
    """Special suite for delete operations - ensures each ID is used exactly once"""
    times = []
    # Copy the list so we don't mutate the original
    targets = list(ids)
    random.shuffle(targets)

    for _ in range(30):
        if not targets: break
        target = targets.pop()  # Ensure we never delete the same ID twice
        _, elapsed = time_operation(func, target)
        times.append(elapsed)
        time.sleep(0.02)

    return {
        "avg": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "stdev": statistics.stdev(times),
    }


def run_concurrent_suite(func, ids, workers=12, total_runs=100):
    """Run operations concurrently to simulate production load"""
    # FORCE Django to initialize the connection in the main thread first
    connections['default'].ensure_connection()
    
    times = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit tasks
        futures = [executor.submit(time_operation, func, random.choice(ids))
                  for _ in range(total_runs)]
        for future in futures:
            _, elapsed = future.result()
            times.append(elapsed)

    sorted_times = sorted(times)
    return {
        "avg": statistics.mean(times),
        "p95": sorted_times[int(len(times) * 0.95)],  # 95th percentile
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "stdev": statistics.stdev(times),
        "throughput": len(times) / sum(times),  # Operations per second
        "total_ops": len(times),
    }


# ------------------------
# Warmup Functions
# ------------------------

def warmup_operations():
    """Warm up connection pool and JIT compiler with safe operations"""
    print("🔥 Warming up connection pool and JIT compiler...")

    # Create warmup data
    warmup_ids = []
    for i in range(20):  # Small warmup dataset
        try:
            bot_id = create_bot(f"warmup_{i}")
            warmup_ids.append(bot_id)
        except:
            pass  # Ignore duplicates or errors during warmup

    if not warmup_ids:
        # If warmup creation failed, try to get existing IDs
        warmup_ids = list(Bot.objects.filter(name__startswith="Bot ").values_list('id', flat=True)[:20])

    if warmup_ids:
        # Warm up ALL operation types that will be tested
        print("  Warming up read operations...")
        for bot_id in warmup_ids[:5]:
            try:
                read_get(bot_id)  # Direct get by ID
                read_filter(bot_id)  # Filter then first
            except:
                pass

        print("  Warming up update operations...")
        for bot_id in warmup_ids[:5]:
            try:
                update_composite(bot_id)  # Full ORM save cycle
                update_direct(bot_id)  # Direct SQL update
                # Reset the status back
                Bot.objects.filter(id=bot_id).update(status="active")
            except:
                pass

        print("  Warming up bulk operations...")
        try:
            # Warm up bulk update with a small batch
            bulk_update(warmup_ids[0], warmup_ids[:4])  # Update 5 records
            # Reset the status back
            Bot.objects.filter(id__in=warmup_ids[:5]).update(status="active")
        except:
            pass

        print("  Warming up delete operations...")
        for bot_id in warmup_ids[10:15]:
            try:
                soft_delete(bot_id)  # Soft delete
                hard_delete(bot_id)  # Hard delete
            except:
                pass

        # Clean up warmup data
        Bot.objects.filter(name__startswith="warmup_").delete()

    print("✅ Warmup complete")
    time.sleep(1)  # Brief pause before actual testing


# ------------------------
# CRUD Operations
# ------------------------

def create_bot(index_or_name):
    """Create a bot with either a numeric index or a custom name"""
    if isinstance(index_or_name, str):
        # Custom name provided
        name = index_or_name
        client_num = abs(hash(index_or_name)) % 10  # Deterministic client assignment
        slug_base = index_or_name.lower().replace(' ', '-')
    else:
        # Numeric index provided
        name = f"Bot {index_or_name}"
        client_num = index_or_name % 10
        slug_base = index_or_name

    # FIX: Make status selective - only 20% active for realistic index performance
    if isinstance(index_or_name, str):
        # For string names, use hash to deterministically make ~20% active
        status = "active" if abs(hash(index_or_name)) % 5 == 0 else "inactive"
    else:
        # For numeric indexes, use modulo
        status = "active" if index_or_name % 5 == 0 else "inactive"

    bot = Bot.objects.create(
        name=name,
        description="Benchmark document",
        client_id=f"client_{client_num}",
        slug=f"bot-{slug_base}",
        deleted_status="N",
        status=status,
        audit_data={
            "create_user_id": "user",
            "update_user_id": "user",
            "record_status": "A",
            "create_ts": datetime.now(timezone.utc).isoformat(),
            "update_ts": datetime.now(timezone.utc).isoformat(),
        },
        metadata={
            "version": "1.0",
            "status": "active",
        },
    )
    return bot.id


def read_get(bot_id):
    return Bot.objects.get(id=bot_id)


def read_filter(bot_id):
    return Bot.objects.filter(id=bot_id).first()


def update_composite(bot_id):
    bot = Bot.objects.get(id=bot_id)
    bot.status = "updated"
    bot.audit_data["update_ts"] = datetime.now(timezone.utc).isoformat()
    bot.save()
    return bot


def update_direct(bot_id):
    return Bot.objects.filter(id=bot_id).update(status="direct_updated")


def bulk_update(bot_id, all_ids):
    # For small datasets, adjust batch size
    available_additional = len(all_ids) - 1  # Exclude the current bot_id
    batch_size = min(4, available_additional)  # Don't exceed available records

    if batch_size > 0:
        batch = [bot_id] + random.sample(
            [i for i in all_ids if i != bot_id], batch_size
        )
    else:
        batch = [bot_id]  # Just update the single record

    return Bot.objects.filter(id__in=batch).update(status="bulk_updated")


def soft_delete(bot_id):
    return Bot.objects.filter(id=bot_id).update(deleted_status="Y")


def hard_delete(bot_id):
    return Bot.objects.filter(id=bot_id).delete()


def read_by_slug(bot_id):
    """Read by slug instead of ID - tests secondary index performance"""
    # Get the slug for this bot_id first
    bot = Bot.objects.get(id=bot_id)
    return Bot.objects.get(slug=bot.slug)


def read_by_status(bot_id):
    """Read by status - tests filtering performance"""
    return Bot.objects.filter(status="active").first()


def read_by_metadata_version(bot_id):
    """Read by nested metadata field - tests complex queries"""
    return Bot.objects.filter(metadata__version="1.0").first()


def ensure_indexes():
    """Create all required indexes for performance testing"""
    print("🔧 Creating database indexes...")

    # Connect directly to MongoDB to create indexes
    client = MongoClient('mongodb://localhost:27017')
    db = client['mongoenv_perf_test']
    collection = db['mongocon_bot']

    # Create indexes defined in Django model
    indexes_created = []

    # Single field indexes from db_index=True
    try:
        collection.create_index("name")
        indexes_created.append("name")
        print("  ✅ Created index: name")
    except Exception as e:
        print(f"  ⚠️  Index name may already exist: {e}")

    try:
        collection.create_index("client_id")
        indexes_created.append("client_id")
        print("  ✅ Created index: client_id")
    except Exception as e:
        print(f"  ⚠️  Index client_id may already exist: {e}")

    try:
        collection.create_index("slug")
        indexes_created.append("slug")
        print("  ✅ Created index: slug")
    except Exception as e:
        print(f"  ⚠️  Index slug may already exist: {e}")

    try:
        collection.create_index("status")
        indexes_created.append("status")
        print("  ✅ Created index: status")
    except Exception as e:
        print(f"  ⚠️  Index status may already exist: {e}")

    # Compound indexes from Meta.indexes
    try:
        collection.create_index([("client_id", 1), ("slug", 1)])
        indexes_created.append("client_id_slug")
        print("  ✅ Created compound index: client_id + slug")
    except Exception as e:
        print(f"  ⚠️  Compound index client_id_slug may already exist: {e}")

    # JSONField nested index for metadata.version
    try:
        collection.create_index("metadata.version")
        indexes_created.append("metadata.version")
        print("  ✅ Created index: metadata.version")
    except Exception as e:
        print(f"  ⚠️  Index metadata.version may already exist: {e}")

    client.close()

    print(f"📊 Index creation complete. Created/verified {len(indexes_created)} indexes")
    return indexes_created


def save_checkpoint_results(dataset_size, results):
    """Save intermediate benchmark results to JSON file"""
    checkpoint_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_size": dataset_size,
        "backend": "official_mongodb",
        "connection_strategy": "persistent",
        "workers": 15,
        "results": results
    }

    filename = f"mongocon_checkpoint_{dataset_size}.json"
    with open(filename, 'w') as f:
        json.dump(checkpoint_data, f, indent=2, default=str)

    print(f"💾 Checkpoint saved: {filename}")


def run():
    print("\nOfficial Backend Fair Benchmark (200000 records)")
    print("=" * 56)

    # FORCE connection initialization before any database operations
    connections['default'].ensure_connection()
    
    # Clear any existing test data
    Bot.objects.all().delete()
    ensure_indexes()

    # Warm up the system
    warmup_operations()

    # Checkpoints at: 1, 40,000, 100,000, 140,000, 200,000 records
    checkpoints = [1, 40000, 100000, 140000, 200000]
    create_times = []

    for i in range(200000):
        _, elapsed = time_operation(create_bot, i)
        create_times.append(elapsed)

        if (i + 1) % 10000 == 0:
            print(f"  Created {i + 1}/200000 records...")

        # Check if we hit a checkpoint
        if (i + 1) in checkpoints:
            print(f"\n🎯 CHECKPOINT: {i + 1} records")
            print("-" * 40)

            # Clean up memory for clean benchmark run
            gc.collect()
            time.sleep(1)

            # Get current IDs for testing
            current_ids = list(Bot.objects.values_list("id", flat=True))
            print(f"  Testing with {len(current_ids)} records...")

            # Run all benchmark operations
            checkpoint_results = {
                "create_avg": statistics.mean(create_times),
                "read_get": run_concurrent_suite(read_get, current_ids),
                "read_filter": run_concurrent_suite(read_filter, current_ids),
                "read_by_slug": run_concurrent_suite(read_by_slug, current_ids),
                "read_by_status": run_concurrent_suite(read_by_status, current_ids),
                "read_by_metadata_version": run_concurrent_suite(read_by_metadata_version, current_ids),
                "update_composite": run_concurrent_suite(update_composite, current_ids),
                "update_direct": run_concurrent_suite(update_direct, current_ids),
                "bulk_update": run_concurrent_suite(lambda x: bulk_update(x, current_ids), current_ids),
                "soft_delete": run_concurrent_suite(soft_delete, current_ids),
            }

            # Add hard delete test for final checkpoint only
            if (i + 1) == 200000:
                hard_delete_ids = []
                for j in range(100):
                    hard_delete_ids.append(create_bot(f"hard_delete_test_{j}"))
                checkpoint_results["hard_delete"] = run_concurrent_suite(hard_delete, hard_delete_ids)

            # Save checkpoint results
            save_checkpoint_results(i + 1, checkpoint_results)

    print("\n✅ Official MongoDB Backend scaling benchmark complete!")
    print("📊 Checkpoints saved as JSON files")
    print("=" * 56)
    print("📈 Performance data available in checkpoint JSON files:")
    print("   - mongocon_checkpoint_1.json")
    print("   - mongocon_checkpoint_40000.json") 
    print("   - mongocon_checkpoint_100000.json")
    print("   - mongocon_checkpoint_140000.json")
    print("   - mongocon_checkpoint_200000.json")
    print("=" * 56)

    print("\n✅ Official MongoDB Backend testing complete!")


if __name__ == "__main__":
    run()