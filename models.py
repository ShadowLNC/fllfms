from collections import defaultdict

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError, NON_FIELD_ERRORS
from django.utils.translation import gettext_lazy as _


def bounds(*, low=None, high=None):
    # Create bounds in the form of validators for a model field.
    res = []
    if low is not None:
        res.append(MinValueValidator(low))
    if high is not None:
        res.append(MaxValueValidator(high))
    return res


class Team(models.Model):
    # Auto PK
    number = models.PositiveIntegerField(unique=True, validators=bounds(low=1))
    name = models.CharField(max_length=255, blank=True)  # Name optional.
    dq = models.BooleanField(default=False)  # If true, team is disqualified.

    def __repr__(self):
        return "<{}: {}>".format(self.__class__.__name__, self.number)

    __str__ = __repr__  # Override Django's version.

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(number__gte=1),
                                   name="number_minimum"),
        ]


class Match(models.Model):
    # Auto PK
    tournament = models.PositiveSmallIntegerField(
        db_index=True, choices=settings.FLLFMS['TOURNAMENTS'])
    number = models.PositiveSmallIntegerField(
        db_index=True, validators=bounds(low=1))

    # Event-specific data. Teams play at least 3 rounds, per the FLL manual.
    round = models.PositiveSmallIntegerField(
        db_index=True, validators=bounds(low=1))
    field = models.PositiveSmallIntegerField(choices=settings.FLLFMS['FIELDS'])

    # Timing data.
    schedule = models.DateTimeField(auto_now=False, auto_now_add=False)
    actual = models.DateTimeField(
        auto_now=False, auto_now_add=False, blank=True, null=True)

    # Matches have teams, so m2m goes on matches (appears on Match admin form).
    # related_query_name == related_name, for both sides of the relationship.
    teams = models.ManyToManyField('Team', through='Player',
                                   related_name="matches")

    def clean(self):
        errs = defaultdict(list)

        # Friendly error for player_round_tournament_uniq.
        if self.pk is not None and Player.objects.filter(
                team__in=self.teams.all(), match__round=self.round,
                match__tournament=self.tournament, surrogate=False
                ).exclude(pk__in=self.players.all()).exists():
            errs['round'].append(ValidationError(_(
                "Cannot have more than one match per team, per round, per "
                "tournament (non-surrogate matches). (It appears you changed "
                "the match round, which would violate this constraint.)")))

        if errs:
            raise ValidationError(errs)

    def __repr__(self):
        return "<{}: {}.{}>".format(self.__class__.__name__,
                                    self.get_tournament_display(), self.number)

    __str__ = __repr__  # Override Django's version.

    class Meta:
        unique_together = [
            # Rounds are still part of that tournament.
            ('tournament', 'number'),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(tournament__in=[
                    choice[0] for choice in settings.FLLFMS['TOURNAMENTS']]),
                name="tournament_choices"),
            models.CheckConstraint(
                check=Q(number__gt=0), name="number_bounds"),

            models.CheckConstraint(check=Q(round__gt=0), name="round_bounds"),
            models.CheckConstraint(
                check=Q(field__in=[
                    choice[0] for choice in settings.FLLFMS['FIELDS']]),
                name="field_choices"),
        ]


class Player(models.Model):
    # Players are teams who play a given match in a given location.
    # Auto PK
    match = models.ForeignKey('Match', on_delete=models.CASCADE,
                              related_name="players")
    team = models.ForeignKey('Team', on_delete=models.CASCADE,
                             related_name="players")

    # Additional data for the relationship.
    station = models.PositiveSmallIntegerField(
        choices=settings.FLLFMS['STATIONS'])
    surrogate = models.BooleanField(default=False)  # Might not be used.

    def clean(self):
        errs = defaultdict(list)

        # Friendly error for player_round_tournament_uniq.
        # Minor race condition if match round/tournament is changed after load.
        if Player.objects.filter(
                team=self.team, match__round=self.match.round,
                match__tournament=self.match.tournament, surrogate=False
                ).exclude(pk=self.pk).exists():
            errs[NON_FIELD_ERRORS].append(ValidationError(_(
                "Cannot have more than one match per team, per round, per "
                "tournament (non-surrogate matches).")))

        if errs:
            raise ValidationError(errs)

    def __repr__(self):
        match = getattr(self, 'match', Match())  # Fallback value.
        return "<{}: {}.{}.{}>".format(
            self.__class__.__name__, match.get_tournament_display(),
            match.number, self.get_station_display())

    __str__ = __repr__  # Override Django's version.

    class Meta:
        unique_together = [
            ('match', 'station'),
            ('match', 'team'),
            # We use an SQL view to enforce the following constraint:
            # ('match__round', 'match__tournament', 'team', 'surrogate')
            # It's not possible to follow relations for Django uniqueness.
            # NOTE: We can't index views and so cannot enforce this on SQLite.
            # See migrations/setup.sql for player_round_tournament_uniq index.
        ]

        constraints = [
            models.CheckConstraint(
                check=Q(station__in=[
                    i[0] for i in settings.FLLFMS['STATIONS']]),
                name="station_choices"),
        ]
