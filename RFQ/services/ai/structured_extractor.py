import json
from RFQ.services.ai.gemini_service import ask_gemini

def extract_rfq_data(text):
    prompt = f"""
You are an expert AI specialized in injection molding and manufacturing RFQ technical analysis.

Analyze the text extracted from this engineering drawing/PDF and extract a structured JSON response.

CRITICAL MATERIAL DETECTION RULES:
1. PRIMARY MATERIAL PRIORITIZATION (Resins & Subcomponents):
   - Actively search for terms like "PRIMARY MATERIAL", "RESIN", or "MATERIAL" to identify the main production material.
   - NOTE: If the document is a subcomponent drawing, the primary material might NOT be a plastic resin. It can be any of the following:
     - Metal (Inserts, Brackets, Stamped/Cut parts, Screws)
     - Imanes / Magnets
     - Silicon / Silicone
     - Arneses / Wiring Harnesses
     - Adhesivos / Adhesives / Glue
     - Pintura / Paint / Coating
     - Pad Print / Tampografía / Ink
     - Antenas or componentes eléctricos / Antennas / PCB / Sensors
     - Gaskets / Seals / O-Rings
     - Pines / Pins / Terminals
   - Map these primary subcomponent materials into the main "materials" array. Set "name" to the exact text found and "resin_family" to the category type (e.g., "METAL", "MAGNET", "SILICONE", "ADHESIVE", "ELECTRICAL", "RUBBER").
   - DO NOT mix alternative/alternate materials into the primary "materials" list.

2. ALTERNATIVE MATERIALS & SUGGESTIONS:
   - If the document explicitly lists an "ALTERNATIVE MATERIAL", "ALTERNATE RESIN", "SUBSTITUTE", or a second material option (whether it's a resin or a subcomponent material), DO NOT put it inside the primary "materials" array.
   - Instead, place any detected alternative material inside the "alternative_material_suggestions" field at the part level.

3. MULTI-COMPONENT & SECONDARY MATERIALS DETECTION (CRITICAL FOR WEIGHT):
   - Check if the drawing describes a composite part, an overmolding assembly, or a part that contains embedded secondary elements (e.g., "Steel insert", "Silicone O-ring", "Co-injection", "Overmold").
   - If any secondary or embedded components made of different materials are found, map them into the "secondary_embedded_components" list so the system can calculate weight differences accurately.

CRITICAL DRAWING CLASSIFICATION RULE:
- Identify if this specific document text represents a 2D engineering drawing of an isolated individual subcomponent/insert rather than a complete primary mold assembly. Set the boolean flag "is_subcomponent_drawing" to true if it explicitly states it is a component, insert, secondary part, or if the geometric context implies it.

Return ONLY a valid JSON object or Array using this model structure:
{{
  "is_subcomponent_drawing": true/false,
  "customer": "Name",
  "parts": [
    {{
      "part_number": "String",
      "description": "String",
      "materials": [
        {{
          "name": "Exact Primary Material text found (e.g. RESIN POLYSULFONE)",
          "resin_family": "Family or Material Type (e.g. POLYSULFONE, ABS, PA12)",
          "color": "String or null (e.g. RAL 9003, BLACK)",
          "pigment": "String or null (e.g. 2% Masterbatch)",
          "supplier": "String or null"
        }}
      ],
      "alternative_material_suggestions": [
        {{
          "name": "Exact Alternative Material text found if present",
          "resin_family": "Family or Material Type",
          "color": "String or null",
          "supplier": "String or null"
        }}
      ],
      "secondary_embedded_components": [
        {{
          "component_name": "Name of the secondary element (e.g. BRASS THREADED INSERT, STEEL PIN)",
          "material_type": "METAL / SILICONE / RUBBER / O-RING",
          "quantity": integer or null
        }}
      ],
      "weight_grams": float or null,
      "volume_cm3": float or null
    }}
  ]
}}

TEXT TO ANALYZE:
{text}
"""
    response = ask_gemini(prompt)
    print("========= GEMINI RESPONSE =========")
    print(response)

    try:
        return json.loads(response)
    except Exception:
        return {
            "raw_response": response
        }