"""Startet LocalScribe. Stürzt der Start ab, steht der Grund in %APPDATA%\\LocalScribe\\absturz.log."""
import os
import pathlib
import sys
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    from diktat.app import main
    main()
except SystemExit:
    raise
except BaseException:
    folder = pathlib.Path(os.environ.get("APPDATA", str(pathlib.Path.home()))) / "LocalScribe"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "absturz.log").write_text(traceback.format_exc(), encoding="utf-8")
    raise
