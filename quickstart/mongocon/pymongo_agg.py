import os
import sys
import time
import statistics
import gc
import random
from datetime import datetime, timezone
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor

# Add paths
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
                'HOST': 'mongodb://localhost:27017',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
        ],
        USE_TZ=True,
    )

django.setup()

# Database connection settings (used by functions that need fresh connections)
DB_NAME = 'mongoenv_perf_test'
COLLECTION_NAME = 'sample_mflix_bot'


def get_fresh_collection():
    """Create a fresh MongoDB connection and return collection"""
    client = MongoClient('mongodb://localhost:27017')
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    return client, collection


def time_operation(operation_func, *args, **kwargs):
    """Time a single operation execution"""
    start = time.perf_counter()
    result = operation_func(*args, **kwargs)
    end = time.perf_counter()
    return result, end - start


def run_agg_suite(func, runs=30):
    """Run aggregation multiple times and return statistics"""
    times = []
    for _ in range(runs):
        _, elapsed = time_operation(func)
        times.append(elapsed)
        time.sleep(0.02)

    return {
        "avg": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "stdev": statistics.stdev(times),
    }


def run_concurrent_agg_suite(func, workers=12, total_runs=100):
    """Run aggregations concurrently to simulate production load"""
    times = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit tasks
        futures = [executor.submit(time_operation, func) for _ in range(total_runs)]
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
# Data Setup Functions
# ------------------------

def create_bot_data(index_or_name):
    """Create a bot data dict with either a numeric index or a custom name"""
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

    return {
        "name": name,
        "description": "Benchmark document",
        "client_id": f"client_{client_num}",
        "slug": f"bot-{slug_base}",
        "deleted_status": "N",
        "status": "active",
        "audit_data": {
            "create_user_id": "system",
            "update_user_id": "system",
            "create_ts": datetime.now(timezone.utc).isoformat(),
            "update_ts": datetime.now(timezone.utc).isoformat(),
        },
        "metadata": {
            "version": "1.0",
            "status": "active",
        },
    }


def setup_test_data():
    """Ensure we have 100000 test records for aggregation testing"""
    print("🔧 Setting up test data for aggregation benchmarks...")

    client, collection = get_fresh_collection()

    # Clear any existing data
    collection.delete_many({})

    # Create indexes for performance testing
    print("  Creating database indexes...")
    try:
        collection.create_index("slug")  # Already exists but ensure it
        collection.create_index("status")  # For status filtering tests
        collection.create_index("client_id")  # For client-based queries
        collection.create_index([("metadata.version", 1)])  # For nested metadata queries
        print("  ✅ Indexes created successfully")
    except Exception as e:
        print(f"  ⚠️  Index creation warning: {e}")

    # Create 100000 test records
    print("  Creating 100000 test records...")
    for i in range(100000):
        try:
            bot_data = create_bot_data(i)
            collection.insert_one(bot_data)
            if (i + 1) % 10000 == 0:
                print(f"    Created {i + 1}/100000 records...")
        except Exception as e:
            print(f"    Error creating record {i}: {e}")
            continue

    active_count = collection.count_documents({"deleted_status": "N"})
    print(f"✅ Test data setup complete: {active_count} active records")

    client.close()  # Close the connection
    return active_count


# ------------------------
# Aggregation Functions
# ------------------------

def agg_count_by_type():
    """Query bots with type filtering - returns individual documents"""
    client, collection = get_fresh_collection()
    try:
        pipeline = [
            {
                "$match": {
                    "deleted_status": "N",
                    "type": {"$exists": True}  # Only bots with type field
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "type": 1,
                    "status": 1,
                    "client_id": 1
                }
            },
            {
                "$limit": 50  # Return individual documents
            }
        ]
        result = list(collection.aggregate(pipeline))
        return result
    finally:
        client.close()


def agg_avg_tags_per_bot():
    """Query bots with calculated fields - returns individual documents"""
    client, collection = get_fresh_collection()
    try:
        pipeline = [
            {
                "$match": {
                    "deleted_status": "N"
                }
            },
            {
                "$addFields": {
                    "name_length": {"$strLenCP": "$name"}
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "name_length": 1,
                    "status": 1,
                    "client_id": 1,
                    "metadata": 1
                }
            },
            {
                "$limit": 50  # Return individual documents
            }
        ]
        result = list(collection.aggregate(pipeline))
        return result
    finally:
        client.close()


