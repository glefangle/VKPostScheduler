@echo off
setlocal ENABLEDELAYEDEXPANSION

cd /d %~dp0

if not exist venv (
  echo Creating virtual environment...
  py -3 -m venv venv
)

call venv\Scripts\activate

python -m pip install --upgrade pip
python -m pip install -e .

python -m vkpostscheduler

endlocal
