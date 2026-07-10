import json
import re
import os
import gc
from django.shortcuts import render
from django.http import JsonResponse
# [PATCH - BUCKET] default_storage apunta automáticamente al bucket R2 si
# configuraste las variables de entorno (ver settings.py), o a disco local
# si no. Ya no necesitamos FileSystemStorage manual ni base64.
from django.core.files.storage import default_storage
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from .models import Material, DrawingAnalysis, DrawingDetectedMaterial, PartComponent
from .forms import DrawingUploadForm

from RFQ.services.parsers.pdf_parser import (
    extract_text_from_pdf, extract_volume, extract_weight, extract_color
)
from RFQ.services.ai.structured_extractor import extract_rfq_data
from RFQ.services.materials.embedding_matcher import match_material

from RFQ.services.cad.step_parser import analyze_step
from RFQ.services.cad.stl_parser import analyze_stl
from django.db.models import Q
from .tasks import process_file_in_background


def upload_and_process_rfq(request):
    context = {}
    form = DrawingUploadForm()

    history_id = request.GET.get('history_id')
    if history_id:
        try:
            past_analysis = DrawingAnalysis.objects.get(id=history_id)
            detected_items = past_analysis.detected_materials.all()
            for item in detected_items:
                if not item.detected_material and item.detected_family != "N/D":
                    clean_family = item.detected_family.replace("Resin", "").strip()
                    item.sugerencias = Material.objects.filter(family__icontains=clean_family[:4])[:3]
                else:
                    item.sugerencias = None

            past_classifications = []
            for item in detected_items:
                if "Origen:" in item.bom_reference:
                    orig = item.bom_reference.split("Origen:")[-1].strip()
                    if orig not in past_classifications:
                        past_classifications.append(orig)

            context['analysis'] = past_analysis
            context['detected_components'] = detected_items
            context['file_classifications'] = past_classifications
            context['filename'] = past_analysis.uploaded_file.name if past_analysis.uploaded_file else "Archivo Histórico"
        except DrawingAnalysis.DoesNotExist:
            context['error'] = "El análisis histórico solicitado no existe."

    if request.method == 'POST' and request.FILES.getlist('rfq_file'):
        uploaded_files = request.FILES.getlist('rfq_file')

        # [PATCH - BUCKET] Creamos el análisis PRIMERO (sin archivo aún) para
        # tener analysis.id disponible y usarlo como prefijo de carpeta en el
        # bucket. Esto evita colisiones de nombres entre distintos lotes.
        analysis = DrawingAnalysis.objects.create(
            uploaded_file='',
            raw_text="",
            gemini_raw_json={},
            status='processing',
            total_files=len(uploaded_files),
        )

        primary_pdf_name = None
        all_saved_files = []

        # 1. Subimos cada archivo DIRECTO al bucket (o a disco local si no
        # hay R2 configurado). Ya no pasa por Base64 ni por Redis.
        for u_file in uploaded_files:
            ext = os.path.splitext(u_file.name)[1].lower()
            storage_key = f"rfq_tmp/{analysis.id}/{u_file.name}"

            # default_storage.save transmite el archivo en streaming al
            # backend configurado (S3Storage para R2, o disco local si no
            # hay credenciales) sin cargarlo completo en una variable Python.
            default_storage.save(storage_key, u_file)

            all_saved_files.append({'name': u_file.name, 'storage_key': storage_key, 'ext': ext})

            if ext == '.pdf' and not primary_pdf_name:
                primary_pdf_name = u_file.name

        if not primary_pdf_name and all_saved_files:
            primary_pdf_name = all_saved_files[0]['name']

        analysis.uploaded_file = f"rfq_tmp/{analysis.id}/{primary_pdf_name}"
        analysis.save()

        is_subcomponent_manual = False

        # 2. Mandamos las tareas a Celery pasando solo la "key" del bucket,
        # no el contenido del archivo. El worker se encarga de descargarlo.
        for file_info in all_saved_files:
            f_name = file_info['name']
            storage_key = file_info['storage_key']
            f_ext = file_info['ext']
            print(f"[QUEUE] Enviando: {f_name} ({f_ext}) -> {storage_key}")

            process_file_in_background.delay(
                analysis.id, f_name, storage_key, f_ext, is_subcomponent_manual
            )

        gc.collect()

        return JsonResponse({
            'status': 'initiated',
            'analysis_id': analysis.id,
            'files': all_saved_files
        })

    context['all_materials_catalog'] = Material.objects.all().order_by('material_code')

    context['past_analyses'] = DrawingAnalysis.objects.all().order_by('-uploaded_at')[:20]
    context['form'] = form
    return render(request, 'RFQ/upload.html', context)


