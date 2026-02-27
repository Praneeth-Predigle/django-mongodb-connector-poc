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
from pymongo import MongoClient

print('=== Return Types Comparison ===')
print()

# Test 1: Django ORM QuerySet (normal Django objects)
print('1. Django ORM QuerySet - Returns Django Model Instances:')
try:
    movies = Movie.objects.filter(runtime__gt=120)[:2]  # Get first 2 movies
    for movie in movies:
        print(f'   Type: {type(movie)}')
        print(f'   Is Django Model: {hasattr(movie, "_meta")}')
        print(f'   Has save() method: {hasattr(movie, "save")}')
        print(f'   Title: {movie.title}')
        print(f'   Runtime: {movie.runtime}')
        print(f'   Can call movie.save(): {callable(getattr(movie, "save", None))}')
        break  # Just show first one
    print('   ✅ Django model instances with full ORM capabilities')
except Exception as e:
    print(f'   ❌ Failed: {e}')

print()

# Test 2: Raw PyMongo aggregation (raw BSON documents)
print('2. Raw PyMongo collection.aggregate() - Returns Raw Documents:')
try:
    client = MongoClient('mongodb://localhost:27017/')
    db = client.poc_db
    collection = db.movies

    pipeline = [
        {"$match": {"runtime": {"$gt": 120}}},
        {"$limit": 1}
    ]

    results = list(collection.aggregate(pipeline))
    if results:
        result = results[0]
        print(f'   Type: {type(result)}')
        print(f'   Is Django Model: {hasattr(result, "_meta")}')
        print(f'   Has save() method: {hasattr(result, "save")}')
        print(f'   Keys: {list(result.keys())}')
        print(f'   Title: {result.get("title")}')
        print(f'   Runtime: {result.get("runtime")}')
        print(f'   _id type: {type(result.get("_id"))}')
        print('   ❌ Raw BSON document - no Django ORM features')
    else:
        print('   No results found')
except Exception as e:
    print(f'   ❌ Failed: {e}')

print()

# Test 3: Official Backend raw_aggregate() - Returns Django Model Instances
print('3. Official Backend raw_aggregate() - Returns Django Model Instances:')
print('   Note: raw_aggregate() requires MongoManager and proper pipeline')
print('   → Would return Django model instances (like QuerySet results)')
print('   → Full ORM capabilities on the results')
print('   → Useful for raw pipelines that still need Django objects')

print()

# Test 4: Django aggregate() - Returns aggregated values (dict)
# Test 4: Django aggregate() - Returns Aggregation Results (dict)
print('4. Django aggregate() - Returns Aggregation Results (dict):')
try:
    from django.db.models import Count
    result = Movie.objects.aggregate(total_movies=Count('id'))
    print(f'   Type: {type(result)}')
    print(f'   Result: {result}')
    print('   ✅ Dictionary with aggregated values')
except Exception as e:
    print(f'   ❌ Failed: {e}')
    print('   Note: Field resolution issues in test environment')

print()
print('=== Summary of Return Types ===')
print()
print('🔹 Django ORM QuerySet (.filter(), .get(), etc.):')
print('   → Django model instances')
print('   → Full ORM features (save, delete, relationships)')
print('   → Lazy loading, caching, etc.')
print()
print('🔹 Raw PyMongo (collection.aggregate()):')
print('   → Raw BSON documents (dict)')
print('   → No Django features')
print('   → Best performance for complex queries')
print()
print('🔹 Official Backend raw_aggregate():')
print('   → Django model instances')
print('   → ORM features available')
print('   → Useful when you want both raw power AND Django objects')
print()
print('🔹 Django aggregate():')
print('   → Dictionary with aggregated values')
print('   → Simple aggregations (Count, Sum, Avg, etc.)')
print()
print('🔹 Djongo mongo_aggregate() (hypothetical):')
print('   → Raw documents (dict) - no Django ORM features')
print('   → Similar to raw PyMongo but through Django manager')