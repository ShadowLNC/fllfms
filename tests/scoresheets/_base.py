from datetime import datetime, timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.utils import IntegrityError
from django.test import TestCase

from ...models import Team, Match, Player, Scoresheet
User = get_user_model()


class BaseScoresheetTests(TestCase):
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

        Player(match=Match.objects.first(), team=Team.objects.first(),
               station=settings.FLLFMS['STATIONS'][0][0]).save()

        User.objects.create_user('su', 'su@example.com', 'norootpassword')

    def get_base(self):
        # By using an instance method, we can expect Player and User objects
        # are set up correctly, and it also means inheritance flows correctly.
        return Scoresheet(
            player=Player.objects.first(), referee=User.objects.first(),
            signature=b'1234')

    def with_missions(self, scoresheet=None):
        # This will be overridden in TestSuite subclasses.
        if scoresheet is None:
            scoresheet = self.get_base()
        return scoresheet

    def test_defaults(self, **kwargs):
        s = self.with_missions()
        # s.score is not validated and is calculated during save.
        self.assertIsNone(s.score)  # Ensure score does not exist yet.
        s.full_clean()
        s.save()
        self.assertIsNotNone(s.pk)
        self.assertIsNotNone(s.score)  # Check save() sets score.
        s.full_clean()  # Simulate edit (pk is not None) for clean()/save().

    def test_player_onetoone(self):
        s1 = self.with_missions()
        s2 = self.with_missions()
        s1.save()
        self.assertIsNotNone(s1.pk)
        s2.player = s1.player  # Copy in case the DB didn't order identically.
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                s2.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                s2.save()

    def test_player_delete(self, **kwargs):
        s = self.with_missions()
        s.save()
        self.assertIsNotNone(s.pk)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                s.player.delete()

    def test_referee_delete(self, **kwargs):
        s = self.with_missions()
        s.save()
        self.assertIsNotNone(s.pk)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                s.referee.delete()

    def test_player_validate_player_change_team_prohibited_form(self):
        # See Player.clean for the player_change_team_prohibited error.
        # Scoresheet would move across to new team, which is bad, so disallow.
        s = self.with_missions()
        s.save()
        self.assertIsNotNone(s.pk)
        # Swap out the player's team, and verify error occurs.
        p = s.player
        p.team = Team.objects.exclude(pk=p.team.pk).first()
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                p.full_clean()

    def test_empty_repr_str(self):
        # No need to assert anything as it just verifies no crash.
        _ = repr(Scoresheet())
        _ = str(Scoresheet())
