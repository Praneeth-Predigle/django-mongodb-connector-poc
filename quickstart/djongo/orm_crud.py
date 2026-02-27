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

# ---------------------------------------------------------
# Django Configuration (POOL HARD CAP FIXED HERE)
# ---------------------------------------------------------

if not settings.configured:
    settings.configure(
        DEBUG=False,
        DATABASES={
            'default': {
                'ENGINE': 'djongo',
                'NAME': 'djongo_perf_test_2',
                # ✅ Hard cap pool settings via URI (PyMongo respects this)
                'HOST': (
                    'mongodb://localhost:27017/'
                    '?maxPoolSize=20'
                    '&minPoolSize=5'
                    '&waitQueueTimeoutMS=5000'
                ),
                'CONN_MAX_AGE': 400,
            }
        },
        INSTALLED_APPS=[
            'bots.apps.BotsConfig',
            'django.contrib.contenttypes',
        ],
        USE_TZ=True,
    )

django.setup()

# ---------------------------------------------------------
# Verify Pool Settings (IMPORTANT)
# ---------------------------------------------------------

def verify_pool_settings():
    connections['default'].ensure_connection()
    client = connections['default'].connection.client
    pool_opts = client.options.pool_options

    print("\n🔍 Mongo Pool Settings:")
    print("  Max Pool Size:", pool_opts.max_pool_size)
    print("  Min Pool Size:", pool_opts.min_pool_size)
    print("  Wait Queue Timeout (ms):", pool_opts.wait_queue_timeout)

verify_pool_settings()

# ---------------------------------------------------------

from pymongo import MongoClient
from bots.models import Bot

# ---------------------------------------------------------
# Benchmark Utilities
# ---------------------------------------------------------

def time_operation(func, *args):
    close_old_connections()
    start = time.perf_counter()
    result = func(*args)
    end = time.perf_counter()
    return result, end - start


def run_concurrent_suite(func, ids, workers=15, total_runs=100):
    connections['default'].ensure_connection()

    times = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(time_operation, func, random.choice(ids))
            for _ in range(total_runs)
        ]
        for future in futures:
            _, elapsed = future.result()
            times.append(elapsed)

    sorted_times = sorted(times)
    return {
        "avg": statistics.mean(times),
        "p95": sorted_times[int(len(times) * 0.95)],
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "stdev": statistics.stdev(times),
        "throughput": len(times) / sum(times),
        "total_ops": len(times),
    }

# ---------------------------------------------------------
# Index Management
# ---------------------------------------------------------

def ensure_indexes():
    print("🔧 Creating database indexes...")

    client = MongoClient('mongodb://localhost:27017/')
    db = client['djongo_perf_test_2']
    collection = db['bots_bot']

    indexes = [
        "name",
        "client_id",
        "slug",
        "status",
        "metadata.version",
    ]

    for index in indexes:
        try:
            collection.create_index(index)
            print(f"  ✅ Created index: {index}")
        except Exception as e:
            print(f"  ⚠️ Index {index} issue: {e}")

    try:
        collection.create_index([("client_id", 1), ("slug", 1)])
        print("  ✅ Created compound index: client_id + slug")
    except Exception as e:
        print(f"  ⚠️ Compound index issue: {e}")

    client.close()
    print("📊 Index creation complete\n")

# ---------------------------------------------------------
# CRUD Operations
# ---------------------------------------------------------

def create_bot(index_or_name):
    if isinstance(index_or_name, str):
        name = index_or_name
        client_num = abs(hash(index_or_name)) % 10
        slug_base = index_or_name.lower().replace(' ', '-')
        status = "active" if abs(hash(index_or_name)) % 5 == 0 else "inactive"
    else:
        name = f"Bot {index_or_name}"
        client_num = index_or_name % 10
        slug_base = index_or_name
        status = "active" if index_or_name % 5 == 0 else "inactive"

    now = datetime.now(timezone.utc)

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
            "create_ts": now,
            "update_ts": now,
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
    bot.audit_data["update_ts"] = datetime.now(timezone.utc)
    bot.save()
    return bot


def update_direct(bot_id):
    return Bot.objects.filter(id=bot_id).update(status="direct_updated")


def bulk_update(bot_id, all_ids):
    available_additional = len(all_ids) - 1
    batch_size = min(4, available_additional)

    if batch_size > 0:
        batch = [bot_id] + random.sample(
            [i for i in all_ids if i != bot_id],
            batch_size
        )
    else:
        batch = [bot_id]

    return Bot.objects.filter(id__in=batch).update(status="bulk_updated")


def soft_delete(bot_id):
    return Bot.objects.filter(id=bot_id).update(deleted_status="Y")


def hard_delete(bot_id):
    return Bot.objects.filter(id=bot_id).delete()


def read_by_slug(bot_id):
    bot = Bot.objects.get(id=bot_id)
    return Bot.objects.get(slug=bot.slug)


def read_by_status(bot_id):
    return Bot.objects.filter(status="active").first()

# ---------------------------------------------------------
# Checkpoint Saving
# ---------------------------------------------------------

def save_checkpoint_results(dataset_size, results):
    checkpoint_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_size": dataset_size,
        "backend": "djongo",
        "connection_strategy": "persistent",
        "workers": 15,
        "results": results
    }

    filename = f"djongo_checkpoint_{dataset_size}.json"
    with open(filename, 'w') as f:
        json.dump(checkpoint_data, f, indent=2, default=str)

    print(f"💾 Checkpoint saved: {filename}")

# ---------------------------------------------------------
# Runner
# ---------------------------------------------------------

def run():
    print("\nDjongo Fair Benchmark (200000 records)")
    print("=" * 50)

    connections['default'].ensure_connection()
    Bot.objects.all().delete()
    ensure_indexes()

    checkpoints = [1, 40000, 100000, 140000, 200000]
    create_times = []

    for i in range(200000):
        _, elapsed = time_operation(create_bot, i)
        create_times.append(elapsed)

        if (i + 1) % 10000 == 0:
            print(f"  Created {i + 1}/200000 records...")

        if (i + 1) in checkpoints:
            print(f"\n🎯 CHECKPOINT: {i + 1} records")
            gc.collect()
            time.sleep(1)

            current_ids = list(Bot.objects.values_list("id", flat=True))

            checkpoint_results = {
                "create_avg": statistics.mean(create_times),
                "read_get": run_concurrent_suite(read_get, current_ids),
                "read_filter": run_concurrent_suite(read_filter, current_ids),
                "read_by_slug": run_concurrent_suite(read_by_slug, current_ids),
                "read_by_status": run_concurrent_suite(read_by_status, current_ids),
                "update_composite": run_concurrent_suite(update_composite, current_ids),
                "update_direct": run_concurrent_suite(update_direct, current_ids),
                "bulk_update": run_concurrent_suite(
                    lambda x: bulk_update(x, current_ids),
                    current_ids
                ),
                "soft_delete": run_concurrent_suite(soft_delete, current_ids),
            }

            if (i + 1) == 200000:
                hard_delete_ids = [
                    create_bot(f"hard_delete_test_{j}")
                    for j in range(100)
                ]
                checkpoint_results["hard_delete"] = run_concurrent_suite(
                    hard_delete,
                    hard_delete_ids
                )

            save_checkpoint_results(i + 1, checkpoint_results)

    print("\n✅ Djongo scaling benchmark complete!")

# ---------------------------------------------------------

if __name__ == "__main__":
    run()