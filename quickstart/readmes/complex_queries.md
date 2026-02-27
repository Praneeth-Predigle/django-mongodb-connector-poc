# Complex Queries (CRUD + Aggregations)

This file collects representative examples from the codebase showing CRUD and complex aggregation usage against MongoDB using:

- Raw PyMongo (`pymongo.MongoClient`) for full MongoDB power
- Official Django MongoDB backend (`django_mongodb_backend`) `MongoManager` + `raw_aggregate()` for hybrid results

Use these snippets in design docs or migration plans to demonstrate the kinds of complex operations we run and how they translate between Djongo and the official backend.

main ways we are doing things:

Dot-path addressing

Array operators ($elemMatch, $unwind, $map, $filter, $reduce)

Aggregation pipelines

Positional updates + arrayFilters
---

## 1) Raw PyMongo CRUD examples
Source: `mongocon/raw_crud.py`

Purpose: demonstrate inserting a deeply nested document that includes arrays, embedded objects, and timestamps.
Create (insert a deeply nested document):

```python
from pymongo import MongoClient
from datetime import datetime, timezone

client = MongoClient('mongodb://localhost:27017/')
db = client.mongoenv_perf_test

bot = {
    "_id": "raw_test_bot_1",
    "name": "Raw Test Bot 1",
    "description": "Test bot for raw MongoDB operations",
    "audit_data": {
        "create_ts": datetime.now(timezone.utc),
        "update_ts": datetime.now(timezone.utc)
    },
    "metadata": {
        "version": "1.0.0",
        "type": {"type": "test", "category": "raw_testing"}
    },
    "tags": [{"name": "test", "value": "raw"}],
    "configuration": {
        "sources": [{"name": "Raw Test Source", "type": "mongodb"}],
        "processors": [{"name": "Raw Test Processor", "config": {"test_param": "value_1"}}]
    }
}

result = db.bot.insert_one(bot)
print('inserted_id=', result.inserted_id)
```

Purpose: demonstrate a simple read by primary key to validate the document was stored.
Read (find one):

```python
bot = db.bot.find_one({"_id": "raw_test_bot_1"})
print(bot)
```

Purpose: demonstrate updating nested fields using dot-paths to modify deep values.
Update (dot-path update of nested fields):

```python
result = db.bot.update_one(
    {"_id": "raw_test_bot_1"},
    {"$set": {
        "description": "Updated by raw PyMongo",
        "audit_data.update_ts": datetime.now(timezone.utc),
        "metadata.status": "updated"
    }}
)
print('modified_count=', result.modified_count)
```

Purpose: demonstrate deleting a document by primary key.
Delete:

```python
result = db.bot.delete_one({"_id": "raw_test_bot_1"})
print('deleted_count=', result.deleted_count)
```

These examples show insertion, read, update, and delete of documents that include nested dicts, arrays of dicts, and mixed primitives/objects.

---

## 2) Aggregation pipelines (PyMongo)
Source: `mongocon/raw_query.py` and `mongocon/pymongo_agg.py`

Purpose: compute counts grouped by the `type` field using an aggregation pipeline.
Count by type (group):

```python
pipeline = [
    {"$match": {"deleted_status": "N"}},
    {"$group": {"_id": "$type", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]
results = list(db.bot.aggregate(pipeline))
```

Purpose: compute an aggregate metric (average number of tags per bot) using `$project` and `$group`.
Average tags per bot (computed field + group):

```python
pipeline = [
    {"$match": {"deleted_status": "N"}},
    {"$project": {"tag_count": {"$size": {"$ifNull": ["$tags", []]}}}},
    {"$group": {"_id": None, "avg_tags": {"$avg": "$tag_count"}}}
]
results = list(db.bot.aggregate(pipeline))
```

Purpose: show how to unwind a nested array (`configuration.sources`) and group results by source type.
Complex nested example: unwind nested array of sources and group:

```python
pipeline = [
    {"$match": {"deleted_status": "N", "configuration.sources": {"$exists": True, "$ne": []}}},
    {"$unwind": "$configuration.sources"},
    {"$match": {"configuration.sources.type": "mongodb"}},
    {"$group": {"_id": {"bot_name": "$name", "source_type": "$configuration.sources.type"}, "source_count": {"$sum": 1}}},
    {"$sort": {"source_count": -1}},
    {"$limit": 10}
]
results = list(db.bot.aggregate(pipeline))
```

Notes:
- Use `$unwind` carefully when array elements can be primitives — filter (`$match`) for objects (`$exists`) before `$replaceRoot` or `$unwind` into object fields.
- Use `$ifNull` with `$size` to avoid errors on missing arrays.

