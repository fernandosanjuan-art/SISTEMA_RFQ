#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Iniciando optimización de entorno para baja memoria RAM..."

python -m pip install --upgrade pip
python -m pip install -r requirements.txt --no-cache-dir --src ./tmp apt-get install -y tesseract-ocr 

echo "Ejecutando tareas de Django..."
python manage.py collectstatic --no-input
python manage.py migrate

python create_admin.py

echo "Poblando Catálogo Maestro de Resinas desde Excel de forma automática..."
python manage.py import_materials