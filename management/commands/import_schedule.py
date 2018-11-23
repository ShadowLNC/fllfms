from collections import defaultdict
from contextlib import suppress
import csv
import datetime
import re
# import warnings  # Replaced by self.style.WARNING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.translation import gettext as _
from django.utils.timezone import get_current_timezone as tz

from ...models import Team, Match, Player


class Command(BaseCommand):
    # We can't gettext_lazy here as the help output function needs a string.
    help = _("Imports a schedule file (with teams).")

    def add_arguments(self, parser):
        def date(strval):
            return datetime.date(*map(int, strval.split('-')))

        parser.add_argument('file', type=str, help=_("File to import"))
        parser.add_argument('date', type=date, nargs='?',
                            default=datetime.date.today(),
                            help=_("First day of competition (yyyy-mm-dd)"))

    @transaction.atomic()
    def handle(self, file, date, *args, **kwargs):
        if Team.objects.exists() or Match.objects.exists():
            # Check for non-empty db. Player objects require Team and Match.
            raise CommandError(_(
                "Data already exists, will not overwrite. Terminating."))

        TOURNAMENTS = [i[0] for i in settings.FLLFMS['TOURNAMENTS']]
        FIELDS = [i[0] for i in settings.FLLFMS['FIELDS']]
        STATIONS = [i[0] for i in settings.FLLFMS['STATIONS']]

        def process_match_row(row, tournament):
            try:
                # Some of them store in decimal (% of day passed).
                days = int(float(row[1]))
                seconds = (float(row[1]) % 1) * 86400  # 86400 in 1 day.
                # hour, minute, second, microsecond
                time = datetime.time(seconds // 3600, seconds // 60,
                                     seconds // 1, seconds % 1)

            except ValueError:
                # Otherwise attempt to match "(Day 1 )11:03(:00) AM".
                strtime = re.match(
                    "^(Day (?P<day>\d+) )?"
                    "(?P<hour>((0?|1)[0-9])|(2[0-3])):(?P<minute>[0-5][0-9])"
                    "(:(?P<second>[0-5][0-9]))? (?P<meridiem>[AP]M)$",
                    row[1], re.IGNORECASE)

                if strtime:
                    def getint(group):
                        # Helper function: make integer from regex group.
                        val = strtime.group(group)
                        if val is None:
                            return 0
                        return int(val)

                    # Days are 1-indexed (subtract 1), but None -> 0.
                    # By using max(0, day-1), it can't fall below 0.
                    days = max(0, getint('day')-1)

                    # Calculate hour before instantiating immutable time().
                    hour = getint('hour')
                    if strtime.group('meridiem').upper() == "PM" and hour < 12:
                        hour += 12

                    # No microsecond value available here.
                    time = datetime.time(hour, getint('minute'),
                                         getint('second'))

                else:
                    raise ValueError(_("Couldn't parse timestamp {!r}.").
                                     format(row[1])) from None

            # We can't simply add a timedelta to the start date.
            # e.g. 11am on the day where daylight savings starts, hours=11 will
            # actually result in 12pm (2am-3am does not exist).
            time = datetime.datetime.combine(
                date + datetime.timedelta(days=days), time)
            time = tz().localize(time)

            players = defaultdict(dict)
            # Each field column is `(field * station) - 1` (zero-indexed).
            # e.g. A1,A2,B1,B2, etc. (works for any number of stations/fields).
            for col, team in enumerate(row[3:]):
                if not team:
                    continue  # No team, skip.
                team = int(team)

                field = col // len(STATIONS)
                if field > len(FIELDS):
                    # (Avoids FIELDS[field] IndexError, more details this way.)
                    raise ValueError(_(
                        "Field number {0} too large (max {1}) (time {2})."
                        ).format(field, len(FIELDS), time.isoformat()))

                players[field][col % len(STATIONS)] = team

            if not players:
                players[0] = {}  # Default to first field (no players).
            elif len(players) > 1:
                # Warn, but not a breaking error, even if extra supplied.
                self.stdout.write(self.style.WARNING(_(
                    "Splitting simultaneous match (time {}).").format(
                        time.isoformat())))

            for field in players:
                # Now save the objects to the database.
                number = 1
                round = 1
                last = Match.objects.filter(
                    tournament=tournament).order_by('number').last()
                if last is not None:
                    number = last.number + 1
                    round = last.round

                # Enum value by index for field.
                match = Match(
                    tournament=tournament, number=number, round=round,
                    field=FIELDS[field], schedule=time, actual=None)
                match.full_clean()  # Ensure friendly errors.
                match.save()

                # Find players that fail full_clean() (duplicate team/round).
                clean_players = []
                dirty_players = []  # "Clean failed."
                for stn, team in players[field].items():
                    team = Team.objects.get(number=team)
                    # Get station enum value by index.
                    player = Player(team=team, match=match,
                                    station=STATIONS[stn], surrogate=False)
                    try:
                        player.full_clean()
                        # No exceptions, so it's clean.
                        clean_players.append(player)
                    except ValidationError:
                        # Too difficult to ensure correct ValidationError, so
                        # just assume it is. Presumably any db constraints will
                        # restrict all the important things anyway.
                        dirty_players.append(player)

                # If (players exist, and) all are repeats, then next round.
                if dirty_players and not clean_players:
                    match.round += 1
                    match.save()  # During setup, no race condition F(...).
                # Else, make the extras surrogates.
                else:
                    for p in dirty_players:
                        p.surrogate = True
                # Finally, save all.
                clean_players.extend(dirty_players)
                for p in clean_players:
                    p.full_clean()  # Ensure friendly errors.
                    p.save()

        with open(file, newline='') as f:
            reader = csv.reader(f, delimiter=',', quotechar='"')
            reader = iter(reader)
            assert next(reader)[:2] == ["Version Number", "1"], _(
                "Unknown format.")
            assert next(reader)[:2] == ["Block Format", "1"], _(
                "Block Format 1 Fail")

            # From here on, we don't know how long the file is.
            # We do have to be wary of StopIteration. Terminate when done.
            # (Not all tournaments have the practice tournament.)
            with suppress(StopIteration):
                # Block 1; teams.
                self.stdout.write(self.style.SUCCESS(_(
                    "Found block 1; importing teams...")))
                next(reader)  # Number of Teams,26
                row = next(reader)  # First team row.
                while row[0] != "Block Format":
                    team = Team(number=int(row[0]), name=row[1])
                    team.full_clean()  # Ensure friendly errors.
                    team.save()
                    row = next(reader)

                # Block 2; ranking matches.
                self.stdout.write(self.style.SUCCESS(_(
                    "Found block 2; importing ranking matches...")))
                if len(row[1]) == 1:
                    # Normally skip Number of [Ranking] Matches, but some tools
                    # do miss the newline character, merging the following line
                    # e.g. Block Format,2Number of Ranking Matches,39
                    # In this case, len(row[1]) is > 1, so we can check for it.
                    # Skip an additional line where it's split correctly.
                    next(reader)
                # Skip unused rows.
                next(reader)  # Number of Tables
                next(reader)  # Teams per Table
                next(reader)  # Simultaneous Tables
                next(reader)  # Table Names
                row = next(reader)  # First match row.
                while row[0] != "Block Format":
                    process_match_row(row, TOURNAMENTS[0])
                    row = next(reader)

                # Block 3; judging, ignored.
                self.stdout.write(self.style.SUCCESS(_(
                    "Found block 3; skipping judging schedule...")))
                row = next(reader)
                while row[0] != "Block Format":
                    row = next(reader)

                # Block 4; practice matches.
                self.stdout.write(self.style.SUCCESS(_(
                    "Found block 4; importing practice matches...")))
                if len(row[1]) == 1:
                    # As before, check if the line was accidentally merged, and
                    # if it's split, we need to skip the extra line.
                    next(reader)
                # Skip unused rows again.
                next(reader)  # Number of Tables
                next(reader)  # Teams per Table
                next(reader)  # Simultaneous Tables
                next(reader)  # Table Names
                row = next(reader)  # First match row.
                while row[0] != "Block Format":
                    # We shouldn't see another "Block Format", so ultimately
                    # this goes until the end of the file (StopIteration).
                    # If we hit a "Block Format", we terminate early, all good.
                    process_match_row(row, TOURNAMENTS[1])
                    row = next(reader)

                self.stdout.write(self.style.WARNING(_(
                    "Found a 5th block, but ignoring the rest of the file.")))

        self.stdout.write(self.style.SUCCESS(_("Complete (end-of-file).")))
