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
        seen["posts"] = seen.get("posts", 0) + 1
        if seen.get("strict") and "reasoning_effort" in req:
            return self._send(400, {"error": "Unknown parameter: reasoning_effort"})
        user = req["messages"][1]["content"]
        if user in ("ohne", "ohne-inhalt", "teile", "kaputt"):        # so antworten manche Server wirklich
            return self._send(200, {"ohne": {"choices": [{"finish_reason": "stop", "index": 0}]},
                                    "ohne-inhalt": {"choices": [{"message": {"role": "assistant"}}]},
                                    "teile": {"choices": [{"message": {"content": [{"type": "text", "text": "Teil A"}]}}]},
                                    "kaputt": {"error": "x"}}[user])
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
check("leere Antwort -> Fehler", fails(lambda: llm.run(cfg, "x", "leer", key=""), "nichts geschrieben"))
check("Antwort ohne message (Noirdoc, Gemini schreibt nichts) ist eine leere Antwort, kein Formatfehler",
      fails(lambda: llm.run(cfg, "x", "ohne", key=""), "nichts geschrieben")
      and fails(lambda: llm.run(cfg, "x", "ohne-inhalt", key=""), "nichts geschrieben")
      and llm.chat(cfg, "x", "ohne", key="") == "")
check("Inhalt in Teilen wird zusammengesetzt", llm.run(cfg, "x", "teile", key="") == "Teil A")
check("Hinweiszeilen am Ende gehören nicht zum Eintrag",
      llm.split("S:\n- gut\n\nZusätzlich dokumentieren: Sturzprotokoll\nNicht diktiert: Befund, Plan\n")
      == ("S:\n- gut", "Zusätzlich dokumentieren: Sturzprotokoll\nNicht diktiert: Befund, Plan")
      and llm.split("Nur Text") == ("Nur Text", "") and llm.split("A: Nicht diktiert: mitten\nP: x")[1] == ""
      and llm.split("") == ("", ""))
check("Antwort ohne choices bleibt ein Formatfehler", fails(lambda: llm.run(cfg, "x", "kaputt", key=""), "unerwartetes Format"))
check("ohne Modell -> Fehler", fails(lambda: llm.run({**cfg, "model": ""}, "x", "y", key=""), "Kein Modell"))
check("Server aus -> Fehler", fails(lambda: llm.run({**cfg, "base_url": "http://127.0.0.1:9/v1"}, "x", "y", key=""), "nicht erreichbar"))
check("Adresse ohne http -> Fehler", fails(lambda: llm.run({**cfg, "base_url": "localhost:1"}, "x", "y", key=""), "http"))
check("lokal erkannt", llm._is_local("http://localhost:1/v1") and llm._is_local("http://192.168.1.5/v1")
      and not llm._is_local("https://api.example.com/v1"))

# Denkaufwand: der Zusatz @low hinter dem Modellnamen
seen["posts"] = 0
llm.run({**cfg, "model": "modell-a@low"}, "x", "y", key="")
check("@low: Modellname ohne Zusatz, Denkaufwand in der Schreibweise der OpenAI-Schnittstelle",
      seen["req"]["model"] == "modell-a" and seen["req"].get("reasoning_effort") == "low" and seen["posts"] == 1)
body = llm._body({"base_url": "https://openrouter.ai/api/v1", "model": "google/gemini-4-hydrogen@low"}, [])
check("OpenRouter bekommt den Denkaufwand in seiner eigenen Schreibweise",
      body["model"] == "google/gemini-4-hydrogen" and body.get("reasoning") == {"effort": "low"} and "reasoning_effort" not in body)
seen.update(strict=True, posts=0)
out = llm.run({**cfg, "model": "modell-a@low"}, "x", "Hallo", key="")
check("Lehnt ein Server den Denkaufwand ab, geht die Anfrage einmal ohne ihn hinaus",
      out == "BEARBEITET: Hallo" and seen["posts"] == 2 and "reasoning_effort" not in seen["req"])
seen["strict"] = False

# kurze Liste, schnelles Modell, Noirdoc
noirdoc = {"base_url": "https://api.noirdoc.de/v1", "model": "gemini-4-hydrogen@low"}
check("Kurze Liste: bei Noirdoc und OpenRouter Gemini 4 Hydrogen mit wenig Nachdenken zuerst, sonst keine",
      llm.picks(noirdoc["base_url"])[0][0] == "gemini-4-hydrogen@low"
      and llm.picks("https://openrouter.ai/api/v1")[0][0] == "google/gemini-4-hydrogen@low"
      and llm.picks("http://localhost:11434/v1") == () and llm.picks("https://api.noirdoc.de.example.com/v1") == ())
check("Fachkorrektur: schnelles Modell des Anbieters, bei unbekannten Servern das gewählte",
      llm.quick(noirdoc)["model"] == "gemini-3.1-flash-lite" and llm.quick(cfg)["model"] == "modell-a"
      and llm.quick({**noirdoc, "model": ""})["model"] == "")
check("Kein Eintrag der kurzen Liste von Noirdoc stammt von einem gesperrten Anbieter",
      not any(llm.refused(noirdoc, m) for m, _ in llm.picks(noirdoc["base_url"])) and not llm.refused(noirdoc, llm.quick(noirdoc)["model"]))
check("Ohne Preisliste gelten die mitgelieferten Namen", llm.refused(noirdoc, "google/gemma-4-31B-it")
      and llm.refused(noirdoc, "zai-org/GLM-5.2@low") and not llm.refused(noirdoc, "gemini-4-hydrogen")
      and not llm.refused(cfg, "google/gemma-4-31B-it"))
real, calls = llm._request, []
PRICES = {"data": [
    {"public_id": "gemini-4-hydrogen", "legacy_public_id": None, "provider_slug": "google", "endpoint_family": "chat"},
    {"public_id": "Neu/Modell-X", "legacy_public_id": "modell-x", "provider_slug": "regolo", "endpoint_family": "chat"},
    {"public_id": "Neu/Modell-X", "legacy_public_id": "modell-x-de", "provider_slug": "ionos", "endpoint_family": "chat"},
    {"public_id": "bild-1", "legacy_public_id": None, "provider_slug": "ionos", "endpoint_family": "image_gen"},
    {"public_id": "beides", "legacy_public_id": None, "provider_slug": "ionos", "endpoint_family": "embeddings"},
    {"public_id": "beides", "legacy_public_id": None, "provider_slug": "weber", "endpoint_family": "chat"}]}


def fake_request(server, path, body=None, key=None):
    calls.append((path, key))
    if path == "/prices":
        return PRICES
    return {"data": [{"id": i} for i in ("gemini-4-hydrogen", "Neu/Modell-X", "modell-x", "modell-x-de", "bild-1", "beides",
                                         "google/gemma-4-31B-it", "eigenes-byok")]}


llm._request = fake_request
check("Noirdoc: die Liste lässt Modelle gesperrter Anbieter und alles außer Chat weg",
      llm.list_models(noirdoc, key="px") == ["beides", "eigenes-byok", "gemini-4-hydrogen", "modell-x-de"]
      and ("/prices", "") in calls)
check("Die Preisliste wird ohne Schlüssel und nur einmal geholt",
      llm.list_models(noirdoc, key="px") and [c for c in calls if c[0] == "/prices"] == [("/prices", "")])
check("Danach gilt die Sperre auch für neu gemeldete Modelle", llm.refused(noirdoc, "Neu/Modell-X") and not llm.refused(noirdoc, "modell-x-de"))
llm._request = real
