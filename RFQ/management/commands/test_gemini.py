from django.core.management.base import BaseCommand

from RFQ.services.parsers.pdf_parser import (
    extract_text_from_pdf
)

from RFQ.services.ai.structured_extractor import (
    extract_rfq_data
)


class Command(BaseCommand):

    help = 'Test Gemini RFQ extraction'

    def add_arguments(self, parser):

        parser.add_argument(
            'pdf_path',
            type=str
        )

    def handle(self, *args, **options):

        pdf_path = options['pdf_path']

        self.stdout.write("Reading PDF...")

        text = extract_text_from_pdf(
            pdf_path
        )

        self.stdout.write(
            self.style.SUCCESS(
                "PDF text extracted"
            )
        )

        result = extract_rfq_data(text)

        self.stdout.write("")

        self.stdout.write("========= FINAL RESULT =========")

        self.stdout.write(str(result))