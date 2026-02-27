'''from django.db import models
from django_mongodb_backend.fields import ObjectIdField
from django_mongodb_backend.managers import MongoManager
from bson import ObjectId

# You can add abstract base classes here if needed, but for now, just migrate Bot
class Bot(models.Model):
    id = ObjectIdField(primary_key=True, default=ObjectId)
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField()
    client_id = models.CharField(max_length=255, db_index=True)
    slug = models.CharField(max_length=255, db_index=True)
    deleted_status = models.CharField(max_length=1)
    status = models.CharField(max_length=50, db_index=True)
    type = models.CharField(max_length=50, db_index=True)
    tags = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    audit_data = models.JSONField()
    metadata = models.JSONField()
    objects = MongoManager()
    class Meta:
        indexes = [
            models.Index(fields=["client_id"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["status"]),
        ]
'''

import uuid
from django.db import models
from django.utils.text import slugify

# Importing your custom field classes from the framework
from py_predigle.utils.models import fields

# ==========================================
# 1. EMBEDDED CONTAINERS (InfoNode)
# ==========================================

class InfoNode(models.Model):
    """
    The container for the benchmark payload.
    In Djongo, model_containers must be abstract or standard classes.
    """
    label = models.CharField(max_length=100, null=True, blank=True)
    data_blob = models.TextField(null=True, blank=True) # The 4KB weight
    flag = models.BooleanField(null=True)

    class Meta:
        abstract = True

# ==========================================
# 2. THE THING INHERITANCE TRACE
# ==========================================

class CDModel(models.Model):
    identifier = fields.CharField(max_length=50, blank=True, null=True)
    client_id = fields.CharField(max_length=50, blank=True, null=True)
    slug = fields.CharField(max_length=50, blank=True, null=True)
    hidden = fields.BooleanField(default=False)
    deleted_status = fields.CharField(max_length=50, blank=True, default="N")
    
    # Nested fields using CustomFormedField logic
    # (Assuming Acl, Audit, Plugin are defined in your framework)
    # acl = fields.ArrayField(model_container=Acl, default=[])
    # audit_data = fields.EmbeddedField(model_container=Audit)
    
    status = fields.CharField(max_length=255, blank=True)

    class Meta:
        abstract = True

class NamedModel(CDModel):
    name = fields.CharField(max_length=100, blank=True, null=True, default="")
    description = fields.CharField(max_length=100, blank=True, null=True)
    image_url = fields.CharField(max_length=1000, blank=True, null=True)
    video_url = fields.CharField(max_length=1000, blank=True, null=True)
    type = fields.CharField(max_length=100, blank=True, null=True)
    path = fields.CharField(max_length=100, blank=True, null=True)

    class Meta:
        abstract = True

class Thing(NamedModel):
    # base = fields.EmbeddedField(model_container=ThingReference)
    # tags = fields.ArrayField(model_container=Tag, default=[])
    # group = fields.EmbeddedField(model_container=Group, default=None)

    class Meta:
        abstract = True

# ==========================================
# 3. THE FINAL BOT MODEL
# ==========================================

class Bot(Thing):
    """
    Model representing a bot for the scientific benchmark.
    Inherits from Thing -> NamedModel -> CDModel.
    """

    _id = fields.ObjectIdField() 
    
    # Containers provided by your framework
    # metadata = fields.EmbeddedField(model_container=Metadata)
    # configuration = fields.EmbeddedField(model_container=Config)
    
    # Benchmarking nodes (mirroring the 'Regular' and 'Sparse' tests)
    main_node = fields.EmbeddedField(model_container=InfoNode)
    node_history = fields.ArrayField(model_container=InfoNode, default=[], blank=True)

    objects = fields.DjongoManager()

    class Meta(Thing.Meta):
        db_table = "bot"
        verbose_name = "Bot"
        verbose_name_plural = "Bots"
        ordering = ("-_id",)
        abstract = False

    def __str__(self):
        name = self.metadata.get("name", "Unknown") if hasattr(self, "metadata") else "Bot"
        return f'{self.pk} - {name}'

    def save(self, *args, **kwargs):
        # 1. Automatic Slug Generation
        if not self.slug:
            # Safely attempt to get name from metadata or the name field
            name_source = "bot"
            if hasattr(self, "metadata") and isinstance(self.metadata, dict):
                name_source = self.metadata.get("name", "bot")
            elif self.name:
                name_source = self.name
            
            self.slug = f"{slugify(name_source)}-{uuid.uuid4().hex[:6]}"

        # 2. Configuration Logic (Recursive UUIDs for sources/destinations)
        if hasattr(self, "configuration") and self.configuration:
            config = self.configuration

            if "slug" not in config:
                config["slug"] = str(uuid.uuid4())

            for nested_key in ["sources", "destinations"]:
                if nested_key in config:
                    for item in config[nested_key]:
                        if isinstance(item, dict) and "slug" not in item:
                            item["slug"] = str(uuid.uuid4())

        # 3. Variable Logic
        if hasattr(self, "variables") and self.variables:
            for variable in self.variables:
                if isinstance(variable, dict) and "slug" not in variable:
                    variable["slug"] = str(uuid.uuid4())

        # Triggers CustomFormedField's _save_value_thru_fields cleaning
        super().save(*args, **kwargs)