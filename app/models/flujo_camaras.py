from django.db import models

from .base import TimestampedModel
from .sitio import Sitio


class FlujoCamaras(TimestampedModel):
    MICROTOPO_CHOICES = [
        ("Hummock", "Hummock (cojines)"),
        ("Hollow", "Hollow (depresiones húmedas)"),
        ("Pool", "Pool (charcos / sobre agua)"),
        ("Lawns", "Lawns (lugares planos)"),
    ]
    TIPO_VEGETACION_CHOICES = [
        ("Pasto_Graminea", "Pasto / Gramínea"),
        ("Graminea_C3", "Gramínea C3"),
        ("Graminea_C4", "Gramínea C4"),
        ("Cultivo_herbaceo", "Cultivo herbáceo"),
        ("Cultivo_lenoso", "Cultivo leñoso"),
        ("Arbol", "Árbol"),
        ("Arbol_caducifolio", "Árbol caducifolio"),
        ("Arbol_perennifolio", "Árbol perennifolio"),
        ("Arbusto", "Arbusto"),
        ("Hierba_Forbia", "Hierba / Forbia"),
        ("Hierba_anual_Forbia_anual", "Hierba anual / Forbia anual"),
        ("Hierba_perenne_Forbia_perenne", "Hierba perenne / Forbia perenne"),
        ("Plantas_con_aerenquima", "Plantas con aerénquima"),
        ("Liana_Enredadera", "Liana / Enredadera"),
        ("Suculenta", "Suculenta"),
        ("No_vasculares", "No vasculares"),
        ("Otro", "Otro"),
        ("Sin_vegetacion", "Sin vegetación"),
        ("Agua", "Agua"),
    ]

    sitio = models.ForeignKey(Sitio, on_delete=models.PROTECT, related_name="flujos_camara")
    camara_id = models.PositiveIntegerField("ID de cámara", null=True, blank=True)

    microtopografia = models.CharField("microtopografía", max_length=10, choices=MICROTOPO_CHOICES, blank=True)
    diametro_anillo = models.DecimalField("diámetro del anillo (cm)", max_digits=8, decimal_places=2, null=True, blank=True)
    tratamiento = models.CharField("tratamiento", max_length=255, blank=True)
    pozo_nivel_freatico = models.CharField("pozo / nivel freático", max_length=80, blank=True)

    cobertura_vegetal_primaria = models.CharField("cobertura vegetal primaria", max_length=40, choices=TIPO_VEGETACION_CHOICES, blank=True)
    porcentaje_cob_veg_pri = models.DecimalField("% cobertura primaria", max_digits=5, decimal_places=2, null=True, blank=True)
    cobertura_vegetal_secundaria = models.CharField("cobertura vegetal secundaria", max_length=40, choices=TIPO_VEGETACION_CHOICES, blank=True)
    porcentaje_cob_veg_sec = models.DecimalField("% cobertura secundaria", max_digits=5, decimal_places=2, null=True, blank=True)
    cobertura_vegetal_terciaria = models.CharField("cobertura vegetal terciaria", max_length=40, choices=TIPO_VEGETACION_CHOICES, blank=True)
    porcentaje_cob_veg_ter = models.DecimalField("% cobertura terciaria", max_digits=5, decimal_places=2, null=True, blank=True)

    distancia_drenaje = models.DecimalField("distancia a drenaje (m)", max_digits=10, decimal_places=2, null=True, blank=True)
    distancia_fuego = models.DecimalField("distancia a fuego (m)", max_digits=10, decimal_places=2, null=True, blank=True)
    distancia_pastoreo = models.DecimalField("distancia a pastoreo (m)", max_digits=10, decimal_places=2, null=True, blank=True)
    distancia_cultivo = models.DecimalField("distancia a cultivo (m)", max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "flujo cámaras"
        verbose_name_plural = "flujos cámaras"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["sitio"])]

    def __str__(self):
        return f"FlujoCámaras {self.pk} — {self.sitio}"
