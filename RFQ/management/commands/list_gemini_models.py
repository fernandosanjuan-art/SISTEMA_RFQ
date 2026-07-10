from django.core.management.base import BaseCommand
from django.conf import settings

import google.generativeai as genai


class Command(BaseCommand):

    help = "List available Gemini models"

    def handle(self, *args, **kwargs):

        genai.configure(
            api_key=settings.GEMINI_API_KEY
        )

        print("\nAVAILABLE MODELS:\n")

        for model in genai.list_models():

            methods = []

            try:
                methods = model.supported_generation_methods
            except:
                pass

            print("=" * 80)
            print("NAME:", model.name)
            print("METHODS:", methods)
            print("=" * 80)