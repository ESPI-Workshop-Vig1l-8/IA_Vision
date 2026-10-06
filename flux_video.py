"""
Flux MJPEG des images analysées, pour le dashboard.

    GET /vision/stream.mjpg?token=<jeton API>   flux vidéo (multipart/x-mixed-replace)
    GET /vision/health                          {"clients": n}, sans jeton

Le jeton (opérateur ou service) est vérifié auprès du backend (GET /api/v1/session) :
sans clé d'accès, la caméra n'est pas visible, même en accédant directement au port.
Les images ne sont encodées en JPEG que si quelqu'un regarde le flux.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2
import requests

CLIENTS_MAX = 4
CACHE_JETON_S = 60


class FluxVideo:
    def __init__(self, port, url_backend, qualite=70, fps_max=15):
        self.port = port
        self.url_backend = url_backend.rstrip("/")
        self.qualite = qualite
        self.intervalle = 1.0 / fps_max
        self.clients = 0
        self._jpeg = None
        self._numero = 0
        self._condition = threading.Condition()
        self._jetons = {}  # jeton -> heure de validation
        self._serveur = None

    # --- côté détection -------------------------------------------------------

    def publier(self, image):
        """Appelé à chaque image traitée ; n'encode que si un client regarde."""
        if not self.clients:
            return
        ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, self.qualite])
        if not ok:
            return
        with self._condition:
            self._jpeg = jpeg.tobytes()
            self._numero += 1
            self._condition.notify_all()

    def demarrer(self):
        flux = self

        class Gestionnaire(BaseHTTPRequestHandler):
            timeout = 10  # un client qui ne lit plus ne bloque pas un thread indéfiniment

            def do_GET(self):
                url = urlparse(self.path)
                if url.path == "/vision/health":
                    self._json(200, {"clients": flux.clients})
                elif url.path == "/vision/stream.mjpg":
                    jeton = parse_qs(url.query).get("token", [""])[0]
                    if not flux.jeton_valide(jeton):
                        self._json(401, {"error": "missing or invalid token"})
                    elif flux.clients >= CLIENTS_MAX:
                        self._json(503, {"error": "too many viewers"})
                    else:
                        flux.diffuser(self)
                else:
                    self._json(404, {"error": "not found"})

            def _json(self, code, corps):
                donnees = json.dumps(corps).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(donnees)))
                self.end_headers()
                self.wfile.write(donnees)

            def log_message(self, format, *args):
                # chemin sans la requête : le jeton ne doit pas apparaître dans les logs
                print(f"[FLUX] {self.address_string()} {urlparse(self.path).path} {args[1] if len(args) > 1 else ''}")

        self._serveur = ThreadingHTTPServer(("0.0.0.0", self.port), Gestionnaire)
        self._serveur.daemon_threads = True
        threading.Thread(target=self._serveur.serve_forever, daemon=True).start()
        print(f"[FLUX] Flux vidéo sur http://0.0.0.0:{self.port}/vision/stream.mjpg (jeton requis)")

    def arreter(self):
        if self._serveur:
            self._serveur.shutdown()

    # --- côté HTTP ------------------------------------------------------------

    def jeton_valide(self, jeton):
        if not jeton or len(jeton) > 256:
            return False
        valide_depuis = self._jetons.get(jeton)
        if valide_depuis and time.time() - valide_depuis < CACHE_JETON_S:
            return True
        try:
            reponse = requests.get(f"{self.url_backend}/api/v1/session",
                                   headers={"Authorization": f"Bearer {jeton}"}, timeout=3)
        except requests.RequestException:
            print(f"[FLUX] Backend injoignable ({self.url_backend}) : jeton non vérifiable")
            return False
        if reponse.status_code == 200:
            self._jetons[jeton] = time.time()
            return True
        self._jetons.pop(jeton, None)
        return False

    def diffuser(self, gestionnaire):
        gestionnaire.send_response(200)
        gestionnaire.send_header("Content-Type", "multipart/x-mixed-replace; boundary=image")
        gestionnaire.send_header("Cache-Control", "no-store")
        gestionnaire.end_headers()
        with self._condition:
            self.clients += 1
        dernier = -1
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._numero != dernier, timeout=5)
                    jpeg, dernier = self._jpeg, self._numero
                if jpeg is None:
                    continue
                gestionnaire.wfile.write(b"--image\r\nContent-Type: image/jpeg\r\n"
                                         + f"Content-Length: {len(jpeg)}\r\n\r\n".encode() + jpeg + b"\r\n")
                time.sleep(self.intervalle)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        finally:
            with self._condition:
                self.clients -= 1
