from django.utils.translation import gettext_lazy as _

from ._base import BaseScoresheet


class Scoresheet(BaseScoresheet):
    missions = (
        (_("Generic mission"), {
            'description': _("(Some mission notes here)"),
            'fields': [
                ('missionscore', {
                    'text': _("mission score"),
                    'help': _("Special condition of the mission."),
                    'choices': range(5),
                    'value': 5,
                }),
            ]
        }),
    )
