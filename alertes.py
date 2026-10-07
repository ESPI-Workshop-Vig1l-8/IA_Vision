"""
Alertes d'intrusion envoyées au backend : POST /api/v1/alerts (jeton service).

Deux niveaux, une fois chacun par intrusion :
  - "warning"   : première image où YOLO confirme une personne
  - "confirmed" : la présence dure depuis duree_confirmation secondes
                  (la LED environnement du nœud clignote)
L'envoi se fait dans un thread : la boucle vidéo n'attend jamais le réseau.
"""

import queue
import threading

import requests


class ClientAlertes:
    def __init__(self, url_backend, jeton, source="ia-vision"):
        self.url = url_backend.rstrip("/")
        self.jeton = jeton
        self.source = source
        self._file = queue.Queue(maxsize=50)
        threading.Thread(target=self._envoyer_en_continu, daemon=True).start()
        if not jeton:
            print("[ALERTE] ATTENTION : API_SERVICE_TOKEN absent, les alertes seront refusées par le backend.")

    def envoyer(self, corps):
        try:
            self._file.put_nowait(corps)
        except queue.Full:
            print("[ALERTE] File pleine, alerte abandonnée")

    def _envoyer_en_continu(self):
        while True:
            corps = self._file.get()
            corps["source"] = self.source
            try:
                reponse = requests.post(f"{self.url}/api/v1/alerts", json=corps, timeout=5,
                                        headers={"Authorization": f"Bearer {self.jeton}"})
            except requests.RequestException as erreur:
                print(f"[ALERTE] Backend injoignable sur {self.url} : {erreur}")
                continue
            if reponse.status_code == 201:
                print(f"[ALERTE] {corps['level']} envoyée : {reponse.json().get('action')}")
            else:
                print(f"[ALERTE] Refusée par le backend ({reponse.status_code}) : {reponse.text[:200]}")


class SuiviIntrusion:
    def __init__(self, client, appareil, duree_confirmation=3.0):
        self.client = client
        self.appareil = appareil
        self.duree_confirmation = duree_confirmation
        self.niveau = None  # None, "warning" ou "confirmed" pour l'intrusion en cours

    def mettre_a_jour(self, debut_intrusion, maintenant, personnes):
        """debut_intrusion : heure de début de l'intrusion en cours, ou None.
        personnes : boîtes (x1, y1, x2, y2, confiance) de l'image courante."""
        if debut_intrusion is None:
            self.niveau = None
            return
        duree = maintenant - debut_intrusion
        if self.niveau is None and personnes:
            self.niveau = "warning"
            self._alerte("warning", duree, personnes, "Personne détectée dans la zone")
        elif self.niveau == "warning" and duree >= self.duree_confirmation and personnes:
            self.niveau = "confirmed"
            self._alerte("confirmed", duree, personnes, f"Intrusion confirmée : présence depuis {duree:.1f} s")

    def _alerte(self, niveau, duree, personnes, details):
        meilleure = max(personnes, key=lambda p: p[4])
        self.client.envoyer({
            "type": "intrusion",
            "level": niveau,
            "device_id": self.appareil,
            "confidence": round(meilleure[4], 3),
            "details": details,
            "data": {"persons": len(personnes), "bbox": list(meilleure[:4]), "duration_s": round(duree, 1)},
        })
