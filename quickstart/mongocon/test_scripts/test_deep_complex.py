"""
Deep nested/array behavior tests using the official Django MongoDB backend (standalone).

Run with the repo virtualenv. Exits 0 on success and prints failures otherwise.
"""
from bson import ObjectId
import sys
import os

import django
from django.conf import settings
from django.db import connections

# Configure Django if not already configured
if not settings.configured:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quickstart.settings')
    settings.configure(
        DEBUG=False,
        DATABASES={
            'default': {
                'ENGINE': 'django_mongodb_backend',
                'NAME': 'mongoenv_perf_test',
                'HOST': 'mongodb://localhost:27017/',
            }
        },
        INSTALLED_APPS=[],
        USE_TZ=True,
    )
django.setup()

def fail(msg):
    print('TEST FAILED:', msg)
    sys.exit(2)

def main():
    # Get collection via the official backend connection
    conn = connections['default']
    coll = conn.get_collection('complexdoc')  # collection name

    # Clean collection
    coll.drop()

    # --- Insert sample documents ---
    docs = [
        # Embedded-within-embedded + array of embedded objects
        {'_id': ObjectId(), 'data': {'embedded': {'inner': {'name': 'a', 'arr': [{'x': 1}, {'y': 2}]}}}},
        # Array-of-arrays
        {'_id': ObjectId(), 'data': {'arr_of_arrs': [[1, 2], [3, 4]]}},
        # Positional update with arrayFilters
        {'_id': ObjectId(), 'data': {'pos_arr': [{'k': 1, 'v': 0}, {'k': 2, 'v': 0}] }},
        # Mixed-type array elements
        {'_id': ObjectId(), 'data': {'mixed': [1, {'a': 2}, 'x', {'b': 3}] }},
    ]
    coll.insert_many(docs)

    # --- Test A: $elemMatch on embedded array ---
    found = coll.find_one({'data.embedded.inner.arr': {'$elemMatch': {'y': 2}}})
    if not found:
        fail('Test A failed: $elemMatch did not find expected document')

    # --- Test B: flatten array-of-arrays ---
    doc2_id = docs[1]['_id']
    pipeline = [
        {'$match': {'_id': doc2_id}},
        {'$project': {'flatten': {'$reduce': {
            'input': '$data.arr_of_arrs',
            'initialValue': [],
            'in': {'$concatArrays': ['$$value', '$$this']}
        }}}},
        {'$unwind': '$flatten'},
        {'$group': {'_id': '$_id', 'vals': {'$push': '$flatten'}}}
    ]
    res = list(coll.aggregate(pipeline))
    if not res or res[0]['vals'] != [1, 2, 3, 4]:
        fail('Test B failed: array-of-arrays flattening incorrect')

    # --- Test C: positional update with arrayFilters ---
    doc3_id = docs[2]['_id']
    coll.update_one(
        {'_id': doc3_id},
        {'$set': {'data.pos_arr.$[elem].v': 9}},
        array_filters=[{'elem.k': 2}]
    )
    updated = coll.find_one({'_id': doc3_id})
    if updated['data']['pos_arr'][1]['v'] != 9:
        fail('Test C failed: arrayFilters positional update did not apply correctly')

    # --- Test D: safe $replaceRoot on object elements in mixed array ---
    doc4_id = docs[3]['_id']
    pipeline = [
        {'$match': {'_id': doc4_id}},
        {'$unwind': '$data.mixed'},
        {'$match': {'$expr': {'$eq': [{'$type': '$data.mixed'}, 'object']}}},
        {'$replaceRoot': {'newRoot': '$data.mixed'}},
        {'$group': {'_id': '$_id', 'objs': {'$push': '$$ROOT'}}}
    ]
    res = list(coll.aggregate(pipeline))
    if not res:
        fail('Test D failed: $replaceRoot returned no results')
    objs = res[0]['objs']
    if not any('a' in o for o in objs) or not any('b' in o for o in objs):
        fail('Test D failed: expected object elements not found')

    print('ALL BASIC DEEP TESTS PASSED')

    # --- MAXIMUM CHAOS SUITE ---
    def chaos_suite():
        # Insert chaos document with deep nested structures
        doc5_id = ObjectId()
        doc5 = {
            '_id': doc5_id,
            'data': {
                'lvl1': {
                    'lvl2': [
                        {
                            'lvl3': [
                                {'k': 1, 'vals': [[1, 2], [3, {'deep': [10, 20]}]]},
                                {'k': 2, 'vals': [[4], [5, 6]]}
                            ]
                        },
                        {'lvl3': [{'k': 3, 'vals': [[7, 8]]}]}
                    ]
                },
                'polymorphic': [
                    {'type': 'obj', 'payload': {'a': 1}},
                    [1, 2, {'nested': {'z': 9}}],
                    "string",
                    42
                ],
                'deep_strings': [[['abc-1'], ['no-match']], [{'level2': [{'s': 'match_me'}]}], 'outerstring']
            }
        }
        coll.insert_one(doc5)

        # CHAOS A — flatten nested arrays deeply
        pipelineA = [
            {'$match': {'_id': doc5_id}},
            {'$unwind': '$data.lvl1.lvl2'},
            {'$unwind': '$data.lvl1.lvl2.lvl3'},
            {'$project': {
                'flat': {'$reduce': {
                    'input': '$data.lvl1.lvl2.lvl3.vals',
                    'initialValue': [],
                    'in': {'$concatArrays': ['$$value', '$$this']}
                }}
            }},
            {'$unwind': '$flat'},
            {'$match': {'$expr': {'$eq': [{'$type': '$flat'}, 'int']}}},
            {'$group': {'_id': '$_id', 'nums': {'$push': '$flat'}}}
        ]
        res = list(coll.aggregate(pipelineA))
        nums = res[0]['nums']
        if 1 not in nums or 8 not in nums:
            fail('CHAOS A failed: deep flattening incorrect')

        # CHAOS B — nested arrayFilters update
        coll.update_one(
            {'_id': doc5_id},
            {'$set': {'data.lvl1.lvl2.$[].lvl3.$[elem].flagged': True}},
            array_filters=[{'elem.k': 2}]
        )
        updated = coll.find_one({'_id': doc5_id})
        if not any(l3.get('flagged') for l2 in updated['data']['lvl1']['lvl2'] for l3 in l2['lvl3'] if l3['k'] == 2):
            fail('CHAOS B failed: deep arrayFilters update failed')

        # CHAOS C — deep removal of 7 in nested arrays
        coll.update_one(
            {'_id': doc5_id},
            [{
                '$set': {
                    'data.lvl1.lvl2': {
                            '$map': {
                            'input': '$data.lvl1.lvl2',
                            'as': 'l2',
                            'in': {
                                'lvl3': {
                                    '$map': {
                                        'input': '$$l2.lvl3',
                                        'as': 'l3',
                                        'in': {
                                            'k': '$$l3.k',
                                            'vals': {
                                                '$map': {
                                                    'input': '$$l3.vals',
                                                    'as': 'arr',
                                                    'in': {
                                                        '$filter': {
                                                            'input': '$$arr',
                                                            'as': 'v',
                                                            'cond': {'$ne': ['$$v', 7]}
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }]
        )
        updated = coll.find_one({'_id': doc5_id})
        if any(
            isinstance(inner, list) and 7 in inner
            for l2 in updated['data']['lvl1']['lvl2']
            for l3 in l2.get('lvl3', [])
            for inner in (l3.get('vals') or [])
        ):
            fail('CHAOS C failed: deep removal of 7 failed')

        # CHAOS D — $mergeObjects structural mutation
        pipelineD = [
            {'$match': {'_id': doc5_id}},
            {'$unwind': '$data.polymorphic'},
            {'$match': {'$expr': {'$eq': [{'$type': '$data.polymorphic'}, 'object']}}},
            {'$replaceRoot': {'newRoot': {'$mergeObjects': ['$data.polymorphic', {'chaos': True}]}}},
            {'$group': {'_id': '$_id', 'objs': {'$push': '$$ROOT'}}}
        ]
        res = list(coll.aggregate(pipelineD))
        if not any(o.get('chaos') for o in res[0]['objs']):
            fail('CHAOS D failed: mergeObjects transform failed')

        # CHAOS F — regex match across deep strings (triple-unwind + type-aware)
        pipelineF = [
            {'$match': {'_id': doc5_id}},

            # Unwind outer array
            {'$unwind': {'path': '$data.deep_strings', 'preserveNullAndEmptyArrays': True}},

            # Unwind inner array if it's a list
            {'$unwind': {'path': '$data.deep_strings', 'preserveNullAndEmptyArrays': True}},

            # Unwind again if nested array
            {'$unwind': {'path': '$data.deep_strings', 'preserveNullAndEmptyArrays': True}},

            # Match strings either directly or inside an object field `s` (type-guarded)
            {'$match': {'$or': [
                {'$and': [
                    {'$expr': {'$eq': [{'$type': '$data.deep_strings'}, 'string']}},
                    {'data.deep_strings': {'$regex': 'match_me|abc'}}
                ]},
                {'data.deep_strings.s': {'$regex': 'match_me|abc'}}
            ]}},

            # Group back results
            {'$group': {'_id': '$_id', 'matches': {'$push': '$data.deep_strings'}}}
        ]
        resF = list(coll.aggregate(pipelineF))

        if not resF:
            fail('CHAOS F failed: regex match returned no results')
        print('CHAOS F passed: regex matches found ->', resF[0]['matches'])

        print('ALL MAXIMUM CHAOS TESTS PASSED')

    chaos_suite()

if __name__ == '__main__':
    main()