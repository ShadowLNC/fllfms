from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


# For boolean and integer fields, we still declare choices, as the Django admin
# site will then make it a select/radio field where we can replicate the style
# of the old LabVIEW system.
# For choices/intchoices, database constraints are still required.
def boolchoices(**kwargs):
    return models.BooleanField(choices=[(1, _("Yes")), (0, _("No"))], **kwargs)


def intchoices(*ints, **kwargs):
    # We might have negative ints here.
    return models.SmallIntegerField(choices=[(i, str(i)) for i in ints],
                                    **kwargs)


def choices(*choices, **kwargs):
    return models.PositiveSmallIntegerField(choices=list(enumerate(choices)),
                                            **kwargs)


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
    signature = models.BinaryField(verbose_name=_("team initials"))

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
