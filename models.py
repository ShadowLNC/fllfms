from collections import defaultdict, OrderedDict
from datetime import datetime, timezone
from importlib import import_module
import os.path

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.validators import (
    MinValueValidator, MaxValueValidator, RegexValidator)
from django.core.exceptions import ValidationError, NON_FIELD_ERRORS
from django.utils.translation import gettext_lazy as _


class AttrDict(OrderedDict):
    # Enums for Django. Must be sorted to serialise, hence OrderedDict.
    # Also retains declaration order for <select> elements in admin etc.
    def __getattr__(self, item):
        return self[item]  # __getattr__ is called when __getattribute__ fails.

    def choices(self):
        # Not a property so as to differentiate between an element.
        return [(v, k) for k, v in self.items()]

    @classmethod
    def fromiter(cls, *data, start=0):
        return cls([(k, v) for v, k in enumerate(data, start)])


# Timer states: prestart (primed), start (running), end (finished), abort.
# States: prestart (initial) > start > end/abort > prestart.
# NOTE: Keep this synchronised with timer.js.
TIMERSTATES = AttrDict([
    ("PRESTART", 0),
    ("START", 1),
    ("END", 2),
    ("ABORT", 3),
])


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


CSSREGEX = r"^( *-?[_a-zA-Z]+[_a-zA-Z0-9-]*( *|$))*"
# Used to find relative paths when reading the soundfield absolute paths.
APP_STATIC_ROOT = os.path.join(settings.BASE_DIR, "fllfms", "static")


def cssfield(**kwargs):
    if 'validators' not in kwargs:
        kwargs['validators'] = []
    kwargs['validators'].append(RegexValidator(CSSREGEX))
    return models.CharField(blank=True, max_length=100, **kwargs)


def soundfield(**kwargs):
    # Note that the path is restricted to the "sounds" subfolder in this
    # repository's static folder. We may need to change this in the future.
    # Django will create a static URL, so no database validation required.
    return models.FilePathField(
        # Blank subdirectory gives path trailing /, removes filename leading /.
        path=os.path.join(APP_STATIC_ROOT, "fllfms", "sounds", ""),
        match=None, recursive=True, max_length=100, blank=True,
        allow_files=True, allow_folders=False, **kwargs)


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


class Timer(models.Model):
    name = models.CharField(
        blank=True, max_length=100, verbose_name=_("name (optional)"),
        help_text=_("Only visible in admin."))

    profile = models.ForeignKey('TimerProfile', on_delete=models.PROTECT,
                                related_name="timers",
                                verbose_name=_("timing profile"))
    # TODO: Add match fields as ManyToMany to restrict timer next/prev matches.
    # This can only be done once fields are ForeignKey and not set choices.

    # Only one timer per match, or we could have a race condition.
    # (Timers... racing... I'm sure there's a pun here.)
    match = models.OneToOneField('Match', on_delete=models.SET_NULL,
                                 blank=True, null=True, related_name="timer",
                                 verbose_name=_("current match"))

    starttime = models.DateTimeField(
        auto_now=False, auto_now_add=False, editable=False,
        default=datetime.fromtimestamp(0, timezone.utc),
        verbose_name=_("start time"),
        help_text=_("Only applicable if running."))
    state = models.PositiveSmallIntegerField(
        editable=False, default=TIMERSTATES.PRESTART,
        choices=TIMERSTATES.choices(), verbose_name=_("timer state"))

    @property
    def elapsed(self):
        # Only applicable if running.
        return datetime.now(timezone.utc) - self.starttime

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Since self.profile will require an additional database query, we
        # could override the model's manager to always get select_related(),
        # but it's not checked unless the timer is running (uncommon case). In
        # order to make the common case fast, we should avoid the JOIN query if
        # the timer isn't running, and therefore not override the manager.
        # (The JOIN cost may be a better option if it's a negligible increase.)
        if (self.state == TIMERSTATES.START
                and self.elapsed > self.profile.duration):
            # Stop the timer if it has been running longer than its duration.
            # WARNING: Don't instantiate in pre/post_save signals, or infinite
            # recursion may ensue.
            self.state = TIMERSTATES.END
            self.save()

    def clean(self):
        errs = defaultdict(list)

        if self.pk is not None:
            # Timer cannot be altered if running (state == start).
            # We can't block prestart as there's no way to exit prestart.
            running = self.state == TIMERSTATES.START
            if not running:
                # Might be different if updated before form submission.
                db_ver = self.__class__.objects.get(pk=self.pk)
                running = db_ver.state == TIMERSTATES.START
            if running:
                errs[NON_FIELD_ERRORS].append(ValidationError(
                    _("Timer is running, cannot change any information."),
                    code="timer_locked_running"))

        if errs:
            raise ValidationError(errs)

    def __repr__(self, raw=False):
        # The raw argument allows for the class name to be omitted.
        out = str(self.pk)
        if raw:
            return out
        return "<{}: {}>".format(self.__class__.__name__, out)

    def __str__(self):
        return "{} ({})".format(self.pk, self.name)

    class Meta:
        verbose_name = _("timer")
        verbose_name_plural = _("timers")

        constraints = [
            models.CheckConstraint(
                # Django can't deconstruct dict.values(), must cast to list().
                check=Q(state__in=list(TIMERSTATES.values())),
                name="state_choices"),
        ]


