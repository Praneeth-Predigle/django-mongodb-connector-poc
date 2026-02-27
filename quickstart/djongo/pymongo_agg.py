import os
import sys
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
import gc
from django.db.models import Count, Avg, F, Func
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

import django
django.setup()

from bots.models import Bot  # import your existing Bot model

# ------------------------
# Aggregation Tests
# ------------------------

def test_1_count_by_type():
    return list(Bot.objects.filter(type="support", deleted_status="N").values("name"))

def test_2_avg_tags():
    qs = Bot.objects.filter(deleted_status="N").annotate(
        tag_count=Func(F("tags"), function="json_array_length")
    )
    return list(qs.values("tag_count"))

def test_3_recent_by_user():
    return list(
        Bot.objects.filter(client_id="client_1", deleted_status="N")
        .order_by("-created_at")[:100]
        .values("name")
    )

def test_4_status_dist():
    return list(
        Bot.objects.filter(metadata__version__gt=1)
        .values("status")
        .annotate(count=Count("id"))
    )

def test_5_nested_complex():
    return list(
        Bot.objects.filter(status="active", deleted_status="N")
        .values("name", version=F("metadata__version"))
    )

import os
import sys
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
from pymongo import MongoClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

DB_NAME = 'djongo_perf_test'
COLLECTION_NAME = 'bots_bot'

def get_collection():
    client = MongoClient('mongodb://localhost:27017/')
    db = client[DB_NAME]
    return client, db[COLLECTION_NAME]

def test_1_count_by_type():
    client, collection = get_collection()
    try:
        pipeline = [
            {"$match": {"type": "support", "deleted_status": "N"}},
            {"$project": {"name": 1}}
        ]
        return list(collection.aggregate(pipeline))
    finally:
        client.close()

def test_2_avg_tags():
    client, collection = get_collection()
    try:
        pipeline = [
            {"$match": {"deleted_status": "N"}},
            {"$addFields": {"tag_count": {"$size": {"$ifNull": ["$tags", []]}}}},
            {"$project": {"tag_count": 1}}
        ]
        return list(collection.aggregate(pipeline))
    finally:
        client.close()

def test_3_recent_by_user():
    client, collection = get_collection()
    try:
        pipeline = [
            {"$match": {"client_id": "client_1", "deleted_status": "N"}},
            {"$sort": {"created_at": -1}},
            {"$limit": 100},
            {"$project": {"name": 1}}
        ]
        return list(collection.aggregate(pipeline))
    finally:
        client.close()

def test_4_status_dist():
    client, collection = get_collection()
    try:
        pipeline = [
            {"$match": {"metadata.version": {"$gt": 1}}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        return list(collection.aggregate(pipeline))
    finally:
        client.close()

def test_5_nested_complex():
    client, collection = get_collection()
    try:
        pipeline = [
            {"$match": {"status": "active", "deleted_status": "N"}},
            {"$project": {"v": "$metadata.version", "name": 1}}
        ]
        return list(collection.aggregate(pipeline))
    finally:
        client.close()

def test_6_group_by_client():
    client, collection = get_collection()
    try:
        pipeline = [
            {"$group": {"_id": "$client_id", "total": {"$sum": 1}}},
            {"$sort": {"total": -1}}
        ]
        return list(collection.aggregate(pipeline))
    finally:
        client.close()

def test_7_BOSS_LEVEL_tags():
    client, collection = get_collection()
    try:
        pipeline = [
            {"$match": {"deleted_status": "N"}},
            {"$unwind": "$tags"},
            {"$group": {
                "_id": "$tags",
                "count": {"$sum": 1},
                "unique_clients": {"$addToSet": "$client_id"}
            }},
            {"$project": {"tag": "$_id", "count": 1, "reach": {"$size": "$unique_clients"}}},
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        return list(collection.aggregate(pipeline))
    finally:
        client.close()

def run_bench(name, func, runs=50):
    times = []
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = [ex.submit(lambda: (time.perf_counter(), func(), time.perf_counter())) for _ in range(runs)]
        for f in futures:
            try:
                start, _, end = f.result()
                times.append(end - start)
            except Exception as e:
                print(f"Error in {name}: {e}")
    if times:
        avg = statistics.mean(times)
        p95 = sorted(times)[int(len(times) * 0.95)]
        print(f"{name:.<30} Avg: {avg:.4f}s | P95: {p95:.4f}s | Ops/s: {1/avg:.2f}")

if __name__ == "__main__":
    client, collection = get_collection()
    print(f"🚀 Starting Full Battery (PyMongo Direct) | Docs: {collection.count_documents({})}")
    client.close()
    tests = [
        ("1. Basic Filter", test_1_count_by_type),
        ("2. Field Computation", test_2_avg_tags),
        ("3. Index Sort", test_3_recent_by_user),
        ("4. Nested Group", test_4_status_dist),
        ("5. Projection Complex", test_5_nested_complex),
        ("6. Analytic Grouping", test_6_group_by_client),
        ("7. BOSS: Tag Distribution", test_7_BOSS_LEVEL_tags),
    ]
    for name, func in tests:
        run_bench(name, func)