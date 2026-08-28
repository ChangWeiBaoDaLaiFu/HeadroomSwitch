@echo off
rem Build HeadroomSwitch.exe (single file, no console) - requires Python 3.10+
python -m pip install -r requirements.txt pyinstaller
python make_icon.py
python fetch_icons.py || echo "icon fetch skipped (offline) - letter avatars will be used"
python -m PyInstaller --noconfirm --onefile --windowed --name HeadroomSwitch ^
  --icon icon.ico --add-data "icon.ico;." --add-data "icons.json;." ^
  --hidden-import webview.platforms.winforms ^
  --hidden-import webview.platforms.edgechromium ^
  --hidden-import pystray --hidden-import pystray._win32 ^
  --collect-submodules pystray ^
  app.py
echo Done: dist\HeadroomSwitch.exe
