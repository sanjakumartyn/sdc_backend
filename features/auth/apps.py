from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'features.auth'
    label = 'features_auth'
    verbose_name = 'Auth Feature'
