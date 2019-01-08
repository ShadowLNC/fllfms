from copy import deepcopy
from base64 import b64decode, b64encode

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.contrib.admin.widgets import AutocompleteSelect
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.forms.widgets import RadioSelect
from django.shortcuts import render
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import path, reverse

from reversion.admin import VersionAdmin
from reversion.models import Version

from .models import (Team, Match, Player, Scoresheet,
                     Timer, TimerProfile, TimerStage, TIMERSTATES,)


class RadioRow(RadioSelect):
    template_name = "fllfms/radiorow.html"
    option_template_name = "fllfms/radiorow_option.html"

    # There are some remanants from the RadioSelect context, we ignore them.
    # self.attrs seems to be applied to both <ul> and <input> elements.
    # This is also true for RadioSelect, and doesn't seem to break anything.
    def get_context(self, name, value, attrs):

        # Work with long choices (automatic class if not declared).
        if not self.attrs.get('class', None):
            # If any option label is more than 5 chars, use vertical.
            # Make sure to cast to str before len()!
            long = any(len(str(i['label'])) > 5
                       for i in self.options(None, []))
            self.attrs['class'] = 'radiocolumn' if long else 'radiorow'

        context = super().get_context(name, value, attrs)
        context['widget']['options'] = self.options(
            name, context['widget']['value'], attrs)
        return context

    class Media:
        css = {'all': ("fllfms/radiorow.css",)}


class SignatureWidget(forms.Widget):
    template_name = 'fllfms/signature_widget.html'

    def format_value(self, value):
        value = value or ""
        if isinstance(value, str):
            # Happens if we don't use to_python(), e.g. validation failure.
            return value
        return str(b64encode(value or b""), 'ascii')

    class Media:
        js = (
            "fllfms/vendor/signature_pad/signature_pad.umd.min.js",
            "fllfms/signature_widget.js",
        )


class SignatureField(forms.Field):
    initial = None
    widget = SignatureWidget

    def to_python(self, value):
        if not value:
            return None
        try:
            return b64decode(value)
        except (TypeError, ValueError):
            raise ValidationError(_("Invalid data format."),
                                  code='invalid')

    def clean(self, value):
        value = self.to_python(value)
        if value is None:
            raise ValidationError(_("A signature is required."),
                                  code='required')

        return value


