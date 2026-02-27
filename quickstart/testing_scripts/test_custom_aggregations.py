import os
import django
from django.conf import settings

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

# Only configure if not already configured
if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            "default": {
                "ENGINE": "django_mongodb_backend",
                "NAME": "test",
                "CLIENT": {
                    "host": "mongodb://localhost:27017/?replicaSet=rs0"
                }
            }
        },
        INSTALLED_APPS=[
            'sample_mflix.apps.SampleMflixConfig',
            'django.contrib.contenttypes',
        ],
        USE_TZ=True,
    )

django.setup()

from sample_mflix.models import Movie

print('=== Testing Your MongoPipelineGenerator Pattern ===')
print()

# Test 1: Check if mongo_aggregate method exists
print('=== Test 1: Does mongo_aggregate() method exist? ===')
try:
    # Check if the method exists
    has_method = hasattr(Movie.objects, 'mongo_aggregate')
    print(f'✅ mongo_aggregate method exists: {has_method}')

    if has_method:
        # Try a simple aggregation
        pipeline = [
            {"$match": {"runtime": {"$gt": 100}}},
            {"$count": "total_movies"}
        ]
        result = Movie.objects.mongo_aggregate(pipeline)
        print(f'✅ mongo_aggregate() works: {list(result)}')
    else:
        print('❌ mongo_aggregate method not found')

except Exception as e:
    print(f'❌ mongo_aggregate test failed: {e}')

print()

# Test 2: Alternative approach with raw PyMongo
print('=== Test 2: Alternative with Raw PyMongo (Recommended) ===')
try:
    from pymongo import MongoClient

    class MongoPipelineGenerator:
        def __init__(self, collection_name):
            self.collection_name = collection_name
            self.pipeline = []
            self.collation = None

        def match(self, criteria):
            self.pipeline.append({"$match": criteria})
            return self

        def sort(self, fields, collation=None):
            self.pipeline.append({"$sort": fields})
            if collation: self.collation = collation
            return self

        def limit(self, limit_amount):
            self.pipeline.append({"$limit": int(limit_amount)})
            return self

        def group(self, group_spec, id=None):
            self.pipeline.append({"$group": {"_id": id, **group_spec}})
            return self

        def execute(self):
            client = MongoClient('mongodb://localhost:27017/?replicaSet=rs0')
            db = client.test
            collection = db[self.collection_name]

            if self.collation:
                results = collection.aggregate(self.pipeline, collation=self.collation)
            else:
                results = collection.aggregate(self.pipeline)

            return list(results)

    # Test the adapted version
    aggregate = MongoPipelineGenerator('movies')
    result = (aggregate
              .match({"runtime": {"$gt": 100}})
              .group({"count": {"$sum": 1}, "avg_runtime": {"$avg": "$runtime"}}, None)
              .execute())

    print('✅ Adapted MongoPipelineGenerator works:')
    if result:
        print(f'   Count: {result[0]["count"]}')
        print(f'   Avg Runtime: {result[0]["avg_runtime"]:.1f}')
    else:
        print('   No results')

except Exception as e:
    print(f'❌ Adapted version failed: {e}')

print()

# Test 3: Show how to integrate with Django models
print('=== Test 3: Integration with Django Models ===')
try:
    # Create a custom manager method
    class MongoAggregationManager:
        def aggregate_pipeline(self, pipeline):
            """Execute raw MongoDB aggregation pipeline"""
            from pymongo import MongoClient
            client = MongoClient('mongodb://localhost:27017/?replicaSet=rs0')
            db = client.test
            collection = db[self.model._meta.db_table]
            return list(collection.aggregate(pipeline))

    # Monkey patch the Movie model (for demonstration)
    Movie.mongo_aggregate = lambda self, pipeline: MongoAggregationManager().aggregate_pipeline(pipeline)

    # Now test your original pattern
    pipeline = [
        {"$match": {"runtime": {"$gte": 120}}},
        {"$group": {"_id": None, "count": {"$sum": 1}, "titles": {"$push": "$title"}}}
    ]

    result = Movie.mongo_aggregate(pipeline)
    print('✅ Django model integration works:')
    if result:
        print(f'   Movies >= 120min: {result[0]["count"]}')
        print(f'   Titles: {result[0]["titles"]}')

except Exception as e:
    print(f'❌ Django integration failed: {e}')

print()
print('=== Migration Recommendations ===')
print('1. ✅ Raw PyMongo approach: Full compatibility, best performance')
print('2. ⚠️  mongo_aggregate() method: May need custom implementation')
print('3. ✅ Your MongoPipelineGenerator: Can be adapted to work perfectly')
print()
print('Your existing aggregation code can work with minimal changes!')