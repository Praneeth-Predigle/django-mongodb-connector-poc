import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            "default": {
                "ENGINE": "django_mongodb_backend",
                "NAME": "test",
                "CLIENT": {
                    "host": "mongodb://localhost:27018/?replicaSet=rs0&directConnection=true"
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

print('=== Aggregate Methods Comparison ===')
print()

print('Available methods containing "aggregate":')
methods = [method for method in dir(Movie.objects) if 'aggregate' in method.lower()]
for method in methods:
    print(f'  - {method}')

print()
print('✅ aggregate() - Provided by Django ORM (works with MongoDB backend)')
print('❌ mongo_aggregate() - Djongo-specific method (not available)')

print()
print('Testing Django aggregate() with proper syntax:')
try:
    from django.db.models import Count
    result = Movie.objects.filter(runtime__gt=100).aggregate(total_count=Count('id'))
    print(f'✅ Django aggregate() works: {result}')
except Exception as e:
    print(f'❌ Django aggregate() failed: {e}')

print()
print('=== Key Difference ===')
print('• aggregate() = Django ORM standard (works with any Django database backend)')
print('• mongo_aggregate() = Djongo custom method (MongoDB-specific, not in official backend)')
print()
print('The official MongoDB backend supports Django standards + raw MongoDB access')