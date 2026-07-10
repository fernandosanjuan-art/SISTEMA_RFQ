import os
import django

# Configurar el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config_rfq.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'katesmk')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'kate.gonzalez@samkwangmx.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '12345skm')

if not User.objects.filter(username=username).exists():
    print(f"Creando superusuario: {username}")
    User.objects.create_superuser(username=username, email=email, password=password)
else:
    print(f"El superusuario {username} ya existe.")