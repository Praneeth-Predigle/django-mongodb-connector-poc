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

from sample_mflix.models import Movie, Viewer
from django.core.exceptions import ValidationError

print('=== Understanding Schema Enforcement ===')
print('Django Model Definition:')
print('class Movie(models.Model):')
print('    title = models.CharField(max_length=200)  # REQUIRED (no null=True/blank=True)')
print('    plot = models.TextField(blank=True)       # OPTIONAL in forms')
print('    released = models.DateTimeField(null=True, blank=True)  # OPTIONAL everywhere')
print()

print('=== Test: Missing REQUIRED field (title) ===')
try:
    movie = Movie.objects.create(plot='Test plot', runtime=100)  # Missing title
    print(f'✅ INSERTED! Movie ID: {movie.id}')
    print(f'   title field value: "{movie.title}" (empty string)')
    print(f'   plot field value: "{movie.plot}"')
    movie.delete()
except Exception as e:
    print(f'❌ FAILED: {type(e).__name__}: {e}')

print()
print('=== Test: Missing OPTIONAL field (released) ===')
try:
    movie = Movie.objects.create(title='Test Movie', runtime=100)  # Missing released
    print(f'✅ INSERTED! Movie ID: {movie.id}')
    print(f'   released field value: {movie.released} (None/null)')
    movie.delete()
except Exception as e:
    print(f'❌ FAILED: {type(e).__name__}: {e}')

print()
print('=== Test: Django Form Validation (simulated) ===')
from django import forms

class MovieForm(forms.ModelForm):
    class Meta:
        model = Movie
        fields = ['title', 'plot', 'runtime', 'released']

print('Creating form with missing required field...')
form = MovieForm(data={'plot': 'Test plot', 'runtime': '100'})  # Missing title
if not form.is_valid():
    print('❌ FORM VALIDATION FAILED:')
    for field, errors in form.errors.items():
        print(f'   {field}: {errors}')
else:
    print('✅ Form would allow creation (but this is just form validation)')

print()
print('=== Key Difference Summary ===')
print('Djongo: Tries to enforce SQL constraints → Missing required fields FAIL')
print('MongoDB Connector: NoSQL flexibility → Missing fields get defaults → SUCCESS')
print('Schema enforcement happens at APPLICATION level (forms/admin), not DATABASE level')