## Description
Détection de présence humaine (MOG2 + YOLOv8n)

## Installation.
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

## Configuration
Copier .env.example en .env et renseigner les valeurs.

## Paramètres principaux
(seuils d'aire, confiance YOLO, taille d'entrée, tableau de latences mesurées)


## Intégration Sentinel-X (dashboard et alertes)

- **Flux vidéo** : les images analysées (cadres, détections, FPS) sont publiées en MJPEG sur `/vision/stream.mjpg?token=<clé>` (port 8000). Le dashboard l'affiche via son proxy `/vision/`. Le jeton est vérifié auprès du backend : sans clé d'accès, la caméra n'est pas visible. Les images ne sont encodées que si quelqu'un regarde.
- **Alertes** (`POST /api/v1/alerts`, jeton service, envoi en arrière-plan) :

| Niveau | Quand | Effet |
|---|---|---|
| `warning` | première image où YOLO confirme une personne | alerte « Avertissement » sur le dashboard |
| `confirmed` | présence continue depuis `CONFIRMATION_S` secondes (3 par défaut) | alerte « Confirmée », la LED environnement du nœud `DEVICE_ID` clignote |

  Une alerte par niveau et par intrusion ; l'intrusion se termine après 2 s sans personne (`delai_persistence`).

### Mode 1 : conteneur Docker (serveur **Linux uniquement**)
Le service `ia-vision` de la stack `infra` est construit depuis ce dépôt (`Dockerfile`) et démarre avec `docker compose up -d`.

- La webcam est passée au conteneur avec `devices: /dev/video0` : **cela ne fonctionne que sur Linux**. Docker Desktop (Windows, macOS) ne donne pas accès aux webcams USB : utiliser le mode 2.
- Le modèle `yolov8n.pt` est téléchargé **à la construction de l'image** : le conteneur fonctionne ensuite hors ligne, sur le hotspot de la table.
- Pas de fenêtre d'affichage (`AFFICHAGE=0`) : les images sont visibles dans le dashboard.
- Image d'environ 2,5 Go (PyTorch CPU) ; la construction demande Internet (PyPI, download.pytorch.org, GitHub pour le modèle).

### Mode 2 : directement sur le PC (Windows, macOS, ou Linux sans Docker)
```
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows (Linux/macOS : source .venv/bin/activate)
pip install -r requirements.txt
copier .env.example.txt en .env     # BACKEND_URL=http://127.0.0.1:10443, API_SERVICE_TOKEN, DEVICE_ID
python main.py
```
- Premier lancement : `yolov8n.pt` est téléchargé par ultralytics. Lancez le script une fois **avec Internet** avant de passer sur le réseau isolé de la table.
- `AFFICHAGE=1` ouvre aussi la fenêtre locale.
- Le dashboard trouve le flux via `VISION_UPSTREAM` dans le `.env` de l'infra (voir le README de l'infra).
