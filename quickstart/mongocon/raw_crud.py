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
    db = client.mongoenv_perf_test

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
                "type": "mongodb",
                "connection_string": "mongodb://localhost:27017/",
                "database": "mongoenv_perf_test"
            }],
            "processors": [{
                "name": "Raw Test Processor",
                "module_name": "raw.test.module",
                "class_name": "RawTestProcessor",
                "config": {"test_param": f"value_{index}"}
            }],
            "destinations": [{
                "name": "Raw Test Destination",
                "type": "console",
                "config": {"format": "json"}
            }]
        },
        "acl": [{
            "client_id": f"raw_client_{index % 10}",
            "user_id": f"user_{index % 50}",
            "allowed_roles": [{"allowed_roles": "admin"}, {"allowed_roles": "user"}]
        }],
        "groups": [f"group_{index % 5}"],
        "hidden": False
    }

    result = db.bot.insert_one(bot)
    return result.inserted_id


def read_raw_bot(bot_id):
    """Read a single bot document using raw PyMongo"""
    client = MongoClient('mongodb://localhost:27017')
    db = client.mongoenv_perf_test

    bot = db.bot.find_one({"_id": bot_id})
    return bot


def update_raw_bot(bot_id):
    """Update a single bot document using raw PyMongo"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.mongoenv_perf_test

    result = db.bot.update_one(
        {"_id": bot_id},
        {"$set": {
            "description": "Updated by raw PyMongo",
            "audit_data.update_ts": datetime.now(timezone.utc),
            "metadata.status": "updated"
        }}
    )
    return result.modified_count


def delete_raw_bot(bot_id):
    """Delete a single bot document using raw PyMongo"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client.mongoenv_perf_test

    result = db.bot.delete_one({"_id": bot_id})
    return result.deleted_count


def run_raw_crud_tests():
    """Run raw PyMongo CRUD performance tests"""
    print("🔹 Running Raw PyMongo CRUD Tests (Official Backend)")
    print("=" * 60)

    # Create test data
    print("Creating test data...")
    bot_ids = []
    for i in range(10):
        bot_id = create_raw_bot(i)
        bot_ids.append(bot_id)
        print(f"  Created bot: {bot_id}")

    print(f"\nTesting with {len(bot_ids)} bot IDs: {[str(id) for id in bot_ids[:3]]}...")

    # Test Create operations
    print("\n📝 CREATE Operations:")
    create_stats = run_multiple_times(create_raw_bot, runs=20, index=1000)
    print(f"  Average: {create_stats['avg']:.4f}s")
    print(f"  Min: {create_stats['min']:.4f}s, Max: {create_stats['max']:.4f}s")
    print(f"  Std Dev: {create_stats['stdev']:.4f}s")

    # Test Read operations
    print("\n📖 READ Operations:")
    read_stats = run_multiple_times(read_raw_bot, runs=20, bot_id=bot_ids[0])
    print(f"  Average: {read_stats['avg']:.4f}s")
    print(f"  Min: {read_stats['min']:.4f}s, Max: {read_stats['max']:.4f}s")
    print(f"  Std Dev: {read_stats['stdev']:.4f}s")

    # Test Update operations
    print("\n✏️  UPDATE Operations:")
    update_stats = run_multiple_times(update_raw_bot, runs=20, bot_id=bot_ids[0])
    print(f"  Average: {update_stats['avg']:.4f}s")
    print(f"  Min: {update_stats['min']:.4f}s, Max: {update_stats['max']:.4f}s")
    print(f"  Std Dev: {update_stats['stdev']:.4f}s")

    # Test Delete operations
    print("\n🗑️  DELETE Operations:")
    delete_stats = run_multiple_times(delete_raw_bot, runs=20, bot_id=bot_ids[1])
    print(f"  Average: {delete_stats['avg']:.4f}s")
    print(f"  Min: {delete_stats['min']:.4f}s, Max: {delete_stats['max']:.4f}s")
    print(f"  Std Dev: {delete_stats['stdev']:.4f}s")

    # Cleanup
    print("\n🧹 Cleaning up test data...")
    client = MongoClient('mongodb://localhost:27017/')
    db = client.mongoenv_perf_test
    db.bot.delete_many({"_id": {"$in": bot_ids}})
    print("  Cleanup complete.")

    print("\n✅ Raw PyMongo CRUD Tests Complete")


if __name__ == "__main__":
    run_raw_crud_tests()