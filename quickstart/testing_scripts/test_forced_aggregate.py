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

from sample_mflix.models import Movie

print('=== Testing Model.objects.aggregate() with Raw MongoDB Pipelines ===')
print()

# Test 1: Normal Django aggregate (should work)
print('1. Normal Django aggregate (should work):')
try:
    from django.db.models import Count
    result = Movie.objects.aggregate(total=Count('id'))
    print(f'✅ Normal Django aggregate works: {result}')
except Exception as e:
    print(f'❌ Failed: {e}')

print()

# Test 2: Try passing raw MongoDB pipeline to Django aggregate
print('2. Raw MongoDB pipeline in Django aggregate (expecting failure):')
try:
    mongo_pipeline = [
        {"$match": {"runtime": {"$gt": 100}}},
        {"$group": {"_id": None, "count": {"$sum": 1}}}
    ]
    result = Movie.objects.aggregate(pipeline=mongo_pipeline)
    print(f'✅ Unexpectedly worked: {result}')
except Exception as e:
    print(f'❌ Expected failure: {type(e).__name__}: {e}')

print()

# Test 3: Try different ways
print('3. Other attempts:')
try:
    # Try with **kwargs
    result = Movie.objects.aggregate(**{"$match": {"runtime": {"$gt": 100}}})
    print(f'✅ Kwargs worked: {result}')
except Exception as e:
    print(f'❌ Kwargs failed: {type(e).__name__}: {e}')

print()

# Test 4: Check what aggregate method accepts
print('4. Django aggregate method signature:')
import inspect
try:
    sig = inspect.signature(Movie.objects.aggregate)
    print(f'aggregate{sig}')
except Exception as e:
    print(f'Could not inspect: {e}')

print()
print('=== Conclusion ===')
print('Django ORM aggregate() is designed for SQL-style aggregations only.')
print('Raw MongoDB pipelines require direct PyMongo access.')
print('This separation is actually GOOD - clear distinction between ORM and raw DB operations!')