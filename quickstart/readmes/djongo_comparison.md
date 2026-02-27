# Djongo vs Official MongoDB Connector - Schema Enforcement Demo

## The Key Difference:

### Official MongoDB Connector (What we tested):
```python
# This WORKS - Missing required fields get defaults
movie = Movie.objects.create(plot='Test plot', runtime=100)  # Missing title
# Result: Document created with title="" (empty string)
print(f"Movie created with title: '{movie.title}'")  # Output: ""
```

### Djongo (SQL-like approach):
```python
# This would FAIL - Djongo enforces SQL constraints
movie = Movie.objects.create(plot='Test plot', runtime=100)  # Missing title
# Result: IntegrityError or similar - INSERT rejected at database level
```

## Why This Matters:

**Djongo's Philosophy:** "Make MongoDB act like PostgreSQL"
- Creates SQL tables with NOT NULL constraints
- Translates Django models to SQL schema
- Missing required fields = Database constraint violation

**Official Connector's Philosophy:** "Embrace MongoDB's document nature"
- No artificial SQL constraints on MongoDB
- Django validation happens at application level
- Missing fields = Default values (flexible documents)

## Real-World Impact:

**With Djongo:**
```python
# This fails even though MongoDB could handle it naturally
Movie.objects.create(title="Movie", runtime=100)  # Missing 'plot' field
# ERROR: column "plot" of relation "movie" violates not-null constraint
```

**With Official Connector:**
```python
# This works - MongoDB's flexible schema shines
Movie.objects.create(title="Movie", runtime=100)  # Missing 'plot' field
# SUCCESS: {"title": "Movie", "runtime": 100} - no 'plot' field in document
```

**Bottom Line:** Djongo fights MongoDB's strengths. Official connector leverages them.