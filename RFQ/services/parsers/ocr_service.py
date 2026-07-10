import fitz
import gc
import io
from PIL import Image
from paddleocr import PaddleOCR

# Se mantiene la inicialización perezosa (lazy) del motor OCR: solo el
# contenedor de Celery paga el costo de cargar PaddleOCR, y solo cuando
# realmente se necesita.
_OCR_ENGINE = None


def _get_ocr_engine():
    # [PATCH] Cacheamos el motor OCR a nivel de módulo en vez de crearlo en
    # cada llamada. Antes, `extract_text_with_ocr` creaba una instancia nueva
    # de PaddleOCR (cientos de MB) CADA VEZ que se invocaba la función. Ahora,
    # dentro del mismo proceso worker se reutiliza. Esto solo funciona bien
    # en conjunto con el aumento de CELERY_WORKER_MAX_TASKS_PER_CHILD (ver
    # settings.py) para que el proceso viva lo suficiente para amortizar el
    # costo de carga.
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        _OCR_ENGINE = PaddleOCR(use_angle_cls=True, lang='en')
    return _OCR_ENGINE


def extract_text_with_ocr(pdf_path):
    ocr_engine = _get_ocr_engine()

    doc = fitz.open(pdf_path)
    full_text = []

    try:
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img_byte_arr = None
            try:
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()

                result = ocr_engine.ocr(img_bytes)

                page_text = []
                if result:
                    for line in result:
                        if line:
                            for item in line:
                                page_text.append(item[1][0])

                full_text.append("\n".join(page_text))
            except Exception as e:
                print(f"OCR Error: {e}")
            finally:
                # [PATCH] Liberamos explícitamente el pixmap (imagen renderizada
                # a 300 DPI, que puede pesar varios MB por página) y el buffer
                # en memoria tan pronto como se usan. En PDFs de muchas páginas,
                # esto evita que se acumulen todas las imágenes decodificadas
                # en RAM simultáneamente durante el ciclo.
                if img_byte_arr is not None:
                    img_byte_arr.close()
                del pix
    finally:
        doc.close()

    gc.collect()
    return "\n".join(full_text)