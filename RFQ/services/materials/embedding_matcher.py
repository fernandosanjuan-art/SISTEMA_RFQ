# embedding_matcher.py
import os
import gc
import json
import numpy as np
import redis
from datetime import datetime, timezone
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from RFQ.models import Material

_MODEL_INSTANCE = None
_MATERIAL_IDS = []
_MATERIAL_VECTORS = None
_redis_client = None

# Usa la misma variable de entorno que ya usas para el broker de Celery
REDIS_URL = os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL")

VECTORS_KEY = "rfq:material_embeddings:vectors"
IDS_KEY = "rfq:material_embeddings:ids"
META_KEY = "rfq:material_embeddings:meta"


def get_redis_client():
    global _redis_client
    if _redis_client is None:
        if not REDIS_URL:
            raise RuntimeError("No se encontró REDIS_URL ni CELERY_BROKER_URL en el entorno.")
        _redis_client = redis.from_url(REDIS_URL)
    return _redis_client


def get_model():
    """Carga el transformador semántico una sola vez de forma estricta en CPU."""
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is None:
        _MODEL_INSTANCE = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
    return _MODEL_INSTANCE


def _save_cache_to_redis(ids, vectors):
    r = get_redis_client()
    meta = {
        "count": len(ids),
        "shape": list(vectors.shape),
        "dtype": str(vectors.dtype),
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    r.set(VECTORS_KEY, vectors.tobytes())
    r.set(IDS_KEY, json.dumps(ids))
    r.set(META_KEY, json.dumps(meta))


def _load_cache_from_redis():
    """Devuelve (ids, vectors) si hay una caché válida en Redis, o (None, None)."""
    try:
        r = get_redis_client()
        raw_vectors = r.get(VECTORS_KEY)
        raw_ids = r.get(IDS_KEY)
        raw_meta = r.get(META_KEY)
        if not raw_vectors or not raw_ids or not raw_meta:
            return None, None

        meta = json.loads(raw_meta)
        vectors = np.frombuffer(raw_vectors, dtype=meta["dtype"]).reshape(meta["shape"])
        ids = json.loads(raw_ids)

        if len(ids) != vectors.shape[0]:
            return None, None

        return ids, vectors
    except Exception as e:
        print(f"No se pudo leer la caché de embeddings desde Redis: {e}")
        return None, None


def build_material_index(force=False):
    """
    Genera la matriz de vectores. Si force=False (caso normal en los workers),
    intenta primero cargar desde Redis para evitar recalcular 928 textos
    cada vez que arranca un proceso nuevo, sea en sistema_rfq o en celery_worker.
    force=True se usa SOLO desde el management command de importación.
    """
    global _MATERIAL_IDS
    global _MATERIAL_VECTORS

    current_count = Material.objects.count()

    if not force:
        cached_ids, cached_vectors = _load_cache_from_redis()
        if cached_ids is not None and len(cached_ids) == current_count:
            _MATERIAL_IDS = cached_ids
            _MATERIAL_VECTORS = cached_vectors
            print(f"Embeddings cargados desde Redis ({len(cached_ids)} materiales, sin recalcular)")
            return

    materials_data = Material.objects.values_list('id', 'family', 'commercial_name', 'color', 'material_code')

    if not materials_data:
        _MATERIAL_IDS = []
        _MATERIAL_VECTORS = None
        return

    local_ids = []
    texts = []
    for m_id, family, commercial_name, color, material_code in materials_data:
        text = f"FAMILIA: {family or ''} | NOMBRE: {commercial_name or ''} | COLOR: {color or ''} | CODIGO: {material_code or ''}".upper()
        local_ids.append(m_id)
        texts.append(text)

    try:
        current_model = get_model()
        vectors = current_model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        _MATERIAL_VECTORS = vectors
        _MATERIAL_IDS = local_ids
        _save_cache_to_redis(local_ids, vectors)
        print(f"Embeddings creados y guardados en Redis: {len(texts)}")
    except Exception as e:
        print(f"Error crítico al construir el índice de materiales: {e}")
        _MATERIAL_VECTORS = None
        _MATERIAL_IDS = []
    finally:
        del texts
        gc.collect()


def match_material(candidate_text):
    global _MATERIAL_VECTORS
    global _MATERIAL_IDS

    if not candidate_text or str(candidate_text).strip() == "":
        return None

    if _MATERIAL_VECTORS is None or len(_MATERIAL_IDS) == 0:
        build_material_index()

    if _MATERIAL_VECTORS is None or len(_MATERIAL_IDS) == 0:
        return None

    try:
        current_model = get_model()
        search_query = f"FAMILIA: {candidate_text} | NOMBRE: {candidate_text}".upper()
        candidate_vector = current_model.encode([search_query], show_progress_bar=False, convert_to_numpy=True)

        similarities = cosine_similarity(candidate_vector, _MATERIAL_VECTORS)[0]
        best_idx = np.argmax(similarities)
        best_score = similarities[best_idx]
        confidence = round(float(best_score) * 100, 2)

        del candidate_vector
        gc.collect()

        if confidence < 70:
            return None

        target_id = _MATERIAL_IDS[best_idx]
        matched_material_obj = Material.objects.get(id=target_id)

        return {"material": matched_material_obj, "confidence": confidence}

    except Exception as run_error:
        print(f"Error durante la ejecución del match de materiales: {run_error}")
        return None