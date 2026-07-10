# tasks.py
import os
import gc
import json
import re
import traceback
from django.conf import settings
# [PATCH - BUCKET] default_storage apunta al bucket R2 (o a disco local si no
# hay credenciales configuradas). Ya no decodificamos Base64 aquí.
from django.core.files.storage import default_storage
from django.db.models import F
from celery import shared_task
from .models import DrawingAnalysis, DrawingDetectedMaterial, PartComponent, Material

from RFQ.services.parsers.pdf_parser import extract_text_from_pdf, extract_volume, extract_weight
from RFQ.services.ai.structured_extractor import extract_rfq_data
from RFQ.services.materials.embedding_matcher import match_material
from RFQ.services.cad.step_parser import analyze_step
from RFQ.services.cad.stl_parser import analyze_stl


def mark_file_done_and_check_batch(analysis_id):
    DrawingAnalysis.objects.filter(id=analysis_id).update(
        processed_files=F('processed_files') + 1
    )
    analysis = DrawingAnalysis.objects.get(id=analysis_id)
    if analysis.processed_files >= analysis.total_files:
        analysis.status = 'completed'
        analysis.save()


# [PATCH - CRÍTICO] Se detectó que los archivos temporales guardados en
# MEDIA_ROOT/tmp NUNCA se borraban tras procesarlos. Esta función centraliza
# la limpieza y se llama SIEMPRE al final (éxito o error) mediante un bloque
# finally.
#
# [PATCH - BUCKET] Ahora limpiamos DOS cosas:
#   1. El archivo local temporal en el disco EFÍMERO del propio worker
#      (ya no necesita ser compartido con nadie, así que puede vivir y
#      morir dentro del mismo proceso sin problema).
#   2. El objeto remoto en el bucket R2, una vez que ya no se necesita,
#      para no acumular archivos (y costo) en el bucket indefinidamente.
def _cleanup_files(local_path, file_name, storage_key):
    try:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
    except Exception as cleanup_err:
        print(f"[CLEANUP WARNING] No se pudo borrar archivo local {file_name}: {cleanup_err}")

    try:
        if storage_key and default_storage.exists(storage_key):
            default_storage.delete(storage_key)
    except Exception as cleanup_err:
        print(f"[CLEANUP WARNING] No se pudo borrar {storage_key} del bucket: {cleanup_err}")


