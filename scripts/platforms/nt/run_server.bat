@echo off
pushd %~dp0
call python.bat -m fllfms.scripts.django runserver
popd
