from django.contrib import admin

from .models import (
    Material,
    DrawingAnalysis,
    PartComponent
)


admin.site.register(Material)
admin.site.register(DrawingAnalysis)
admin.site.register(PartComponent)