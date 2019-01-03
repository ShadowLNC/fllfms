from contextlib import suppress
from datetime import datetime, timezone
from functools import partial
import os.path

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.generic.websocket import JsonWebsocketConsumer
from django.contrib.staticfiles.templatetags.staticfiles import static

from .models import APP_STATIC_ROOT, Match, Timer, TimerProfile


def usec(time):
    # Helper function to convert timedeltas into microseconds.
    # Since some fields might be None, we can't multiply those.
    if time is None:
        return None
    return int(time.total_seconds()*1000000)


class TimerConsumer(JsonWebsocketConsumer):
    # NOTE: This pulls from the parent class, if changed then you must update.
    channel_layer = get_channel_layer(
        JsonWebsocketConsumer.channel_layer_alias)

    channel_prefix = "timer"
    valid_subscriptions = ["profile", "state", "match"]

    @classmethod
    def group_sendable(cls, group):
        return partial(async_to_sync(cls.channel_layer.group_send), group)

    @classmethod
    def getgroup(cls, obj_id, subscription):
        return "{}_{}_{}".format(cls.channel_prefix, obj_id, subscription)

    @classmethod
    def send_profile(cls, profile, sendable=None):
        if sendable is None:
            def sendable(msg):
                for timer in profile.timers.values('pk'):
                    cls.group_sendable(cls.getgroup(timer, "profile"))

        def as_static(path):
            return static(os.path.relpath(path, APP_STATIC_ROOT))

        sendable({
            'type': "profile",

            'duration': usec(profile.duration),
            'format': profile.format,

            'prestartcss': profile.prestartcss,

            'startcss': profile.startcss,
            'display': usec(profile.startdisplay),
            'startsound': as_static(profile.startsound),

            'endcss': profile.endcss,
            'endsound': as_static(profile.endsound),

            'abortsound': as_static(profile.abortsound),

            'stages': [
                {
                    'trigger': usec(stage.trigger),
                    'css': stage.css,
                    'display': usec(stage.display),
                    'sound': as_static(stage.sound),
                }
                for stage in profile.stages.all()
            ],
        })

    @classmethod
    def send_state(cls, timer, sendable=None):
        if sendable is None:
            sendable = cls.group_sendable(cls.getgroup(timer.pk, "state"))

        msg = {
            'type': "state",
            'state': timer.state,
        }
        if timer.start:
            msg['elapsed'] = usec(
                datetime.utcnow(timezone.utc) - timer.starttime)

        sendable(msg)

    @classmethod
    def send_match(cls, match, sendable=None):
        if sendable is None:
            if match.timer is None:
                return  # No timer to update.
            sendable = cls.group_sendable(
                cls.getgroup(match.timer.pk, "match"))

        if match is None:
            sendable({
                'type': "match",
                # TODO
            })
            return

        sendable({
            'type': "match",
            'number': match.number,
            'title': str(match),
            'field': match.get_field_display(),
            'players': [
                {
                    'station': player.get_station_display(),
                    'number': player.team.number,
                    'name': player.team.name,
                    'dq': player.team.dq,
                }
                for player in match.players.select_related(
                    'team').order_by('station')
            ]
        })

    def __init__(self, *args, **kwargs):
        self.groups = set()
        super().__init__(*args, **kwargs)

    @database_sync_to_async
    def dispatch(self, message):
        # All our subscription events send as json, so no handler needed.
        if message.get('type') in self.valid_subscriptions:
            self.send_json(message)
            return

        async_to_sync(super().dispatch)(message)

    def join(self, group):
        async_to_sync(self.channel_layer.group_add)(group, self.channel_name)
        self.groups.add(group)

    def leave(self, group):
        async_to_sync(self.channel_layer.group_discard)(group,
                                                        self.channel_name)
        self.groups.discard(group)

    def connect(self):
        # TODO auth & validate.
        self.object_id = self.scope['url_route']['kwargs']['object_id']
        self.accept()

    def disconnect(self, close_code):
        for group in list(self.groups):
            self.leave(group)

    def receive_json(self, data):
        if data['type'] == "subscribe":
            if data['channel'] in self.valid_subscriptions:
                self.join(self.getgroup(self.object_id, data['channel']))

                # Now trigger a first-time-send of the data.
                # Get the appropriate function and object to apply to it.
                func = getattr(self, "send_" + data['channel'])
                obj = None
                if data['channel'] == "profile":
                    obj = TimerProfile.objects.get(timers__pk=self.object_id)
                elif data['channel'] == "state":
                    obj = Timer.objects.get(pk=self.object_id)
                elif data['channel'] == "match":
                    with suppress(Match.DoesNotExist):
                        obj = Match.objects.get(timer__pk=self.object_id)

                # Don't send if there's nothing to send.
                # Timer.match can be None, but others can't.
                if obj is not None or data['channel'] == "match":
                    func(obj, sendable=async_to_sync(self.dispatch))
