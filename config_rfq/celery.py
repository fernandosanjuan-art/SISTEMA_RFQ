import os
from celery import Celery

# Configura las variables de entorno de Django para Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config_rfq.settings')

app = Celery('config_rfq')

# Lee la configuración de Django, todas las opciones de Celery tendrán el prefijo 'CELERY_'
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descubre automáticamente las tareas en tus aplicaciones (buscará archivos tasks.py)
app.autodiscover_tasks()