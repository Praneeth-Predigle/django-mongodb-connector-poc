from django.db import models
from django_mongodb_backend.fields import ObjectIdField
from django_mongodb_backend.managers import MongoManager
from django_mongodb_backend.models import EmbeddedModel
from django_mongodb_backend.fields import EmbeddedModelField, EmbeddedModelArrayField
from bson import ObjectId


# Custom manager that strips None values before creating objects
'''class SparseManager(MongoManager):
    def create(self, **kwargs):
        # We define what "Empty" means for your NoSQL policy
        # We strip None, "", [], and {}
        clean_kwargs = {
            k: v for k, v in kwargs.items() 
            if v is not None and v != "" and v != [] and v != {}
        }
        xyysaz=1
        return super().create(**clean_kwargs)
'''

class InfoNode(EmbeddedModel):
    label = models.CharField(max_length=100, null=True, blank=True)
    data_blob = models.TextField(null=True, blank=True) # Our 500KB weight goes here
    flag = models.BooleanField(null=True)

    class Meta:
        app_label = 'mongocon'

# Abstract base class level 1 — track runtime-set non-empty fields for sparse UPDATEs
class AbstractBotBase1(models.Model):
    name = models.IntegerField(db_index=True, null=True, blank=True)

    @staticmethod
    def iterative_clean(root_value):
        """
        Final iterative loop for deep pruning.
        One pass, in-place, zero recursion overhead.
        """
        if not isinstance(root_value, (dict, list)):
            return root_value

        stack = [root_value]
        while stack:
            curr = stack.pop()
            if isinstance(curr, dict):
                # Prune top level of this dict
                to_delete = [k for k, v in curr.items() if v in (None, "", [], {})]
                for k in to_delete:
                    del curr[k]
                # Queue nested objects
                for v in curr.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(curr, list):
                # Prune top level of this list
                curr[:] = [i for i in curr if i not in (None, "", [], {})]
                # Queue nested objects
                for i in curr:
                    if isinstance(i, (dict, list)):
                        stack.append(i)
        return root_value

    def _do_insert(self, manager, using, fields, returning_fields, raw):
        essential = {self._meta.pk.name, 'id', 'created_at'}
        sparse_fields = []
        
        for f in fields:
            val = getattr(self, f.attname)
            if val not in (None, "", [], {}) or f.attname in essential:
                # Clean the data before it hits the compiler
                if isinstance(val, (dict, list)):
                    self.iterative_clean(val)
                sparse_fields.append(f)

        return manager._insert(
            [self], 
            fields=sparse_fields, 
            returning_fields=returning_fields, 
            using=using, 
            raw=raw
        )

    class Meta:
        abstract = True

# Abstract base class level 2
class AbstractBotBase2(AbstractBotBase1):
    status = models.CharField(max_length=50, db_index=True, null=True, blank=True)
    class Meta:
        abstract = True

# Abstract base class level 3
class AbstractBotBase3(AbstractBotBase2):
    level3_field = models.CharField(max_length=100, null=True, blank=True)
    class Meta:
        abstract = True


class Bot(AbstractBotBase3):
    id = ObjectIdField(primary_key=True, default=ObjectId)
    description = models.TextField(null=True, blank=True)
    client_id = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    slug = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    deleted_status = models.CharField(max_length=1, null=True, blank=True)
    type = models.CharField(max_length=50, db_index=True, null=True, blank=True)
    tags = models.JSONField(default=list, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, null=True, blank=True)
    audit_data = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    main_node = EmbeddedModelField(InfoNode, null=True, blank=True)
    node_history = EmbeddedModelArrayField(InfoNode, null=True, blank=True, default=list)
    #objects = MongoManager()
    class Meta:
        indexes = [
            models.Index(fields=["client_id"]),
            models.Index(fields=["slug"]),
        ]


class AbstractBot2Base1(models.Model):
    name = models.IntegerField(db_index=True, null=True, blank=True)
    class Meta:
        abstract = True

class AbstractBot2Base2(AbstractBot2Base1):
    status = models.CharField(max_length=50, db_index=True, null=True, blank=True)
    class Meta:
        abstract = True

# Abstract base class level 3
class AbstractBot2Base3(AbstractBot2Base2):
    level3_field = models.CharField(max_length=100, null=True, blank=True)
    class Meta:
        abstract = True

class Bot2(AbstractBot2Base3):
    id = ObjectIdField(primary_key=True, default=ObjectId)
    description = models.TextField(null=True, blank=True)
    client_id = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    slug = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    deleted_status = models.CharField(max_length=1, null=True, blank=True)
    type = models.CharField(max_length=50, db_index=True, null=True, blank=True)
    tags = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, null=True, blank=True)
    audit_data = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    dynamic_data = models.JSONField(null=True, blank=True)
    main_node = EmbeddedModelField(InfoNode, null=True, blank=True)
    node_history = EmbeddedModelArrayField(InfoNode, null=True, blank=True, default=list)
    #objects = MongoManager()
    class Meta:
        indexes = [
            models.Index(fields=["client_id"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["status"]),
        ]

# Example EmbeddedModel + parent model to demonstrate embedded-field behavior
class Address(EmbeddedModel):
    city = models.CharField(max_length=100, null=True, blank=True)
    street = models.CharField(max_length=200, null=True, blank=True)


class Bot3(models.Model):
    id = ObjectIdField(primary_key=True, default=ObjectId)
    name = models.CharField(max_length=255, null=True, blank=True)
    # single embedded object
    address = EmbeddedModelField(Address, null=True, blank=True)
    # array of embedded objects
    previous_addresses = EmbeddedModelArrayField(Address, blank=True, default=list, null=True)
    objects = MongoManager()

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
        ]