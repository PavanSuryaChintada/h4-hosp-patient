@echo off
rem One-click demo on Windows: build the web app, start the ward server on an empty ward and
rem open the sign-in page. Previous ward records are moved to data\ward\archive\, not deleted.
rem Add --keep to carry on with the ward as it was:  demo.cmd --keep
cd /d "%~dp0"

set PY=python
if exist .venv\Scripts\python.exe set PY=.venv\Scripts\python.exe

where npm >nul 2>nul
if %errorlevel%==0 (
  pushd ui
  if not exist node_modules call npm ci
  call npm run build
  popd
) else (
  echo npm not found: serving the last build in ui\dist
)

if "%1"=="--keep" (
  %PY% tools\serve_ui.py --open
) else (
  %PY% tools\serve_ui.py --fresh --open
)
