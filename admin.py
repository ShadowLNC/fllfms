from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Team, Match, Player


class PlayerAdmin(admin.TabularInline):
    model = Player

    fields = ('match', 'station', 'team', 'surrogate',)

    # We want to disallow editing the team once set, else scores would move to
    # the new team, so require a new Player instead. Blocked by Django #15602.
    # readonly_fields = tuple()
    autocomplete_fields = ('team',)

    ordering = ('station',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    class EligibilityFilter(admin.SimpleListFilter):
        title = _("eligibility")
        parameter_name = 'dq'

        def lookups(self, request, model_admin):
            return (
                # Values are negated to filter on dq, eligible=yes -> dq=False.
                (0, _("Eligible")),
                (1, _("Disqualified")),
            )

        def queryset(self, request, queryset):
            # self.value() is taken from self.lookups()
            if self.value() is not None:
                return queryset.filter(dq__exact=self.value())

    # Eligibility column so ticks represent eligible teams (not disqualified).
    def eligible(self, team):
        return not team.dq
    eligible.short_description = _("eligible")
    eligible.boolean = True
    eligible.admin_order_field = 'dq'

    list_display = ('number', 'name', 'eligible')
    list_display_links = list_display[:-1]  # Cut the dq column.
    list_filter = (EligibilityFilter,)

    fields = list_display[:-1] + ('dq', )
    readonly_fields = tuple()

    ordering = ('number',)

    search_fields = ('number', 'name',)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            # Disallow editing the team number once set.
            return self.readonly_fields + ('number',)
        return self.readonly_fields


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    class MatchCompleteFilter(admin.SimpleListFilter):
        title = _("completion state")
        parameter_name = 'complete'

        def lookups(self, request, model_admin):
            return (
                (1, _("Played")),
                (0, _("Yet To Play")),
            )

        def queryset(self, request, queryset):
            if self.value() is not None:
                # When scores are implemented, we will use their presence as
                # a completion indicator too.
                # For now, if match actual start is NOT null, it is complete.
                return queryset.filter(actual__isnull=not int(self.value()))

    list_display = ('tournament', 'number', 'round',
                    'field', 'schedule', 'actual',)
    list_display_links = list_display[:2]
    list_editable = list_display[2:]
    list_filter = ('tournament', 'round', 'field', MatchCompleteFilter,)

    ordering = ('-tournament', 'number',)

    inlines = [
        PlayerAdmin,
    ]
