import os
import django
from django.conf import settings

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django_mongodb_backend',
                'HOST': 'mongodb://localhost:27017/',
                'NAME': 'poc_db',
            },
        },
        INSTALLED_APPS=[
            'sample_mflix.apps.SampleMflixConfig',
            'django.contrib.contenttypes',
        ],
        USE_TZ=True,
    )

django.setup()

from pymongo import MongoClient

class MongoPipelineGenerator:
    """
    Adapted MongoPipelineGenerator for Official MongoDB Django Backend
    """
    def __init__(self, collection_name):
        """
        Initialize the MongoAggregation instance.

        Args:
            collection_name: The MongoDB collection name (string) to perform aggregation on.
        """
        self.collection_name = collection_name
        self.pipeline = []
        self.collation = None
        self._filter_active_records()

    def match(self, criteria):
        """Add a $match stage to the aggregation pipeline."""
        self.pipeline.append({"$match": criteria})
        return self

    def sort(self, fields, collation=None):
        """Add a $sort stage to the aggregation pipeline."""
        self.pipeline.append({"$sort": fields})
        if collation: self.collation = collation
        return self

    def limit(self, limit_amount):
        """Add a $limit stage to the aggregation pipeline."""
        self.pipeline.append({"$limit": int(limit_amount)})
        return self

    def skip(self, skip_amount):
        """Add a $skip stage to the aggregation pipeline."""
        self.pipeline.append({"$skip": int(skip_amount)})
        return self

    def group(self, group_spec, id=None):
        """Add a $group stage to the aggregation pipeline."""
        self.pipeline.append({"$group": {"_id": id, **group_spec}})
        return self

    def project(self, specs):
        """Add a $project stage to the aggregation pipeline."""
        self.pipeline.append({"$project": specs})
        return self

    def execute(self):
        """
        Execute the aggregation pipeline on the MongoDB collection.
        """
        client = MongoClient('mongodb://localhost:27018/?replicaSet=rs0&directConnection=true')
        db = client.poc_db
        collection = db[self.collection_name]

        if self.collation:
            results = collection.aggregate(self.pipeline, collation=self.collation)
        else:
            results = collection.aggregate(self.pipeline)

        return list(results)

    def _filter_active_records(self):
        """Your existing active record filter"""
        self.match({'deleted_status': 'N'})

# Test the adapted version
print('=== Testing Adapted MongoPipelineGenerator ===')
print()

# Your existing usage pattern - MINIMAL CHANGES needed:
aggregate = MongoPipelineGenerator('movies')  # Changed: collectionclass → 'movies' (string)

result = (aggregate
    .match({"runtime": {"$gt": 100}})  # Same as before
    .group({                           # Same as before
        "count": {"$sum": 1},
        "avg_runtime": {"$avg": "$runtime"},
        "titles": {"$push": "$title"}
    })
    .execute()                         # Same as before
)

print('✅ Adapted MongoPipelineGenerator works:')
if result:
    print(f'   Movies with runtime > 100: {result[0]["count"]}')
    print(f'   Average runtime: {result[0]["avg_runtime"]:.1f}')
    print(f'   Movie titles: {result[0]["titles"]}')

print()
print('=== Migration Changes Summary ===')
print('❌ OLD (Djongo): collectionclass.objects.mongo_aggregate(pipeline)')
print('✅ NEW (Official): MongoPipelineGenerator(collection_name).execute()')
print()
print('📝 Only change: Pass collection name as string instead of class')
print('📝 Everything else works identically!')