# Baut die portable Windows-Version: dist\LocalScribe\LocalScribe.exe und dist\LocalScribe-<Version>-windows.zip
# Voraussetzung: uv (https://docs.astral.sh/uv/). Keine Adminrechte nötig.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) { uv venv --python 3.11 .venv }
uv pip install --python .venv\Scripts\python.exe -r requirements.txt pyinstaller
$version = & .venv\Scripts\python.exe -c "import diktat; print(diktat.__version__)"
& .venv\Scripts\python.exe -c "from PySide6 import QtWidgets; from diktat.ui import make_pixmap; a = QtWidgets.QApplication([]); make_pixmap(256).save('build_icon.ico', 'ICO')"
& .venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --name LocalScribe --icon build_icon.ico `
    --add-data "diktat\silero_vad.onnx;diktat" --add-data "diktat\basiswoerterbuch.json;diktat" --add-data "diktat\fachlexikon.json;diktat" --add-data "diktat\bekannt.txt.gz;diktat" --add-data "diktat\lesetexte.json;diktat" `
    --collect-all onnx_asr --collect-all _sounddevice_data --collect-submodules keyring --copy-metadata keyring `
    --hidden-import win32ctypes.core --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 `
    --exclude-module pyarrow --exclude-module tkinter --exclude-module matplotlib --exclude-module PySide6.QtWebEngineCore `
    --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module PySide6.Qt3DCore `
    run.pyw
if ($LASTEXITCODE -ne 0) { throw "PyInstaller ist fehlgeschlagen" }
# PyInstaller greift mitunter zu fremden OpenSSL-DLLs aus dem PATH; die passenden liegen bei Python selbst.
$base = & .venv\Scripts\python.exe -c "import sys; print(sys.base_prefix)"
foreach ($dll in "libcrypto-3-x64.dll", "libssl-3-x64.dll") {
    if (Test-Path "$base\DLLs\$dll") { Copy-Item "$base\DLLs\$dll" "dist\LocalScribe\_internal\$dll" -Force }
}
Copy-Item README.md dist\LocalScribe\LIESMICH.md
Copy-Item LICENSE dist\LocalScribe\LICENSE.txt
Copy-Item THIRD_PARTY.md dist\LocalScribe\THIRD_PARTY.md
$zip = "dist\LocalScribe-$version-windows.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path dist\LocalScribe -DestinationPath $zip
"{0}: {1:N0} MB" -f $zip, ((Get-Item $zip).Length / 1MB)
"$((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower())  $(Split-Path $zip -Leaf)" | Set-Content dist\SHA256SUMS.txt -Encoding ascii
Get-Content dist\SHA256SUMS.txt
