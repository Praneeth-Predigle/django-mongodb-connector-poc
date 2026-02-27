Good. Let’s make this **clean, simple, and permanent in your head**.

You now understand Mongo properly — so here’s the correct mental model.

---

# 🟢 HOW TO RUN MongoDB WITH REPLICA SET (transactions enabled)

This is what Django needs.

### Start Mongo manually:

```powershell
& "C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe" --dbpath "C:\Program Files\MongoDB\Server\8.2\data" --replSet rs0 --bind_ip localhost --port 27017
```

Then in another terminal:

```powershell
mongosh mongodb://localhost:27017
```

Run once (only first time ever):

```js
rs.initiate()
```

Check:

```js
rs.status()
```

You should see:

```
PRIMARY
```

Done.

---

## Django config for replica mode

```python
DATABASES = {
    "default": {
        "ENGINE": "django_mongodb_backend",
        "NAME": "test",
        "CLIENT": {
            "host": "mongodb://localhost:27017/?replicaSet=rs0",
        },
    }
}
```

That `?replicaSet=rs0` is REQUIRED for transactions.

---

# 🔴 HOW TO RUN MongoDB IN NORMAL (NO REPLICATION) MODE

Stop Mongo (Ctrl+C).

Then start it WITHOUT `--replSet`:

```powershell
& "C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe" --dbpath "C:\Program Files\MongoDB\Server\8.2\data" --bind_ip localhost --port 27017
```

That’s it.

Now it is standalone Mongo.

If you try:

```js
rs.status()
```

You’ll get:

```
NoReplicationEnabled
```

That’s expected.

---

## Django config for normal mode

Remove replicaSet:

```python
DATABASES = {
    "default": {
        "ENGINE": "django_mongodb_backend",
        "NAME": "test",
        "CLIENT": {
            "host": "mongodb://localhost:27017",
        },
    }
}
```

No `?replicaSet=rs0`.

---

# ⚠ IMPORTANT TRUTH

You **cannot switch modes while Mongo is running**.

Replica mode vs normal mode is determined at server startup.

---

# 🧠 What Actually Changes?

| Mode    | Start flag      | Django connection string                    | Transactions |
| ------- | --------------- | ------------------------------------------- | ------------ |
| Normal  | (no flag)       | `mongodb://localhost:27017`                 | ❌ No         |
| Replica | `--replSet rs0` | `mongodb://localhost:27017/?replicaSet=rs0` | ✅ Yes        |

That’s it.

Nothing else changes.
Your data files remain the same.
Your databases remain the same.

---

# 💡 PRO TIP (Best Practice)

There is **no downside** to running single-node replica set locally.

So honestly?

Just always run:

```
--replSet rs0
```

And never think about this again.

That’s how most serious dev setups are done.

---

net stop MongoDB

---

from django.db import connections

# Force connection
connections["default"].ensure_connection()

# Get raw PyMongo client
client = connections["default"].connection.client._client

# Check topology
print(client.topology_description.topology_type_name)