"""Startet LocalScribe. Stürzt der Start ab, steht der Grund in %LOCALAPPDATA%\\LocalScribe\\absturz.log."""
import os
import pathlib
import sys
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    from diktat import __version__, ort
    if ort.handover(__version__):      # eine neuere Fassung ist eingerichtet: sie übernimmt
        sys.exit(0)
    from diktat.app import main
    main()
except SystemExit:
    raise
except BaseException:
    import tempfile
    text = traceback.format_exc()
    for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA"), tempfile.gettempdir()):
        try:
            folder = pathlib.Path(base) / "LocalScribe"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "absturz.log").write_text(text, encoding="utf-8")
            break
        except (OSError, TypeError):
            continue
    raise