class PlayerAdmin(admin.TabularInline):
    model = Player
    fields = ('match', 'station', 'team', 'surrogate', 'scoresheet_link',)
    readonly_fields = ('scoresheet_link',)

    # We want to disallow editing the team once set, else scores would move to
    # the new team, so require a new Player instead. Blocked by Django #15602.
    # In the meantime: clean() checks on model.
    # readonly_fields = tuple()

    ordering = ('station',)

    def scoresheet_link(self, obj):
        url_name_data = (self.admin_site.name, Scoresheet._meta.app_label,
                         Scoresheet._meta.model_name)

        if getattr(obj, 'scoresheet', None) is not None:
            text = _(
                "Edit scoresheet... (Score: {})").format(obj.scoresheet.score)
            url = reverse("{}:{}_{}_change".format(*url_name_data),
                          args=[obj.scoresheet.pk])
        elif obj.station is not None and obj.match.actual is not None:
            # Only allow adding for existing players on a completed match.
            text = _("Click to add...")
            # Kinda hacky to prepopulate via querystring, but it works, so...
            url = (reverse("{}:{}_{}_add".format(*url_name_data)) +
                   "?player={}".format(obj.pk))

        else:
            return "-"  # No link for not-yet-created players.
        return format_html('<a href="{}">{}</a>', url, text)
    scoresheet_link.short_description = _("scoresheet")

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
class TeamAdmin(VersionAdmin, admin.ModelAdmin):
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
class MatchAdmin(VersionAdmin, admin.ModelAdmin):
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

                action = queryset.filter  # For '0', filter on played matches.
                if self.value() == '1':
                    action = queryset.exclude  # Exclude played (Yet To Play).

                # Distinct to prevent duplicates.
                return action(Q(actual__isnull=False)
                              | Q(players__scoresheet__isnull=False)
                              ).distinct()

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

    @staticmethod
    def action_reset(self, request, queryset):
        # NOTE: 'self' is the modeladmin object, which is provided.
        # The staticmethod decorator ensures that it's not provided twice.

        # Reset the match to an unplayed state.
        # Completed matches only (actual is not None or scoresheets exist).
        # Note that distinct() is needed else the second Q causes duplicates.
        queryset = queryset.prefetch_related('players__scoresheet').filter(
            Q(actual__isnull=False) | Q(players__scoresheet__isnull=False)
            ).distinct()
        scoring = self.admin_site._registry.get(Scoresheet)

        for match in queryset:
            # We seek permission to clear actual and delete scoresheets,
            # but not modify the player, since we don't do that.
            if not self.has_change_permission(request, match):
                break
            for player in match.players.all():
                if (getattr(player, 'scoresheet', None) is not None
                        and not scoring.has_delete_permission(
                            request, player.scoresheet)):
                    break
        else:
            # Valid, the loop did not terminate.
            with transaction.atomic():
                count = queryset.count()  # Get count before updating.
                Scoresheet.objects.filter(player__match__in=queryset).delete()
                for match in queryset:
                    if match.actual is not None:
                        match.actual = None
                        match.save()  # Trigger a reversion change.
            self.message_user(
                request, _(
                    "{} matches were reset. Any other selected matches were "
                    "already in an unplayed state.").format(count),
                level=messages.SUCCESS)

            return  # Skip error below.

        self.message_user(
            request, _("You do not have sufficient privileges to perform the "
                       "requested action."),
            level=messages.ERROR)

    @staticmethod
    def action_empty(self, request, queryset):
        # NOTE: 'self' is the modeladmin object, which is provided.
        # The staticmethod decorator ensures that it's not provided twice.

        # Remove players from stations (only possible if match is unplayed).
        if queryset.filter(
                Q(actual__isnull=False) | Q(players__scoresheet__isnull=False)
                ).exists():
            self.message_user(
                request, _("Selection includes matches that have already been "
                           "played (cannot clear players). Reset those "
                           "matches first."),
                level=messages.ERROR)
            return

        playeradmin = PlayerAdmin(parent_model=self.model,
                                  admin_site=self.admin_site)
        playerset = Player.objects.filter(match__in=queryset)
        valid = all((
            playeradmin.has_delete_permission(request, obj)
            for obj in playerset
        ))
        if valid:
            num = playerset.delete()[0]
            for match in queryset:
                match.save()  # Trigger reversion change.
            # TODO the ngettext translation thing.
            self.message_user(
                request, _("{} players were deleted.").format(num),
                level=messages.SUCCESS)
        else:
            self.message_user(
                request, _("You do not have sufficient privileges to perform "
                           "the requested action."),
                level=messages.ERROR)

    list_display = (
        'tournament', 'number', 'round', 'field', 'schedule', 'actual',)
    list_display_links = list_display[:2]
    list_editable = list_display[2:]
    list_filter = ('tournament', 'round', 'field',
                   MatchCompleteFilter, StationCountFilter,)
    ordering = ('-tournament', 'number',)
    fields = list_display
    search_fields = ('number',)

    def get_actions(self, request):
        actions = super().get_actions(request)
        # TODO check scoresheet deletion permissions.
        if self.has_change_permission(request) and True:
            actions['reset'] = (self.action_reset, 'reset', _(
                "Reset selected matches to unplayed state (time/scores)"))
        if PlayerAdmin(parent_model=self.model, admin_site=self.admin_site
                       ).has_delete_permission(request):
            actions['empty'] = (self.action_empty, 'empty', _(
                "Delete all players from selected matches"))
        return actions

    inlines = [
        PlayerAdmin,
    ]


