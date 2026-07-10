from django.apps import AppConfig
import threading


class RFQConfig(AppConfig):

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'RFQ'

    def ready(self):

        def preload():

            try:

                from RFQ.services.materials.embedding_matcher import (
                    build_material_index
                )

                build_material_index()

                print(
                    "\n================================="
                )
                print(
                    "Material embeddings cargados"
                )
                print(
                    "=================================\n"
                )

            except Exception as e:

                print(
                    f"ERROR EMBEDDINGS: {e}"
                )

        threading.Thread(
            target=preload,
            daemon=True
        ).start()