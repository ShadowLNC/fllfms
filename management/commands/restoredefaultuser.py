from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.translation import gettext as _


class Command(BaseCommand):
    DEFAULT_USER = "root"
    DEFAULT_PASSWORD = "321Lego!"
    # We can't gettext_lazy here as the help output function needs a string.
    help = _("Creates or resets the default (superuser) account. \n"
             f"Username: '{DEFAULT_USER}'. Password: '{DEFAULT_PASSWORD}'.")

    @transaction.atomic()
    def handle(self, *args, **kwargs):
        # This isn't very elegant, but it works and I don't have a better
        # solution. It's for people who can't use CLI/Django commands.

        # By deleting and recreating, we ensure all flags are correct (active,
        # (staff, superuser, etc.) and also force the logout of all current
        # sessions (for this user). delete() only acts if the user exists.
        get_user_model().objects.filter(username=self.DEFAULT_USER).delete()
        get_user_model().objects.create_superuser(
            username=self.DEFAULT_USER, email=None,
            password=self.DEFAULT_PASSWORD)
