"""Handy als Mikrofon: Das Telefon nimmt auf, der Rechner erkennt und fügt ein.

LocalScribe öffnet dafür einen kleinen Webserver im eigenen Netz. Das Telefon ruft die Seite über einen QR-Code auf,
nimmt im Browser auf und schickt den Ton nach dem Stopp an den Rechner. Erkannt wird wie bei jedem Diktat lokal;
der Ton verlässt das eigene Netz nicht und wird nicht gespeichert.

Browser geben das Mikrofon nur auf verschlüsselten Seiten frei. Der Server erzeugt sich deshalb beim ersten Start
ein eigenes Zertifikat; das Telefon zeigt dafür einmal eine Warnung, die man bestätigt. Ohne das geheime Kürzel
aus dem QR-Code nimmt der Server nichts an.
"""
import datetime
import hmac
import io
import ipaddress
import json
import logging
import socket
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

from . import config

log = logging.getLogger("diktat")
PORT = 8765
RATE = 16000
LIMIT = RATE * 2 * 60 * 15          # höchstens 15 Minuten je Aufnahme (16 kHz, 16 Bit, mono)


def addresses():
    """IPv4-Adressen dieses Rechners im lokalen Netz, die wahrscheinlichste zuerst."""
    found = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))                     # sendet nichts; verrät nur die Adresse des Standardwegs
            found.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in found:
                found.append(ip)
    except OSError:
        pass
    return [ip for ip in found if not ip.startswith(("127.", "169.254."))]


def _certificate(folder: Path, ips):
    """Eigenes Zertifikat für die Adressen dieses Rechners; neu, wenn sich die Adressen geändert haben."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    folder.mkdir(parents=True, exist_ok=True)
    cert, key, note = folder / "cert.pem", folder / "key.pem", folder / "adressen.json"
    try:
        if cert.exists() and key.exists() and json.loads(note.read_text()) == sorted(ips):
            return cert, key
    except Exception:
        pass
    private = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "LocalScribe")])
    now = datetime.datetime.now(datetime.timezone.utc)
    names = [x509.DNSName("localhost")] + [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips]
    made = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(private.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1)).not_valid_after(now + datetime.timedelta(days=397))
            .add_extension(x509.SubjectAlternativeName(names), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(private, hashes.SHA256()))
    key.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    cert.write_bytes(made.public_bytes(serialization.Encoding.PEM))
    note.write_text(json.dumps(sorted(ips)))
    return cert, key


def qr_png(text: str, scale: int = 7) -> bytes:
    import segno
    out = io.BytesIO()
    segno.make(text, error="m").save(out, kind="png", scale=scale, border=2)
    return out.getvalue()


def decode(body: bytes):
    """Rohton vom Telefon (16 kHz, 16 Bit, mono) als Fließkomma zwischen -1 und 1."""
    return np.frombuffer(body[: len(body) // 2 * 2], dtype="<i2").astype(np.float32) / 32768


PAGE = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>LocalScribe Mikrofon</title><style>
html,body{height:100%;margin:0;background:#0e1116;color:#e8eaed;font:17px/1.4 system-ui,sans-serif}
body{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:26px;padding:24px;box-sizing:border-box;text-align:center}
button{width:210px;height:210px;border-radius:50%;border:0;background:#2f6fed;color:#fff;font:600 21px system-ui;
 -webkit-tap-highlight-color:transparent;touch-action:manipulation}
button.on{background:#d93025;animation:p 1.2s infinite}button:disabled{background:#444}
@keyframes p{50%{box-shadow:0 0 0 18px rgba(217,48,37,.25)}}
#s{min-height:3em;max-width:22em}#t{font-variant-numeric:tabular-nums;color:#9aa0a6}small{color:#9aa0a6;max-width:24em}
</style></head><body>
<div><b>LocalScribe</b><br><small>Dieses Telefon ist das Mikrofon. Der Text erscheint am Rechner.</small></div>
<button id="b">Aufnehmen</button><div id="t">0:00</div><div id="s">Tippen, sprechen, noch einmal tippen.</div>
<script>
const K=new URLSearchParams(location.search).get("k"),b=document.getElementById("b"),s=document.getElementById("s"),t=document.getElementById("t");
let ctx,src,node,stream,chunks=[],on=false,t0=0,tick,lock=null;
function say(x){s.textContent=x}
async function start(){
  try{stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:false,noiseSuppression:false,autoGainControl:true}})}
  catch(e){say("Kein Zugriff auf das Mikrofon. Im Browser erlauben und noch einmal tippen.");return}
  ctx=new (window.AudioContext||window.webkitAudioContext)();src=ctx.createMediaStreamSource(stream);
  node=ctx.createScriptProcessor(4096,1,1);chunks=[];
  node.onaudioprocess=e=>{if(on)chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)))};
  src.connect(node);node.connect(ctx.destination);on=true;t0=Date.now();
  b.className="on";b.textContent="Stopp";say("Aufnahme läuft …");
  tick=setInterval(()=>{const n=Math.floor((Date.now()-t0)/1000);t.textContent=Math.floor(n/60)+":"+String(n%60).padStart(2,"0")},250);
  try{lock=await navigator.wakeLock.request("screen")}catch(e){}
}
function pcm(){
  let n=0;for(const c of chunks)n+=c.length;const a=new Float32Array(n);let o=0;for(const c of chunks){a.set(c,o);o+=c.length}
  const r=ctx.sampleRate/16000,m=Math.floor(n/r),out=new Int16Array(m);
  for(let i=0;i<m;i++){const x=Math.floor(i*r),y=Math.min(n,Math.floor((i+1)*r));let v=0;for(let j=x;j<y;j++)v+=a[j];
    v=Math.max(-1,Math.min(1,v/Math.max(1,y-x)));out[i]=v*32767}
  return out.buffer;
}
async function stop(){
  on=false;clearInterval(tick);b.className="";b.disabled=true;b.textContent="Sende …";
  const body=pcm();stream.getTracks().forEach(x=>x.stop());node.disconnect();src.disconnect();ctx.close();if(lock){lock.release();lock=null}
  try{const r=await fetch("/audio?k="+encodeURIComponent(K),{method:"POST",body});const j=await r.json();
    say(j.ok?"Gesendet. Der Text erscheint am Rechner.":j.error)}
  catch(e){say("Der Rechner ist nicht erreichbar. Läuft LocalScribe, und sind beide im selben WLAN?")}
  b.disabled=false;b.textContent="Aufnehmen";
}
b.onclick=()=>on?stop():start();
if(!navigator.mediaDevices)say("Dieser Browser gibt das Mikrofon hier nicht frei.");
</script></body></html>"""


