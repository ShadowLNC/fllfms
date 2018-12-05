from collections import defaultdict
from contextlib import suppress
from itertools import chain

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase
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
        choices=[(i, _(str(c))) for i, c in enumerate(choices)], **kwargs)


class MetaScoresheet(ModelBase):
    def __new__(mcls, name, bases, attrs, **kwargs):
        # This method transforms the mission specification [tuple] into a set
        # of fields that are actually handled by the models.Model metaclass.
        # It also wraps strings in gettext(), so it's not needed in the spec.

        newmissions = []  # Can't edit the missions tuple.
        for mname, mission in attrs['missions']:
            mname = _(mname)
            if 'description' in mission:
                mission['description'] = _(mission['description'])

            for fname, config in mission['fields']:
                # Setup kwargs for field (rename/wrap with gettext).
                fkwargs = {}
                with suppress(KeyError):
                    fkwargs['verbose_name'] = _(config['text'])
                with suppress(KeyError):
                    fkwargs['help_text'] = _(config['help'])

                # If choices are present, map to integers, else default bool.
                try:
                    field = choices(*config['choices'], **fkwargs)
                except KeyError:
                    field = boolchoices(**fkwargs)

                if fname not in attrs:
                    # Prevent mission spec from overriding existing values.
                    attrs[fname] = field

            newmissions.append((mname, mission))

        attrs['missions'] = newmissions
        return super().__new__(mcls, name, bases, attrs, **kwargs)


class BaseScoresheet(models.Model, metaclass=MetaScoresheet):
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
    # Student signature. (PNG < 50KB)
    signature = models.BinaryField(editable=True,
                                   verbose_name=_("team initials"))

    def calculatescore(self):
        score = 0

        # Iterate over each mission to calculate the score.
        # Subclasses can implement custom logic if missions rely on each other.
        fields = chain.from_iterable((m[1]['fields'] for m in self.missions))
        for name, config in fields:
            # If weight is not declared, a zero multiplier (no score) is used.
            value = getattr(self, name)  # The value entered on the scoresheet.
            weight = config.get('value', 0)  # What the mission is worth.

            # Determine type(weight) and use accordingly.
            if callable(weight):
                score += weight(value)
            elif hasattr(weight, '__getitem__'):
                score += weight[value]
            else:
                # Assume multiplier (integer/float).
                score += value * weight

        return score

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

    missions = ()
