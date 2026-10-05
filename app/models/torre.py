from django.db import models

from .base import TimestampedModel
from .co2 import Equipo
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


class MuestraTorre(TimestampedModel):
    """Ancla de identidad de un registro semihorario de torre EC: torre + instante de tiempo."""

    torre = models.ForeignKey(TorreEc, on_delete=models.CASCADE, related_name="muestras_torre")
    fecha = models.DateField("fecha")
    hora = models.TimeField("hora")

    class Meta:
        verbose_name = "muestra de torre"
        verbose_name_plural = "muestras de torre"
        ordering = ["torre", "fecha", "hora"]
        unique_together = [("torre", "fecha", "hora")]

    def __str__(self):
        return f"{self.torre} — {self.fecha} {self.hora}"


class SubmuestraEddy(TimestampedModel):
    """Datos de salida de Eddypro para un registro semihorario de torre EC. Obligatoria por cada `MuestraTorre`."""

    muestra = models.OneToOneField(MuestraTorre, on_delete=models.CASCADE, related_name="submuestra_eddy")

    # Flujos corregidos y su control de calidad
    co2_flux = models.DecimalField("flujo CO₂", max_digits=14, decimal_places=6, null=True, blank=True)
    qc_co2_flux = models.PositiveSmallIntegerField("flag calidad CO₂", null=True, blank=True)
    rand_err_co2_flux = models.DecimalField("error aleatorio CO₂", max_digits=14, decimal_places=6, null=True, blank=True)

    ch4_flux = models.DecimalField("flujo CH₄", max_digits=14, decimal_places=6, null=True, blank=True)
    qc_ch4_flux = models.PositiveSmallIntegerField("flag calidad CH₄", null=True, blank=True)
    rand_err_ch4_flux = models.DecimalField("error aleatorio CH₄", max_digits=14, decimal_places=6, null=True, blank=True)

    h2o_flux = models.DecimalField("flujo H₂O", max_digits=14, decimal_places=6, null=True, blank=True)
    qc_h2o_flux = models.PositiveSmallIntegerField("flag calidad H₂O", null=True, blank=True)
    rand_err_h2o_flux = models.DecimalField("error aleatorio H₂O", max_digits=14, decimal_places=6, null=True, blank=True)

    h_flux = models.DecimalField("calor sensible (H)", max_digits=14, decimal_places=6, null=True, blank=True)
    qc_h_flux = models.PositiveSmallIntegerField("flag calidad H", null=True, blank=True)
    rand_err_h_flux = models.DecimalField("error aleatorio H", max_digits=14, decimal_places=6, null=True, blank=True)

    le_flux = models.DecimalField("calor latente (LE)", max_digits=14, decimal_places=6, null=True, blank=True)
    qc_le_flux = models.PositiveSmallIntegerField("flag calidad LE", null=True, blank=True)
    rand_err_le_flux = models.DecimalField("error aleatorio LE", max_digits=14, decimal_places=6, null=True, blank=True)

    tau = models.DecimalField("esfuerzo cortante (Tau)", max_digits=14, decimal_places=6, null=True, blank=True)
    qc_tau = models.PositiveSmallIntegerField("flag calidad Tau", null=True, blank=True)
    rand_err_tau = models.DecimalField("error aleatorio Tau", max_digits=14, decimal_places=6, null=True, blank=True)

    # Turbulencia
    ustar = models.DecimalField("velocidad de fricción (u*)", max_digits=10, decimal_places=6, null=True, blank=True)
    tke = models.DecimalField("energía cinética turbulenta (TKE)", max_digits=14, decimal_places=6, null=True, blank=True)
    monin_obukhov_length = models.DecimalField("longitud de Monin-Obukhov (L)", max_digits=14, decimal_places=4, null=True, blank=True)
    bowen_ratio = models.DecimalField("razón de Bowen", max_digits=14, decimal_places=6, null=True, blank=True)

    # Footprint
    footprint_x_peak = models.DecimalField("footprint x_peak (m)", max_digits=10, decimal_places=2, null=True, blank=True)
    footprint_x_70 = models.DecimalField("footprint x_70% (m)", max_digits=10, decimal_places=2, null=True, blank=True)
    footprint_x_90 = models.DecimalField("footprint x_90% (m)", max_digits=10, decimal_places=2, null=True, blank=True)

    # Aire / viento
    air_temperature = models.DecimalField("temperatura del aire (°C)", max_digits=6, decimal_places=2, null=True, blank=True)
    air_pressure = models.DecimalField("presión atmosférica (Pa)", max_digits=10, decimal_places=2, null=True, blank=True)
    relative_humidity = models.DecimalField("humedad relativa (%)", max_digits=5, decimal_places=2, null=True, blank=True)
    vpd = models.DecimalField("déficit de presión de vapor (VPD, Pa)", max_digits=10, decimal_places=2, null=True, blank=True)
    air_density = models.DecimalField("densidad del aire (kg/m³)", max_digits=8, decimal_places=4, null=True, blank=True)
    wind_speed = models.DecimalField("velocidad del viento (m/s)", max_digits=8, decimal_places=4, null=True, blank=True)
    wind_dir = models.DecimalField("dirección del viento (°)", max_digits=6, decimal_places=2, null=True, blank=True)

    # Resto de las columnas de Eddypro no modeladas individualmente todavía
    # (varianzas/covarianzas, spikes, diagnósticos propios de LI-7200/LI-7700).
    datos_extra = models.JSONField("datos adicionales", null=True, blank=True)

    class Meta:
        verbose_name = "submuestra Eddypro"
        verbose_name_plural = "submuestras Eddypro"

    def __str__(self):
        return f"Eddy — {self.muestra}"


class SubmuestraReddy(TimestampedModel):
    """Datos de salida de ReddyProc para un registro semihorario de torre EC. Opcional: solo existe si la torre tiene ese postprocesamiento."""

    muestra = models.OneToOneField(MuestraTorre, on_delete=models.CASCADE, related_name="submuestra_reddy")

    nee_f = models.DecimalField("NEE con gap-filling", max_digits=14, decimal_places=6, null=True, blank=True)
    nee_fqc = models.PositiveSmallIntegerField("flag calidad gap-filling NEE", null=True, blank=True)
    reco = models.DecimalField("respiración del ecosistema (Reco)", max_digits=14, decimal_places=6, null=True, blank=True)
    gpp_f = models.DecimalField("productividad primaria bruta (GPP)", max_digits=14, decimal_places=6, null=True, blank=True)
    ustar_used = models.DecimalField("umbral de u* usado en el filtrado", max_digits=10, decimal_places=6, null=True, blank=True)

    # Resto de las columnas de ReddyProc no modeladas individualmente todavía.
    datos_extra = models.JSONField("datos adicionales", null=True, blank=True)

    class Meta:
        verbose_name = "submuestra ReddyProc"
        verbose_name_plural = "submuestras ReddyProc"

    def __str__(self):
        return f"Reddy — {self.muestra}"
