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
                'HOST': 'mongodb://localhost:27018/?replicaSet=rs0&directConnection=true',
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

print('=== Nested Field Querying Examples ===')
print('Using your Movie model with awards (embedded) and genres (array) fields')
print()

# Example 1: Query embedded fields (awards.wins)
print('1. Movies with award wins >= 5:')
try:
    movies = Movie.objects.filter(awards__wins__gte=5)[:3]
    print(f'Found {len(movies)} movies with 5+ award wins')
    for movie in movies:
        wins = movie.awards.wins if movie.awards else 0
        print(f'  - {movie.title}: {wins} wins')
except Exception as e:
    print(f'Query failed: {e}')

print()

# Example 2: Query embedded fields (awards.nominations)
print('2. Movies with award nominations >= 10:')
try:
    movies = Movie.objects.filter(awards__nominations__gte=10)[:3]
    print(f'Found {len(movies)} movies with 10+ award nominations')
    for movie in movies:
        if movie.awards:
            print(f'  - {movie.title}: {movie.awards.nominations} nominations')
except Exception as e:
    print(f'Query failed: {e}')

print()

# Example 3: Query array fields (genres contains)
print('3. Movies with Action genre:')
try:
    movies = Movie.objects.filter(genres__icontains='action')[:3]
    print(f'Found {len(movies)} action movies')
    for movie in movies:
        print(f'  - {movie.title}: {movie.genres}')
except Exception as e:
    print(f'Query failed: {e}')

print()

# Example 4: Complex nested query
print('4. Long movies (>=120min) with awards:')
try:
    movies = Movie.objects.filter(
        runtime__gte=120,
        awards__wins__gte=1
    )[:3]
    print(f'Found {len(movies)} long movies with awards')
    for movie in movies:
        wins = movie.awards.wins if movie.awards else 0
        print(f'  - {movie.title}: {movie.runtime}min, {wins} wins')
except Exception as e:
    print(f'Query failed: {e}')

print()

# Example 5: Text search in plot
print('5. Movies with love in plot:')
try:
    movies = Movie.objects.filter(plot__icontains='love')[:3]
    print(f'Found {len(movies)} movies with love in plot')
    for movie in movies:
        plot_preview = movie.plot[:50] if movie.plot else 'No plot'
        print(f'  - {movie.title}: {plot_preview}...')
except Exception as e:
    print(f'Query failed: {e}')

print()
print('=== Key Django Lookup Types for Nested Fields ===')
print('• __gte, __lte, __gt, __lt - Comparisons')
print('• __icontains - Case-insensitive text search')
print('• __contains - Exact match (arrays: contains element)')
print('• __in - Value in list')
print('• __isnull - Check for null values')
print()
print('=== MongoDB vs Django Query Syntax ===')
print('Django: awards__wins__gte=5')
print('MongoDB: {"awards.wins": {"$gte": 5}}')
print()
print('The official backend translates Django syntax to MongoDB queries!')