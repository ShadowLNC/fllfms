from django.apps import AppConfig


class FLLFMSConfig(AppConfig):
    name = 'fllfms'
    verbose_name = "FLL FMS"

    def ready(self):
        from . import signals  # Bind signals.
