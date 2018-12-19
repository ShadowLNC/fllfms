from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from ._base import BaseScoresheet


class Scoresheet(BaseScoresheet):
    missions = (

        ("M01 – SPACE TRAVEL", {
            'description': "(For each roll, cart must be independent by the "
                           "time it reaches first track connection)",
            'fields': [
                ('m01a', {
                    'text':
                        "Vehicle Payload rolled past first track connection",
                    'value': 22,
                }),
                ('m01b', {
                    'text':
                        "Supply Payload rolled past first track connection",
                    'value': 14,
                }),
                ('m01c', {
                    'text': "Crew Payload rolled past first track connection",
                    'value': 10,
                }),
            ],
        }),

        ("M02 – SOLAR PANEL ARRAY", {
            'fields': [
                ('m02a', {
                    'text':
                        "Both Solar Panels are angled toward the same Field",
                    'value': 22,
                }),
                ('m02b', {
                    'text': "Your Solar Panel is angled to other team's Field",
                    'value': 18,
                }),
            ],
        }),

        ("M03 – 3D PRINTING", {
            'fields': [
                ('m03a', {
                    'text': "2x4 Brick is ejected",
                    'help': "(due only to a Regolith Core Sample in the 3D "
                            "Printer)",
                    'value': 18,
                }),
                ('m03b', {
                    'text': "2x4 Brick is completely in Northeast Planet Area",
                    'help': "(brick must be ejected)",
                    'value': 4,  # Total 22.
                }),
            ],
        }),

        ("M04 – CRATER CROSSING", {
            'fields': [
                ('m04a', {
                    'text': "All weight-bearing features of crossing "
                            "equipment crossed completely between towers",
                }),
                ('m04b', {
                    'text': "All crossing equipment crossed from east to "
                            "west, completely past flattened Gate",
                }),
            ],
        }),

        ("M05 – EXTRACTION", {
            'fields': [
                ('m05a', {
                    'text': "All four Core Samples no longer touching axle of "
                            "Core Site Model",
                    'value': 16,
                }),
                ('m05b', {
                    'text': "Gas Core Sample touching Mat & completely in "
                            "Lander's Target Circle",
                    'help': "(cannot be in base)",
                    'value': 12,
                }),
                ('m05c', {
                    'text': "Gas Core Sample is completely in Base",
                    'help': "(cannot be in Lander's Target Circle)",
                    'value': 10,
                }),
                ('m05d', {
                    'text': "Water Core Sample supported only by Food Growth "
                            "Chamber",
                    'value': 8,
                }),
            ],
        }),

        ("M06 – SPACE STATION MODULE", {
            'description': "(Inserted Modules must not touch anything "
                           "except Habitation Hub)",
            'fields': [
                ('m06a', {
                    'text': "Cone Module is completely in Base",
                    'value': 16,
                }),
                ('m06b', {
                    'text': "Tube Module is in west port of Habitation Hub",
                    'value': 16,
                }),
                ('m06c', {
                    'text': "Dock Module is in east port of Habitation Hub",
                    'value': 14,
                }),
            ],
        }),

        ("M07 – SPACE WALK EMERGENCY", {
            'fields': [
                ('m07', {
                    'text': "Astronaut \"Gerhard\" is in the Habitation Hub's "
                            "Airlock Chamber",
                    'choices': ["No", "Partly", "Completely"],
                    'value': [0, 18, 22],
                }),
            ],
        }),

        ("M08 – AEROBIC EXERCISE", {
            'description': "(If Pointer is partly covering either grey or "
                           "orange end borders, select that respective color)",
            'fields': [
                ('m08', {
                    'text': "Exercise Pointer tip is in",
                    'help':
                        "(due only to moving one or both Handle Assemblies)",
                    'choices': ["None", "Gray", "White", "Orange"],
                    'value': [0, 18, 20, 22],
                }),
            ],
        }),

        ("M09 – STRENGTH EXERCISE", {
            'fields': [
                ('m09', {
                    'text': "Strength Bar lifted so that tooth-strip’s 4th "
                            "hole is at least partly in view",
                    'value': 16,
                }),
            ],
        }),

        ("M10 – FOOD PRODUCTION", {
            'fields': [
                ('m10', {
                    'text':
                        "Grey weight is dropped after green, but before tan",
                    'help': "(due only to moving the Push Bar)",
                    'value': 16,
                }),
            ],
        }),

        ("M11 – ESCAPE VELOCITY", {
            'fields': [
                ('m11', {
                    'text': "Spacecraft stays up",
                    'help': "(due only to pressing/hitting Strike Pad)",
                    'value': 24,
                }),
            ],
        }),

        ("M12 – SATELLITE ORBITS", {
            'fields': [
                ('m12', {
                    'text': "Satellites on or above the area between the two "
                            "lines of Outer Orbit",
                    'choices': range(4),
                    'value': 8,
                }),
            ],
        }),

        ("M13 – OBSERVATORY", {
            'description': "(If pointer is partly covering either grey or "
                           "orange end borders, select that respective color)",
            'fields': [
                ('m13', {
                    'text': "The Observatory pointer tip is in",
                    'choices': ["None", "Gray", "White", "Orange"],
                    'value': [0, 16, 18, 20],
                }),
            ]
        }),

        ("M14 – METEOROID DEFLECTION", {
            'description': "(The Meteoroid must cross from west of the "
                           "Free-Line)<br>"
                           "(The Meteoroid must be completely independent "
                           "between the hit/release and scoring position)",
            'fields': [
                ('m14a', {
                    'text': "Meteoroids touching the Mat and in the Center "
                            "Section",
                    'help': "Total Meteroid count must be no more than 2",
                    'choices': range(3),
                    'value': 12,
                }),
                ('m14b', {
                    'text': "Meteoroids touching the Mat and in Either Side "
                            "Section",
                    'help': "Total Meteroid count must be no more than 2",
                    'choices': range(3),
                    'value': 8,
                }),
            ],
        }),

        ("M15 – LANDER TOUCH-DOWN", {
            'fields': [
                ('m15a', {
                    'text': "Lander is intact and touching the Mat",
                }),
                ('m15b', {
                    'text': "Lander is completely in",
                    'choices': ["None", "Base",
                                "Northeast Planet Area", "Target Circle"],
                }),
            ],
        }),

        ("PENALTIES", {
            'fields': [
                ('penalties', {
                    'text': "Penalty discs in the southeast triangle",
                    'choices': range(7),
                    'value': -3,
                }),
            ],
        }),
    )

    def calculatescore(self):
        score = super().calculatescore()

        # Custom values.
        if self.m04a and self.m04b:
            score += 20

        if self.m15b == 1:
            # 16 points if Lander in Base [m15b == 1], 0 for None [m15b == 0].
            score += 16
        elif self.m15a:
            # Verify m15a (Lander intact) as a prerequisite for
            # Northeast Planet Area [m15b == 2] and Target Circle [m15b == 3].
            if self.m15b == 2:
                score += 20
            elif self.m15b == 3:
                score += 22

        return score

    def clean_scores(self, errs):
        if self.m03b and not self.m03a:
            e = ValidationError(
                _("Brick cannot be in Northeast Planet Area if not ejected"),
                code='m03b_prerequisite')
            errs['m03a'].append(e)
            errs['m03b'].append(e)

        if self.m05b and self.m05c:
            e = ValidationError(
                _("Gas Core Sample cannot be in both Base and Lander's Target "
                  "Circle"),
                code='m05_exclusive')
            errs['m05b'].append(e)
            errs['m05c'].append(e)

        if self.m14a + self.m14b > 2:
            e = ValidationError(_("Maximum 2 total Meteoroids"),
                                code='m14_sum')
            errs['m14a'].append(e)
            errs['m14b'].append(e)

    class Meta(BaseScoresheet.Meta):
        constraints = [
            models.CheckConstraint(check=~Q(m03a=False, m03b=True),
                                   name="m03b_prerequisite"),
            models.CheckConstraint(check=~Q(m05b=True, m05c=True),
                                   name="m05_exclusive"),
            models.CheckConstraint(check=Q(m14a__lte=2 - F('m14b')),
                                   name="m14_sum"),
        ]
