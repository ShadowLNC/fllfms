from django.db import models
from django.db.models import Q

from ._base import BaseScoresheet


class Scoresheet(BaseScoresheet):
    missions = (
        ("Generic mission", {
            'description': "(Some mission notes here)",
            'fields': [
                ('missionscore', {
                    'text': "mission score",
                    'help': "Special condition of the mission.",
                    'choices': range(5),
                    'value': 5,
                }),
            ]
        }),
    )

    class Meta:
        # Remember to cast range objects to lists! Django can't deconstruct.
        constraints = [
            models.CheckConstraint(check=Q(missionscore__in=list(range(5))),
                                   name="missionscore_choices"),
        ]
