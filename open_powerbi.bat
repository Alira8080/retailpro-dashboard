@echo off
cd /d "%~dp0"
if not exist _pbip_template (
  git clone --depth 1 https://github.com/Mofaji/Agentic-PBIP-Template.git _pbip_template
)
python build_powerbi_project.py
echo.
echo Откройте файл: RetailPro\RetailPro.pbip
start "" "%~dp0RetailPro\RetailPro.pbip"
pause