class Server:
    """Nimmt Aufnahmen vom Telefon an und reicht sie an on_audio(Ton) weiter. on_audio darf ablehnen (Text)."""

    def __init__(self, on_audio, token: str, port: int = PORT, folder: Path = None):
        self.on_audio, self.token, self.port = on_audio, token, int(port or PORT)
        self.folder = folder or (config.DIR / "handy")
        self.httpd = None
        self.ips = addresses()

    def url(self) -> str:
        return f"https://{self.ips[0] if self.ips else 'localhost'}:{self.port}/?k={self.token}"

    def start(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _allowed(self) -> bool:
                given = (parse_qs(urlparse(self.path).query).get("k") or [""])[0]
                return bool(outer.token) and hmac.compare_digest(given.encode(), outer.token.encode())

            def _send(self, code, body: bytes, kind):
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code, **data):
                self._send(code, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

            def do_GET(self):
                if urlparse(self.path).path != "/" or not self._allowed():
                    return self._send(403, "Bitte den QR-Code aus LocalScribe scannen.".encode(), "text/plain; charset=utf-8")
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")

            def do_POST(self):
                if urlparse(self.path).path != "/audio" or not self._allowed():
                    return self._json(403, ok=False, error="Nicht erlaubt. Den QR-Code neu scannen.")
                size = int(self.headers.get("Content-Length") or 0)
                if not 0 < size <= LIMIT:
                    return self._json(413, ok=False, error="Aufnahme leer oder länger als 15 Minuten.")
                try:
                    refused = outer.on_audio(decode(self.rfile.read(size)))
                except Exception:
                    log.exception("Aufnahme vom Telefon nicht annehmbar")
                    refused = "Der Rechner konnte die Aufnahme nicht annehmen."
                self._json(200, ok=not refused, error=refused or "")

        cert, key = _certificate(self.folder, self.ips)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cert), str(key))
        self.httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        self.httpd.daemon_threads = True
        self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="handy").start()
        log.info("Handy-Mikrofon bereit auf Port %s", self.port)

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                log.debug("Handy-Server nicht sauber beendet", exc_info=True)
            self.httpd = None
