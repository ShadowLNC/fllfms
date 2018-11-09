from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from ._base import BaseScoresheet, choices


class Scoresheet(BaseScoresheet):
    missionscore = choices(*range(5), verbose_name=_("mission score"),
                           help_text=_("Special condition of the mission."))

    fieldsets = (
        (_("Generic mission score"), {
            'description': _("(Some mission notes here)"),
            'fields': ['missionscore']
        }),
    )

    def calculatescore(self):
        return self.missionscore * 5

    class Meta:
        # Remember to cast range objects to lists! Django can't deconstruct.
        constraints = [
            models.CheckConstraint(check=Q(missionscore__in=list(range(5))),
                                   name="missionscore_choices"),
        ]
