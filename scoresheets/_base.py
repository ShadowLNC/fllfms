from collections import defaultdict

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


# For boolean and integer fields, we still declare choices, as the Django admin
# site will then make it a select/radio field where we can replicate the style
# of the old LabVIEW system.
# For choices/intchoices, database constraints are still required.
# In all cases, ensure choices are strings for proper AdminSite handling.
def boolchoices(**kwargs):
    return models.BooleanField(choices=[(False, _("No")), (True, _("Yes"))],
                               **kwargs)


def choices(*choices, **kwargs):
    return models.PositiveSmallIntegerField(
        choices=[(i, str(c)) for i, c in enumerate(choices)], **kwargs)


class BaseScoresheet(models.Model):
    player = models.OneToOneField(
        'player', related_name="scoresheet", on_delete=models.PROTECT,
        verbose_name=_("player"))

    # NOTE: Cache value only.
    score = models.IntegerField(
        editable=False, db_index=True, verbose_name=_("cached score"))

    # Keep as a ForeignKey for now, but need to filter to referee group later.
    referee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        verbose_name=_("station referee"))
    # BLOB preferred vs file: https://arxiv.org/ftp/cs/papers/0701/0701168.pdf
    # Student signature. (PNG < 50KB0)
    signature = models.BinaryField(editable=True,
                                   verbose_name=_("team initials"))

    def clean(self, doraise=True):
        errs = defaultdict(list)

        if self.pk is not None:
            old = self.__class__.objects.get(pk=self.pk)
            if old.signature == self.signature:
                errs['signature'].append(ValidationError(
                    _("A new signature is required when updating scores."),
                    code='signature_must_change'))

        if errs and doraise:
            raise ValidationError(errs)
        return errs  # In case we're subclassing.

    def save(self, *args, **kwargs):
        self.score = self.calculatescore()
        super().save(*args, **kwargs)

    def __repr__(self, raw=False):
        # The raw argument allows for the class name to be omitted.
        # The fallback value cannot be Player() due to circular imports.
        out = "None"
        player = getattr(self, 'player', None)  # Fallback value.
        if player is not None:
            out = player.__repr__(raw=True)
        if raw:
            return out
        return "<{}: {}>".format(self.__class__.__name__, out)

    def __str__(self):
        player = getattr(self, 'player', None)  # Fallback.
        return str(player)

    class Meta:
        abstract = True
        verbose_name = _("scoresheet")
        verbose_name_plural = _("scoresheets")

    # Everything below is expected to be overridden, but stubs are provided.

    fieldsets = ()

    def calculatescore(self):
        return 0
