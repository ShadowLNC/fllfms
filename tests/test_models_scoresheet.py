from importlib import import_module
import warnings

from django.conf import settings

# We cannot test the abstract model on its own, so we attempt to import the
# current Scoresheet subclass model as defined in settings. If there's no tests
# for the set model, we must skip Scoresheet tests (including ABC) entirely.

model_path = settings.FLLFMS.get('SCORESHEET', 'fllfms.scoresheets._stub')

try:
    # TestSuite is assumed to be defined if the file exists.
    ModelScoresheetTests = import_module(
        'fllfms.tests.scoresheets.' + model_path.rpartition('.')[-1]).TestSuite

except (ImportError, AttributeError):
    # Technically the only expected error is ModuleNotFoundError, but capture
    # any and all ImportErrors in case something else happens.
    # AttributeError in case the file is defined by TestSuite is not.
    warnings.warn("SCORESHEET model ({!r}) missing tests.".format(model_path))