@admin.register(Scoresheet)
class ScoresheetAdmin(VersionAdmin, admin.ModelAdmin):
    # Deepcopy but cast list to allow modifiction without altering original.
    _mission_fieldsets = list(deepcopy(Scoresheet.missions))
    for missionset in _mission_fieldsets:
        # This modifies by reference, taking only first entry from each tuple.
        # Each 'field' is a tuple (name, {**config}), we want a list of names.
        missionset[1]['fields'] = [
            mission[0] for mission in missionset[1]['fields']]

    _mission_fields = sum(
        (section[1]['fields'] for section in _mission_fieldsets), [])

    def imgsignature(self, obj):
        return format_html('<img src="data:image/png;base64,{}">',
                           str(b64encode(obj.signature), 'ascii'))
    imgsignature.short_description = _("team initials")

    def get_fieldsets(self, request, obj=None):
        # Replace signature with imgsignature if it's going to be readonly.
        # Kinda cheaty, but admin forms can only output text/booleans.
        # We'd have to subclass at least 3 classes to do it "properly".
        # I copied the "readonly form" check from ModelAdmin._changeform_view.
        signature = 'signature'
        if obj is not None and not self.has_change_permission(request, obj):
            signature = 'imgsignature'

        return (
            (_("Player details"), {
                'fields': ['player', 'referee']
            }),
            *self._mission_fieldsets,
            (_("Sign off"), {
                'fields': [signature]
            }),
        )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        db = kwargs.get('using')

        if db_field.name == 'player':
            if 'queryset' not in kwargs:
                # Specify limiting and especially ordering here, not model.
                mgr = db_field.remote_field.model._default_manager.using(db)
                filter = Q(scoresheet__isnull=True,
                           match__actual__isnull=False)

                # If we're editing existing, show current selection too.
                obj = request.resolver_match.kwargs.get('object_id')
                if obj is None:
                    # django-reversion uses args
                    # The last item will always be the Version pk.
                    # Slice, then add [None] in case empty, then get element.
                    obj = (request.resolver_match.args[-1:] + (None,))[0]
                    if obj is not None:
                        obj = Version.objects.get(pk=obj)  # Get prev version.

                        # When editing a revision, or recovering a deleted
                        # object, a fake version is created to restore from. If
                        # editing, this fake version overwrites the current
                        # value, "freeing" that Player and allowing it to be
                        # selected.

                        # In both cases, the fake object uses the old Player in
                        # the fake object, blocking it from appearing as
                        # selectable (indeed, if the old Player is in use
                        # elsewhere, the view fails since the fake cannot be
                        # created). If the Player is unchanged between old and
                        # current, the view succeeds, but still blocks the
                        # value from selection.

                        # We must whitelist the old Player for selection, since
                        # this is a history view, so we want it visible, even
                        # if it could not be selected (which won't happen since
                        # the fake object creation would fail instead).

                        # Without the fake, this gets the old value.
                        # prev = obj.field_dict.get(db_field.column)
                        # if prev is not None:
                        #     filter |= Q(pk=prev)

                        # Without the fake, this gets the current value.
                        # For now, it's actually the old value from the fake.
                        obj = obj.field_dict.get(Scoresheet._meta.pk.column)

                if obj is not None:
                    filter |= Q(scoresheet__pk=obj)

                kwargs['queryset'] = mgr.filter(filter).order_by(
                    '-match__actual', 'match', 'station')

            # Skip the RelatedFieldWidgetWrapper.
            return db_field.formfield(**kwargs)

        if db_field.name == 'referee':
            # Skip the RelatedFieldWidgetWrapper.
            return db_field.formfield(**kwargs)

        if db_field.name == 'signature':
            return db_field.formfield(form_class=SignatureField, **kwargs)

        if db_field.name in self._mission_fields:
            if 'widget' not in kwargs:
                kwargs['widget'] = RadioRow()
            if 'choices' not in kwargs:
                kwargs['choices'] = db_field.get_choices(include_blank=False)

            return db_field.formfield(**kwargs)

        # Later: filter on referee role for referee field.
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class TimerStageAdmin(admin.TabularInline):
    model = TimerStage
    fields = ('name', 'trigger', 'css', 'display', 'sound',)

    ordering = ('trigger', 'name', 'pk',)


@admin.register(Timer)
class TimerAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ('id', 'name', 'match', 'state', 'profile',)
    list_display_links = list_display[:2]
    list_editable = ('match',)
    fields = list_display
    readonly_fields = ('id', 'state',)
    autocomplete_fields = ('match',)

    ordering = ('name', 'pk',)

    def state(self, timer):
        states = {
            TIMERSTATES.PRESTART: _('Pre-Start'),
            TIMERSTATES.START: _('Running'),
            TIMERSTATES.END: _('Stopped'),
            TIMERSTATES.ABORT: _('Failed'),
        }
        return states.get(timer.state)
    state.short_description = _("timer state")

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name

        return [
            path('<path:object_id>/control/',
                 self.admin_site.admin_view(self.control_view),
                 name="{}_{}_control".format(*info)),
            *super().get_urls(),
        ]

    def control_view(self, request, object_id):
        # Check if exists (404) first, then permissions (403).
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            # Later: when moving this function to views.py, add 404/403 args.
            return self._get_obj_does_not_exist_redirect(
                request, self.model._meta, object_id)

        # NOTE: Keep synchronised with permissions checks in consumers.py.
        profile_admin = self.admin_site._registry.get(TimerProfile)
        if not (self.has_change_permission(request, obj)
                and profile_admin.has_view_permission(request, obj.profile)):
            raise PermissionDenied

        return render(request, 'fllfms/timer_control.html', context={
            'object_id': object_id,  # Already quoted as passed argument.
        })


@admin.register(TimerProfile)
class TimerProfileAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ('name', 'duration', 'format',)
    # fields = list_display
    ordering = ('name', 'duration', 'pk',)
    fieldsets = (
        (_("General"), {'fields': ('name', 'duration', 'format',)}),
        (_("Pre-Start"), {'fields': ('prestartcss',)}),
        (_("Start"), {'fields': ('startcss', 'startdisplay', 'startsound',)}),
        (_("End"), {'fields': ('endcss', 'endsound',)}),
        (_("Abort"), {'fields': ('abortsound',)}),
    )

    inlines = [
        TimerStageAdmin,
    ]
