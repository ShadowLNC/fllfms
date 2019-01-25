@echo off
pushd %~dp0
call localpython.bat -m fllfms.userscripts.django restoredefaultuser
popd
