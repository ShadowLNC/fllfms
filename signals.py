from contextlib import suppress

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from .consumers import TimerConsumer
from .models import Timer, TimerProfile, Match


class TimerSignalCache:
    # Caches old copies before saving, allowing them to be diffed against new.
    # Particularly useful given that update_fields is often None in post_save.

    # This is a singleton class to prevent multiple bindings of the signal.
    # Rationale: If the object was recreated, new receivers might be installed,
    # or the old ones might be left untouched, and if the old instance is
    # garbage collected, then there would be no receivers (due to weakref).
    # Using weak=False and allowing multiple instances could result in race
    # conditions where receivers are from different classes.
    # If the class is redefined/reimported, then there might be issues anyway.
    _SINGLETON = None

    @classmethod
    def __new__(cls, *args, **kwargs):
        if cls._SINGLETON is None:
            cls._SINGLETON = super().__new__(*args, **kwargs)
        return cls._SINGLETON

    def __init__(self):
        self.oldcopies = {}
        # dispatch_uid shouldn't be necessary with singleton, but doesn't hurt.
        pre_save.connect(self.timer_pre_save, sender=Timer,
                         dispatch_uid="timer_pre_save")
        post_save.connect(self.timer_post_save, sender=Timer,
                          dispatch_uid="timer_post_save")

    def timer_pre_save(self, sender, instance, raw, using, update_fields,
                       **kwargs):
        if not instance.pk:
            return
        with suppress(Timer.DoesNotExist):
            # Use values() to prevent infinite recursion as Timer.__init__
            # calls save().
            self.oldcopies[instance.pk] = Timer.objects.values().get(
                pk=instance.pk)

    def timer_post_save(self, sender, instance, created, raw, using,
                        update_fields, **kwargs):
        if created or raw:
            # No listeners can exist since it was just created.
            # Also, pre_save won't have stored anything, no need to clear.
            return

        old = self.oldcopies[instance.pk]
        del self.oldcopies[instance.pk]
        # Get values() to match data with pre_save.
        new = Timer.objects.values().get(pk=instance.pk)

        def changed(attr):
            return old.get(attr) != new.get(attr)

        if any(changed(i) for i in ['starttime', 'state']):
            # starttime also affects state/elapsed, must also be checked.
            TimerConsumer.send_state(instance)

        if changed('profile'):
            # sendable should be declared to just be timer's profile, not all
            # timers using this profile (the profile itself was not changed).
            sendable = TimerConsumer.group_sendable(
                TimerConsumer.getgroup(instance.pk, "profile"))
            TimerConsumer.send_profile(instance.profile, sendable=sendable)

        if changed('match'):
            TimerConsumer.send_match(instance)


_timer_signal_cache = TimerSignalCache()


# No receivers below rely on diffs (list of changed fields), so no class.
@receiver(post_save, sender=TimerProfile, dispatch_uid="profile_post_save")
def profile_post_save(sender, instance, created, raw, using, update_fields,
                      **kwargs):
    if not created:
        TimerConsumer.send_profile(instance)


@receiver(post_save, sender=Match, dispatch_uid="match_post_save")
def match_post_save(sender, instance, created, raw, using, update_fields,
                    **kwargs):
    if not created:
        # We don't want to send an event if there's no timer.
        # If no timer, no event will be sent due to Timer.DoesNotExist.
        with suppress(Timer.DoesNotExist):
            TimerConsumer.send_match(instance.timer)


# We need to close sockets where the timer has been deleted. Note that it's not
# necessary to listen for profile deletes (can't have attached timers) nor
# match deletes (sets timer.match = None, triggering timer_post_save).
@receiver(post_delete, sender=Timer, dispatch_uid="timer_post_delete")
def timer_post_delete(sender, instance, using, **kwargs):
    for sub in TimerConsumer.valid_subscriptions:
        TimerConsumer.terminate_group(TimerConsumer.group_sendable(
            TimerConsumer.getgroup(instance.pk, sub)))
