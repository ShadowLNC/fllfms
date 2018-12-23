from collections import defaultdict
from contextlib import suppress
from itertools import chain

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
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
    return models.PositiveSmallIntegerField(choices=list(enumerate(choices)),
                                            **kwargs)


class MetaScoresheet(ModelBase):
    def __new__(mcls, name, bases, attrs, **kwargs):
        # This method transforms the mission specification [tuple] into a set
        # of fields that are actually handled by the models.Model metaclass,
        # and sets up the model Meta options to inherit parent Meta options.
        # It also wraps strings in gettext(), in case it's omitted in the spec.

        # WARNING: the gettext() calls are a last-ditch attempt to translate,
        # as Django's makemessages won't pick up these calls, so there probably
        # won't be a translation available. Wrapping the mission strings
        # individually is still necessary.

        # Because the Meta options class is a standard class attribute, a child
        # class declaring the Meta options class won't actually inherit any
        # parent Meta options. This adds "nested" inheritance (for Meta only).

        # Doing this also allows BaseScoresheet to define default constraints.
        # Later: If necessary, we can extract constraints from metabases and
        # flatten them together for more "nested" inheritance.
        metabases = []
        for base in bases:
            with suppress(AttributeError):
                metabases.append(base.Meta)

        # Prevent nested inheritance from making every model abstract.
        class NotAbstactMeta:
            abstract = False
        metabases.insert(0, NotAbstactMeta)

        # Create an empty class which inherits from attrs['Meta'] if defined,
        # then all the metabases from above.
        with suppress(KeyError):
            metabases.insert(0, attrs['Meta'])
        attrs['Meta'] = type('Meta', tuple(metabases), {})

        # Now, we take each "mission" which has multiple fields or scoring
        # opportunities, and take each field and instantiate a Django field.
        # We also add constraints for database integrity where appropriate.

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
                if 'choices' in config:
                    field = choices(*config['choices'], **fkwargs)
                    # Validate field choice restrictions.
                    constraint = {
                        # choices() uses enumerate, so available choices are
                        # equivalent to range(len(config['choices'])), but
                        # Django can't deconstruct range(), so we cast to list.
                        # We could use {}__in=<above list>, but it should be
                        # more efficient to define interval start and end.
                        "{}__gte".format(fname): 0,
                        "{}__lt".format(fname): len(config['choices']),
                    }
                    constraint = models.CheckConstraint(
                        check=Q(**constraint), name="{}_choices".format(fname))
                else:
                    field = boolchoices(**fkwargs)
                    constraint = None

                if fname not in attrs:
                    # Prevent mission spec from overriding existing values.
                    attrs[fname] = field
                    # Only append constraint if we are also defining the field.
                    if constraint is not None:
                        attrs['Meta'].constraints.append(constraint)

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

    def clean(self):
        errs = defaultdict(list)

        if self.pk is not None:
            old = self.__class__.objects.get(pk=self.pk)
            if old.signature == self.signature:
                errs['signature'].append(ValidationError(
                    _("A new signature is required when updating scores."),
                    code='signature_must_change'))

        with suppress(ValidationError):
            # By cleaning the fields first, we ensure the data is of a valid
            # type, and won't crash when we try to validate scores.
            # If ValidationError is raised, the suppress catches it and we skip
            # the clean_scores() call (we know model validation fails anyway).
            self.clean_fields()
            self.clean_scores(errs)  # Modifies by reference to add errors.

        if errs:
            raise ValidationError(errs)

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

        constraints = []  # Expected to be overridden, as per below.

    # Everything below is expected to be overridden, but stubs are provided.

    missions = ()

    def clean_scores(self, errs):
        pass