---

## 3) Django ORM + Official backend hybrid (raw_aggregate)
Source: `mongocon/orm_agg.py`

Purpose: show running a raw aggregation pipeline via the Django `MongoManager` so teams understand how to mix ORM and raw pipelines.

If models use `objects = MongoManager()` (from `django_mongodb_backend.managers`), you can run raw MongoDB pipelines and (optionally) get Django model instances.

Example using `raw_aggregate()` on `Bot` model:

```python
results = list(Bot.objects.raw_aggregate([
    {"$match": {"deleted_status": "N"}},
    {"$unwind": "$tags"},
    {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
    {"$limit": 20}
]))

for r in results:
    print(r)  # may be Django model instances or dicts depending on manager implementation
```

Caveats:
- `raw_aggregate()` implementations may require the pipeline to return the model primary key (`_id`) so instances can be materialized. If you get errors like "Raw query must include the primary key", include `{"$project": {"_id": 1, ...}}` early in the pipeline.

---

## 4) Safe nested-array querying patterns

Purpose: demonstrate a safe pattern for matching an element inside an array of embedded documents using `$elemMatch`.

- Use `$elemMatch` for matching an element inside an array of embedded documents:

```python
db.collection.find_one({"data.level1": {"$elemMatch": {"name": "a"}}})
```

Purpose: show a safe unwind pattern that guards against primitives before replacing root or accessing object fields.

- When unwinding to access nested arrays of mixed types, filter for objects first:

```python
pipeline = [
    {'$unwind': '$data.level1'},
    {'$unwind': '$data.level1.items'},
    {'$match': {'data.level1.items.deep2': {'$exists': True}}},
    {'$unwind': '$data.level1.items.deep2.sub'},
    {'$match': {'data.level1.items.deep2.sub.k': 'v2'}},
]
```

---

## 5) Mapping notes for migration (Djongo → Official backend)

- Djongo provided `Model.objects.mongo_aggregate(pipeline)` — not available in the official backend. Replace with either:
  - Raw PyMongo calls (`db.collection.aggregate(pipeline)`) for performance and full feature access, or
  - `Model.objects.raw_aggregate(pipeline)` with `MongoManager()` when you need Django model instances.
- Ensure pipelines include `_id` if you expect results to be converted to model instances.
- Watch for type conversions: use native `ArrayField` / `EmbeddedModelField` in official backend where possible, and avoid Djongo SQL-like constraints.

---

## 6) Files where examples live

- `mongocon/raw_crud.py` — raw CRUD with nested docs
- `mongocon/raw_query.py` — raw aggregation examples
- `mongocon/pymongo_agg.py` — aggregation benchmarks & patterns
- `mongocon/orm_agg.py` — `raw_aggregate()` examples via `MongoManager`
- `testing_scripts/nested_field_queries.py` — ORM lookups into embedded/array fields

Use this document as a handoff to explain complexity and to justify migration choices (raw PyMongo for performance + `raw_aggregate()` for convenience).

---

## 7) Deep Tests (new)

