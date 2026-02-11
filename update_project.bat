@echo off
echo ===============================
echo Updating ENT Assistant Project
echo ===============================

cd /d %~dp0

git pull

echo.
echo Update complete.
pause
