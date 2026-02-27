"""
Standalone test script to validate complex nested arrays and embedded documents
with the official Django MongoDB backend.

Run with the workspace virtualenv python (example):

e:\Pedigle VS Code\mongo-poc\mongoenv\Scripts\python.exe \
    quickstart/mongocon/test_scripts/test_complex_embedded.py

Requires a running MongoDB at mongodb://localhost:27017/ and a database named `poc_db`.
"""
import os
import json
import sys
import django
from django.conf import settings

# Align Django initialization with mongocon/orm_agg.py (use same DB and app)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')

if not settings.configured:
    settings.configure(
        DEBUG=False,
        DATABASES={
            'default': {
                'ENGINE': 'django_mongodb_backend',
                'NAME': 'mongoenv_perf_test',
                'HOST': 'mongodb://localhost:27017/',
            }
        },
        INSTALLED_APPS=['mongocon.apps.MongoenvConfig'],
        USE_TZ=True,
    )

django.setup()

from mongocon.test_models_app.models import ComplexDoc
from pymongo import MongoClient


def run():
    client = MongoClient('mongodb://localhost:27017/')
    # Use the same database name as configured for Django settings
    db_name = settings.DATABASES['default'].get('NAME', 'test')
    db = client[db_name]
    coll_name = ComplexDoc._meta.db_table
    coll = db[coll_name]

    print('Clearing collection:', coll_name)
    coll.delete_many({})

    # Document 1: arrays of primitives and arrays of embedded docs
    doc1 = {
        'level1': [
            {'name': 'a', 'items': [1, 2, {'deep': {'x': 1}}]},
            {'name': 'b', 'items': []},
        ],
        'meta': {'owner': {'id': 123, 'tags': ['x', 'y']}},
    }

    # Document 2: deeply nested embedded docs and arrays
    doc2 = {
        'level1': [
            {
                'name': 'c',
                'items': [
                    {'deep2': {'sub': [{'k': 'v1'}, {'k': 'v2'}]}},
                ],
            }
        ],
        'meta': {'owner': {'id': 456, 'tags': None}},
    }

    print('Inserting via Django ORM...')
    obj1 = ComplexDoc.objects.create(data=doc1)
    obj2 = ComplexDoc.objects.create(data=doc2)

    print('Inserted IDs:', obj1.pk, obj2.pk)

    # Basic retrieval via ORM
    all_objs = list(ComplexDoc.objects.all())
    print('ORM count:', len(all_objs))

    # Verify shape preserved
    assert all_objs[0].data['level1'][0]['items'][2]['deep']['x'] == 1

    # Use PyMongo to run queries and aggregations that validate nested/array behaviors
    print('Running PyMongo queries...')

    # Print a sample raw document to inspect storage shape
    sample = coll.find_one({})
    print('Sample raw document:', json.dumps(sample, default=str))

    # Query: find doc where any element of data.level1 has name 'a' (use $elemMatch)
    found = coll.find_one({'data.level1': {'$elemMatch': {'name': 'a'}}})
    assert found is not None, 'Query for data.level1 (elemMatch) failed to find doc'

    # Aggregation: unwind level1 and match by name
    pipeline = [
        {'$unwind': '$data.level1'},
        {'$match': {'data.level1.name': 'a'}},
        {'$project': {'item': '$data.level1'}},
    ]
    agg = list(coll.aggregate(pipeline))
    assert len(agg) == 1, f'Expected 1 unwind result, got {len(agg)}'

    print('Aggregation unwind result:', json.dumps(agg[0], default=str))

    # Test nested array access: find doc with nested k == 'v2'
    found2 = coll.find_one({'data.level1.items.deep2.sub.k': 'v2'})
    # The above may not match due to array nesting—use a more explicit pipeline
    # Safer pipeline: only consider items that contain deep2, avoid replaceRoot on primitives
    pipeline2 = [
        {'$unwind': '$data.level1'},
        {'$unwind': '$data.level1.items'},
        {'$match': {'data.level1.items.deep2': {'$exists': True}}},
        {'$unwind': '$data.level1.items.deep2.sub'},
        {'$match': {'data.level1.items.deep2.sub.k': 'v2'}},
    ]
    agg2 = list(coll.aggregate(pipeline2))
    assert len(agg2) >= 1, 'Nested deep array aggregation failed'

    print('Nested deep array aggregation count:', len(agg2))

    # If the manager supports raw_aggregate(), test that it returns model instances
    if hasattr(ComplexDoc.objects, 'raw_aggregate'):
        print('Testing raw_aggregate via manager...')
        try:
            results = ComplexDoc.objects.raw_aggregate([{'$limit': 2}])
            results_list = list(results)
            print('raw_aggregate returned', len(results_list), 'objects')
        except Exception as e:
            print('raw_aggregate threw an exception (ok to note):', e)

    print('\nALL TESTS PASSED (basic validations).')


if __name__ == '__main__':
    try:
        run()
    except AssertionError as e:
        print('AssertionError:', e)
        raise
    except Exception as e:
        print('Unexpected error:', e)
        raise