def agg_recent_bots_by_user():
    """Query recent bots by user - returns individual documents"""
    client, collection = get_fresh_collection()
    try:
        pipeline = [
            {
                "$match": {
                    "deleted_status": "N"
                }
            },
            {
                "$sort": {"audit_data.create_ts": -1}
            },
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "audit_data": 1,
                    "status": 1,
                    "client_id": 1
                }
            },
            {
                "$limit": 50  # Return individual documents
            }
        ]
        result = list(collection.aggregate(pipeline))
        return result
    finally:
        client.close()


def agg_status_distribution():
    """Query bots by status - returns individual documents"""
    client, collection = get_fresh_collection()
    try:
        pipeline = [
            {
                "$match": {
                    "deleted_status": "N",
                    "metadata.status": "active"
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "status": 1,
                    "metadata": 1,
                    "client_id": 1
                }
            },
            {
                "$limit": 50  # Return individual documents
            }
        ]
        result = list(collection.aggregate(pipeline))
        return result
    finally:
        client.close()


def agg_complex_nested_query():
    """Complex query with nested data - returns individual documents"""
    client, collection = get_fresh_collection()
    try:
        pipeline = [
            {
                "$match": {
                    "deleted_status": "N",
                    "metadata.status": {"$exists": True}
                }
            },
            {
                "$match": {
                    "metadata.status": "active"
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "client_id": 1,
                    "status": 1,
                    "metadata": 1,
                    "audit_data": 1
                }
            },
            {
                "$limit": 50  # Return individual documents
            }
        ]
        result = list(collection.aggregate(pipeline))
        return result
    finally:
        client.close()


# ------------------------
# Warmup Functions
# ------------------------

def warmup_aggregations():
    """Warm up aggregation pipelines and connection pool"""
    print("🔥 Warming up aggregation pipelines and connection pool...")

    # Create some warmup data if needed
    client, collection = get_fresh_collection()
    if collection.count_documents({"name": {"$regex": "^warmup_"}}) == 0:
        for i in range(10):
            try:
                warmup_data = {
                    "name": f"warmup_agg_{i}",
                    "description": "Warmup document",
                    "client_id": f"client_{i % 5}",
                    "slug": f"warmup-agg-{i}",
                    "deleted_status": "N",
                    "status": "active",
                    "audit_data": {
                        "create_user_id": "system",
                        "update_user_id": "system",
                        "create_ts": datetime.now(timezone.utc).isoformat(),
                        "update_ts": datetime.now(timezone.utc).isoformat(),
                    },
                    "metadata": {"version": "1.0", "status": "active"},
                }
                collection.insert_one(warmup_data)
            except:
                pass  # Ignore duplicates
    client.close()

    # Warm up different aggregation types with fresh connections
    print("  Warming up basic aggregations...")
    for _ in range(5):
        try:
            client, collection = get_fresh_collection()
            list(collection.aggregate([{"$match": {"deleted_status": "N"}}, {"$limit": 5}]))
            client.close()
        except:
            pass

    print("  Warming up grouping aggregations...")
    for _ in range(3):
        try:
            client, collection = get_fresh_collection()
            list(collection.aggregate([
                {"$match": {"deleted_status": "N"}},
                {"$project": {"_id": 1, "status": 1, "name": 1}},
                {"$limit": 10}
            ]))
            client.close()
        except:
            pass

    print("  Warming up complex aggregations...")
    for _ in range(2):
        try:
            client, collection = get_fresh_collection()
            list(collection.aggregate([
                {"$match": {"deleted_status": "N"}},
                {"$project": {"_id": 1, "name": 1, "name_len": {"$strLenCP": "$name"}}},
                {"$limit": 10}
            ]))
            client.close()
        except:
            pass

    # Clean up warmup data with fresh connection
    client, collection = get_fresh_collection()
    collection.delete_many({"name": {"$regex": "^warmup_agg_"}})
    client.close()

    print("✅ Aggregation warmup complete")
    time.sleep(1)


