from django.db import models

from .base import TimestampedModel
from .sitio import UnidadMuestreo


class MuestraMOM(TimestampedModel):
    """Contenido de carbono en materia orgánica muerta (MOM) de una unidad de muestreo, por pool IPCC."""

    unidad_muestreo = models.ForeignKey(
        UnidadMuestreo, on_delete=models.PROTECT, related_name="muestras_mom",
        verbose_name="unidad de muestreo",
    )
    fecha = models.DateField("fecha", null=True, blank=True, help_text="Fecha de la medición.")

    carbono_mom_valor_reportado = models.DecimalField(
        "carbono MOM (valor reportado)", max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Contenido de carbono en MOM, valor tal como lo reporta la fuente.",
    )
    carbono_mom_tc_ha = models.DecimalField(
        "carbono MOM total (tC/ha)", max_digits=10, decimal_places=4, null=True, blank=True,
    )
    error_mom = models.CharField("medida de error MOM (SD;EE;U%)", max_length=80, blank=True)

    carbono_amp_tm_tc_ha = models.DecimalField(
        "carbono AMP+TM (tC/ha)", max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Carbono en árboles muertos en pie (AMP) y tocones muertos (TM), en toneladas de carbono por hectárea.",
    )
    error_amp_tm = models.CharField("medida de error AMP_TM (SD;EE;U%)", max_length=80, blank=True)

    carbono_dfm_tc_ha = models.DecimalField(
        "carbono DFM (tC/ha)", max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Carbono en detritos finos de madera (DFM), en toneladas de carbono por hectárea.",
    )
    error_dfm = models.CharField("medida de error DFM (SD;EE;U%)", max_length=80, blank=True)

    carbono_dgm_tc_ha = models.DecimalField(
        "carbono DGM (tC/ha)", max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Carbono en detritos gruesos de madera (DGM), en toneladas de carbono por hectárea.",
    )
    error_dgm = models.CharField("medida de error DGM (SD;EE;U%)", max_length=80, blank=True)

    carbono_hojarasca_g_m2 = models.DecimalField(
        "carbono en hojarasca (g/m²)", max_digits=10, decimal_places=4, null=True, blank=True,
    )
    carbono_hojarasca_tc_ha = models.DecimalField(
        "carbono en hojarasca (tC/ha)", max_digits=10, decimal_places=4, null=True, blank=True,
    )
    error_hojarasca = models.CharField("medida de error hojarasca (SD;EE;U%)", max_length=80, blank=True)

    metodologia_muestreo_mom = models.CharField("metodología: muestreo MOM", max_length=255, blank=True)
    metodologia_muestreo_dfm_dgm = models.CharField("metodología: muestreo DFM-DGM", max_length=255, blank=True)
    metodologia_tamano = models.CharField("metodología: tamaño", max_length=255, blank=True)
    metodologia_amp_to = models.CharField("metodología: AMP y TO", max_length=255, blank=True)
    metodologia_hojarasca = models.CharField("metodología: hojarasca", max_length=255, blank=True)

    class Meta:
        verbose_name = "muestra de materia orgánica muerta"
        verbose_name_plural = "muestras de materia orgánica muerta"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Muestra MOM {self.pk} — {self.unidad_muestreo}"
