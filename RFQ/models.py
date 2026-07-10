# models.py

from django.db import models


class Material(models.Model):

    material_code = models.CharField(
        max_length=100, 
        unique=True
    )

    material_type = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    commercial_name = models.CharField(
        max_length=255
    )

    family = models.CharField(
        max_length=100
    )

    supplier = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    unit = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )

    standard_price = models.FloatField(
        null=True,
        blank=True
    )

    notes = models.TextField(
        null=True,
        blank=True
    )

    payment_terms = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    density = models.FloatField(
        null=True,
        blank=True
    )

    color = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    glass_fill = models.FloatField(
        default=0
    )

    # NUEVOS CAMPOS

    alternate_names = models.TextField(
        null=True,
        blank=True
    )

    manufacturer_code = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    base_resin = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    is_reinforced = models.BooleanField(
        default=False
    )

    reinforcement_type = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    pigment = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    glass_fill = models.FloatField(default=0)

    last_purchase_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Last modification date"
    )
    last_price = models.FloatField(
        null=True, 
        blank=True,
        verbose_name="Last price"
    )

    class Meta:
       
        indexes = [
            models.Index(fields=['material_code']),
            models.Index(fields=['commercial_name']),
            models.Index(fields=['family']),
        ]

    def __str__(self):
        return f"{self.material_code} - {self.commercial_name}"


class DrawingAnalysis(models.Model):
    total_files = models.IntegerField(default=0)
    processed_files = models.IntegerField(default=0)
    uploaded_file = models.FileField(
        upload_to='rfq_drawings/'
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )
    
    gemini_raw_json = models.JSONField(null=True, blank=True)

    # LEGACY
    part_number = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    # LEGACY
    material_text = models.TextField(
        null=True,
        blank=True
    )

    # LEGACY
    detected_material = models.ForeignKey(
        Material,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    estimated_volume = models.FloatField(
        null=True,
        blank=True
    )

    estimated_weight = models.FloatField(
        null=True,
        blank=True
    )

    confidence = models.FloatField(
        default=0
    )

    raw_text = models.TextField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=50,
        default='pending'
    )

    def __str__(self):

        return (
            self.part_number or
            f"Analysis {self.id}"
        )


class DrawingDetectedMaterial(models.Model):

    analysis = models.ForeignKey(
        DrawingAnalysis,
        related_name='detected_materials',
        on_delete=models.CASCADE
    )

    part_number = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    raw_material_text = models.TextField(
        null=True,
        blank=True
    )

    detected_material = models.ForeignKey(
        Material,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    detected_family = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    detected_color = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    detected_pigment = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    detected_supplier = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    glass_fill = models.FloatField(
        null=True,
        blank=True
    )
    
    component_weight = models.FloatField(null=True, blank=True)
    component_volumen = models.FloatField(null=True, blank=True)

    confidence = models.FloatField(
        default=0
    )

    text_position = models.IntegerField(
        null=True,
        blank=True
    )

    bom_reference = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):

        material = (
            self.detected_material.material_code
            if self.detected_material
            else "UNKNOWN"
        )

        return (
            f"{self.part_number} -> {material}"
        )


class PartComponent(models.Model):

    parent = models.ForeignKey(
        DrawingAnalysis,
        related_name='components',
        on_delete=models.CASCADE
    )

    child_part_number = models.CharField(
        max_length=100
    )

    estimated_weight = models.FloatField(
        default=0
    )

    quantity = models.IntegerField(
        default=1
    )

    def __str__(self):

        return self.child_part_number