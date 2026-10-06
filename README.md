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

## Limites connues
## Intégration Sentinel-X (dashboard et alertes)
Le script tourne **sur le PC serveur, hors Docker** : la webcam USB y est branchée (Docker sous Windows/macOS n'accède pas aux webcams). Configuration dans `.env` (voir `.env.example.txt`).

- **Flux vidéo** : les images analysées (cadres, détections, FPS) sont publiées en MJPEG sur `http://<serveur>:8000/vision/stream.mjpg?token=<clé>`. Le dashboard l'affiche via son proxy `/vision/`. Le jeton est vérifié auprès du backend : sans clé d'accès, la caméra n'est pas visible. Les images ne sont encodées que si quelqu'un regarde.
- **Alertes** (`POST /api/v1/alerts`, jeton service, envoi en arrière-plan) :

| Niveau | Quand | Effet |
|---|---|---|
| `warning` | première image où YOLO confirme une personne | alerte « Avertissement » sur le dashboard |
| `confirmed` | présence continue depuis `CONFIRMATION_S` secondes (3 par défaut) | alerte « Confirmée », la LED environnement du nœud `DEVICE_ID` clignote |

  Une alerte par niveau et par intrusion ; l'intrusion se termine après 2 s sans personne (`delai_persistence`).
- `AFFICHAGE=0` : sans fenêtre, pour un serveur sans écran.
- Premier lancement : `yolov8n.pt` est téléchargé par ultralytics. Lancez le script une fois **avec Internet** avant de passer sur le réseau isolé de la table.
