from django.db import models

from .base import TimestampedModel
from .sitio import UnidadMuestreo


class MuestraBiomasa(TimestampedModel):
    """Evento de medición de producción de biomasa aérea en una unidad de muestreo, con el agregado de carbono de la parcela."""

    unidad_muestreo = models.ForeignKey(
        UnidadMuestreo, on_delete=models.PROTECT, related_name="muestras_biomasa",
        verbose_name="unidad de muestreo",
    )
    fecha = models.DateField("fecha", null=True, blank=True, help_text="Fecha de la medición.")
    prod_biomasa_g = models.DecimalField(
        "producción de biomasa (g)", max_digits=12, decimal_places=4, null=True, blank=True,
    )
    contenido_carbono = models.DecimalField(
        "contenido de carbono", max_digits=12, decimal_places=4, null=True, blank=True,
    )
    prom_tonc_ha = models.DecimalField(
        "promedio (TonC/ha)", max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Promedio de carbono en biomasa aérea de la parcela, en toneladas de carbono por hectárea.",
    )
    sd_tonc_ha = models.DecimalField(
        "desviación estándar (TonC/ha)", max_digits=10, decimal_places=4, null=True, blank=True,
    )
    min_tonc_ha = models.DecimalField(
        "mínimo (TonC/ha)", max_digits=10, decimal_places=4, null=True, blank=True,
    )
    max_tonc_ha = models.DecimalField(
        "máximo (TonC/ha)", max_digits=10, decimal_places=4, null=True, blank=True,
    )

    class Meta:
        verbose_name = "muestra de biomasa"
        verbose_name_plural = "muestras de biomasa"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Muestra biomasa {self.pk} — {self.unidad_muestreo}"


class IndividuoArboreo(TimestampedModel):
    """Medición de un individuo arbóreo dentro de una muestra de biomasa (DAP, altura, especie)."""

    muestra = models.ForeignKey(
        MuestraBiomasa, on_delete=models.CASCADE, related_name="individuos",
        verbose_name="muestra de biomasa",
    )
    tipo = models.CharField("tipo", max_length=80, blank=True)
    n_ind = models.PositiveIntegerField("número de individuo", null=True, blank=True)
    condicion = models.CharField("condición", max_length=80, blank=True)
    numero_fuste = models.CharField(
        "número de fuste", max_length=20, blank=True,
        help_text="Identificador del fuste dentro del individuo, tal como lo reporta la fuente.",
    )
    multiples = models.CharField(
        "múltiples", max_length=20, blank=True,
        help_text="Si el individuo tiene múltiples fustes, tal como lo reporta la fuente.",
    )
    dap_1 = models.DecimalField("DAP 1 (cm)", max_digits=8, decimal_places=2, null=True, blank=True)
    dap_2 = models.DecimalField("DAP 2 (cm)", max_digits=8, decimal_places=2, null=True, blank=True)
    dap_analisis_cm = models.DecimalField("DAP de análisis (cm)", max_digits=8, decimal_places=2, null=True, blank=True)
    equipo = models.CharField("equipo", max_length=120, blank=True)
    pom_m = models.DecimalField(
        "POM (m)", max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Point of Measurement: altura a la que se midió el DAP, en metros.",
    )
    altura_fuste_m = models.DecimalField("altura del fuste (m)", max_digits=6, decimal_places=2, null=True, blank=True)
    altura_total_m = models.DecimalField("altura total (m)", max_digits=6, decimal_places=2, null=True, blank=True)
    diff_alturas = models.DecimalField("diferencia de alturas (m)", max_digits=6, decimal_places=2, null=True, blank=True)
    familia = models.CharField("familia", max_length=120, blank=True)
    genero = models.CharField("género", max_length=120, blank=True)
    especie = models.CharField("especie", max_length=160, blank=True)

    class Meta:
        verbose_name = "individuo arbóreo"
        verbose_name_plural = "individuos arbóreos"
        ordering = ["muestra", "n_ind"]

    def __str__(self):
        return f"Individuo {self.n_ind} — {self.especie or self.tipo} ({self.muestra_id})"
