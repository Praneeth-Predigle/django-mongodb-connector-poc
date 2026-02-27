import os
import sys
from pymongo import MongoClient

# Make project root importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            "default": {
                "ENGINE": "django_mongodb_backend",
                "NAME": "test",
                "CLIENT": {"host": "mongodb://localhost:27017"},
            }
        },
        INSTALLED_APPS=[
            'mongocon.apps.MongoenvConfig',
            'django.contrib.contenttypes',
        ],
        USE_TZ=True,
    )

django.setup()

from mongocon.models import Bot2


def wipe_bot2_collection():
    client = MongoClient("mongodb://localhost:27017")
    db = client["test"]
    db["mongocon_bot2"].delete_many({})
    print("[INFO] Wiped mongocon_bot2 collection.")


def test_status_int():
    wipe_bot2_collection()
    print("\n[TEST] Creating Bot2 with integer status (status=123)")
    try:
        obj = Bot2.objects.create(name="halamadrid", status=123)
        print("[RESULT] Created object id=", obj.id)
    except Exception as e:
        print("[EXCEPTION] During create:", repr(e))

    docs = list(Bot2.objects.all().values('id', 'name', 'status'))
    print('[DB] Retrieved documents:')
    for d in docs:
        print(' -', d)


def main():
    test_status_int()


if __name__ == '__main__':
    main()
