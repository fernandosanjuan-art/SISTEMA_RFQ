
from google import genai
from django.conf import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

MODEL_NAME = "gemini-3.1-flash-lite"

def ask_gemini(prompt):
    """
    Invocación corregida al motor Gemini mediante el SDK moderno de Google.
    Garantiza el mapeo correcto del parámetro requerido 'contents'.
    """
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,   
            contents=prompt, 
        )
        return response.text
    except Exception as e:
        print(f"Error crítico en la llamada a Gemini Flash Lite: {str(e)}")
        raise e