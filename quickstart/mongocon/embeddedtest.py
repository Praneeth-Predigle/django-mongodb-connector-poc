import os
import sys
import traceback

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=False,
        DATABASES={
            'default': {
                'ENGINE': 'django_mongodb_backend',
                'NAME': 'mongoenv_perf_test',
                'HOST': 'mongodb://localhost:27017',
            }
        },
        INSTALLED_APPS=[
            'mongocon.apps.MongoenvConfig',
            'django.contrib.contenttypes',
        ],
        USE_TZ=True,
    )

django.setup()

from mongocon.models import Bot3, Address


def run_test():
    print("\n[embeddedtest] Creating Bot3 with embedded Address")
    try:
        b = Bot3.objects.create(
            name="EmbedTest",
            address=Address(city="NY", street="5th Ave")
        )
        print("  Created Bot3 id:", b.id)

        # Query by dotted lookup on parent
        found = Bot3.objects.filter(address__city="NY").first()
        print("  Found via parent dotted lookup:", bool(found), getattr(found, 'id', None))

        # Try direct Address manager (should not exist/should raise)
        try:
            ao = Address.objects.filter(city="NY")
            print("  Address.objects exists; count:", ao.count())
        except Exception as e:
            print("  Address.objects query raised:", repr(e))

        # Sniper update using dotted-path update
        Bot3.objects.filter(id=b.id).update(**{'address__city': 'San Francisco'})
        refreshed = Bot3.objects.get(id=b.id)
        print("  After update, address.city =", getattr(refreshed.address, 'city', None))

    except Exception:
        print("  Exception during embedded test:\n", traceback.format_exc())
    finally:
        try:
            Bot3.objects.filter(name="EmbedTest").delete()
            print("  Cleanup done")
        except Exception:
            pass


if __name__ == '__main__':
    run_test()
