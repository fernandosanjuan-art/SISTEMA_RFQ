import pdfplumber

def extract_tables(pdf_path):

    tables = []

    with pdfplumber.open(pdf_path) as pdf:

        for page in pdf.pages:

            extracted = page.extract_tables()

            tables.extend(extracted)

    return tables