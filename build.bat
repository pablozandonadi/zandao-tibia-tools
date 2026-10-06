@echo off
rem Gera "Zandao Tibia Tools.exe" nesta pasta (precisa de Python + PyInstaller + pywebview).
rem A pasta web/ e o icone vao dentro do exe; data/ e os .json ficam do lado (editaveis).
cd /d "%~dp0"
python -m unittest || (echo Testes falharam, exe nao gerado. & pause & exit /b 1)
python -m PyInstaller --noconfirm --onefile --windowed --name "Zandao Tibia Tools" ^
  --icon "%~dp0icon.ico" --add-data "%~dp0web;web" --add-data "%~dp0icon.ico;." ^
  --distpath "%~dp0." --workpath "%TEMP%\zandao-tibia-tools-build" --specpath "%TEMP%\zandao-tibia-tools-build" ^
  zandao_tibia_tools.py
pause
