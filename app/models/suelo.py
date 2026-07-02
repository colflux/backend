from django.db import models

from .base import TimestampedModel
from .sitio import Sitio


class CaracterizacionMuestreoSuelo(TimestampedModel):
    TIPO_SUELO_CHOICES = [
        ("Mineral", "Mineral"),
        ("Organico", "Orgánico"),
    ]

    sitio = models.ForeignKey(Sitio, on_delete=models.PROTECT, related_name="caracterizaciones_suelo")
    muestreo_id = models.PositiveIntegerField("ID de muestreo")
    tipo_de_suelo = models.CharField("tipo de suelo", max_length=10, choices=TIPO_SUELO_CHOICES, blank=True)
    profundidad_perfil = models.DecimalField("profundidad del perfil (cm)", max_digits=8, decimal_places=2, null=True, blank=True)
    intervalos_perfil = models.DecimalField("intervalos del perfil (cm)", max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "caracterización muestreo suelo"
        verbose_name_plural = "caracterizaciones muestreo suelo"
        ordering = ["sitio", "muestreo_id"]

    def __str__(self):
        return f"Muestreo {self.muestreo_id} — {self.sitio}"


class MonitoreoSuelo(TimestampedModel):
    TIPO_CHOICES = [
        ("Macrofosiles", "Macrofósiles"),
        ("Datacion", "Datación"),
        ("Densidad_Aparente", "Densidad aparente"),
        ("COS", "Carbono orgánico del suelo (COS)"),
    ]
    PROTOCOLO_COS_CHOICES = [
        ("combustion_seca", "Combustión seca"),
        ("perdida_por_ignicion", "Pérdida por ignición (LOI)"),
        ("oxidacion_humeda", "Oxidación húmeda (Walkley-Black)"),
    ]

    caracterizacion = models.ForeignKey(
        CaracterizacionMuestreoSuelo, on_delete=models.CASCADE, related_name="monitoreos",
    )
    tipo_monitoreo = models.CharField("tipo de monitoreo", max_length=20, choices=TIPO_CHOICES)
    activo = models.BooleanField("activo", default=True)
    protocolo = models.CharField("protocolo", max_length=255, blank=True)

    class Meta:
        verbose_name = "monitoreo de suelo"
        verbose_name_plural = "monitoreos de suelo"
        unique_together = [("caracterizacion", "tipo_monitoreo")]

    def __str__(self):
        return f"{self.get_tipo_monitoreo_display()} — {self.caracterizacion}"