class TimerProfile(models.Model):
    name = models.CharField(unique=True, max_length=100,
                            verbose_name=_("name"))
    duration = models.DurationField(
        verbose_name=_("timer length"),
        help_text=_("Time fields use the format \"D H:M:S\" "
                    "(omit leading fields if not used)."))
    format = models.BooleanField(
        choices=((False, _("Seconds")), (True, _("Minutes"))),
        verbose_name=_("display time as"), default=True)

    # No prestartdisplay: Always displays 0 to indicate not running.
    # (No prestartsound by definition.)
    prestartcss = cssfield(verbose_name=_("pre-start css class(es)"))

    startcss = cssfield(verbose_name=_("start css class(es)"))
    startdisplay = models.DurationField(
        blank=True, null=True, verbose_name=_("count down from"),
        help_text=_("Leave blank to use the timer length.<br>"
                    "Negative values will be displayed as 0."))
    startsound = soundfield(verbose_name=_("start sound file"))

    # No enddisplay: Always 0.
    endcss = cssfield(verbose_name=_("end css class(es)"))
    endsound = soundfield(verbose_name=_("end sound file"))

    # No abortcss: Upon abort, inherit from endcss/enddisplay.
    abortsound = soundfield(verbose_name=_("abort sound file"))

    def clean(self):
        errs = defaultdict(list)

        if any(t.state == TIMERSTATES.START for t in self.timers.all()):
            errs[NON_FIELD_ERRORS].append(ValueError(
                _("One or more linked timers are running, cannot change any "
                  "information."),
                code="timer_locked_running"))

        if errs:
            raise ValidationError(errs)

    def __repr__(self, raw=False):
        # The raw argument allows for the class name to be omitted.
        out = str(self.name)
        if raw:
            return out
        return "<{}: {}>".format(self.__class__.__name__, out)

    # Django admin site representation.
    def __str__(self):
        return self.__repr__(raw=True)

    class Meta:
        verbose_name = _("timing profile")
        verbose_name_plural = _("timing profiles")

        constraints = [
            models.CheckConstraint(check=Q(prestartcss__regex=CSSREGEX),
                                   name="prestartcss_regex"),
            models.CheckConstraint(check=Q(startcss__regex=CSSREGEX),
                                   name="startcss_regex"),
            models.CheckConstraint(check=Q(endcss__regex=CSSREGEX),
                                   name="endcss_regex"),
        ]


class TimerStage(models.Model):
    profile = models.ForeignKey('TimerProfile', on_delete=models.CASCADE,
                                related_name="stages",
                                verbose_name=_("timing stages"))

    name = models.CharField(blank=True, max_length=100,
                            verbose_name=_("name (optional)"))

    # Elapsed time before this stage will be triggered.
    trigger = models.DurationField(verbose_name=_("begin stage after"))

    css = cssfield(verbose_name=_("css class(es)"))
    # Help text won't be shown here, but behaviour is consistent with
    # startdisplay from TimerProfile. It needs to be documented in the manual.
    display = models.DurationField(blank=True, null=True,
                                   verbose_name=_("count down from"))
    sound = soundfield(verbose_name=_("sound file"))

    def clean(self):
        errs = defaultdict(list)

        if (self.profile is not None
                and any(timer.start for timer in self.profile.timers.all())):
            errs[NON_FIELD_ERRORS].append(ValueError(
                _("One or more linked timers are running, cannot change any "
                  "information."),
                code="timer_locked_running"))

        if errs:
            raise ValidationError(errs)

    def __repr__(self, raw=False):
        # The raw argument allows for the class name to be omitted.
        profile = getattr(self, 'profile', TimerProfile())
        out = "{}.{}".format(profile.__repr__(raw=True), self.name)
        if raw:
            return out
        return "<{}: {}>".format(self.__class__.__name__, out)

    # Django admin site representation.
    def __str__(self):
        return self.__repr__(raw=True)

    class Meta:
        verbose_name = _("timing stage")
        verbose_name_plural = _("timing stages")

        ordering = ('trigger', 'pk',)  # Always used, both admin and consumer.

        constraints = [
            models.CheckConstraint(check=Q(css__regex=CSSREGEX),
                                   name="css_regex"),
        ]
