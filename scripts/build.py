"""
This script will create a "build" (zip file) for your current environment
(operating system, architecture, and Python version), including everything
needed for offline setup.

To create a build, you will need the following:
    -   An internet connection (or cached copies of dependencies)
    -   A C++ compiler (dependencies require it)
    -   `git` on your PATH environment variable
    -   A copy of Python which will be embedded in the build (see more below)

For the embedded copy of Python, ensure the following:
    -   It must exist in a subdirectory called `python`
    -   The subdirectory must exist in the same directory as this file
    -   The copy must be self contained (not require anything outside itself)

    -   The Python version must be the same as your current environment
        (Due to bytecode and compiled dependencies)
    -   Sqlite must be version 3.26+ (on Windows, you can just replace the DLL)
        (This should be fixed in Python 3.7.3, see Python bug #35360.)
    -   If a ._pth file is present, it must `import site` to allow .pth files
        (Required to enable pywin32 and zope.interface .pth files.)

It will be copied to a directory named `lib` in the build root.
Packages will be preinstalled to the copy of the `lib` directory.

Platform scripts (wrappers to Python scripts and common Django commands, etc.)
will also be placed in the build root (if provided for the target platform).
"""

from contextlib import suppress
# import glob
import os
from os.path import abspath, basename, dirname, isdir, join
import sys
from shutil import copy, copytree, make_archive, rmtree
import subprocess


# Unfortunately we use a lot of directories when building. What can you do?
APP_ROOT = dirname(dirname(abspath(__file__)))
APP_PARENT = dirname(APP_ROOT)
BUILD_DIR = join(APP_ROOT, "build")
PYTHON_BUNDLE = join(APP_ROOT, "python")

# Build subdirectories are used as "clean copies" when referencing files.
BUILD_PYTHON = join(BUILD_DIR, "lib")
BUILD_APP_ROOT = join(BUILD_PYTHON, basename(APP_ROOT))


def run_and_check(*args, **kwargs):
    # Run a subprocess, raising an exception if it exits with nonzero status.
    proc = subprocess.run(*args, **kwargs)
    proc.check_returncode()
    return proc


# Clean previous builds.
with suppress(FileNotFoundError):
    rmtree(BUILD_DIR)
os.makedirs(BUILD_DIR)

copytree(PYTHON_BUNDLE, BUILD_PYTHON)  # Include Python.

# Copy the repository for a clean slate (HEAD plus staged changes).
# No point cloning, and archive requires unpacking. Must occur after Python
# is copied, since we live in the Python bundle (simplifies PYTHONPATH).
# WARNING: Must add "" to target path for trailing separator. See git docs.
os.makedirs(BUILD_APP_ROOT)  # Since git checkout-index doesn't create.
run_and_check(["git", "-C", APP_ROOT, "checkout-index", "-a", "-f",
               "--prefix=" + join(BUILD_APP_ROOT, "")])

# Now install dependencies. (We use the Python root to simplify PYTHONPATH).
# Vendor packages can't be zipped as some packages may not be zip_safe.
# Leaving dist-infos in place as they contain licences which may need to remain
# according to the licence terms. Size increase is negligible.
requirements = join(BUILD_APP_ROOT, "requirements.txt")
run_and_check([sys.executable, "-m", "pip", "install", "-r", requirements,
               "--compile", "--target", BUILD_PYTHON])

# We use the embedded Python executable (not sys.executable) for running setup
# scripts, this way the correct paths are set. If we can't find it,
# run_and_check (subprocess) raises FileNotFoundError. Can't be used to install
# packages as the embedded copy doesn't have pip (on Windows at least).
executable = join(BUILD_PYTHON, {
    'win32': 'python.exe',
}.get(sys.platform, 'python'))

# Setup the Django environment, so the user doesn't have to.
# Generates some __pycache__ directories (negligible size increase).
run_and_check([executable, "-m", "fllfms.djangoproject", "firsttimerun"])
os.remove(join(BUILD_PYTHON, ".secret_key"))  # Regenerates when user runs.

# Platform-specific subdirectories house system-native scripts or executables
# that serve as wrappers, so the user can simply double-click to run.
# If a platform-specific subdirectory exists, its contents are copied into
# BUILD_DIR, otheriwse, users can still invoke Python from the command line.
platform = os.name
if platform:
    platform_path = join(BUILD_APP_ROOT, "scripts", "platforms", platform)

    if isdir(platform_path):
        for entry in os.scandir(platform_path):
            # Use the correct copy function based on file/directory.
            # If neither then it won't be copied.
            if entry.is_file():
                copy(entry.path, BUILD_DIR)
            elif entry.is_dir():
                copytree(entry.path, join(BUILD_DIR, entry.name))

# Finally, zip the folder for distribution. We are not using a container
# directory (e.g. file.zip/folder/all_files), so no base_dir is supplied.
make_archive(join(APP_PARENT, "FLLFMS"), "zip", BUILD_DIR)
