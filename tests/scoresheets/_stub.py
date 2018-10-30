from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError

from ._base import BaseScoresheetTests


class TestSuite(BaseScoresheetTests):
    def with_missions(self, scoresheet=None):
        scoresheet = super().with_missions(scoresheet)
        scoresheet.missionscore = 3
        return scoresheet

    # Specific scoring tests.
    def test_score_1(self):
        s = self.get_base()
        s.missionscore = 4
        self.assertEqual(s.calculatescore(), 20)

    def test_missionscore_constraints(self):
        s = self.get_base()
        s.missionscore = 6
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                s.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                s.save()
