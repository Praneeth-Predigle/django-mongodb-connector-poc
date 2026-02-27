import os
import sys
import random
from datetime import datetime, timezone
from bson import ObjectId

# Setup Django Environment for Djongo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=False,
        DATABASES={
            'default': {
                'ENGINE': 'djongo',
                'NAME': 'djongo_perf_test',
                'HOST': 'mongodb://localhost:27017/',
            }
        },
        INSTALLED_APPS=['bots.apps.BotsConfig'],
        USE_TZ=True,
    )
django.setup()

from bots.models import Bot
from pymongo import MongoClient

def create_djongo_dataset():
    """Create 200K test records for Djongo aggregation benchmarks"""

    print("🔥 ERASING DJONGO DATABASE...")
    # Clear Django ORM
    Bot.objects.all().delete()

    # Clear MongoDB directly
    client = MongoClient('mongodb://localhost:27017/')
    db = client['djongo_perf_test']
    db['bots_bot'].delete_many({})
    print("✅ Database wiped clean")

    print("🏗️ Creating 200,000 test records for Djongo...")

    # Predefined data for consistency
    types = ['support', 'sales', 'admin', 'user', 'system']
    statuses = ['active', 'inactive', 'pending', 'suspended']
    tag_templates = ['urgent', 'priority', 'escalated', 'resolved', 'open', 'closed', 'high', 'medium', 'low']

    for i in range(200000):
        # Create deterministic but varied data
        client_num = i % 10
        type_val = types[i % len(types)]
        status_val = statuses[i % len(statuses)]

        # Create 1-3 random tags per record
        num_tags = random.randint(1, 3)
        tags = random.sample(tag_templates, num_tags)

        # Create record
        bot = Bot.objects.create(
            id=ObjectId(),  # Explicit ID for Djongo
            name=f"Bot {i}",
            description=f"Test bot {i} for aggregation benchmarks",
            client_id=f"client_{client_num}",
            slug=f"bot-{i}",
            deleted_status="N",
            status=status_val,
            type=type_val,
            tags=tags,
            created_at=datetime.now(timezone.utc),
            audit_data={
                "created_by": "system",
                "updated_by": "system",
                "version": i % 5 + 1,  # 1-5 for version filtering
                "last_modified": datetime.now(timezone.utc).isoformat()
            },
            metadata={
                "version": i % 5 + 1,  # 1-5 for nested queries
                "category": f"cat_{i % 3}",
                "priority": random.choice(['high', 'medium', 'low'])
            }
        )

        if (i + 1) % 20000 == 0:
            print(f"📊 Created {i + 1}/200,000 records...")

    # Final count
    total_count = Bot.objects.count()
    active_count = Bot.objects.filter(deleted_status="N").count()
    type_support_count = Bot.objects.filter(type="support").count()

    print("\n✅ Djongo dataset creation complete!")
    print(f"   Total records: {total_count:,}")
    print(f"   Active records: {active_count:,}")
    print(f"   Support type records: {type_support_count:,}")
    print(f"   Sample tags distribution: {Bot.objects.filter(tags__0='urgent').count()} urgent tags")

if __name__ == "__main__":
    create_djongo_dataset()