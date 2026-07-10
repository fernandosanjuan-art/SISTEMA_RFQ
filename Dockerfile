# Usamos Python 3.10-slim como base
FROM python:3.10-slim

# Evita que Python escriba archivos .pyc en el disco y asegura que los logs se vean en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema operativo (Cambiamos libgl1-mesa-glx por libgl1)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    tesseract-ocr \
    libgomp1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Definir el directorio de trabajo dentro del contenedor
WORKDIR /app

# Actualizar pip e instalar los requerimientos de Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar todo el código de tu proyecto al contenedor
COPY . /app/

# Comando por defecto para arrancar Django con Gunicorn
EXPOSE 8000
# Por esta nueva versión con la bandera --timeout:
CMD ["gunicorn", "config_rfq.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "300"]