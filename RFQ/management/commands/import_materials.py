import os
import re
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from RFQ.models import Material

DENSITY_MAP = {
    'PC' : 1.20, 'NYLON 6' : 1.13, 'ABS' : 1.04, 'PP' : 0.90,  
    'PBT' : 1.31, 'POM' : 1.41, 'POLYSULFONE' : 1.24, 'PPO' : 1.06, 
}

COLOR_MAP = {
    'BLACK': 'BLACK', 'BK' : 'BLACK', 'BLK' : 'BLACK', 'NEGRO' : 'BLACK',
    'CLEAR': 'CLEAR', 'CLR' : 'CLEAR', 'NATURAL' : 'NATURAL', 'NAT' : 'NATURAL',
    'WHITE' : 'WHITE', 'WHT' : 'WHITE', 'GRAY' : 'GRAY', 'GREY' : 'GRAY',
    'RED' : 'RED', 'RD' : 'RED', 'SILVER' : 'SILVER', 'SLR' : 'SILVER',
}

def clean_description(description):
    if not description: return ""
    description = str(description).upper()
    remove_words = ['RESIN', 'COLOR', 'MODIFIED', 'NATURAL', 'BLACK', 'GRADE']
    for word in remove_words:
        description = description.replace(word, '')
    return re.sub(r'\s+', ' ', description).strip()

def clean_price(value):
    import pandas as pd
    if pd.isna(value): return None
    value = str(value).replace('$', '').replace(',', '').strip()
    try: return float(value)
    except: return None

def clean_excel_date(value):
    import pandas as pd
    if pd.isna(value) or str(value).strip().lower() in ['nan', '']: return None
    try:
        if isinstance(value, datetime):
            return value.date()
        return pd.to_datetime(value).date()
    except:
        return None

class Command(BaseCommand): 
    help = 'Import materials from Excel including historical metadata safely'

    def handle(self, *args, **kwargs):
        import pandas as pd 
        
        file_path = os.path.join(settings.BASE_DIR, 'materials.xlsx')
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"Error: No se encontró el archivo en {file_path}. Asegúrate de renombrarlo a 'materials.xlsx' y subirlo a la raíz."))
            return

        df = pd.read_excel(file_path, header=1)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
        
        target_part_col = 'PART No.' if 'PART No.' in df.columns else 'PART No'
        
        # AJUSTE DE TOLERANCIA NPI: Removemos el dropna agresivo para capturar las 1289 líneas de pinturas/pigmentos
        if target_part_col not in df.columns:
            self.stdout.write(self.style.ERROR(f"Error: No se detectó la columna del número de parte."))
            return
            
        print("Columnas Indexadas con Éxito:", df.columns.tolist())
        
        count_success = 0
        
        for index, row in df.iterrows():
            try:
                raw_part = row.get(target_part_col)
                if pd.isna(raw_part):
                    continue
                    
                part_no = str(raw_part).strip()
                if not part_no or part_no.lower() in ['nan', '', 'none']: 
                    continue
                    
                description = str(row.get('DESCRIPTION:', '')).upper().strip() if not pd.isna(row.get('DESCRIPTION:')) else ""
                notes_text = str(row.get('Notes', '')).upper().strip() if not pd.isna(row.get('Notes')) else ""
                family = str(row.get('FAMILY', '')).upper().strip() if not pd.isna(row.get('FAMILY')) else "N/D"
                
                detected_color = "N/D"
                for key, value in COLOR_MAP.items():
                    if key in description or key in notes_text:
                        detected_color = value
                        break
                    
                glass_fill = 0
                gf_match = re.search(r'GF[\s\-]?(\d+)', description)
                if gf_match: 
                    glass_fill = float(gf_match.group(1))
                    
                density_val = row.get('DENSITY') or row.get('density')
                if pd.isna(density_val):
                    density = DENSITY_MAP.get(family, 1.10)
                else:
                    try: density = float(density_val)
                    except: density = DENSITY_MAP.get(family, 1.10)
                    
                if glass_fill > 0: 
                    density += (glass_fill * 0.003) 
                    
                raw_date = row.get('Last modification date') or row.get('Modification Date') or row.get('LAST MODIFICATION DATE')
                raw_last_price = row.get('Last price') or row.get('last price') or row.get('Last Price') or row.get('LAST PRICE')

                # CAPTURA DE TIPO DEL EXCEL (RESIN, PAINT, PIGMENT)
                excel_type = str(row.get('TYPE', 'RESIN')).upper().strip() if not pd.isna(row.get('TYPE')) else 'RESIN'

                Material.objects.update_or_create(
                    material_code=part_no,
                    defaults={
                        'material_type': excel_type,
                        'commercial_name': clean_description(row.get('DESCRIPTION:', '')),
                        'family': family,
                        'supplier': str(row.get('SUPPLIER / Distributor', '')).strip() if not pd.isna(row.get('SUPPLIER / Distributor')) else 'No especificado',
                        'unit': str(row.get('UNIT', 'LB')).strip() if not pd.isna(row.get('UNIT')) else 'LB',
                        'standard_price': clean_price(row.get('Standard price') or row.get('Standard Price')),
                        'notes': str(row.get('Notes', '')).strip() if not pd.isna(row.get('Notes')) else '',
                        'payment_terms' : str(row.get('TERM OF PAYMENTS', '')).strip() if not pd.isna(row.get('TERM OF PAYMENTS')) else '',
                        'density': round(density, 4),
                        'color' : detected_color,
                        'glass_fill': glass_fill,
                        'last_purchase_date': clean_excel_date(raw_date),
                        'last_price': clean_price(raw_last_price)
                    }
                )   
                count_success += 1
            except Exception as line_error:
                continue
                
        self.stdout.write(self.style.SUCCESS(f"Importación limpia finalizada: {count_success} registros procesados con éxito en la BD."))

        # Reconstruir índice SOLO después de importar los materiales
from RFQ.services.materials.embedding_matcher import build_material_index                  
build_material_index(force=True)   # <-- antes: build_material_index()
self.stdout.write(self.style.SUCCESS("Índice de IA de materiales reconstruido con éxito."))