"""
This script will configure Django and allow you to start developing quickly.

NOTE: Dependencies are handled by the build process (platform scripts, bundling
with Python, etc.). In development you must run the following:
pip install -r extras/requirements.txt
(It is assumed that you have pip available, otherwise consult the Python docs.)
"""

from contextlib import suppress
import os
from os.path import abspath, dirname, exists, join
import subprocess
import sys
from shutil import copy, copytree

# It's assumed that sys.executable is the correct Python.
# That's what the platform-specific wrappers are for.

# Move to the root of the installation. This file is in the app directory.
APP_ROOT = dirname(abspath(__file__))
INSTALL_ROOT = dirname(APP_ROOT)
PACKAGING_DIR = join(APP_ROOT, "extras")
os.chdir(INSTALL_ROOT)


def run_and_check(*args, **kwargs):
    # Run a subprocess, raising an exception if it exits with nonzero status.
    proc = subprocess.run(*args, **kwargs)
    proc.check_returncode()
    return proc


# ##### STAGE 1: COPY FILES ##### #


# Copy djangoproject folder and manage.py. Suppress exception in case user has
# already configured their install and/or they're running the script twice.
with suppress(FileExistsError):
    copytree(join(PACKAGING_DIR, "djangoproject"),
             join(INSTALL_ROOT, "djangoproject"))
if not exists(join(INSTALL_ROOT, "manage.py")):
    # We don't care about race condition, just prevent overwriting custom data.
    copy(join(PACKAGING_DIR, "manage.py"), INSTALL_ROOT)

# Copy the userscripts directory. This directory contains helpful python
# scripts that perform somewhat complex actions. The user can invoke any of
# these with a single command, simplifying the workflow. Simple commands,
# such as `python manage.py runserver`, are not wrapped in a script.

# If this project is "built" for a specific platform, then platform-specific
# scripts/executables will serve as user-friendly wrappers to both these python
# python scripts and any relevant simple commands. See PACKAGING_DIR/build.py
# for details on building for a specific platform.

# NOTE: There are currently no userscripts, so this is disabled (the folder is
# not yet tracked due to the lack of scripts, and copying will fail).
# with suppress(FileExistsError):
#     copytree(join(PACKAGING_DIR, "userscripts"),
#              join(INSTALL_ROOT, "userscripts"))


# ##### STAGE 2: DJANGO SETUP ##### #


# Create and execute migrations, collect static files.
for subcommand in ["makemigrations", "migrate", "collectstatic"]:
    run_and_check([sys.executable, "manage.py", subcommand])

# TODO setup initial data, including superuser account.
# NOTE: Probably need a custom management command to do this.
# sys.executable, "manage.py", "createsuperuser", "root"
