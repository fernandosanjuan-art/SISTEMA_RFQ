MATERIAL_ALIASES = {

    "LEXAN": "PC",

    "CYCOLOY": "PC/ABS",

    "ULTRAMID": "PA6",

    "ZYTEL": "PA66",

    "PBT": "PBT",

    "CELANEX": "PBT",

    "DELRIN": "POM",
}

def normalize_material(text):

    upper = text.upper()

    for alias, family in MATERIAL_ALIASES.items():

        if alias in upper:
            return family

    return None