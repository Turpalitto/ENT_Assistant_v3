@echo off
echo ===============================
echo Saving and pushing ENT project
echo ===============================

cd /d %~dp0

git add .
git commit -m "Auto update from this PC"
git push

echo.
echo Done.
pause
