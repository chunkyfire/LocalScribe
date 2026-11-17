# Baut die portable Windows-Version: dist\LocalScribe\LocalScribe.exe, dist\LocalScribe-<Version>-windows.zip und,
# wenn das Sprachmodell auf diesem Rechner liegt, das Komplettpaket dist\LocalScribe-<Version>-windows-komplett.zip
# Voraussetzung: uv (https://docs.astral.sh/uv/). Keine Adminrechte nötig.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) { uv venv --python 3.11 .venv }
uv pip install --python .venv\Scripts\python.exe -r requirements.txt pyinstaller
$version = & .venv\Scripts\python.exe -c "import diktat; print(diktat.__version__)"
& .venv\Scripts\python.exe -c "from PySide6 import QtWidgets; from diktat.ui import make_pixmap; a = QtWidgets.QApplication([]); make_pixmap(256).save('build_icon.ico', 'ICO')"
& .venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --name LocalScribe --icon build_icon.ico `
    --add-data "diktat\silero_vad.onnx;diktat" --add-data "diktat\segmentierung.onnx;diktat" --add-data "diktat\basiswoerterbuch.json;diktat" --add-data "diktat\fachlexikon.json;diktat" --add-data "diktat\bekannt.txt.gz;diktat" --add-data "diktat\lesetexte.json;diktat" `
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
# Schlank halten: Qt-Teile, die eine Fenster-App ohne 3D, Web und PDF nicht braucht (QtNetwork bleibt: die App prüft damit, ob sie schon läuft), und der
# Xet-Lader von Hugging Face (abgeschaltet, siehe diktat/modelle.py). Spart rund 50 MB.
$qt = "dist\LocalScribe\_internal\PySide6"
foreach ($item in "opengl32sw.dll", "Qt6Quick*.dll", "Qt6Qml*.dll", "Qt6Pdf.dll", "Qt6VirtualKeyboard.dll",
                  "Qt6OpenGL.dll", "translations", "plugins\imageformats\qpdf.dll",
                  "plugins\imageformats\qtiff.dll", "plugins\imageformats\qwebp.dll", "plugins\platforminputcontexts",
                  "plugins\networkinformation", "plugins\generic") {
    Get-ChildItem "$qt\$item" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
}
Remove-Item "dist\LocalScribe\_internal\hf_xet" -Recurse -Force -ErrorAction SilentlyContinue
# Im Programmordner nur Dateien, die jeder öffnen kann: Text und PDF, kein Markdown.
Copy-Item LIESMICH.txt dist\LocalScribe\LIESMICH.txt
Copy-Item LICENSE dist\LocalScribe\LICENSE.txt
Copy-Item THIRD_PARTY.md dist\LocalScribe\THIRD_PARTY.txt
Copy-Item docs\LocalScribe-Handbuch.pdf dist\LocalScribe\LocalScribe-Handbuch.pdf
$zip = "dist\LocalScribe-$version-windows.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path dist\LocalScribe -DestinationPath $zip
$zips = @($zip)
# Komplettpaket: dasselbe mit dem Sprachmodell im Ordner modelle (für Netze, die den Download sperren)
# und dem Stimmmodell für „Sprecher trennen“ (26 MB)
$name = & .venv\Scripts\python.exe -c "from diktat import config; print(config.MODELS['de']['release']['name'])"
$model = "$env:LOCALAPPDATA\LocalScribe\modelle\$name"
$voice = & .venv\Scripts\python.exe -c "from diktat import modelle, sprecher; from pathlib import Path; print(Path(sprecher.prepare()).parent)"
if ((Test-Path "$model\.vollstaendig") -and $voice -like "*\LocalScribe\modelle\*") {
    New-Item -ItemType Directory dist\LocalScribe\modelle -Force | Out-Null
    Copy-Item $model dist\LocalScribe\modelle -Recurse -Force
    Copy-Item $voice dist\LocalScribe\modelle -Recurse -Force
    $full = "dist\LocalScribe-$version-windows-komplett.zip"
    if (Test-Path $full) { Remove-Item $full }
    tar.exe -a -c -f $full -C dist LocalScribe          # Compress-Archive schafft keine 2 GB und ist hier sehr langsam
    if ($LASTEXITCODE -ne 0) { throw "Komplettpaket: Packen fehlgeschlagen" }
    Remove-Item dist\LocalScribe\modelle -Recurse -Force
    $zips += $full
} else { throw "Sprachmodell (${model}) oder Stimmmodell (${voice}) liegt nicht unter LOCALAPPDATA - kein Komplettpaket" }
$zips | ForEach-Object { "{0}: {1:N0} MB" -f $_, ((Get-Item $_).Length / 1MB) }
$zips | ForEach-Object { "$((Get-FileHash $_ -Algorithm SHA256).Hash.ToLower())  $(Split-Path $_ -Leaf)" } | Set-Content dist\SHA256SUMS.txt -Encoding ascii
Get-Content dist\SHA256SUMS.txt
