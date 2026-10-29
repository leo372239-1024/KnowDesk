@echo off
cd /d "g:\IT_develop\Agent_projects\KnowDesk3\backend"
.venv314\Scripts\python.exe -m pip install --progress-bar off -r requirements-core.txt > pip_install.log 2>&1
echo DONE_EXIT=%ERRORLEVEL% >> pip_install.log
