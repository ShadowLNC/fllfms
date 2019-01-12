from contextlib import suppress
import os
import subprocess
import sys
import shutil

# It's assumed that sys.executable is the correct Python.
# That's what the platform-specific wrappers are for.

# Move to the root of the installation. This file is in the app directory.
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
INSTALL_ROOT = os.path.dirname(APP_ROOT)
PACKAGING_ROOT = os.path.join(APP_ROOT, "extras")
os.chdir(INSTALL_ROOT)


# ##### STAGE 1: INSTALL DEPENDENCIES ##### #


# If the wheels directory does not exist, pip will complain, so prevent that.
with suppress(FileExistsError):
    os.mkdir("wheels")

# Install dependencies, no upgrades, and use wheels if available. This means
# there will be no need for network access on a platform-specific build.
subprocess.run([sys.executable, "-m", "pip", "install", "--find-links=wheels",
                "-r", os.path.join(PACKAGING_ROOT, "requirements.txt")])


# ##### STAGE 2: COPY FILES ##### #


# Copy djangoproject folder and manage.py.
shutil.copytree(os.path.join(PACKAGING_ROOT, "djangoproject"),
                os.path.join(INSTALL_ROOT, "djangoproject"))
shutil.copy(os.path.join(PACKAGING_ROOT, "manage.py"), INSTALL_ROOT)

# Copy the userscripts directory. This directory contains helpful python
# scripts that perform somewhat complex actions. The user can invoke any of
# these with a single command, simplifying the workflow. Simple commands,
# such as `python manage.py runserver`, are not wrapped in a script.

# If this project is "built" for a specific platform, then platform-specific
# scripts/executables will serve as user-friendly wrappers to both these python
# python scripts and any relevant simple commands. See packaging/build.py for
# details on building for a specific platform.

# NOTE: There are currently no userscripts, so this is disabled (the folder is
# not yet tracked due to the lack of scripts, and copying will fail).
# shutil.copytree(os.path.join(PACKAGING_ROOT, "userscripts"),
#                 os.path.join(INSTALL_ROOT, "userscripts"))


# ##### STAGE 3: DJANGO SETUP ##### #


# Create and execute migrations, collect static files.
for subcommand in ["makemigrations", "migrate", "collectstatic"]:
    subprocess.run([sys.executable, "manage.py", subcommand])

# TODO setup initial data, including superuser account.
# NOTE: Probably need a custom management command to do this.
# sys.executable, "manage.py", "createsuperuser", "root"
