@echo off
pushd %~dp0
call python.bat -m fllfms.djangoproject restoredefaultuser
popd
