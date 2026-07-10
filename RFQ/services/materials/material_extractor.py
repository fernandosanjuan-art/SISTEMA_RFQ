# material_extractor.py

import re


MATERIAL_PATTERNS = [

    r'(PC[\+\-\w\s]*)',
    r'(ABS[\+\-\w\s]*)',
    r'(PA66[\+\-\w\s]*)',
    r'(PA6[\+\-\w\s]*)',
    r'(PBT[\+\-\w\s]*)',
    r'(PP[\+\-\w\s]*)',
    r'(POM[\+\-\w\s]*)',
    r'(TPU[\+\-\w\s]*)',
    r'(PPE[\+\-\w\s]*)',
    r'(PC\/ABS[\+\-\w\s]*)',
]


COLOR_PATTERNS = [

    r'\bBLACK\b',
    r'\bBK\b',
    r'\bBLK\b',
    r'\bWHITE\b',
    r'\bWHT\b',
    r'\bCLEAR\b',
    r'\bNATURAL\b',
    r'\bGRAY\b',
    r'\bSILVER\b',
]


SUPPLIER_PATTERNS = [

    r'\bSABIC\b',
    r'\bBASF\b',
    r'\bDUPONT\b',
    r'\bCELANESE\b',
    r'\bDSM\b',
]


GF_PATTERN = r'GF[\-\s]?(\d+)'

PIGMENT_PATTERN = r'\b(BK\d+|COLOR\d+|MB\d+)\b'


def extract_material_candidates(text):

    candidates = []

    lines = text.splitlines()

    for line in lines:

        clean = line.upper().strip()

        material = None

        for pattern in MATERIAL_PATTERNS:

            match = re.search(pattern, clean)

            if match:

                material = match.group(1).strip()

                break

        if not material:
            continue

        color = None

        for pattern in COLOR_PATTERNS:

            match = re.search(pattern, clean)

            if match:

                color = match.group()

                break

        gf = None

        gf_match = re.search(
            GF_PATTERN,
            clean
        )

        if gf_match:
            gf = float(gf_match.group(1))

        pigment = None

        pigment_match = re.search(
            PIGMENT_PATTERN,
            clean
        )

        if pigment_match:
            pigment = pigment_match.group(1)

        supplier = None

        for pattern in SUPPLIER_PATTERNS:

            match = re.search(pattern, clean)

            if match:

                supplier = match.group()

                break

        candidates.append({

            "raw": clean,

            "material": material,

            "color": color,

            "gf": gf,

            "pigment": pigment,

            "supplier": supplier,

            "position": text.find(line)
        })

    return candidates