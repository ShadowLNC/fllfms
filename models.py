from collections import defaultdict
from importlib import import_module

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError, NON_FIELD_ERRORS
from django.utils.translation import gettext_lazy as _


Scoresheet = import_module(settings.FLLFMS.get(
    'SCORESHEET', 'fllfms.scoresheets._stub')).Scoresheet


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
    # Number must be editable as it needs to be set during creation in admin.
    number = models.PositiveIntegerField(unique=True,
                                         validators=bounds(low=1),
                                         verbose_name=_("team number"))
    name = models.CharField(max_length=255, blank=True,
                            verbose_name=_("team name"))  # Name optional.
    dq = models.BooleanField(default=False, verbose_name=_("is disqualified?"))

    def __repr__(self, raw=False):
        # The raw argument allows for the class name to be omitted.
        out = str(self.number)
        if raw:
            return out
        return "<{}: {}>".format(self.__class__.__name__, out)

    # Django admin site representation.
    def __str__(self):
        return "{}: {}".format(self.number, self.name)

    class Meta:
        verbose_name = _("team")
        verbose_name_plural = _("teams")

        constraints = [
            models.CheckConstraint(check=Q(number__gte=1),
                                   name="number_minimum"),
        ]


class Match(models.Model):
    # Auto PK
    tournament = models.PositiveSmallIntegerField(
        db_index=True, choices=settings.FLLFMS['TOURNAMENTS'],
        verbose_name=_("tournament"))
    number = models.PositiveSmallIntegerField(
        db_index=True, validators=bounds(low=1),
        verbose_name=_("match number"))

    # Event-specific data. Teams play at least 3 rounds, per the FLL manual.
    round = models.PositiveSmallIntegerField(
        db_index=True, validators=bounds(low=1),
        verbose_name=_("match round"))
    field = models.PositiveSmallIntegerField(
        choices=settings.FLLFMS['FIELDS'], verbose_name=_("field/table pair"))

    # Timing data.
    schedule = models.DateTimeField(auto_now=False, auto_now_add=False,
                                    verbose_name=_("scheduled start time"))
    actual = models.DateTimeField(
        auto_now=False, auto_now_add=False, blank=True, null=True,
        verbose_name=_("actual start time"))

    # Matches have teams, so m2m goes on matches (appears on Match admin form).
    # related_query_name == related_name, for both sides of the relationship.
    teams = models.ManyToManyField('Team', through='Player',
                                   related_name="matches",
                                   verbose_name=_("players"))

    def clean(self):
        errs = defaultdict(list)

        # Friendly error for player_round_tournament_uniq.
        if self.pk is not None and Player.objects.filter(
                    team__in=self.teams.exclude(players__surrogate=True),
                    match__round=self.round, match__tournament=self.tournament,
                    surrogate=False
                ).exclude(pk__in=self.players.all()).exists():
            errs['round'].append(ValidationError(
                _("Cannot have more than one match per team, per round, per "
                  "tournament (non-surrogate matches). (It appears you changed"
                  " the match round, which would violate this constraint.)"),
                code="team_too_many_matches"))

        if errs:
            raise ValidationError(errs)

    def __repr__(self, raw=False):
        # The raw argument allows for the class name to be omitted.
        out = "{}.{}".format(self.get_tournament_display(), self.number)
        if raw:
            return out
        return "<{}: {}>".format(self.__class__.__name__, out)

    # Django admin site representation.
    def __str__(self):
        # Translation can't really be done on the fly for sentence structure.
        return "{} {} {}".format(self.get_tournament_display(), _("Match"),
                                 self.number)

    class Meta:
        verbose_name = _("match")
        verbose_name_plural = _("matches")

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

    @property
    def ordered_players(self):
        return self.players.all().order_by('station')


class Player(models.Model):
    # Players are teams who play a given match in a given location.
    # Auto PK
    # Cascase on deletion for the match/team, but scoresheets may block.
    match = models.ForeignKey('Match', on_delete=models.CASCADE,
                              related_name="players",
                              verbose_name=_("match"))
    team = models.ForeignKey('Team', on_delete=models.CASCADE,
                             related_name="players",
                             verbose_name=_("team"))

    # Additional data for the relationship.
    station = models.PositiveSmallIntegerField(
        choices=settings.FLLFMS['STATIONS'], verbose_name=_("station/side"))
    surrogate = models.BooleanField(default=False,  # Might not be used.
                                    verbose_name=_("is surrogate?"))

    def clean(self):
        errs = defaultdict(list)

        # Friendly error for player_round_tournament_uniq.
        # Minor race condition if match round/tournament is changed after load.
        # Apparently this runs even if individual field validation fails.
        if (getattr(self, 'team', None) is not None
                and getattr(self, 'match', None) is not None
                and not self.surrogate
                and Player.objects.filter(
                    team=self.team, match__round=self.match.round,
                    match__tournament=self.match.tournament, surrogate=False
                    ).exclude(pk=self.pk).exists()):
            errs[NON_FIELD_ERRORS].append(ValidationError(
                _("Cannot have more than one match per team, per round, per "
                  "tournament (non-surrogate matches)."),
                code="team_too_many_matches"))

        # We want to disallow editing the team once set, else scores would move
        # to the new team, so require scoresheet deletion first.
        if (self.pk is not None
                and getattr(self, 'scoresheet', None) is not None):
            old = self.__class__.objects.get(pk=self.pk)
            if getattr(self, 'team', Team()) != old.team:
                errs['team'].append(ValidationError(
                    _("Cannot change a player's team once set, as it would "
                      "transfer scores to the new team. (Delete the "
                      "scoresheet, then change the team.)"),
                    code="player_change_team_prohibited"))

        if errs:
            raise ValidationError(errs)

    def __repr__(self, raw=False):
        match = getattr(self, 'match', Match())  # Fallback value.
        out = "{}-{}".format(match.__repr__(raw=True),
                             self.get_station_display())
        # The raw argument allows for the class name to be omitted.
        if raw:
            return out
        return "<{}: {}>".format(self.__class__.__name__, out)

    # Django admin site representation. Format is for scoresheet lookup later.
    def __str__(self):
        team = getattr(self, 'team', Team())  # Fallback if missing.
        return "{}/{}".format(self.__repr__(raw=True), team)

    class Meta:
        verbose_name = _("player")
        verbose_name_plural = _("players")

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
