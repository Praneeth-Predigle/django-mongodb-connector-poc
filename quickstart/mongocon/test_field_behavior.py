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
    """Delete all documents from the Bot2 collection using pymongo."""
    client = MongoClient("mongodb://localhost:27017")
    db = client["test"]
    db["mongocon_bot2"].delete_many({})
    print("[INFO] Wiped mongocon_bot2 collection.")


def test_type_mismatch_name_string_for_integer():
    """Attempt to create a Bot2 with a string value for IntegerField `name`.

    This test wipes the collection once, then tries the insert and prints a
    clear single outcome.
    """
    wipe_bot2_collection()
    print("\n[TEST] Bot2.objects.create() with type mismatch (string for IntegerField 'name'):")
    try:
        obj = Bot2.objects.create(name="should_be_int", status="should_fail")
        print("[WARNING] String for IntegerField 'name' did NOT raise an error!")
        fetched = Bot2.objects.get(id=obj.id)
        print(f"[RESULT] Inserted object: id={fetched.id}, name={fetched.name} (type: {type(fetched.name)})")
    except Exception as e:
        print("[EXPECTED] Exception for type mismatch:", e)


def main():
    test_type_mismatch_name_string_for_integer()


if __name__ == '__main__':
    main()
