import fitz
import re

from RFQ.services.parsers.ocr_service import (
    extract_text_with_ocr
)


PART_PATTERNS = [

    # VALIDOS

    r'PART\s\*NUMBER\s\*\[:\-\]\?\s\*\(\[A\-Z0\-9\-\]\+\)',

    r'PART\s\*NO\\.\?\s\*\[:\-\]\?\s\*\(\[A\-Z0\-9\-\]\+\)',

    r'P\/N\s\*\[:\-\]\?\s\*\(\[A\-Z0\-9\-\]\+\)',

    r'NUMBER\s\*PART\s\*\[:\-\]\?\s\*\(\[A\-Z0\-9\-\]\+\)',

    r'\b\d\{2\}-\d\{3,5\}-\d\+\b',

    r'\b21\d\{6,9\}\b',
]


INVALID_PART_CONTEXT = [
    'RAW MATERIAL',
    'RAW MATERIAL NO',
    'MATERIAL NO',
    'RESIN NO',
    'RESIN NUMBER',
    'MATERIAL NUMBER',
    'COLOR NO',
    'PIGMENT',
    'SUPPLIER',
    r'?\s*([A-Z0-9\-]+)',
    r'PART\s*NO\.?\s*[:\-]?\s*([A-Z0-9\-]+)',
    r'P\/N\s*[:\-]?\s*([A-Z0-9\-]+)',
    r'NUMBER\s*PART\s*[:\-]?\s*([A-Z0-9\-]+)',
    r'\b\d{2}-\d{3,5}-\d+\b',
    r'\b21\d{6,9}\b',
] 


MATERIAL_KEYWORDS = [

    'MATERIAL',
    'RESIN',
    'PRIMARY MATERIAL',
]


COLOR_KEYWORDS = [

    'BLACK',
    'BK',
    'BLK',
    'WHITE',
    'WHT',
    'GRAY',
    'GREY',
    'NATURAL',
    'CLEAR'
]


def extract_text_from_pdf(pdf_path):

    doc = fitz.open(pdf_path)

    full_text = []

    for page in doc:

        text = page.get_text("text")

        full_text.append(text)

    combined = "\n".join(full_text)

    # Si PDF no tiene texto
    if len(combined.strip()) < 50:

        combined = extract_text_with_ocr(
            pdf_path
        )

    return combined


def extract_part_numbers(text):

    found = set()

    lines = text.splitlines()

    for line in lines:

        upper_line = line.upper().strip()

        if any(
            invalid in upper_line
            for invalid in INVALID_PART_CONTEXT
        ):
            continue

        for pattern in PART_PATTERNS:

            matches = re.findall(
                pattern,
                upper_line,
                re.IGNORECASE
            )

            for match in matches:

                if isinstance(match, tuple):
                    match = match[0]

                clean = match.strip()

                if len(clean) < 5:
                    continue

                if clean.startswith('RM'):
                    continue

                if clean.startswith('MAT'):
                    continue

                found.add(clean)

    return list(found)


def extract_material_lines(text):

    candidates = []

    lines = text.splitlines()

    for i, line in enumerate(lines):

        clean = line.upper().strip()

        if any(
            keyword in clean
            for keyword in MATERIAL_KEYWORDS
        ):

            block = clean

            if i + 1 < len(lines):

                next_line = (
                    lines[i + 1]
                    .upper()
                    .strip()
                )

                block += " " + next_line

            candidates.append({
                "text": block,
                "position": text.find(line)
            })

    return candidates


def extract_color(text):

    upper = text.upper()

    for color in COLOR_KEYWORDS:

        if color in upper:
            return color

    return None


def extract_volume(text):

    patterns = [

        r'VOLUME\s*[:\-]?\s*([\d\.]+)',

        r'PART\s*VOLUME\s*[:\-]?\s*([\d\.]+)',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            try:
                return float(match.group(1)) / 1000

            except:
                pass

    return None


def extract_weight(text):
    patterns = [
      
        r'\b(?:PART\s+|NET\s+|EST\.?\s+)?WT\.?\b\s*[^0-9\.\,]*([\d\.,]+)',
        r'\b(?:PART\s+|NET\s+|EST\.?\s+)?WEIGHT\b\s*[^0-9\.\,]*([\d\.,]+)',
        
        r'\bMASS(?:E)?\b\s*[^0-9\.\,]*([\d\.,]+)',
        r'\bMAßE\b\s*[^0-9\.\,]*([\d\.,]+)',
        
        r'\bPESO\b\s*[^0-9\.\,]*([\d\.,]+)',
    ]

    text_clean = text.upper().replace('\n', ' ')

    for pattern in patterns:
        match = re.search(pattern, text_clean)
        if match:
            try:
                num_str = match.group(1).replace(',', '.')
                return float(num_str)
            except:
                pass

    return None
