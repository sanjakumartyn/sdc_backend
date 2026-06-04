from django.apps import AppConfig

class DealsConfig(AppConfig):
    default_auto_field = 'django_mongodb_backend.fields.ObjectIdAutoField'
    name = 'features.deals'
    verbose_name = 'Deals Management'
