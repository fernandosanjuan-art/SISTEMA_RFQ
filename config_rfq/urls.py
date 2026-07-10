from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView  # <-- 1. Agregamos esta importación

urlpatterns = [
    path('admin/', admin.site.urls),
    path('analisis/', include('RFQ.urls')), 
    
    # <-- 2. Agregamos esta línea para redirigir la raíz al panel de subida
    path('', RedirectView.as_view(url='/analisis/rfq/upload/', permanent=False)),
]