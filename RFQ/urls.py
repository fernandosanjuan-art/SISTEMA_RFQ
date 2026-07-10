from django.urls import path
from . import views
from .views import upload_and_process_rfq, process_single_file_async, finalize_analysis_status, check_analysis_status

app_name = 'RFQ'

urlpatterns = [
    # Ruta: /analisis/rfq/upload/
    path('rfq/upload/', upload_and_process_rfq, name='upload_rfq'),
    
    # Ruta: /analisis/rfq/process-file-async/
    path('rfq/process-file-async/', process_single_file_async, name='process-file-async'),
    
    # CORREGIDA -> Ruta: /analisis/api/rfq/finalize-status/
    path('api/rfq/finalize-status/', finalize_analysis_status, name='finalize_analysis_status'),
    
    # CORREGIDA -> Ruta: /analisis/api/rfq/check-status/
    path('api/rfq/check-status/', check_analysis_status, name='check_analysis_status'),
    
    # CORREGIDA -> Ruta: /analisis/api/rfq/cancel/
    path('api/rfq/cancel/', views.cancel_analysis_view, name='cancel_analysis'),
]