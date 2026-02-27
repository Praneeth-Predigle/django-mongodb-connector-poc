#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')
import django
from django.conf import settings
from django.db import connections, close_old_connections

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django_mongodb_backend',
                'NAME': 'mongoenv_perf_test',
                'HOST': 'mongodb://localhost:27017/',
                'CONN_MAX_AGE': 400,
                'OPTIONS': {
                    'maxPoolSize': 50,
                    'minPoolSize': 10,
                    'serverSelectionTimeoutMS': 5000,
                    'directConnection': True,
                },
            }
        },
        INSTALLED_APPS=['mongocon.apps.MongoenvConfig', 'django.contrib.contenttypes'],
        USE_TZ=True,
    )

django.setup()

# Monkey patch for official backend
from django_mongodb_backend.base import DatabaseWrapper
def patched_auto_encryption_opts(self):
    if self.connection is None:
        return None
    if not hasattr(self.connection, '_options'):
        return None
    return self.connection._options.auto_encryption_opts
DatabaseWrapper.auto_encryption_opts = property(patched_auto_encryption_opts)

from mongocon.models import Bot

# Create a few records to trigger index creation
print('Creating test data in mongoenv_perf_test...')
for i in range(10):
    Bot.objects.create(
        name=f'Bot {i}',
        description='Test',
        client_id=f'client_{i%3}',
        slug=f'bot-{i}',
        deleted_status='N',
        status='active',
        audit_data={'test': True},
        metadata={'version': '1.0'}
    )
print('Done - official backend indexes should be created')