@csrf_exempt
def process_single_file_async(request):
    """
    [PATCH - NOTA] Este endpoint no parece estar conectado al flujo actual del
    template upload.html (que usa el endpoint principal de arriba), pero lo
    dejamos funcional por si lo usas desde otro lado. Ajustado para que
    reciba `storage_key` (la key del bucket) en vez de una ruta local de
    disco, ya que `process_file_in_background` ahora espera eso.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        analysis_id = data.get('analysis_id')
        file_name = data.get('file_name')
        storage_key = data.get('storage_key') or data.get('file_path')  # compat retro
        ext = data.get('ext')
        is_subcomponent_manual = data.get('is_subcomponent', False)

        # Disparamos la tarea en segundo plano usando Celery (.delay)
        process_file_in_background.delay(
            analysis_id, file_name, storage_key, ext, is_subcomponent_manual
        )

        # Respondemos de inmediato al navegador que la tarea ya está en cola
        return JsonResponse({
            'success': True,
            'status': 'queued',
            'message': 'El archivo se está procesando mediante IA en segundo plano.'
        })

    except Exception as general_err:
        return JsonResponse({'success': False, 'error': str(general_err)}, status=500)


@csrf_exempt
def finalize_analysis_status(request):
    """
    Consolida el estado final de la auditoría. Configura la nomenclatura específica
    multi-maestro e introduce el campo descriptivo final de los números de parte.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método inválido'}, status=400)

    try:
        data = json.loads(request.body)
        analysis_id = data.get('analysis_id')
        analysis = DrawingAnalysis.objects.get(id=analysis_id)
        detected_items = analysis.detected_materials.all()

        total_validos = 0
        archivos_maestros = []
        partes_sistema = []

        for item in detected_items:
            if item.component_weight or item.detected_material:
                total_validos += 1

            if item.part_number and item.part_number != "Insumo / Adicional":
                if item.part_number not in partes_sistema:
                    partes_sistema.append(item.part_number)

            if "Origen:" in item.bom_reference:
                orig_file = item.bom_reference.split("Origen:")[-1].split("|")[0].strip()
                if orig_file and orig_file not in archivos_maestros:
                    archivos_maestros.append(orig_file)

        if archivos_maestros:
            nombres_limpios = [os.path.splitext(f)[0] for f in archivos_maestros]
            nuevo_nombre = f"Planos: [{', '.join(nombres_limpios[:3])}]"
            if len(nombres_limpios) > 3:
                nuevo_nombre += "..."
        elif partes_sistema:
            nuevo_nombre = f"Partes: [{', '.join(partes_sistema[:3])}]"
        else:
            nuevo_nombre = f"Análisis Técnico Lote #{analysis.id}"

        analysis.material_text = nuevo_nombre
        analysis.raw_text = f"TITULO_LOTE: {nuevo_nombre}\n" + analysis.raw_text

        if total_validos == 0:
            analysis.status = 'failed'
        else:
            analysis.status = 'completed'

        analysis.save()
        return JsonResponse({
            'status': 'finalized',
            'final_status': analysis.status,
            'suggested_name': nuevo_nombre
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


from django.http import JsonResponse
from .models import DrawingAnalysis
def check_analysis_status(request):
    analysis_id = request.GET.get('analysis_id')
    if not analysis_id:
        return JsonResponse({'error': 'Falta el ID'}, status=400)

    try:
        analysis = DrawingAnalysis.objects.get(id=analysis_id)

        # Optimizamos la consulta usando values() para no consumir RAM del contenedor
        detected_items = analysis.detected_materials.all().values(
            'part_number', 'bom_reference', 'raw_material_text',
            'detected_family', 'detected_color', 'component_weight', 'component_volumen',
            'detected_material__commercial_name', 'detected_material__material_code'
        )

        components_payload = []
        for item in detected_items:
            weight_val = item['component_weight']
            weight_lbs = round(float(weight_val) * 0.00220462, 4) if weight_val else None

            components_payload.append({
                'part_number': item['part_number'],
                'description': item['bom_reference'].split('|')[0].strip() if item['bom_reference'] else 'Componente',
                'bom_reference': item['bom_reference'],
                'detected_material': item['detected_material__commercial_name'],
                'material_code': item['detected_material__material_code'],
                'raw_material_text': item['raw_material_text'],
                'detected_family': item['detected_family'],
                'detected_color': item['detected_color'],
                'component_weight': weight_val,
                'component_weight_lbs': weight_lbs,
                'component_volumen': item['component_volumen'],
                'alternative_resin': 'Evaluando...'
            })

        return JsonResponse({
            'status': analysis.status,
            'components': components_payload
        })
    except Exception as e:
        return JsonResponse({'status': 'failed', 'error': str(e)}, status=500)


@csrf_exempt
def cancel_analysis_view(request):
    """
    Endpoint para abortar el análisis actual y cambiar su estado a fallido,
    permitiendo al usuario limpiar la interfaz inmediatamente.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        analysis_id = data.get('analysis_id')
        if not analysis_id:
            return JsonResponse({'error': 'Falta el ID del análisis'}, status=400)

        analysis = DrawingAnalysis.objects.get(id=analysis_id)
        analysis.status = 'failed'
        analysis.material_text = "Análisis Cancelado por el Usuario"
        analysis.save()

        return JsonResponse({'success': True, 'message': 'Análisis cancelado con éxito.'})
    except DrawingAnalysis.DoesNotExist:
        return JsonResponse({'error': 'Análisis no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)