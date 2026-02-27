import os
import sys
import time
import statistics
from datetime import datetime, timezone

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

# Configure Django (for timezone support)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django_mongodb_backend',
                'NAME': 'mongoenv_perf_test',
                'HOST': 'mongodb://localhost:27017',
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


def time_operation(operation_func, *args, **kwargs):
    """Time a single operation execution"""
    start = time.perf_counter()
    result = operation_func(*args, **kwargs)
    end = time.perf_counter()
    return result, end - start


def run_multiple_times(operation_func, runs=5, *args, **kwargs):
    """Run operation multiple times and return statistics"""
    times = []
    for i in range(runs):
        _, elapsed = time_operation(operation_func, *args, **kwargs)
        times.append(elapsed)
        time.sleep(0.1)  # Small delay between runs

    return {
        'times': times,
        'avg': statistics.mean(times),
        'min': min(times),
        'max': max(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0
    }


def raw_agg_count_by_type():
    """Count bots by type using raw PyMongo aggregation"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.mongoenv_perf_test

    pipeline = [
        {"$match": {"deleted_status": "N"}},
        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]

    result = list(db.bot.aggregate(pipeline))
    return result


def raw_agg_avg_tags_per_bot():
    """Calculate average number of tags per bot using raw PyMongo"""
    client = MongoClient('mongodb://localhost:27017')
    db = client.mongoenv_perf_test

    pipeline = [
        {"$match": {"deleted_status": "N"}},
        {"$project": {"tag_count": {"$size": "$tags"}}},
        {"$group": {"_id": None, "avg_tags": {"$avg": "$tag_count"}}}
    ]

    result = list(db.bot.aggregate(pipeline))
    return result


def raw_agg_recent_bots_by_user():
    """Find recent bots created by each user using raw PyMongo"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.mongoenv_perf_test

    pipeline = [
        {"$match": {"deleted_status": "N"}},
        {"$sort": {"audit_data.create_ts": -1}},
        {"$group": {
            "_id": "$audit_data.create_user_id",
            "recent_bots": {
                "$push": {
                    "name": "$name",
                    "created": "$audit_data.create_ts"
                }
            }
        }},
        {"$project": {
            "user_id": "$_id",
            "recent_bots": {"$slice": ["$recent_bots", 3]}  # Top 3 recent
        }}
    ]

    result = list(db.bot.aggregate(pipeline))
    return result


def raw_agg_status_distribution():
    """Get distribution of bot statuses using raw PyMongo"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.mongoenv_perf_test

    pipeline = [
        {"$match": {"deleted_status": "N"}},
        {"$group": {"_id": "$metadata.status", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]

    result = list(db.bot.aggregate(pipeline))
    return result


def raw_agg_complex_nested_query():
    """Complex aggregation with nested data using raw PyMongo"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.mongoenv_perf_test

    pipeline = [
        {"$match": {
            "deleted_status": "N",
            "configuration.sources": {"$exists": True, "$ne": []}
        }},
        {"$unwind": "$configuration.sources"},
        {"$match": {
            "configuration.sources.type": "mongodb"
        }},
        {"$group": {
            "_id": {
                "bot_name": "$name",
                "source_type": "$configuration.sources.type"
            },
            "source_count": {"$sum": 1}
        }},
        {"$sort": {"source_count": -1}},
        {"$limit": 10}
    ]

    result = list(db.bot.aggregate(pipeline))
    return result


def run_raw_aggregation_tests():
    """Run complete raw PyMongo aggregation pipeline performance tests"""
    print("🧪 Running Raw PyMongo Aggregation Pipeline Performance Tests (Official Backend)")
    print("=" * 70)

    # Test 1: Count by type
    print("\n📊 RAW AGGREGATION TEST 1: Count Bots by Type")
    print("-" * 45)
    count_stats = run_multiple_times(raw_agg_count_by_type, runs=5)
    print(f"  Average time: {count_stats['avg']:.4f}s")
    print(f"  Min/Max: {count_stats['min']:.4f}s / {count_stats['max']:.4f}s")
    print(f"  Result count: {len(raw_agg_count_by_type())} groups")

    # Test 2: Average tags per bot
    print("\n📊 RAW AGGREGATION TEST 2: Average Tags per Bot")
    print("-" * 45)
    tags_stats = run_multiple_times(raw_agg_avg_tags_per_bot, runs=5)
    print(f"  Average time: {tags_stats['avg']:.4f}s")
    print(f"  Min/Max: {tags_stats['min']:.4f}s / {tags_stats['max']:.4f}s")
    result = raw_agg_avg_tags_per_bot()
    if result:
        print(f"  Average tags per bot: {result[0].get('avg_tags', 0):.2f}")

    # Test 3: Recent bots by user
    print("\n📊 RAW AGGREGATION TEST 3: Recent Bots by User")
    print("-" * 45)
    recent_stats = run_multiple_times(raw_agg_recent_bots_by_user, runs=5)
    print(f"  Average time: {recent_stats['avg']:.4f}s")
    print(f"  Min/Max: {recent_stats['min']:.4f}s / {recent_stats['max']:.4f}s")
    print(f"  Result count: {len(raw_agg_recent_bots_by_user())} users")

    # Test 4: Status distribution
    print("\n📊 RAW AGGREGATION TEST 4: Status Distribution")
    print("-" * 45)
    status_stats = run_multiple_times(raw_agg_status_distribution, runs=5)
    print(f"  Average time: {status_stats['avg']:.4f}s")
    print(f"  Min/Max: {status_stats['min']:.4f}s / {status_stats['max']:.4f}s")
    print(f"  Result count: {len(raw_agg_status_distribution())} statuses")

    # Test 5: Complex nested query
    print("\n📊 RAW AGGREGATION TEST 5: Complex Nested Query")
    print("-" * 45)
    complex_stats = run_multiple_times(raw_agg_complex_nested_query, runs=5)
    print(f"  Average time: {complex_stats['avg']:.4f}s")
    print(f"  Min/Max: {complex_stats['min']:.4f}s / {complex_stats['max']:.4f}s")
    print(f"  Result count: {len(raw_agg_complex_nested_query())} results")

    # SUMMARY
    print("\n📊 RAW PYMONGO AGGREGATION PERFORMANCE SUMMARY (Official Backend)")
    print("=" * 70)
    print(f"Count by Type: {count_stats['avg']:.4f}s")
    print(f"Average Tags: {tags_stats['avg']:.4f}s")
    print(f"Recent by User: {recent_stats['avg']:.4f}s")
    print(f"Status Distribution: {status_stats['avg']:.4f}s")
    print(f"Complex Nested: {complex_stats['avg']:.4f}s")

    all_times = [
        count_stats['avg'], tags_stats['avg'], recent_stats['avg'],
        status_stats['avg'], complex_stats['avg']
    ]
    overall_avg = statistics.mean(all_times)
    print(f"\nOverall Average: {overall_avg:.4f}s per aggregation")

    print("\n✅ Raw PyMongo aggregation pipeline testing complete!")
    print("📁 Results saved for comparison with Official Backend ORM aggregations")


if __name__ == "__main__":
    run_raw_aggregation_tests()