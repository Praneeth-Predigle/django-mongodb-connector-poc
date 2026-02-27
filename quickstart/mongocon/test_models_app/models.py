from django.db import models

try:
    from django_mongodb_backend.managers import MongoManager
except Exception:
    # Fallback if manager import is unavailable during static analysis
    class MongoManager(models.Manager):
        pass


class ComplexDoc(models.Model):
    """A simple model storing a JSON document. Used to test nested arrays/embedded docs."""

    data = models.JSONField()
    objects = MongoManager()

    class Meta:
        app_label = 'test_models_app'
        db_table = 'test_models_app_complexdoc'