@shared_task
def process_file_in_background(analysis_id, file_name, storage_key, ext, is_subcomponent_manual):
    """
    [PATCH - BUCKET] El tercer parámetro ahora es `storage_key`: la ruta del
    objeto dentro del bucket R2 (por ejemplo "rfq_tmp/42/plano.pdf"), no el
    contenido del archivo en Base64. El worker descarga el archivo del bucket
    en streaming (por bloques) y lo escribe en un directorio local EFÍMERO
    propio del worker — este directorio ya NO necesita ser compartido con el
    servicio web, porque el bucket es ahora el medio compartido real.
    """

    print(f"[TASK] Archivo: {file_name}")
    print(f"[TASK] Extensión: {ext}")
    print(f"[TASK] Storage key: {storage_key}")
    analysis = DrawingAnalysis.objects.get(id=analysis_id)

    # [PATCH] Usamos un directorio de trabajo propio del worker, distinto al
    # que usaba el servicio web. Es solo un scratch local, se borra siempre.
    local_dir = os.path.join(settings.MEDIA_ROOT, 'tmp_worker')
    os.makedirs(local_dir, exist_ok=True)
    file_path = os.path.join(local_dir, file_name)

    try:
        # [PATCH] Descarga en streaming por bloques de 1MB, en vez de leer
        # el objeto completo de una sola vez en una variable de Python. Esto
        # evita picos de RAM con archivos grandes (planos STEP pueden pesar
        # decenas o cientos de MB).
        with default_storage.open(storage_key, 'rb') as remote_file, open(file_path, 'wb') as local_file:
            for chunk in remote_file.chunks(chunk_size=1024 * 1024):
                local_file.write(chunk)
    except Exception as e:
        print(f"[ERROR DESCARGA] {file_name}: {e}\n{traceback.format_exc()}")
        DrawingDetectedMaterial.objects.create(
            analysis=analysis,
            part_number=os.path.splitext(file_name)[0],
            raw_material_text="Error",
            detected_family="N/D",
            detected_color="N/D",
            bom_reference=f"{file_name}: ⚠ No se pudo descargar el archivo del bucket ({str(e)[:150]})"
        )
        mark_file_done_and_check_batch(analysis.id)
        _cleanup_files(file_path, file_name, storage_key)
        gc.collect()
        return {'success': False, 'file_name': file_name, 'error': str(e)}

    # [PATCH] Envolvemos TODO el procesamiento en try/finally para garantizar
    # que el archivo local Y el objeto en el bucket se borren siempre, sin
    # importar el resultado.
    try:
        # CASO 1: ARCHIVOS 3D
        if ext in ['.step', '.stp', '.stl']:
            print(f"[3D] Entró al bloque 3D: {file_name}")
            try:
                if ext in ['.step', '.stp']:
                    threed_data = analyze_step(file_path)
                else:
                    threed_data = analyze_stl(file_path)

                if not threed_data.get("ok"):
                    raise Exception(threed_data.get("error", "Error desconocido procesando geometría 3D"))

                volume_cm3 = threed_data.get('volume_cm3', 0)
                classification_string = f"{file_name}: 📐 Geometría 3D Indexada ({volume_cm3} cm³)"

                DrawingDetectedMaterial.objects.create(
                    analysis=analysis,
                    part_number=os.path.splitext(file_name)[0],
                    raw_material_text="Geometría 3D",
                    detected_family="N/D",
                    detected_color="N/D",
                    component_volumen=round(float(volume_cm3), 2) if volume_cm3 else None,
                    bom_reference=classification_string
                )
                print(f"[3D] Resultado: {threed_data}")
                mark_file_done_and_check_batch(analysis.id)
                return {'success': True, 'type': '3d', 'file_name': file_name, 'classification': classification_string}

            except Exception as e:
                print(f"[ERROR 3D] {file_name}: {e}\n{traceback.format_exc()}")
                DrawingDetectedMaterial.objects.create(
                    analysis=analysis,
                    part_number=os.path.splitext(file_name)[0],
                    raw_material_text="Geometría 3D",
                    detected_family="N/D",
                    detected_color="N/D",
                    bom_reference=f"{file_name}: ⚠ Error al procesar geometría 3D ({str(e)[:150]})"
                )
                mark_file_done_and_check_batch(analysis.id)
                return {'success': False, 'type': '3d', 'file_name': file_name, 'error': str(e)}

        # CASO 2: PLANOS TÉCNICOS 2D (.PDF)
        elif ext == '.pdf':
            try:
                raw_text = extract_text_from_pdf(file_path)
                previous_text = analysis.raw_text or ""

                # [PATCH] `raw_text` del análisis crecía sin límite: en lotes
                # con muchos PDFs grandes, cada tarea releía y reescribía TODO
                # el texto acumulado hasta ese momento. Ponemos un techo
                # razonable (300k caracteres ~ decenas de planos) para evitar
                # que un campo TEXT de MySQL crezca de forma descontrolada y
                # se cargue completo en RAM en cada tarea subsecuente.
                combined_text = previous_text + f"\n--- ORIGEN: {file_name} ---\n" + raw_text
                MAX_RAW_TEXT_CHARS = 300_000
                if len(combined_text) > MAX_RAW_TEXT_CHARS:
                    combined_text = combined_text[-MAX_RAW_TEXT_CHARS:]
                analysis.raw_text = combined_text

                clean_text_for_regex = re.sub(r'MASSE\s*:\s*WEIGHT', 'WEIGHT', raw_text, flags=re.IGNORECASE)
                local_volume = extract_volume(raw_text)
                local_weight = extract_weight(clean_text_for_regex) or extract_weight(raw_text)

                if local_volume and not analysis.estimated_volume:
                    analysis.estimated_volume = local_volume
                if local_weight and not analysis.estimated_weight:
                    analysis.estimated_weight = local_weight
                analysis.save()

                try:
                    gemini_result = extract_rfq_data(raw_text)
                    raw_json = gemini_result.get('raw_response', '{}') if 'raw_response' in gemini_result else json.dumps(gemini_result)
                    clean_json = re.sub(r'^```json\s*|```$', '', raw_json, flags=re.MULTILINE).strip()
                    raw_data = json.loads(clean_json)
                except Exception:
                    raw_data = {}

                parts_list = []
                if not raw_data:
                    file_pure_name = os.path.splitext(file_name)[0]
                    parts_list = [{"part_number": file_pure_name, "description": "Componente extraído"}]
                elif isinstance(raw_data, list):
                    parts_list = raw_data
                elif isinstance(raw_data, dict):
                    parts_list = raw_data.get('parts', raw_data.get('part_numbers', [raw_data] if 'part_number' in raw_data else []))

                for part in parts_list:
                    part_num = part.get('part_number') or part.get('part_number_base')
                    part_desc = part.get('name') or part.get('description') or ''

                    material_data = part.get('materials', [{}])[0] if part.get('materials') else part.get('material', {})
                    if not isinstance(material_data, dict):
                        material_data = {"name": str(material_data)}

                    commercial_name_ia = material_data.get('material_name') or material_data.get('name') or ''
                    resin_family_ia = material_data.get('resin_family') or material_data.get('family') or ''
                    color_ia = material_data.get('color') or ''

                    alt_material_data = part.get('alternative_material_suggestions', [{}])[0] if part.get('alternative_material_suggestions') else {}
                    alt_resin_name = alt_material_data.get('name', '')
                    if not alt_resin_name or alt_resin_name.upper() == 'NULL':
                        alt_resin_name = 'Ninguna registrada'

                    matched_material_db = None
                    if isinstance(commercial_name_ia, str) and commercial_name_ia.strip():
                        match_result = match_material(commercial_name_ia)
                        if match_result and match_result["confidence"] >= 70:
                            matched_material_db = match_result["material"]

                    if not matched_material_db and alt_resin_name and alt_resin_name != 'Ninguna registrada':
                        alt_match_result = match_material(alt_resin_name)
                        if alt_match_result and alt_match_result["confidence"] >= 70:
                            matched_material_db = alt_match_result["material"]

                    volume_val = part.get('volume_cm3') or part.get('volume')
                    if not volume_val:
                        threed_geom = DrawingDetectedMaterial.objects.filter(
                            analysis=analysis,
                            bom_reference__icontains="Geometría 3D Indexada"
                        ).first()
                        if threed_geom and threed_geom.component_volumen:
                            volume_val = threed_geom.component_volumen
                    if not volume_val:
                        volume_val = local_volume

                    weight_val = part.get('weight_grams') or part.get('weight')
                    data_source_flag = "Extraído de Plano PDF"

                    if volume_val and not weight_val:
                        density = matched_material_db.density if matched_material_db and matched_material_db.density else 1.05
                        try:
                            weight_val = float(volume_val) * float(density)
                            data_source_flag = f"Peso Estimado ({volume_val} cm³ x {density} g/cm³)"
                        except Exception:
                            weight_val = None

                    secondary_components = part.get('secondary_embedded_components', [])
                    secondary_text_list = []
                    if secondary_components and weight_val:
                        for sub_item in secondary_components:
                            s_name = sub_item.get('component_name', '')
                            m_type = sub_item.get('material_type', '')
                            qty = sub_item.get('quantity', 1) or 1
                            added_weight = (2.5 * qty) if m_type == 'METAL' else (0.5 * qty)
                            weight_val = float(weight_val) + added_weight
                            secondary_text_list.append(f"{qty}x {s_name}")
                            data_source_flag = "Peso Compuesto (Resina + Insertos)"

                    ref_secundarios = f" | Lleva: {', '.join(secondary_text_list)}" if secondary_text_list else ""

                    DrawingDetectedMaterial.objects.create(
                        analysis=analysis,
                        part_number=part_num,
                        raw_material_text=commercial_name_ia if commercial_name_ia else part_desc,
                        detected_material=matched_material_db,
                        detected_family=resin_family_ia if resin_family_ia else "N/D",
                        detected_color=color_ia if color_ia else "N/D",
                        component_weight=round(float(weight_val), 2) if weight_val else None,
                        component_volumen=round(float(volume_val), 2) if volume_val else None,
                        bom_reference=f"{part_desc}{ref_secundarios} | [Alt: {alt_resin_name}] | [{data_source_flag}] | Origen: {file_name}"
                    )

                    if part_num:
                        PartComponent.objects.create(
                            parent=analysis,
                            child_part_number=part_num,
                            estimated_weight=weight_val if weight_val else 0,
                            quantity=part.get('quantity', 1)
                        )

                mark_file_done_and_check_batch(analysis.id)
                return {'success': True, 'type': 'pdf', 'file_name': file_name}

            except Exception as e:
                print(f"[ERROR PDF] {file_name}: {e}\n{traceback.format_exc()}")
                DrawingDetectedMaterial.objects.create(
                    analysis=analysis,
                    part_number=os.path.splitext(file_name)[0],
                    raw_material_text="Error",
                    detected_family="N/D",
                    detected_color="N/D",
                    bom_reference=f"{file_name}: ⚠ Error al procesar PDF ({str(e)[:150]})"
                )
                mark_file_done_and_check_batch(analysis.id)
                return {'success': False, 'type': 'pdf', 'file_name': file_name, 'error': str(e)}

    finally:
        # [PATCH - CRÍTICO + BUCKET] Este es el fix principal: se borra
        # SIEMPRE (éxito o error) tanto el archivo local temporal del worker
        # como el objeto remoto en el bucket, evitando que el bucket (y el
        # disco del worker) crezcan sin control con cada análisis.
        _cleanup_files(file_path, file_name, storage_key)
        # [PATCH] Forzamos recolección de basura al cerrar la tarea. Con
        # max_tasks_per_child > 1 (ver settings.py), el proceso worker se
        # reutiliza para varias tareas, así que es importante ayudar a
        # liberar la memoria de esta tarea antes de tomar la siguiente.
        gc.collect()