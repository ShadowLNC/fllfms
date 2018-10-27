from datetime import datetime, timezone
from unittest import skip, skipIf

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.utils import IntegrityError
from django.test import TestCase

from ..models import Team, Match, Player


class ModelTeamTests(TestCase):
    def test_defaults(self):
        t = Team(number=3)
        t.full_clean()
        t.save()
        self.assertIsNotNone(t.pk)

    def test_number_constraints(self):
        for i in (-1, 0):
            with self.subTest(i=i):
                t = Team(number=i, name="My Robotics Team", dq=False)
                with self.assertRaises(ValidationError):
                    # transaction.atomic required per Django ticket #21540.
                    with transaction.atomic():
                        t.full_clean()
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        t.save()

    def test_number_unique(self):
        t1 = Team(number=1, name="Team 1", dq=False)
        t1.save()
        self.assertIsNotNone(t1.pk)
        t2 = Team(number=1, name="Robot 2", dq=True)
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                t2.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                t2.save()

    def test_empty_repr_str(self):
        # No need to assert anything as it just verifies no crash.
        _ = repr(Team())
        _ = str(Team())


class ModelMatchTests(TestCase):
    # Field and tournament data fields are enums (int fields with choices).
    def test_defaults(self):
        m = Match(tournament=settings.FLLFMS['TOURNAMENTS'][0][0],
                  number=42, round=2,
                  field=settings.FLLFMS['FIELDS'][0][0],
                  schedule=datetime(2018, 2, 21, 4, 59, 00,
                                    tzinfo=timezone.utc)
                  )
        m.full_clean()
        m.save()
        self.assertIsNotNone(m.pk)

    @skip("Django bug #29868")
    def test_tournament_constraints(self):
        # 999 is sufficiently large that it should exceed all enum values.
        # It's also less than 32767 which is the max smallint (signed) size.
        m = Match(tournament=999,
                  number=12, round=1,
                  field=settings.FLLFMS['FIELDS'][0][0],
                  schedule=datetime(2018, 2, 21, 4, 59, 00,
                                    tzinfo=timezone.utc),
                  actual=datetime(2019, 3, 21, 12, 21, 1, 213545,
                                  tzinfo=timezone.utc)
                  )
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                m.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                m.save()

    @skip("Django bug #29868")
    def test_number_constraints(self):
        for i in (-1, 0):
            with self.subTest(i=i):
                m = Match(tournament=settings.FLLFMS['TOURNAMENTS'][0][0],
                          number=i, round=2,
                          field=settings.FLLFMS['FIELDS'][0][0],
                          schedule=datetime(2018, 2, 21, 4, 59, 00,
                                            tzinfo=timezone.utc),
                          actual=datetime(2019, 3, 21, 1, 21, 43, 424242,
                                          tzinfo=timezone.utc)
                          )
                with self.assertRaises(ValidationError):
                    with transaction.atomic():
                        m.full_clean()
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        m.save()

    @skip("Django bug #29868")
    def test_round_constraints(self):
        for i in (-1, 0):
            with self.subTest(i=i):
                m = Match(tournament=settings.FLLFMS['TOURNAMENTS'][0][0],
                          number=654, round=i,
                          field=settings.FLLFMS['FIELDS'][0][0],
                          schedule=datetime(2019, 2, 21, 4, 59, 00,
                                            tzinfo=timezone.utc),
                          actual=datetime(2019, 3, 21, 12, 21, 00, 999999,
                                          tzinfo=timezone.utc)
                          )
                with self.assertRaises(ValidationError):
                    with transaction.atomic():
                        m.full_clean()
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        m.save()

    def test_field_constraints(self):
        # 999 is sufficiently large that it should exceed all enum values.
        # It's also less than 32767 which is the max smallint (signed) size.
        m = Match(tournament=settings.FLLFMS['TOURNAMENTS'][0][0],
                  number=12, round=1, field=999,
                  schedule=datetime(2018, 2, 21, 4, 59, 00,
                                    tzinfo=timezone.utc),
                  actual=datetime(2019, 3, 21, 22, 41, 22, 258741,
                                  tzinfo=timezone.utc)
                  )
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                m.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                m.save()

    def test_uniq_together_tournament_number(self):
        m = Match(tournament=settings.FLLFMS['TOURNAMENTS'][0][0],
                  number=21, round=2,
                  field=settings.FLLFMS['FIELDS'][0][0],
                  schedule=datetime(2018, 2, 21, 4, 59, 00,
                                    tzinfo=timezone.utc),
                  actual=datetime(2019, 3, 21, 12, 21, 11, 654789,
                                  tzinfo=timezone.utc)
                  )
        m.save()
        self.assertIsNotNone(m.pk)

        m2 = Match(tournament=settings.FLLFMS['TOURNAMENTS'][0][0],
                   number=21, round=2,
                   field=settings.FLLFMS['FIELDS'][0][0],
                   schedule=datetime(2018, 2, 21, 4, 59, 00,
                                     tzinfo=timezone.utc),
                   actual=datetime(2019, 3, 21, 12, 41, 23, 5000,
                                   tzinfo=timezone.utc)
                   )
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                m2.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                m2.save()

    def test_empty_repr_str(self):
        # No need to assert anything as it just verifies no crash.
        _ = repr(Match())
        _ = str(Match())


class ModelPlayerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        Team(number=1).save()
        Team(number=2).save()

        Match(tournament=settings.FLLFMS['TOURNAMENTS'][0][0],
              number=1, round=1,
              field=settings.FLLFMS['FIELDS'][0][0],
              schedule=datetime(2019, 2, 21, 4, 59, 00,
                                tzinfo=timezone.utc),
              actual=datetime(2019, 2, 22, 5, 21, 32, 987541,
                              tzinfo=timezone.utc)
              ).save()

        Match(tournament=settings.FLLFMS['TOURNAMENTS'][0][0],
              number=2, round=2,
              field=settings.FLLFMS['FIELDS'][0][0],
              schedule=datetime(2019, 2, 21, 4, 59, 00,
                                tzinfo=timezone.utc),
              actual=datetime(2019, 2, 22, 6, 21, 2, 300012,
                              tzinfo=timezone.utc)
              ).save()

    def test_defaults(self):
        p = Player(match=Match.objects.first(), team=Team.objects.first(),
                   station=settings.FLLFMS['STATIONS'][0][0])
        p.full_clean()
        p.save()
        self.assertIsNotNone(p.pk)

    def test_station_constraints(self):
        # 999 should exceed the max enum value (max smallint is 32767).
        p = Player(match=Match.objects.last(), team=Team.objects.last(),
                   station=999, surrogate=True)
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                p.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                p.save()

    @skipIf(len(settings.FLLFMS['STATIONS'][0]) < 2, "Insufficient stations.")
    def test_uniq_together_match_player(self):
        m = Match.objects.first()
        t = Team.objects.first()
        p = Player(match=m, team=t, station=settings.FLLFMS['STATIONS'][0][0])
        p.save()
        self.assertIsNotNone(p.pk)

        p2 = Player(match=m, team=t, station=settings.FLLFMS['STATIONS'][1][0])
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                p2.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                p2.save()

    def test_uniq_together_match_station(self):
        m = Match.objects.first()
        t, t2 = Team.objects.all()[:2]
        p = Player(match=m, team=t, station=settings.FLLFMS['STATIONS'][0][0])
        p.save()
        self.assertIsNotNone(p.pk)

        p2 = Player(match=m, team=t2,
                    station=settings.FLLFMS['STATIONS'][0][0])
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                p2.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                p2.save()

    def test_uniq_together_matchdata_player_form(self):
        # Constraint: unique_together: (match__round, match__tournament, team)
        # (optionally where surrogate == False)
        # This is basically the same as database one but full_clean vs save.
        Match.objects.update(round=1)  # Same round. Tournament already same.
        m, m2 = Match.objects.all()[:2]
        t = Team.objects.first()
        station = settings.FLLFMS['STATIONS'][0][0]

        p = Player(match=m, team=t, station=station, surrogate=False)
        p.save()
        self.assertIsNotNone(p.pk)
        p2 = Player(match=m2, team=t, station=station, surrogate=False)

        # Ensure clean() rejects this.
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                p2.full_clean()

        # Change the match round, and ensure DB allows it if rounds differ.
        m2.round = 2
        m2.save()
        p2.full_clean()

    @skipIf(connection.settings_dict['ENGINE'] == "django.db.backends.sqlite3",
            "Cannot test constraint on SQLite3 databases (no view indexes).")
    def test_uniq_together_matchdata_player_db(self):
        # Constraint: unique_together: (match__round, match__tournament, team)
        # (optionally where surrogate == False)
        # We can't enforce this on SQLite, so it's a separate test.
        Match.objects.update(round=1)  # Same round. Tournament already same.
        m, m2 = Match.objects.all()[:2]
        t = Team.objects.first()
        station = settings.FLLFMS['STATIONS'][0][0]

        p = Player(match=m, team=t, station=station, surrogate=False)
        p.save()
        self.assertIsNotNone(p.pk)
        p2 = Player(match=m2, team=t, station=station, surrogate=False)

        # Ensure DB rejects this save.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                p2.save()

        # Change the match round, and ensure DB allows it if rounds differ.
        m2.round = 2
        m2.save()
        p2.save()
        self.assertIsNotNone(p2.pk)

    def test_match_uniq_together_matchdata_player_form(self):
        # Constraint: unique_together: (match__round, match__tournament, team)
        # (optionally where surrogate == False)
        # This tests validation on the Match clean, for the Player constraint.
        m, m2 = Match.objects.all()[:2]
        t = Team.objects.first()
        station = settings.FLLFMS['STATIONS'][0][0]

        p = Player(match=m, team=t, station=station, surrogate=False)
        p.save()
        self.assertIsNotNone(p.pk)
        p2 = Player(match=m2, team=t, station=station, surrogate=False)
        p2.save()
        self.assertIsNotNone(p2.pk)

        m2.full_clean()  # Check it passes before altering round.
        m2.round = 1  # Now change round to violate constraint, and verify.
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                m2.full_clean()

    def test_empty_repr_str(self):
        # No need to assert anything as it just verifies no crash.
        _ = repr(Player())
        _ = str(Player())
