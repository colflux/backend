from django.db import models

from .base import TimestampedModel
from .sitio import Sitio


class ConfiguracionSensorGas(TimestampedModel):
    """Configuración del sensor de un gas (CO₂, CH₄, N₂O) en una torre EC: tubería y separaciones respecto al anemómetro."""

    GAS_CHOICES = [
        ("CO2", "CO₂"),
        ("CH4", "CH₄"),
        ("N2O", "N₂O"),
    ]

    torre = models.ForeignKey("TorreEc", on_delete=models.CASCADE, related_name="configuraciones_gas")
    gas = models.CharField("gas", max_length=4, choices=GAS_CHOICES)
    longitud_tubo = models.DecimalField("longitud del tubo (cm)", max_digits=8, decimal_places=2, null=True, blank=True)
    diametro_tubo = models.DecimalField("diámetro del tubo (mm)", max_digits=8, decimal_places=2, null=True, blank=True)
    separacion_norte_sur = models.DecimalField("separación N–S (m)", max_digits=8, decimal_places=4, null=True, blank=True)
    separacion_este_oeste = models.DecimalField("separación E–O (m)", max_digits=8, decimal_places=4, null=True, blank=True)
    separacion_vertical = models.DecimalField("separación vertical (m)", max_digits=8, decimal_places=4, null=True, blank=True)

    class Meta:
        verbose_name = "configuración sensor de gas"
        verbose_name_plural = "configuraciones sensores de gas"
        unique_together = [("torre", "gas")]

    def __str__(self):
        return f"{self.gas} — Torre {self.torre_id}"


class Equipo(TimestampedModel):
    """Equipo instalado en una torre EC (anemómetro, analizadores de gas, adquisición, …) con modelo y serial."""

    TIPO_CHOICES = [
        ("Anemometro", "Anemómetro"),
        ("Analizador_CO2", "Analizador CO₂"),
        ("Analizador_CH4", "Analizador CH₄"),
        ("Adquisicion", "Adquisición"),
        ("Retencion", "Retención"),
        ("Procesamiento", "Procesamiento"),
        ("Biomet", "Biomet"),
        ("Estacion_Complementaria", "Estación complementaria"),
    ]

    torre = models.ForeignKey("TorreEc", on_delete=models.CASCADE, related_name="equipos")
    tipo_equipo = models.CharField("tipo de equipo", max_length=30, choices=TIPO_CHOICES)
    modelo = models.CharField("modelo", max_length=120, blank=True)
    serial = models.CharField("serial", max_length=120, blank=True)

    class Meta:
        verbose_name = "equipo"
        verbose_name_plural = "equipos"
        ordering = ["torre", "tipo_equipo"]

    def __str__(self):
        return f"{self.get_tipo_equipo_display()} {self.modelo} — Torre {self.torre_id}"


class TorreEc(TimestampedModel):
    """Torre de covarianza de remolinos (eddy covariance) instalada en un sitio: alturas, frecuencia de adquisición y sensores."""

    sitio = models.ForeignKey(Sitio, on_delete=models.PROTECT, related_name="torres_ec")
    fecha_instalacion = models.DateField("fecha de instalación", null=True, blank=True)
    utc = models.CharField("UTC offset", max_length=10, blank=True)

    altura_canopy = models.DecimalField("altura del canopy (m)", max_digits=8, decimal_places=2, null=True, blank=True)
    altura_torre = models.DecimalField("altura de la torre (m)", max_digits=8, decimal_places=2, null=True, blank=True)
    altura_anemometro = models.DecimalField("altura del anemómetro (m)", max_digits=8, decimal_places=2, null=True, blank=True)

    frecuencia_adquisicion = models.DecimalField("frecuencia de adquisición (Hz)", max_digits=8, decimal_places=2, null=True, blank=True)
    north_offset = models.DecimalField("north offset (°)", max_digits=8, decimal_places=4, null=True, blank=True)

    equipo_principal = models.ForeignKey(
        Equipo, on_delete=models.SET_NULL, related_name="+",
        null=True, blank=True, verbose_name="equipo principal",
    )
    configuracion_principal = models.ForeignKey(
        ConfiguracionSensorGas, on_delete=models.SET_NULL, related_name="+",
        null=True, blank=True, verbose_name="configuración principal",
    )

    longitud_tubo_sensor_co2 = models.DecimalField("longitud tubo sensor CO₂ (cm)", max_digits=8, decimal_places=2, null=True, blank=True)
    diametro_tubo_sensor_co2 = models.DecimalField("diámetro tubo sensor CO₂ (mm)", max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "torre EC"
        verbose_name_plural = "torres EC"
        ordering = ["sitio"]

    def __str__(self):
        return f"Torre EC {self.pk} — {self.sitio}"


class TorreFuenteEnergia(TimestampedModel):
    FUENTE_CHOICES = [
        ("generador_metanol", "Generador metanol"),
        ("generador_gasolina", "Generador gasolina"),
        ("solar_mas_generador", "Solar + generador"),
        ("otro", "Otro"),
    ]

    torre = models.ForeignKey(TorreEc, on_delete=models.CASCADE, related_name="fuentes_energia")
    tipo_fuente = models.CharField("tipo de fuente", max_length=30, choices=FUENTE_CHOICES)
    numero_unidades_recepcion = models.PositiveIntegerField("unidades de recepción", null=True, blank=True)
    numero_unidades_almacenamiento = models.PositiveIntegerField("unidades de almacenamiento", null=True, blank=True)
    sistema_puesta_tierra = models.BooleanField("sistema de puesta a tierra", default=False)

    class Meta:
        verbose_name = "fuente de energía"
        verbose_name_plural = "fuentes de energía"

    def __str__(self):
        return f"{self.get_tipo_fuente_display()} — {self.torre}"
