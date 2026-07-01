@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === RetailPro: сборка пакета для заказчика ===
python prepare_retailpro_data.py --input sales.csv
python build_powerbi_project.py
python test_all.py
if errorlevel 1 (
  echo Тесты не пройдены. Пакет не собран.
  pause
  exit /b 1
)
powershell -NoProfile -Command ^
  "$root = Get-Location; $out = Join-Path $root 'RetailPro_Delivery';" ^
  "if (Test-Path $out) { Remove-Item $out -Recurse -Force };" ^
  "New-Item -ItemType Directory -Path $out | Out-Null;" ^
  "$items = @('prepare_retailpro_data.py','build_powerbi_project.py','role_access.py','dax_measures.txt','power_bi_visuals.txt','requirements.txt','prepare_powerbi.bat','open_powerbi.bat','start_dashboard.bat','dashboard.py','test_all.py');" ^
  "foreach ($i in $items) { Copy-Item $i (Join-Path $out $i) };" ^
  "Copy-Item powerbi_data $out\powerbi_data -Recurse;" ^
  "Copy-Item RetailPro $out\RetailPro -Recurse;" ^
  "Copy-Item ИНСТРУКЦИЯ_ЗАКАЗЧИКУ.txt $out\;" ^
  "if (Test-Path sales.csv) { New-Item (Join-Path $out 'data') -ItemType Directory | Out-Null; Copy-Item sales.csv (Join-Path $out 'data\sales.csv') };" ^
  "$zip = Join-Path $root 'RetailPro_Delivery.zip';" ^
  "if (Test-Path $zip) { Remove-Item $zip -Force };" ^
  "Compress-Archive -Path $out\* -DestinationPath $zip -Force;" ^
  "Write-Host ''; Write-Host 'Готово:' $zip"
pause