I added a standalone deep-tests script that validates several of the "annoying" edge cases we care about. File: [quickstart/mongocon/test_scripts/test_deep_complex.py](quickstart/mongocon/test_scripts/test_deep_complex.py#L1)

What it checks
- **Embedded within embedded + arrays of embedded objects:** uses `$elemMatch` to match nested array elements.
- **Array-of-arrays flattening:** demonstrates `$reduce` + `$concatArrays` to flatten nested arrays and verifies the flattened order.
- **Positional updates with `arrayFilters`:** uses `update_one(..., array_filters=[...])` to update the correct array element.
- **Mixed-type arrays + safe `$replaceRoot`:** unwinds an array containing primitives and objects, filters to object types using `$type`, and then `$replaceRoot` to expose object fields.

Why these tests
- They reproduce real-world shapes where Djongo and the official backend can behave differently (array matching, positional updates, pipelines that must guard for primitives).

How to run (from repo root, with the `mongoenv` virtualenv activated):

```powershell
cd "E:\Pedigle VS Code\mongo-poc\quickstart\mongocon\test_scripts"
..\..\..\mongoenv\Scripts\python.exe .\test_deep_complex.py
```

Expected output: `ALL DEEP TESTS PASSED` on success.

Notes
- The script is intentionally standalone and uses PyMongo directly to avoid requiring the Django app import during quick validation runs.
- If you need these checks integrated into the Django test suite, I can convert the script into Django `TestCase`s that use the project's test DB settings.

### Code snippets (excerpts from `quickstart/mongocon/test_scripts/test_deep_complex.py`)

Purpose: include the actual test code so reviewers see exactly what each check does.

- Insert sample documents (creates several shapes used by the tests):

```python
from bson import ObjectId

doc1 = {'_id': ObjectId(), 'embedded': {'inner': {'name': 'a', 'arr': [{'x': 1}, {'y': 2}]}}}
doc2 = {'_id': ObjectId(), 'arr_of_arrs': [[1, 2], [3, 4]]}
doc3 = {'_id': ObjectId(), 'pos_arr': [{'k': 1, 'v': 0}, {'k': 2, 'v': 0}]}
doc4 = {'_id': ObjectId(), 'mixed': [1, {'a': 2}, 'x', {'b': 3}]}

coll.insert_many([doc1, doc2, doc3, doc4])
```

- Test: match an element inside an array of embedded documents using `$elemMatch`:

```python
found = coll.find_one({'embedded.inner.arr': {'$elemMatch': {'y': 2}}})
assert found and found['_id'] == doc1['_id']
```

- Test: flatten `arr_of_arrs` with `$reduce` + `$concatArrays`, unwind and collect values:

```python
pipeline = [
    {'$match': {'_id': doc2['_id']}},
    {'$project': {'flatten': {'$reduce': {
        'input': '$arr_of_arrs',
        'initialValue': [],
        'in': {'$concatArrays': ['$$value', '$$this']}
    }}}},
    {'$unwind': '$flatten'},
    {'$group': {'_id': '$_id', 'vals': {'$push': '$flatten'}}}
]
res = list(coll.aggregate(pipeline))
assert res and res[0]['vals'] == [1, 2, 3, 4]
```

- Test: positional update using `arrayFilters` to target the element with `k == 2`:

```python
coll.update_one({'_id': doc3['_id']}, {'$set': {'pos_arr.$[elem].v': 9}}, array_filters=[{'elem.k': 2}])
updated = coll.find_one({'_id': doc3['_id']})
assert updated['pos_arr'][1]['v'] == 9
```

- Test: unwind mixed-type array, filter by `$type` to only handle object elements, then `$replaceRoot`:

```python
pipeline2 = [
    {'$match': {'_id': doc4['_id']}},
    {'$unwind': '$mixed'},
    {'$match': {'$expr': {'$eq': [{'$type': '$mixed'}, 'object']}}},
    {'$replaceRoot': {'newRoot': '$mixed'}},
    {'$group': {'_id': '$_id', 'objs': {'$push': '$$ROOT'}}}
]
res2 = list(coll.aggregate(pipeline2))
assert res2 and any('a' in o for o in res2[0]['objs']) and any('b' in o for o in res2[0]['objs'])
```

These snippets match the standalone script and provide reviewers a quick copy-pasteable set of checks to run locally.

---

## 8) MAXIMUM CHAOS SUITE (PyMongo)

Purpose: exercise the document model with deeply nested arrays, mixed types, multi-level `arrayFilters`, nested `$map/$filter/$reduce`, `$mergeObjects`, and structural rewrites. These tests are intentionally pathological to reveal edge-case behavior.

Insert the chaos document (copy into a PyMongo script or run the `test_deep_complex.py` which already inserts this):

```python
# 5) MAXIMUM CHAOS DOCUMENT
doc5 = {
    '_id': ObjectId(),
    'lvl1': {
        'lvl2': [
            {
                'lvl3': [
                    {'k': 1, 'vals': [[1, 2], [3, {'deep': [10, 20]}]]},
                    {'k': 2, 'vals': [[4], [5, 6]]}
                ]
            },
            {
                'lvl3': [
                    {'k': 3, 'vals': [[7, 8]]}
                ]
            }
        ]
    },
    'polymorphic': [
        {'type': 'obj', 'payload': {'a': 1}},
        [1, 2, {'nested': {'z': 9}}],
        "string",
        42
    ]
}

coll.insert_one(doc5)
```

CHAOS A — Deep flattening with `$reduce` + `$concatArrays`

Purpose: flatten all numeric values inside `lvl3.vals` across all levels, then verify expected numbers are present.

```python
pipeline = [
    {'$match': {'_id': doc5['_id']}},
    {'$unwind': '$lvl1.lvl2'},
    {'$unwind': '$lvl1.lvl2.lvl3'},
    {'$project': {
        'flat': {
            '$reduce': {
                'input': '$lvl1.lvl2.lvl3.vals',
                'initialValue': [],
                'in': {'$concatArrays': ['$$value', '$$this']}
            }
        }
    }},
    {'$unwind': '$flat'},
    {'$match': {'$expr': {'$eq': [{'$type': '$flat'}, 'int']}}},
    {'$group': {'_id': '$_id', 'nums': {'$push': '$flat'}}}
]

res = list(coll.aggregate(pipeline))
assert res and 1 in res[0]['nums'] and 8 in res[0]['nums']
```

CHAOS B — Multi-level `arrayFilters` update

Purpose: set a flag only on `lvl3` elements where `k == 2`, using `$[]` + arrayFilters to traverse layers.

```python
coll.update_one(
    {'_id': doc5['_id']},
    {'$set': {'lvl1.lvl2.$[].lvl3.$[elem].flagged': True}},
    array_filters=[{'elem.k': 2}]
)

updated = coll.find_one({'_id': doc5['_id']})
assert any(
    l3.get('flagged')
    for l2 in updated['lvl1']['lvl2']
    for l3 in l2['lvl3']
    if l3['k'] == 2
)
```

CHAOS C — Deep removal from nested array-of-arrays

Purpose: remove a specific numeric value (`7`) buried inside nested arrays using an aggregation-style update (mapping + filtering). This avoids brittle positional dot-path `$pull` addressing.

```python
coll.update_one(
    {'_id': doc5['_id']},
    [{
        '$set': {
            'lvl1.lvl2': {
                '$map': {
                    'input': '$lvl1.lvl2',
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

updated = coll.find_one({'_id': doc5['_id']})
assert not any(7 in inner for l2 in updated['lvl1']['lvl2'] for l3 in l2['lvl3'] for inner in l3['vals'] if isinstance(inner, list))
```

CHAOS D — `$mergeObjects` structural mutation on polymorphic elements

Purpose: apply `$mergeObjects` to only object-typed entries of `polymorphic`, adding a new field to transformed objects.

```python
pipeline2 = [
    {'$match': {'_id': doc5['_id']}},
    {'$unwind': '$polymorphic'},
    {'$match': {'$expr': {'$eq': [{'$type': '$polymorphic'}, 'object']}}},
    {'$replaceRoot': {
        'newRoot': {
            '$mergeObjects': [
                '$polymorphic',
                {'chaos': True}
            ]
        }
    }},
    {'$group': {'_id': '$_id', 'objs': {'$push': '$$ROOT'}}}
]

res2 = list(coll.aggregate(pipeline2))
assert res2 and any(o.get('chaos') for o in res2[0]['objs'])
```

CHAOS E — `$map` recursion to increment numeric values deeply

Purpose: use an aggregation-update pipeline that applies nested `$map` transforms to increment integers inside `vals` by 1. This tests nested `$map`/`$cond` behavior in updates.

```python
coll.update_one(
    {'_id': doc5['_id']},
    [{
        '$set': {
            'lvl1.lvl2': {
                '$map': {
                    'input': '$lvl1.lvl2',
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
                                                '$map': {
                                                    'input': '$$arr',
                                                    'as': 'v',
                                                    'in': {
                                                        '$cond': [
                                                            {'$eq': [{'$type': '$$v'}, 'int']},
                                                            {'$add': ['$$v', 1]},
                                                            '$$v'
                                                        ]
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
        }
    }]
)
```

Notes and next steps
- These snippets are already present and exercised in `quickstart/mongocon/test_scripts/test_deep_complex.py` (chaos suite appended). Use the script for quick validation.
- If you'd like, I can also embed these code blocks into `readmes/migration_plan.md` or produce Django `TestCase` equivalents for CI.

---

## 9) MAXIMUM CHAOS — model-free (use `collection.aggregate`)

Purpose: For these pathological pipelines it's simpler and more predictable to run them directly against the backend collection using `connections['default'].get_collection(...).aggregate(...)`. That returns plain dicts and avoids `raw_aggregate()` trying to materialize Django model instances (which requires `_id` to be carried through early and can convert results into non-subscriptable model objects).

Insert the chaos document (model-free example; in the test script we insert under `data` to keep pipelines consistent):

```python
doc5 = {
        '_id': ObjectId(),
        'data': {
                'lvl1': {
                        'lvl2': [
                                {'lvl3': [{'k':1, 'vals': [[1,2],[3,{'deep':[10,20]}]]}, {'k':2,'vals': [[4],[5,6]]}]},
                                {'lvl3': [{'k':3, 'vals': [[7,8]]}]}
                        ]
                },
                'polymorphic': [{'type':'obj','payload':{'a':1}}, [1,2,{'nested':{'z':9}}], 'string', 42],
                'deep_strings': [[['abc-1'], ['no-match']], [{'level2': [{'s': 'match_me'}]}], 'outerstring']
        }
}
coll.insert_one(doc5)
```

Key chaos snippets (copy-pasteable):

- CHAOS A — deep flattening (reduce + concatArrays):

```python
pipelineA = [
    {'$match': {'_id': doc5['_id']}},
    {'$unwind': '$data.lvl1.lvl2'},
    {'$unwind': '$data.lvl1.lvl2.lvl3'},
    {'$project': {'flat': {'$reduce': {'input':'$data.lvl1.lvl2.lvl3.vals','initialValue':[],'in':{'$concatArrays':['$$value','$$this']}}}}},
    {'$unwind':'$flat'},
    {'$match': {'$expr': {'$eq': [{'$type': '$flat'}, 'int']}}},
    {'$group': {'_id':'$_id','nums':{'$push':'$flat'}}}
]
res = list(coll.aggregate(pipelineA))
```

- CHAOS B — multi-level `arrayFilters` update:

```python
coll.update_one({'_id': doc5['_id']}, {'$set': {'data.lvl1.lvl2.$[].lvl3.$[elem].flagged': True}}, array_filters=[{'elem.k': 2}])
```

- CHAOS C — deep removal (aggregation-style map+filter update). Note the corrected `data.` input path:

```python
coll.update_one({'_id': doc5['_id']}, [{
    '$set': {
        'data.lvl1.lvl2': {
            '$map': {
                'input': '$data.lvl1.lvl2',
                'as': 'l2',
                'in': {'lvl3': {'$map': {
                     'input': '$$l2.lvl3','as':'l3','in':{
                         'k':'$$l3.k','vals':{'$map':{
                             'input':'$$l3.vals','as':'arr','in':{'$filter':{'input':'$$arr','as':'v','cond':{'$ne':['$$v',7]}}}
}}}}}}
    }
}])
```

- CHAOS D — `$mergeObjects` transform on object-typed `polymorphic` elements:

```python
pipelineD = [
    {'$match': {'_id': doc5['_id']}},
    {'$unwind': '$data.polymorphic'},
    {'$match': {'$expr': {'$eq': [{'$type': '$data.polymorphic'}, 'object']}}},
    {'$replaceRoot': {'newRoot': {'$mergeObjects': ['$data.polymorphic', {'chaos': True}]}}},
    {'$group': {'_id': '$_id', 'objs': {'$push': '$$ROOT'}}}
]
res = list(coll.aggregate(pipelineD))
```

- CHAOS E — nested `$map` update to increment integers:

```python
coll.update_one({'_id': doc5['_id']}, [{'$set': {'data.lvl1.lvl2': { ... nested $map/$cond ... }}}])
```

- CHAOS F — regex across deep string positions (unwind + match):

```python
pipelineF = [
    {'$match': {'_id': doc5['_id']}},
    {'$unwind':'$data.deep_strings'},
    {'$unwind': {'path':'$data.deep_strings','preserveNullAndEmptyArrays':True}},
    {'$match': {'$or':[{'data.deep_strings':{'$regex':'match_me|abc'}},{'data.deep_strings.s':{'$regex':'match_me|abc'}}]}},
    {'$group':{'_id':'$_id','matches':{'$push':'$data.deep_strings'}}}
]
resF = list(coll.aggregate(pipelineF))
```

- CHAOS G — regex on object keys via `$objectToArray`:

Regex pattern used in CHAOS F:

```python
# The exact regex used in the CHAOS F pipeline (matches either 'match_me' or 'abc')
REGEX_PATTERN = r'match_me|abc'

# In MongoDB pipelines the same pattern appears as:
#{'$regex': 'match_me|abc'}
```


 - CHAOS G — regex on object keys via `$objectToArray`:

```python
pipelineG = [
    {'$match': {'_id': doc5['_id']}},
    {'$project': {'kv': {'$objectToArray': '$data.lvl1'}}},
    {'$unwind': '$kv'},
    {'$match': {'kv.k': {'$regex': '^lvl'}}},
    {'$group': {'_id': '$_id', 'keys': {'$addToSet': '$kv.k'}}}
]
resG = list(coll.aggregate(pipelineG))
```

Recommendation summary:
- Use `connections['default'].get_collection('<your_collection>')` and call `.aggregate(...)` for chaotic raw pipelines — you get plain dicts and avoid model-materialization constraints.
- Only use `Model.objects.raw_aggregate(...)` if you explicitly want Django model instances back; then ensure `_id` is preserved in the first projection/group stage.



