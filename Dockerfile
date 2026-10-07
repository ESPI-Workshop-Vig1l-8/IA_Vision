# IA_Vision in a container — LINUX ONLY: the USB webcam is passed with
# `devices: /dev/video0` (Docker on Windows/macOS cannot access webcams;
# there, run `python main.py` on the host, see README).
FROM python:3.12-slim
WORKDIR /app

# opencv-python (pulled by ultralytics) needs libGL and glib
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# PyTorch CPU first (the default wheel bundles ~3 GB of CUDA libraries)
COPY requirements.txt .
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# YOLO weights downloaded at build time: the container then runs offline
# on the table hotspot
ENV YOLO_CONFIG_DIR=/tmp/Ultralytics
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

COPY . .
RUN useradd -r -u 10001 vision && chown vision /app
USER vision

# No window in a container; the analysed frames go to the dashboard
ENV PYTHONUNBUFFERED=1 AFFICHAGE=0 STREAM_PORT=8000
EXPOSE 8000
CMD ["python", "main.py"]
