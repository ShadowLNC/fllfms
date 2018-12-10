from django.conf import settings
from django.db.models import Max, OuterRef, Subquery, Window, F
from django.db.models.functions.window import Rank
from django.shortcuts import render

from .models import Team, Match, Scoresheet


def schedule_basic(request):
    return render(request, 'fllfms/schedule_basic.html', context={
        'matches': Match.objects.all().order_by('schedule', 'number')})


def rankings(request, tournament):
    annotates = {}
    maxround = Match.objects.filter(tournament=tournament).aggregate(
        maxround=Max('round'))['maxround']
    teamscores = Scoresheet.objects.filter(
        player__team=OuterRef('pk'), player__surrogate=False)

    # best1, best2, ... for ranking and round1, round2, ... for output.
    for round in range(1, maxround + 1):
        annotates["best{}".format(round)] = Subquery(
            teamscores.order_by('score')[round - 1:round].values('score'))
        annotates["round{}".format(round)] = Subquery(
            teamscores.filter(player__match__round=round).values('score'))

    annotates['rank'] = Window(expression=Rank(), order_by=[
        F("best{}".format(round)).desc() for round in range(1, maxround + 1)])

    # Only rank eligible teams. Add disqualified teams later (no scores).
    teams = Team.objects.filter(dq=False).annotate(
        **annotates).order_by('rank', 'number')

    # Patch each object with the scores property for ease of template access.
    def patch(t):
        def scores(self):
            for round in range(1, maxround + 1):
                yield getattr(self, "round{}".format(round))
        t.scores = scores.__get__(t)
        return t
    teams = map(patch, teams)

    # Add disqualified teams as mentioned above (we do it after patching).
    teams = (*teams, *Team.objects.filter(dq=True).order_by('number'))

    context = {
        'teams': teams,
        'roundrange': range(1, maxround + 1),
        'tournament': Match(tournament=tournament).get_tournament_display(),
        'event': settings.FLLFMS.get('EVENT_NAME', ""),
    }
    return render(request, 'fllfms/rankings.html', context=context)
