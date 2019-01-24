from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _


class Command(BaseCommand):
    # We can't gettext_lazy here as the help output function needs a string.
    help = _("Initial setup command to prepare the environment.")

    def handle(self, *args, **kwargs):
        call_command('collectstatic')
        call_command('makemigrations')
        call_command('migrate')
        call_command('restoredefaultuser')
