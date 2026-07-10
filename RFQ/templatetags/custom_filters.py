from django import template

register = template.Library()

@register.filter(name='split_origin_name')

def split_origin_name(value):
    if not value:
        return ""
    if " | Origen:" in value:
        return value.split(" | Origen:")[0]
    return value


@register.filter(name='multiply_filter')
def multiply_filter(value, arg):
    """Multiplica el valor del campo por un argumento flotante"""
    try:
        if value is None or value == '':
            return 0
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter(name='round_filter')
def round_filter(value, decimals=2):
    """Redondea un número flotante al número de decimales indicado"""
    try:
        if value is None or value == '':
            return 0
        return round(float(value), int(decimals))
    except (ValueError, TypeError):
        return 0