# Sentinel-X — Détection d'intrusion vidéo par IA

Sentinel-X est un module de vision par ordinateur qui analyse un flux caméra en
temps réel pour détecter les intrusions. Il combine une soustraction de fond
classique (OpenCV) avec une confirmation par un modèle YOLO, puis remonte les
alertes à un backend central tout en exposant un flux vidéo pour le dashboard.

## Fonctionnement

- **Soustraction de fond** : un modèle MOG2 apprend le décor pendant les
   premières images, puis signale les zones de mouvement. Les gros contours
   suspects déclenchent l'analyse YOLO.
- **Confirmation par YOLO** : seules les personnes (classe 0) sont retenues,
   avec un seuil de confiance de 0,5. Les boîtes sont dessinées sur l'image.
- **Suivi d'intrusion** : un chronomètre démarre à la première détection. Une
   persistance de 2 s évite les faux positifs entre deux images.
- **Alertes à deux niveaux** (voir `alertes.py`) :
   - `warning` : première personne confirmée dans la zone ;
   - `confirmed` : présence continue depuis `CONFIRMATION_S` secondes, ce qui
     fait clignoter la LED du nœud concerné.
   Les envois se font dans un thread : la boucle vidéo n'attend jamais le réseau.
- **Flux MJPEG** (voir `flux_video.py`) : les images annotées sont diffusées
   sur `GET /vision/stream.mjpg?token=...`, protégé par vérification du jeton
   auprès du backend. Les JPEG ne sont encodés que si un client regarde.

## Fichiers

- `main.py` : boucle principale (capture, détection, affichage, métriques).
- `alertes.py` : client d'alertes asynchrone et logique de suivi d'intrusion.
- `flux_video.py` : serveur HTTP MJPEG pour le dashboard.
- `.env` : configuration (voir `.env.example.txt`).

## Configuration (.env)

- `CAMERA` : index webcam ou chemin/URL vidéo (défaut `0`).
- `AFFICHAGE` : `1` pour la fenêtre locale, `0` en serveur sans écran.
- `STREAM_PORT` : port du flux MJPEG, `0` pour désactiver.
- `BACKEND_URL` : URL du backend (défaut `http://127.0.0.1:10443`).
- `DEVICE_ID` : nœud dont la LED clignote sur intrusion confirmée.
- `CONFIRMATION_S` : durée avant passage en `confirmed` (défaut `3`).
- `API_SERVICE_TOKEN` : jeton de service pour authentifier les alertes.

## Installation et lancement

```bash
pip install ultralytics opencv-python requests python-dotenv
python main.py        # appuyer sur q pour quitter la fenêtre