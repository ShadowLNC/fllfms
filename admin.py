from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.widgets import AutocompleteSelect
from django.db import models
from django.utils.translation import gettext_lazy as _

from .models import Team, Match, Player


class PlayerAdmin(admin.TabularInline):
    model = Player
    fields = ('match', 'station', 'team', 'surrogate',)

    # We want to disallow editing the team once set, else scores would move to
    # the new team, so require a new Player instead. Blocked by Django #15602.
    # In the meantime: clean() checks on model.
    # readonly_fields = tuple()

    ordering = ('station',)

    # autocomplete_fields = ('team',)  # Overriden below.
    # Standard autocomplete field won't allow us to clear it once selected. We
    # fix that by subclassing the AutocompleteSelect widget, and using that.
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        class ClearableAutocompleteSelect(AutocompleteSelect):
            def build_attrs(self, base_attrs, extra_attrs=None):
                attrs = super().build_attrs(base_attrs, extra_attrs)
                attrs.update({'data-allow-clear': 'true'})
                return attrs

        db = kwargs.get('using')
        if db_field.name == 'team':
            kwargs['widget'] = ClearableAutocompleteSelect(
                db_field.remote_field, self.admin_site, using=db)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # This is all blocked by Django bug #15602 (wrong obj value).
    # We will also need to add Player.Meta.default_permissions = tuple().
    # def has_view_permission(self, request, obj=None):
    #    if not obj:
    #        obj = Player(match=Match())
    #    return MatchAdmin(
    #        Match, self.admin_site).has_view_permission(request, obj.match)
    #
    # def has_write_permission(self, request, obj=None):
    #    if not obj:
    #        obj = Player(match=Match())
    #    return MatchAdmin(
    #        Match, self.admin_site).has_change_permission(request, obj.match)
    #
    # has_create_permission = has_write_permission
    # has_change_permission = has_write_permission
    # has_delete_permission = has_write_permission


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
            # self.value() is taken from self.lookups() (and is a string).
            if self.value() in ('0', '1'):
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
                (0, _("Played")),
                (1, _("Yet To Play")),
            )

        def queryset(self, request, queryset):
            if self.value() in ('0', '1'):
                # A match is complete if (and only if):
                #   - Scores are present (when implemented - TODO), or
                #   - Actual start time is NOT null
                # (Str always casts True, so cast self.value() to int first.)
                return queryset.filter(actual__isnull=int(self.value()))

    class StationCountFilter(admin.SimpleListFilter):
        title = _("missing teams")
        parameter_name = 'stationcount'

        def lookups(self, request, model_admin):
            # See Django #1873 for feature request to filter multiple options.
            # (Method listed doesn't seem to work with SimpleListFilter.)
            return (
                (0, _("Missing All Teams")),
                (1, _("Missing Some Teams")),
                (2, _("All Teams Present")),
            )

        def queryset(self, request, queryset):
            queryset = queryset.annotate(models.Count('players'))
            # self.value() is taken from self.lookups() (and is a string)
            if self.value() == '0':
                return queryset.filter(players__count=0)
            if self.value() == '1':
                return queryset.filter(
                    players__count__gt=0,
                    players__count__lt=len(settings.FLLFMS['TOURNAMENTS']))
            if self.value() == '2':
                return queryset.filter(
                    players__count=len(settings.FLLFMS['TOURNAMENTS']))

    def reset(self, request, queryset):
        # Filter to completed matches. TODO check for scoresheets when added.
        queryset = queryset.filter(actual__isnull=False)
        valid = all((
            # TODO check scores once added.
            self.has_change_permission(request, obj)
            and True
            for obj in queryset
        ))
        if valid:
            # TODO delete scores, if present.
            num = queryset.update(actual=None)
            self.message_user(request, _("{} matches were reset.").format(num),
                              level=messages.SUCCESS)
        else:
            self.message_user(
                request, _("You do not have sufficient privileges to perform "
                           "the requested action."),
                level=messages.ERROR)

    def empty(self, request, queryset):
        playeradmin = PlayerAdmin(parent_model=self.model,
                                  admin_site=self.admin_site)
        queryset = Player.objects.filter(match__in=queryset)
        valid = all((
            playeradmin.has_delete_permission(request, obj) for obj in queryset
        ))
        if valid:
            num = queryset.delete()[0]
            # TODO the ngettext translation thing.
            self.message_user(
                request, _("{} players were deleted.").format(num),
                level=messages.SUCCESS)
        else:
            self.message_user(
                request, _("You do not have sufficient privileges to perform "
                           "the requested action."),
                level=messages.ERROR)

    list_display = ('tournament', 'number', 'round',
                    'field', 'schedule', 'actual',)
    list_display_links = list_display[:2]
    list_editable = list_display[2:]
    list_filter = ('tournament', 'round', 'field',
                   MatchCompleteFilter, StationCountFilter,)

    def get_actions(self, request):
        actions = super().get_actions(request)
        # TODO check scoresheet deletion permissions.
        if self.has_change_permission(request) and True:
            actions['reset'] = (self.__class__.reset, 'reset',
                                _("Reset selected matches (time/scores)"))
        if PlayerAdmin(parent_model=self.model, admin_site=self.admin_site
                       ).has_delete_permission(request):
            actions['empty'] = (self.__class__.empty, 'empty',
                                _("Delete all players from selected matches"))
        return actions

    ordering = ('-tournament', 'number',)

    inlines = [
        PlayerAdmin,
    ]
