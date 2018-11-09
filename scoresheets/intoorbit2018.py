from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from ._base import BaseScoresheet, boolchoices, choices


class Scoresheet(BaseScoresheet):
    m01a = boolchoices(verbose_name=_(
        "Vehicle Payload rolled past first track connection"))
    m01b = boolchoices(verbose_name=_(
        "Supply Payload rolled past first track connection"))
    m01c = boolchoices(verbose_name=_(
        "Crew Payload rolled past first track connection"))

    m02a = boolchoices(verbose_name=_(
        "Both Solar Panels are angled toward the same Field"))
    m02b = boolchoices(verbose_name=_(
        "Your Solar Panel is angled to other team's Field"))

    m03a = boolchoices(verbose_name=_("2x4 Brick is ejected"), help_text=_(
        "(due only to a Regolith Core Sample in the 3D Printer)"))
    m03b = boolchoices(
        verbose_name=_("2x4 Brick is completely in Northeast Planet Area"),
        help_text=_("(brick must be ejected)"))

    m04a = boolchoices(verbose_name=_(
        "All weight-bearing features of crossing equipment crossed completely "
        "between towers"))
    m04b = boolchoices(verbose_name=_(
        "All crossing equipment crossed from east to west, completely past "
        "flattened Gate"))

    m05a = boolchoices(verbose_name=_(
        "All four Core Samples no longer touching axle of Core Site Model"))
    m05b = boolchoices(verbose_name=_(
        "Gas Core Sample touching Mat & completely in Lander's Target Circle"),
                       help_text=_("(cannot be in base)"))
    m05c = boolchoices(verbose_name=_("Gas Core Sample is completely in Base"),
                       help_text=_("(cannot be in Lander's Target Circle)"))
    m05d = boolchoices(verbose_name=_(
        "Water Core Sample supported only by Food Growth Chamber"))

    m06a = boolchoices(verbose_name=_(
        "Cone Module is completely in Base"))
    m06b = boolchoices(verbose_name=_(
        "Tube Module is in west port of Habitation Hub"))
    m06c = boolchoices(verbose_name=_(
        "Dock Module is in east port of Habitation Hub"))

    m07 = choices(_("No"), _("Partly"), _("Completely"), verbose_name=_(
        "Astronaut \"Gerhard\" is in the Habitation Hub's Airlock Chamber"))

    m08 = choices(
        _("None"), _("Gray"), _("White"), _("Orange"),
        verbose_name=_("Exercise Pointer tip is in"),
        help_text=_("(due only to moving one or both Handle Assemblies)"))

    m09 = boolchoices(verbose_name=_(
        "Strength Bar lifted so that tooth-strip’s 4th hole is at least "
        "partly in view"))

    m10 = boolchoices(
        verbose_name=_("Grey weight is dropped after green, but before tan"),
        help_text=_("(due only to moving the Push Bar)"))

    m11 = boolchoices(
        verbose_name=_("Spacecraft stays up"),
        help_text=_("(due only to pressing/hitting Strike Pad)"))

    m12 = choices(*range(4), verbose_name=_(
        "Satellites on or above the area between the two lines of Outer "
        "Orbit"))

    m13 = choices(
        _("None"), _("Gray"), _("White"), _("Orange"),
        verbose_name=_("The Observatory pointer tip is in"))

    m14a = choices(*range(3), verbose_name=_("Meteoroids touching the Mat and "
                                             "in the Center Section"),
                   help_text=_("Total Meteroid count must be no more than 2"))
    m14b = choices(*range(3), verbose_name=_("Meteoroids touching the Mat and "
                                             "in Either Side Section"),
                   help_text=_("Total Meteroid count must be no more than 2"))

    m15a = boolchoices(verbose_name=_("Lander is intact and touching the Mat"))
    m15b = choices(
        _("None"), _("Base"), _("Northeast Planet Area"), _("Target Circle"),
        verbose_name=_("Lander is completely in"))

    penalties = choices(*range(7), verbose_name=_(
        "Penalty discs in the southeast triangle"))

    fieldsets = (
        (_("M01 – SPACE TRAVEL"), {
            'description': _("(For each roll, cart must be independent by the "
                             "time it reaches first track connection)"),
            'fields': ['m01a', 'm01b', 'm01c']
        }),
        (_("M02 – SOLAR PANEL ARRAY"), {
            'fields': ['m02a', 'm02b']
        }),
        (_("M03 – 3D PRINTING"), {
            'fields': ['m03a', 'm03b']
        }),
        (_("M04 – CRATER CROSSING"), {
            'fields': ['m04a', 'm04b']
        }),
        (_("M05 – EXTRACTION"), {
            'fields': ['m05a', 'm05b', 'm05c', 'm05d']
        }),
        (_("M06 – SPACE STATION MODULE"), {
            'description': _("(Inserted Modules must not touch anything "
                             "except Habitation Hub)"),
            'fields': ['m06a', 'm06b', 'm06c']
        }),
        (_("M07 – SPACE WALK EMERGENCY"), {
            'fields': ['m07']
        }),
        (_("M08 – AEROBIC EXERCISE"), {
            'description': _("(If Pointer is partly covering either grey or "
                             "orange end borders, select that respective "
                             "color)"),
            'fields': ['m08']
        }),
        (_("M09 – STRENGTH EXERCISE"), {
            'fields': ['m09']
        }),
        (_("M10 – FOOD PRODUCTION"), {
            'fields': ['m10']
        }),
        (_("M11 – ESCAPE VELOCITY"), {
            'fields': ['m11']
        }),
        (_("M12 – SATELLITE ORBITS"), {
            'fields': ['m12']
        }),
        (_("M13 – OBSERVATORY"), {
            'description': _("(If pointer is partly covering either grey or "
                             "orange end borders, select that respective "
                             "color)"),
            'fields': ['m13']
        }),
        (_("M14 – METEOROID DEFLECTION"), {
            'description': _("(The Meteoroid must cross from west of the "
                             "Free-Line)\n"
                             "(The Meteoroid must be completely independent "
                             "between the hit/release and scoring position)"),
            'fields': ['m14a', 'm14b']
        }),
        (_("M15 – LANDER TOUCH-DOWN"), {
            'fields': ['m15a', 'm15b']
        }),
        (_("PENALTIES"), {
            'fields': ['penalties']
        }),
    )

    def calculatescore(self):
        score = 0

        boolvalues = {
            'm01a': 22,
            'm01b': 14,
            'm01c': 10,

            'm02a': 22,
            'm02b': 18,

            'm03a': 18,
            'm03b': 4,  # Total 22.

            'm05a': 16,
            'm05b': 12,
            'm05c': 10,
            'm05d': 8,

            'm06a': 16,
            'm06b': 16,
            'm06c': 14,

            'm09': 16,

            'm10': 16,

            'm11': 24,
        }

        lookups = {
            'm07': [0, 18, 22],
            'm08': [0, 18, 20, 22],
            'm13': [0, 16, 18, 20],
            'm14b': [
                0, 16, (20 if self.m14a else 0), (22 if self.m14a else 0)],
        }

        multipliers = {
            'm12': 8,
            'm14a': 12,
            'm14b': 8,

            'penalties': -3,
        }

        for field, adds in boolvalues.items():
            if getattr(self, field):
                score += adds

        for field, lookup in lookups.items():
            score += lookup[getattr(self, field)]

        for field, multiplier in multipliers.items():
            score += multiplier * getattr(self, field)

        # Custom values
        if self.m04a and self.m04b:
            score += 20

        return score

    def clean(self):
        errs = super().clean(doraise=False)
        if self.m03b and not self.m03a:
            e = ValidationError(
                _("Brick cannot be in Northeast Planet Area without ejection"),
                code='m03b_prerequisite')
            errs['m03a'].append(e)
            errs['m03b'].append(e)

        if self.m05b and self.m05c:
            e = ValidationError(
                _("Gas Core Sample cannot be both in Base and Lander's Target "
                  "Circle"),
                code='m05_exclusive')
            errs['m05b'].append(e)
            errs['m05c'].append(e)

        if self.m14a + self.m14b > 2:
            e = ValidationError(_("Maximum 2 total Meteoroids"),
                                code='m14_sum')
            errs['m14a'].append(e)
            errs['m14b'].append(e)

        if errs:
            raise ValidationError(errs)

    class Meta:
        # Remember to cast range objects to lists! Django can't deconstruct.
        constraints = [
            models.CheckConstraint(check=~Q(m03a=False, m03b=True),
                                   name="m03b_prerequisite"),
            models.CheckConstraint(check=~Q(m05b=True, m05c=True),
                                   name="m05_exclusive"),
            models.CheckConstraint(check=Q(m14a__lte=2 - F('m14b')),
                                   name="m14_sum"),
        ]
