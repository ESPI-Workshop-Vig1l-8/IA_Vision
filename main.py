import cv2
import time
import numpy as np
from ultralytics import YOLO
from collections import deque

images_apprentissage = 60
seuil_lumiere = 0.4

# chargement du modèle YOLO pour la détection d'objets
modele_yolo = YOLO("yolov8n.pt")
yolo_conf = 0.5
yolo_imgsz = 320
delai_persistence = 2.0

# variables couleurs
bleu = (255, 0, 0)
vert = (0, 255, 0)
rouge = (0, 0, 255)
jaune = (0, 255, 255)
blanc = (255, 255, 255)

# déclaration de la variable camera
camera = cv2.VideoCapture(0)

# définition zone minimale et maximale de l'aire de détection
aire_min = 4000
aire_inter = 8000
aire_max = 20000

# détecte le décor et capte ce qui bouge
fond = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=80, detectShadows=True)
noyau = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

# échauffement de YOLO : la 1ère inférence est lente, on la fait avant la boucle
modele_yolo(np.zeros((480, 640, 3), dtype=np.uint8), imgsz=yolo_imgsz, verbose=False)

# initialisation des compteurs
surface = 640 * 480
temps_precedent = time.perf_counter()
fps = 0.0
historique_latence = deque(maxlen=30)
compteur = 0
debut_intrusion = None
derniere_detection = 0.0

while True:
    # récupération des images frame par frame
    ret, frame = camera.read()
    if not ret:
        break

    debut = time.perf_counter()

    # effet miroir pour de la cam
    frame = cv2.flip(frame, 1)
    # ajustement de la taille de la fenêtre
    frame = cv2.resize(frame, (640, 480))

    # application des filtres (frame reste en couleur pour YOLO)
    nuance_gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    flou = cv2.GaussianBlur(nuance_gris, (21, 21), 0)
    gris_bgr = cv2.cvtColor(nuance_gris, cv2.COLOR_GRAY2BGR)

    # masque les zones de mouvement
    masque = fond.apply(flou)
    compteur += 1

    declenche_yolo = False
    yolo_ms = 0.0
    personnes = []

    if compteur <= images_apprentissage:
        cv2.putText(gris_bgr, "Apprentissage du decor...", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, jaune, 2)
    else:
        _, masque = cv2.threshold(masque, 200, 255, cv2.THRESH_BINARY)
        masque = cv2.morphologyEx(masque, cv2.MORPH_OPEN, noyau)
        masque = cv2.dilate(masque, None, iterations=2)

        if cv2.countNonZero(masque) > seuil_lumiere * surface:
            cv2.putText(gris_bgr, "Changement de lumiere ignore", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, jaune, 2)
        else:
            contours, _ = cv2.findContours(masque, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # dessin des contours
            for c in contours:
                aire = cv2.contourArea(c)
                if aire < aire_min:
                    continue
                if aire < aire_inter:
                    couleur = bleu
                elif aire < aire_max:
                    couleur = vert
                else:
                    couleur = rouge
                    declenche_yolo = True
                x, y, w, h = cv2.boundingRect(c)
                cv2.rectangle(gris_bgr, (x, y), (x + w, y + h), couleur, 2)

            # confirmation par YOLO, seulement si un contour est rouge
            if declenche_yolo:
                t_yolo = time.perf_counter()
                resultats = modele_yolo(frame, classes=[0], conf=yolo_conf,
                                        imgsz=yolo_imgsz, verbose=False)
                yolo_ms = (time.perf_counter() - t_yolo) * 1000
                for boite in resultats[0].boxes:
                    x1, y1, x2, y2 = map(int, boite.xyxy[0])
                    personnes.append((x1, y1, x2, y2, float(boite.conf[0])))

    if compteur > images_apprentissage and (declenche_yolo or debut_intrusion is not None):
        t_yolo = time.perf_counter()
        resultats = modele_yolo(frame, classes=[0], conf=yolo_conf,
                                imgsz=yolo_imgsz, verbose=False)
        yolo_ms = (time.perf_counter() - t_yolo) * 1000
        for boite in resultats[0].boxes:
            x1, y1, x2, y2 = map(int, boite.xyxy[0])
            personnes.append((x1, y1, x2, y2, float(boite.conf[0])))

    # personnes confirmées + chrono d'intrusion
    maintenant_t = time.time()
    if personnes:
        derniere_detection = maintenant_t
        if debut_intrusion is None:
            debut_intrusion = maintenant_t
        for (x1, y1, x2, y2, confiance) in personnes:
            cv2.rectangle(gris_bgr, (x1, y1), (x2, y2), blanc, 3)
            cv2.putText(gris_bgr, f"PERSONNE {confiance:.2f}", (x1, max(y1 - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, blanc, 2)
    elif debut_intrusion is not None and maintenant_t - derniere_detection > delai_persistence:
        debut_intrusion = None

    if debut_intrusion is not None:
        cv2.putText(gris_bgr, f"INTRUSION : {maintenant_t - debut_intrusion:.1f} s", (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, rouge, 2)

    # latence : tout le traitement est terminé, on mesure maintenant
    latence_ms = (time.perf_counter() - debut) * 1000
    historique_latence.append(latence_ms)
    latence_moy = sum(historique_latence) / len(historique_latence)

    # calcul des FPS
    maintenant = time.perf_counter()
    fps_instant = 1 / (maintenant - temps_precedent)
    temps_precedent = maintenant
    fps = 0.9 * fps + 0.1 * fps_instant if fps else fps_instant

    couleur_lat = vert if latence_moy < 100 else rouge
    cv2.putText(gris_bgr, f"FPS : {fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, vert, 2)
    cv2.putText(gris_bgr, f"Latence : {latence_moy:.0f} ms (YOLO : {yolo_ms:.0f} ms)", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur_lat, 2)
    cv2.imshow("Sentinel-X", gris_bgr)

    # presser q pour quitter la fenêtre
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()