from django.db import models

from .base import TimestampedModel
from .sitio import Sitio, UnidadMuestreo


class CaracterizacionMuestreoSuelo(TimestampedModel):
    """Caracterización de un muestreo de suelo en un sitio: tipo de suelo, profundidad e intervalos del perfil."""

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
    """Tipo de monitoreo aplicado a una caracterización de suelo (COS, densidad aparente, datación, …) y su protocolo."""

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


class SubmuestraSuelo(TimestampedModel):
    """Toma de suelo por intervalo de profundidad en una unidad de muestreo: carbono orgánico del suelo (COS) y densidad aparente."""

    unidad_muestreo = models.ForeignKey(
        UnidadMuestreo, on_delete=models.PROTECT, related_name="submuestras_suelo",
        verbose_name="unidad de muestreo",
    )
    fecha = models.DateField("fecha", null=True, blank=True, help_text="Fecha en la que se realizó la toma.")
    hora = models.TimeField("hora", null=True, blank=True, help_text="Hora en la que se realizó la toma.")
    barreno_vol = models.CharField(
        "barreno / volumen", max_length=80, blank=True,
        help_text="Identificador o volumen del barreno/cilindro usado para la toma, tal como lo reporta la fuente.",
    )
    profundidad_desde_cm = models.DecimalField(
        "profundidad desde (cm)", max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Límite superior del intervalo de profundidad muestreado, en centímetros.",
    )
    profundidad_hasta_cm = models.DecimalField(
        "profundidad hasta (cm)", max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Límite inferior del intervalo de profundidad muestreado, en centímetros.",
    )
    densidad_aparente_g_cm3 = models.DecimalField(
        "densidad aparente (g/cm³)", max_digits=8, decimal_places=4, null=True, blank=True,
    )
    carbono_pct = models.DecimalField(
        "% carbono", max_digits=8, decimal_places=4, null=True, blank=True,
        help_text="Porcentaje de carbono orgánico medido en la toma.",
    )
    soil_chem_c_org = models.DecimalField(
        "SOIL_CHEM_C_ORG", max_digits=8, decimal_places=4, null=True, blank=True,
        help_text="Carbono orgánico del suelo reportado por la fuente (SOIL_CHEM_C_ORG).",
    )
    medida_error = models.CharField(
        "medida de error (SD;EE;U%)", max_length=80, blank=True,
        help_text="Error asociado reportado por la fuente: desviación estándar (SD), error estándar (EE) o incertidumbre (U%).",
    )
    metodologia_tipo_muestreo = models.CharField("metodología: tipo de muestreo", max_length=255, blank=True)
    metodologia_distancia_m = models.DecimalField(
        "metodología: distancia (m)", max_digits=8, decimal_places=2, null=True, blank=True,
    )
    metodologia_azimut = models.DecimalField(
        "metodología: azimut (°)", max_digits=6, decimal_places=2, null=True, blank=True,
    )
    metodologia_analisis = models.CharField("metodología: método de análisis", max_length=255, blank=True)

    class Meta:
        verbose_name = "submuestra de suelo"
        verbose_name_plural = "submuestras de suelo"
        ordering = ["unidad_muestreo", "profundidad_desde_cm"]

    def __str__(self):
        return f"Submuestra suelo {self.pk} — {self.unidad_muestreo}"
