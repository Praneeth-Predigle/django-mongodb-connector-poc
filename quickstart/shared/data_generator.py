import os
import sys
import django
from datetime import datetime, timezone
from bson import ObjectId

# Add the quickstart directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djongo.settings')

# Import after path setup
import django
from django.conf import settings

# Configure Django with Djongo settings
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

def generate_test_data(num_records=1000):
    """
    Generate test data matching the user's company structure
    Based on their Bot document analysis
    """
    client = MongoClient('mongodb://localhost:27017/')
    db = client.djongo_perf_test

    # Clear existing data
    db.bot.drop()

    # Sample data pools
    statuses = ["active", "inactive", "draft", "scheduled"]
    types = ["data_processor", "etl", "analytics", "reporting"]
    connection_types = ["mongodb", "postgresql", "mysql", "kafka", "s3"]
    user_ids = [f"user_{i}" for i in range(1, 51)]  # 50 different users

    # Generate bot documents
    bots = []
    for i in range(num_records):
        bot_id = ObjectId()

        # Create embedded documents
        audit_data = {
            "create_user_id": user_ids[i % len(user_ids)],
            "update_user_id": user_ids[i % len(user_ids)],
            "record_status": "A",
            "create_ts": datetime.now(timezone.utc),
            "update_ts": datetime.now(timezone.utc)
        }

        metadata = {
            "name": f"Test Bot {i+1}",
            "version": f"1.{i%10}.{(i%5)+1}",
            "status": statuses[i % len(statuses)],
            "type": {
                "type": types[i % len(types)],
                "category": "processing" if i % 2 == 0 else "analytics"
            }
        }

        # Generate tags (array of embedded objects)
        num_tags = (i % 4) + 1  # 1-4 tags
        tags = []
        for j in range(num_tags):
            tags.append({
                "name": f"tag_{j+1}",
                "value": f"value_{i}_{j}"
            })

        # Generate configuration with sources and destinations
        num_sources = (i % 3) + 1  # 1-3 sources
        sources = []
        for j in range(num_sources):
            sources.append({
                "name": f"Source {j+1}",
                "category": "database" if j % 2 == 0 else "file",
                "connection_type": {
                    "type": connection_types[j % len(connection_types)],
                    "category": "nosql" if connection_types[j % len(connection_types)] == "mongodb" else "sql"
                },
                "connection_config": {
                    "host": "mongodb://localhost:27017/" if connection_types[j % len(connection_types)] == "mongodb" else "postgresql://localhost:5432/",
                    "database": f"db_{i}_{j}",
                    "collection": f"collection_{i}_{j}" if connection_types[j % len(connection_types)] == "mongodb" else f"table_{i}_{j}",
                    "connection_details": {
                        "credentials": {
                            "username": f"user_{i}_{j}",
                            "password": "encrypted_password"
                        }
                    }
                }
            })

        # Similar for destinations
        num_destinations = (i % 2) + 1  # 1-2 destinations
        destinations = []
        for j in range(num_destinations):
            destinations.append({
                "name": f"Destination {j+1}",
                "category": "database",
                "connection_type": {
                    "type": "postgresql",
                    "category": "sql"
                }
            })

        # Create the full bot document
        bot = {
            "_id": bot_id,
            "name": f"Test Bot {i+1}",
            "description": f"Description for test bot {i+1}",
            "type": types[i % len(types)],
            "client_id": f"client_{(i % 10) + 1}",
            "slug": f"test-bot-{i+1}-slug",
            "deleted_status": "N",
            "audit_data": audit_data,
            "base": {
                "reference_id": f"base_{i+1}",
                "name": f"Base Config {i+1}"
            },
            "tags": tags,
            "group": {
                "name": f"Test Group {(i % 5) + 1}",
                "description": f"Group for bot {i+1}"
            },
            "metadata": metadata,
            "configuration": {
                "metadata": {
                    "name": f"Bot Configuration {i+1}",
                    "version": "1.0"
                },
                "sources": sources,
                "processor": {
                    "reference_id": f"proc_{(i % 20) + 1}",
                    "name": f"Processor {(i % 20) + 1}",
                    "module_name": "processors.data_processor",
                    "class_name": "DataProcessor"
                },
                "destinations": destinations
            }
        }

        bots.append(bot)

    # Insert all bots
    result = db.bot.insert_many(bots)
    print(f"✅ Inserted {len(result.inserted_ids)} bot documents into djongo_perf_test.bot")

    # Create indexes for performance
    db.bot.create_index([("metadata.status", 1)])
    db.bot.create_index([("audit_data.create_user_id", 1)])
    db.bot.create_index([("deleted_status", 1)])
    db.bot.create_index([("metadata.name", 1)])
    print("✅ Created performance indexes")

    return len(result.inserted_ids)

if __name__ == "__main__":
    print("🎯 Generating test data for Djongo performance testing...")
    count = generate_test_data(1000)
    print(f"✅ Generated {count} test records")
    print("📊 Data structure matches your company's Bot documents")
    print("🚀 Ready for Djongo performance testing!")