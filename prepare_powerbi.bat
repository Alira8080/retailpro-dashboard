@echo off
cd /d "%~dp0"
if not exist sales.csv python generate_sample_data.py
python prepare_retailpro_data.py --input sales.csv --powerbi-dir powerbi_data
echo.
echo Готово. Откройте Power BI Desktop и загрузите файлы из папки powerbi_data
echo Инструкция: power_bi_visuals.txt
pause