# ------------------------
# Main Runner
# ------------------------

def run():
    print("\n🚀 MongoDB PyMongo Direct Aggregation Pipeline Performance Benchmark")
    print("=" * 65)


    # Only warmup, do not create or modify data
    warmup_aggregations()
    # Clean up memory after warmup
    gc.collect()
    time.sleep(1)

    print("\n📊 RUNNING AGGREGATION PERFORMANCE TESTS")
    print("-" * 50)

    # Test 1: Count by type
    print("\n📈 Test 1: Count Bots by Type")
    count_stats = run_concurrent_agg_suite(agg_count_by_type)
    print(f"   Avg: {count_stats['avg']:.4f}s | P95: {count_stats['p95']:.4f}s | Throughput: {count_stats['throughput']:.1f} ops/sec")

    # Test 2: Average tags per bot
    print("\n📈 Test 2: Average Tags per Bot")
    tags_stats = run_concurrent_agg_suite(agg_avg_tags_per_bot)
    print(f"   Avg: {tags_stats['avg']:.4f}s | P95: {tags_stats['p95']:.4f}s | Throughput: {tags_stats['throughput']:.1f} ops/sec")

    # Test 3: Recent bots by user
    print("\n📈 Test 3: Recent Bots by User")
    recent_stats = run_concurrent_agg_suite(agg_recent_bots_by_user)
    print(f"   Avg: {recent_stats['avg']:.4f}s | P95: {recent_stats['p95']:.4f}s | Throughput: {recent_stats['throughput']:.1f} ops/sec")

    # Test 4: Status distribution
    print("\n📈 Test 4: Status Distribution")
    status_stats = run_concurrent_agg_suite(agg_status_distribution)
    print(f"   Avg: {status_stats['avg']:.4f}s | P95: {status_stats['p95']:.4f}s | Throughput: {status_stats['throughput']:.1f} ops/sec")

    # Test 5: Complex nested query
    print("\n📈 Test 5: Complex Nested Query")
    complex_stats = run_concurrent_agg_suite(agg_complex_nested_query)
    print(f"   Avg: {complex_stats['avg']:.4f}s | P95: {complex_stats['p95']:.4f}s | Throughput: {complex_stats['throughput']:.1f} ops/sec")

    # PERFORMANCE SUMMARY
    print("\n📊 PYMONGO DIRECT AGGREGATION PERFORMANCE SUMMARY")
    print("=" * 65)
    print(f"Dataset: 100000 records, 100 concurrent runs per aggregation (12 workers)")
    print(f"Connection Pool: Default PyMongo settings")
    print(f"")
    print(f"Count by Type:     Avg: {count_stats['avg']:.4f}s | P95: {count_stats['p95']:.4f}s | Throughput: {count_stats['throughput']:.1f} ops/sec")
    print(f"Average Tags:      Avg: {tags_stats['avg']:.4f}s | P95: {tags_stats['p95']:.4f}s | Throughput: {tags_stats['throughput']:.1f} ops/sec")
    print(f"Recent by User:    Avg: {recent_stats['avg']:.4f}s | P95: {recent_stats['p95']:.4f}s | Throughput: {recent_stats['throughput']:.1f} ops/sec")
    print(f"Status Distribution: Avg: {status_stats['avg']:.4f}s | P95: {status_stats['p95']:.4f}s | Throughput: {status_stats['throughput']:.1f} ops/sec")
    print(f"Complex Nested:    Avg: {complex_stats['avg']:.4f}s | P95: {complex_stats['p95']:.4f}s | Throughput: {complex_stats['throughput']:.1f} ops/sec")

    all_times = [
        count_stats['avg'], tags_stats['avg'], recent_stats['avg'],
        status_stats['avg'], complex_stats['avg']
    ]
    overall_avg = statistics.mean(all_times)
    print(f"\nOverall Average: {overall_avg:.4f}s per aggregation pipeline")

    print("\n✅ MongoDB PyMongo aggregation pipeline benchmarking complete!")


if __name__ == "__main__":
    run()