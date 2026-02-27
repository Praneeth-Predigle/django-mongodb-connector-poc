from django.contrib.admin.apps import AdminConfig
from django.contrib.auth.apps import AuthConfig
from django.contrib.contenttypes.apps import ContentTypesConfig


class MongoAdminConfig(AdminConfig):
    default_auto_field = "django.db.models.AutoField"


class MongoAuthConfig(AuthConfig):
    default_auto_field = "django.db.models.AutoField"


class MongoContentTypesConfig(ContentTypesConfig):
    default_auto_field = "django.db.models.AutoField"
