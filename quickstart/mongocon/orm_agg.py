import os
import sys
import time
import statistics
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Setup Django Environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=False,
        DATABASES={
            'default': {
                'ENGINE': 'django_mongodb_backend',
                'NAME': 'mongoenv_perf_test',
                'HOST': 'mongodb://localhost:27017/',
            }
        },
        INSTALLED_APPS=['mongocon.apps.MongoenvConfig'],
        USE_TZ=True,
    )
django.setup()
from mongocon.models import Bot

# --- THE 7 AGGREGATION PIPELINES ---

def test_1_count_by_type():
    return list(Bot.objects.raw_aggregate([
        {"$match": {"type": "support", "deleted_status": "N"}},
        {"$project": {"id": "$_id", "name": 1}}
    ]))

def test_2_avg_tags():
    return list(Bot.objects.raw_aggregate([
        {"$match": {"deleted_status": "N"}},
        {"$addFields": {"tag_count": {"$size": {"$ifNull": ["$tags", []]}}}},
        {"$project": {"id": "$_id", "tag_count": 1}}
    ]))

def test_3_recent_by_user():
    return list(Bot.objects.raw_aggregate([
        {"$match": {"client_id": "client_1", "deleted_status": "N"}},
        {"$sort": {"created_at": -1}},
        {"$limit": 100},
        {"$project": {"id": "$_id", "name": 1}}
    ]))

def test_4_status_dist():
    return list(Bot.objects.raw_aggregate([
        {"$match": {"metadata.version": {"$gt": 1}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$project": {"id": "$_id", "count": 1}}
    ]))

def test_5_nested_complex():
    return list(Bot.objects.raw_aggregate([
        {"$match": {"status": "active", "deleted_status": "N"}},
        {"$project": {"id": "$_id", "v": "$metadata.version", "name": 1}}
    ]))

def test_6_group_by_client():
    return list(Bot.objects.raw_aggregate([
        {"$group": {"_id": "$client_id", "total": {"$sum": 1}}},
        {"$project": {"id": "$_id", "total": 1}},
        {"$sort": {"total": -1}}
    ]))

def test_7_BOSS_LEVEL_tags():
    """The Heavy Lifter: Unwind + Group + Set"""
    return list(Bot.objects.raw_aggregate([
        {"$match": {"deleted_status": "N"}},
        {"$unwind": "$tags"},
        {"$group": {
            "_id": "$tags",
            "count": {"$sum": 1},
            "unique_clients": {"$addToSet": "$client_id"}
        }},
        {"$project": {"id": "$_id", "tag": "$_id", "count": 1, "reach": {"$size": "$unique_clients"}}},
        {"$sort": {"count": -1}},
        {"$limit": 20}
    ]))

# --- BENCHMARK ENGINE ---

def run_bench(name, func, runs=50):
    times = []
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = [ex.submit(lambda: (time.perf_counter(), func(), time.perf_counter())) for _ in range(runs)]
        for f in futures:
            start, _, end = f.result()
            times.append(end - start)
    
    avg = statistics.mean(times)
    p95 = sorted(times)[int(runs * 0.95)]
    print(f"{name:.<30} Avg: {avg:.4f}s | P95: {p95:.4f}s | Ops/s: {1/avg:.2f}")

if __name__ == "__main__":
    print(f"🚀 Starting Full Battery (Official Backend) | Docs: {Bot.objects.count()}")
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