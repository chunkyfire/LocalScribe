"""KI-Anbindung gegen einen lokalen Attrappen-Server prüfen (kein echtes Modell nötig)."""
import json
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from diktat import llm

seen = {}


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        seen["auth"] = self.headers.get("Authorization")
        if self.headers.get("Authorization") == "Bearer falsch":
            return self._send(401, {"error": "invalid api key"})
        self._send(200, {"data": [{"id": "modell-b"}, {"id": "modell-a"}]})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen["req"] = req
        user = req["messages"][1]["content"]
        reply = {"leer": "", "denkt": "<think>hm, mal sehen</think>\n Fertig. "}.get(user, "BEARBEITET: " + user)
        self._send(200, {"choices": [{"message": {"content": reply}}]})


server = HTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=server.serve_forever, daemon=True).start()
cfg = {"base_url": f"http://127.0.0.1:{server.server_port}/v1/", "model": "modell-a", "temperature": 0.2, "timeout": 5}


def check(name, ok):
    print("OK  " if ok else "FAIL", name)
    if not ok:
        sys.exit(1)


def fails(fn, part):
    try:
        fn()
    except llm.LlmError as e:
        return part in str(e)
    return False


check("Modelle sortiert", llm.list_models(cfg, key="") == ["modell-a", "modell-b"])
check("ohne Schlüssel kein Authorization-Kopf", seen["auth"] is None)
llm.list_models(cfg, key="geheim")
check("Schlüssel als Bearer", seen["auth"] == "Bearer geheim")
check("falscher Schlüssel -> 401 verständlich", fails(lambda: llm.list_models(cfg, key="falsch"), "401"))
out = llm.run(cfg, "Mach es kürzer.", "  Hallo Welt  ", key="")
check("Antwort kommt zurück", out == "BEARBEITET: Hallo Welt")
msgs = seen["req"]["messages"]
check("Anweisung im Systemtext, Transkript getrennt",
      msgs[0]["role"] == "system" and msgs[0]["content"].endswith("Mach es kürzer.") and msgs[1]["content"] == "Hallo Welt")
check("Modell und Temperatur übergeben", seen["req"]["model"] == "modell-a" and seen["req"]["temperature"] == 0.2)
check("Denkblock entfernt", llm.run(cfg, "x", "denkt", key="") == "Fertig.")
check("leere Antwort -> Fehler", fails(lambda: llm.run(cfg, "x", "leer", key=""), "keinen Text"))
check("ohne Modell -> Fehler", fails(lambda: llm.run({**cfg, "model": ""}, "x", "y", key=""), "Kein Modell"))
check("Server aus -> Fehler", fails(lambda: llm.run({**cfg, "base_url": "http://127.0.0.1:9/v1"}, "x", "y", key=""), "nicht erreichbar"))
check("Adresse ohne http -> Fehler", fails(lambda: llm.run({**cfg, "base_url": "localhost:1"}, "x", "y", key=""), "http"))
check("lokal erkannt", llm._is_local("http://localhost:1/v1") and llm._is_local("http://192.168.1.5/v1")
      and not llm._is_local("https://api.example.com/v1"))
