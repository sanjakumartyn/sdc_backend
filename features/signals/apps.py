from django.apps import AppConfig

class SignalsConfig(AppConfig):
    default_auto_field = 'django_mongodb_backend.fields.ObjectIdAutoField'
    name = 'features.signals'
    verbose_name = 'Signals Management'
