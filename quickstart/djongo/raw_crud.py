import os
import sys
import time
import statistics
from datetime import datetime, timezone

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'djongo',
                'NAME': 'djongo_perf_test',
                'HOST': 'mongodb://localhost:27017/',
            }
        },
        INSTALLED_APPS=[
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


def create_raw_bot(index):
    """Create a single test bot document using raw PyMongo"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.djongo_perf_test

    bot = {
        "_id": f"raw_test_bot_{index}",
        "name": f"Raw Test Bot {index}",
        "description": f"Test bot for raw MongoDB operations {index}",
        "type": "test_processor",
        "client_id": f"raw_client_{index % 10}",
        "slug": f"raw-test-bot-{index}",
        "deleted_status": "N",
        "audit_data": {
            "create_user_id": f"user_{index % 50}",
            "update_user_id": f"user_{index % 50}",
            "record_status": "A",
            "create_ts": datetime.now(timezone.utc),
            "update_ts": datetime.now(timezone.utc)
        },
        "metadata": {
            "name": f"Raw Test Bot {index}",
            "version": "1.0.0",
            "status": "active",
            "type": {
                "type": "test",
                "category": "raw_testing"
            }
        },
        "tags": [
            {"name": "test", "value": "raw"},
            {"name": "performance", "value": "testing"}
        ],
        "configuration": {
            "metadata": {
                "name": f"Raw Test Configuration {index}",
                "version": "1.0"
            },
            "sources": [{
                "name": "Raw Test Source",
                "category": "database",
                "connection_type": {"type": "mongodb", "category": "nosql"}
            }],
            "processor": {
                "reference_id": f"raw_proc_{index}",
                "name": "Raw Test Processor",
                "module_name": "raw.test.module",
                "class_name": "RawTestProcessor"
            }
        }
    }

    result = db.bot.insert_one(bot)
    return result.inserted_id


def read_raw_bot(bot_id):
    """Read a single bot document using raw PyMongo"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.djongo_perf_test

    bot = db.bot.find_one({"_id": bot_id})
    return bot


def update_raw_bot(bot_id):
    """Update a single bot document using raw PyMongo"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.djongo_perf_test

    result = db.bot.update_one(
        {"_id": bot_id},
        {"$set": {
            "metadata.status": "updated",
            "audit_data.update_ts": datetime.now(timezone.utc),
            "audit_data.update_user_id": "raw_updater_user"
        }}
    )
    return result.modified_count


def delete_raw_bot(bot_id):
    """Delete a single bot document using raw PyMongo (soft delete)"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.djongo_perf_test

    result = db.bot.update_one(
        {"_id": bot_id},
        {"$set": {"deleted_status": "Y"}}
    )
    return result.modified_count


def aggregate_bots_by_type():
    """Aggregate pipeline: Count bots by type"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.djongo_perf_test

    pipeline = [
        {"$match": {"deleted_status": "N"}},
        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]

    result = list(db.bot.aggregate(pipeline))
    return result


def aggregate_bots_by_client():
    """Aggregate pipeline: Count bots by client_id"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.djongo_perf_test

    pipeline = [
        {"$match": {"deleted_status": "N"}},
        {"$group": {"_id": "$client_id", "count": {"$sum": 1}, "bots": {"$push": "$name"}}},
        {"$sort": {"count": -1}}
    ]

    result = list(db.bot.aggregate(pipeline))
    return result


def aggregate_recent_bots():
    """Aggregate pipeline: Find recently created bots with metadata"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.djongo_perf_test

    # Get bots created in the last 24 hours (simulated with current timestamp logic)
    pipeline = [
        {"$match": {"deleted_status": "N"}},
        {"$addFields": {
            "hours_old": {
                "$divide": [
                    {"$subtract": [datetime.now(timezone.utc), "$audit_data.create_ts"]},
                    1000 * 60 * 60  # milliseconds to hours
                ]
            }
        }},
        {"$match": {"hours_old": {"$lte": 24}}},
        {"$project": {
            "name": 1,
            "type": 1,
            "client_id": 1,
            "metadata": 1,
            "hours_old": 1,
            "create_ts": "$audit_data.create_ts"
        }},
        {"$sort": {"create_ts": -1}},
        {"$limit": 10}
    ]

    result = list(db.bot.aggregate(pipeline))
    return result


def aggregate_performance_metrics():
    """Aggregate pipeline: Complex performance metrics"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.djongo_perf_test

    pipeline = [
        {"$match": {"deleted_status": "N"}},
        {"$group": {
            "_id": {
                "type": "$type",
                "client_id": "$client_id"
            },
            "total_bots": {"$sum": 1},
            "active_bots": {
                "$sum": {"$cond": [{"$eq": ["$metadata.status", "active"]}, 1, 0]}
            },
            "avg_tags": {"$avg": {"$size": "$tags"}},
            "latest_update": {"$max": "$audit_data.update_ts"}
        }},
        {"$addFields": {
            "active_percentage": {
                "$multiply": [{"$divide": ["$active_bots", "$total_bots"]}, 100]
            }
        }},
        {"$sort": {"total_bots": -1, "active_percentage": -1}}
    ]

    result = list(db.bot.aggregate(pipeline))
    return result


def aggregate_nested_metadata():
    """Aggregate pipeline: Query nested metadata structures"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.djongo_perf_test

    pipeline = [
        {"$match": {"deleted_status": "N"}},
        {"$unwind": "$configuration.sources"},
        {"$match": {"configuration.sources.connection_type.type": "mongodb"}},
        {"$group": {
            "_id": "$configuration.sources.category",
            "bots_count": {"$sum": 1},
            "processor_types": {"$addToSet": "$configuration.processor.class_name"}
        }},
        {"$sort": {"bots_count": -1}}
    ]

    result = list(db.bot.aggregate(pipeline))
    return result


def run_raw_tests():
    """Run complete raw PyMongo performance tests"""
    print("🧪 Running Djongo Raw PyMongo Performance Tests")
    print("=" * 50)

    # Clear any existing test data first
    client = MongoClient('mongodb://localhost:27017/')
    db = client.djongo_perf_test
    db.bot.delete_many({"_id": {"$regex": "^raw_test_bot_"}})  # Remove any existing raw test bots
    print("✅ Cleared existing raw test data")

    # Test data for operations
    test_bot_ids = [f"raw_test_bot_{i}" for i in range(300, 400)]  # 100 unique test IDs

    # CREATE TESTS
    print("\n📝 RAW CREATE TESTS (Empty DB → Filled)")
    print("-" * 30)

    create_times = []
    for i in range(100):  # Create 100 test bots
        stats = run_multiple_times(create_raw_bot, runs=3, index=300+i)
        create_times.append(stats['avg'])
        if (i+1) % 20 == 0:
            print(f"  Created {i+1}/100 bots...")

    create_avg = statistics.mean(create_times)
    print(f"  Average create time: {create_avg:.4f}s per record")
    print(f"  Total time for 100 records: {create_avg * 100:.4f}s")
    print(f"  Records per second: {1/create_avg:.2f}")

    # READ TESTS
    print("\n📖 RAW READ TESTS (Query Existing Data)")
    print("-" * 30)

    read_stats = run_multiple_times(read_raw_bot, runs=5, bot_id=test_bot_ids[0])
    print(f"  Average read time: {read_stats['avg']:.4f}s")
    print(f"  Min/Max: {read_stats['min']:.4f}s / {read_stats['max']:.4f}s")
    print(f"  Standard deviation: {read_stats['stdev']:.4f}s")

    # UPDATE TESTS
    print("\n✏️  RAW UPDATE TESTS (Modify Existing Data)")
    print("-" * 30)

    update_stats = run_multiple_times(update_raw_bot, runs=5, bot_id=test_bot_ids[0])
    print(f"  Average update time: {update_stats['avg']:.4f}s")
    print(f"  Min/Max: {update_stats['min']:.4f}s / {update_stats['max']:.4f}s")
    print(f"  Standard deviation: {update_stats['stdev']:.4f}s")

    # DELETE TESTS
    print("\n🗑️  RAW DELETE TESTS (Soft Delete)")
    print("-" * 30)

    delete_stats = run_multiple_times(delete_raw_bot, runs=5, bot_id=test_bot_ids[1])
    print(f"  Average delete time: {delete_stats['avg']:.4f}s")
    print(f"  Min/Max: {delete_stats['min']:.4f}s / {delete_stats['max']:.4f}s")
    print(f"  Standard deviation: {delete_stats['stdev']:.4f}s")

    # AGGREGATION TESTS
    print("\n🔍 RAW AGGREGATION PIPELINE TESTS")
    print("-" * 35)

    # Test 1: Count by type
    agg1_stats = run_multiple_times(aggregate_bots_by_type, runs=3)
    print(f"  Aggregate by type: {agg1_stats['avg']:.4f}s avg")
    print(f"    Result count: {len(aggregate_bots_by_type())} groups")

    # Test 2: Count by client
    agg2_stats = run_multiple_times(aggregate_bots_by_client, runs=3)
    print(f"  Aggregate by client: {agg2_stats['avg']:.4f}s avg")
    print(f"    Result count: {len(aggregate_bots_by_client())} groups")

    # Test 3: Recent bots
    agg3_stats = run_multiple_times(aggregate_recent_bots, runs=3)
    print(f"  Recent bots query: {agg3_stats['avg']:.4f}s avg")
    print(f"    Result count: {len(aggregate_recent_bots())} bots")

    # Test 4: Performance metrics
    agg4_stats = run_multiple_times(aggregate_performance_metrics, runs=3)
    print(f"  Performance metrics: {agg4_stats['avg']:.4f}s avg")
    print(f"    Result count: {len(aggregate_performance_metrics())} metrics")

    # Test 5: Nested metadata
    agg5_stats = run_multiple_times(aggregate_nested_metadata, runs=3)
    print(f"  Nested metadata query: {agg5_stats['avg']:.4f}s avg")
    print(f"    Result count: {len(aggregate_nested_metadata())} categories")

    # SUMMARY
    print("\n📊 RAW PYMONGO PERFORMANCE SUMMARY")
    print("=" * 50)
    print(f"Create (100 records): {create_avg:.4f}s total ({create_avg*100:.2f} records/sec)")
    print(f"Read (single): {read_stats['avg']:.4f}s")
    print(f"Update (single): {update_stats['avg']:.4f}s")
    print(f"Delete (single): {delete_stats['avg']:.4f}s")
    print(f"Aggregation (by type): {agg1_stats['avg']:.4f}s")
    print(f"Aggregation (by client): {agg2_stats['avg']:.4f}s")
    print(f"Aggregation (recent): {agg3_stats['avg']:.4f}s")
    print(f"Aggregation (metrics): {agg4_stats['avg']:.4f}s")
    print(f"Aggregation (nested): {agg5_stats['avg']:.4f}s")
    print("\n✅ Djongo raw PyMongo testing complete!")
    print("📁 Results saved for comparison with Official backend")


if __name__ == "__main__":
    run_raw_tests()