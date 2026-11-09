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
    """Serie de una variable de torre EC (ej. flujo de CO₂, u*, NEE): mismo rol que `MuestraGEI`, pero para datos de torre en vez de cámaras manuales."""

    TIPO_VARIABLE_CHOICES = [
        # Eddypro: flujos + control de calidad
        ("co2_flux", "Flujo de CO₂"),
        ("ch4_flux", "Flujo de CH₄"),
        ("h2o_flux", "Flujo de H₂O"),
        ("h_flux", "Calor sensible (H)"),
        ("le_flux", "Calor latente (LE)"),
        ("tau", "Esfuerzo cortante (Tau)"),
        # Eddypro: turbulencia
        ("ustar", "Velocidad de fricción (u*)"),
        ("tke", "Energía cinética turbulenta (TKE)"),
        ("monin_obukhov_length", "Longitud de Monin-Obukhov (L)"),
        ("bowen_ratio", "Razón de Bowen"),
        # Eddypro: footprint
        ("footprint_x_peak", "Footprint x_peak"),
        ("footprint_x_70", "Footprint x_70%"),
        ("footprint_x_90", "Footprint x_90%"),
        # Eddypro: aire / viento
        ("air_temperature", "Temperatura del aire"),
        ("air_pressure", "Presión atmosférica"),
        ("relative_humidity", "Humedad relativa"),
        ("vpd", "Déficit de presión de vapor (VPD)"),
        ("air_density", "Densidad del aire"),
        ("wind_speed", "Velocidad del viento"),
        ("wind_dir", "Dirección del viento"),
        # ReddyProc: postprocesamiento (gap-filling + partición)
        ("nee_f", "NEE con gap-filling"),
        ("reco", "Respiración del ecosistema (Reco)"),
        ("gpp_f", "Productividad primaria bruta (GPP)"),
        ("ustar_used", "Umbral de u* usado en el filtrado"),
    ]

    torre = models.ForeignKey(TorreEc, on_delete=models.PROTECT, related_name="muestras_torre")
    fuente_datos = models.ForeignKey(
        "app.FuenteDatos", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="muestras_torre", verbose_name="fuente de datos",
    )
    tipo_variable = models.CharField("variable", max_length=30, choices=TIPO_VARIABLE_CHOICES)
    unidad_medida = models.ForeignKey(
        "app.UnidadMedida", on_delete=models.PROTECT, related_name="muestras_torre",
        null=True, blank=True, verbose_name="unidad de medida",
    )

    class Meta:
        verbose_name = "muestra de torre"
        verbose_name_plural = "muestras de torre"
        ordering = ["torre", "tipo_variable"]

    def __str__(self):
        return f"{self.torre} — {self.get_tipo_variable_display()}"


class SubMuestraTorre(TimestampedModel):
    """Valor diario de una `MuestraTorre`: mismo rol que `SubmuestraGEI`, una fila por día en vez de por toma."""

    muestra = models.ForeignKey(MuestraTorre, on_delete=models.CASCADE, related_name="submuestras")
    fecha = models.DateField("fecha")
    valor = models.DecimalField(
        "valor del flujo", max_digits=14, decimal_places=6, null=True, blank=True,
        help_text="Valor promedio del día para la variable de la muestra (MuestraTorre.tipo_variable).",
    )
    pct_calidad_buena = models.DecimalField(
        "% calidad buena", max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="% de filas semihorarias usadas en el promedio con flag de calidad 0 (bueno). Solo aplica a variables de Eddypro.",
    )
    n_registros_validos = models.PositiveSmallIntegerField(
        "registros válidos", null=True, blank=True,
        help_text="Cantidad de filas semihorarias que entraron al promedio de este día.",
    )

    class Meta:
        verbose_name = "submuestra de torre"
        verbose_name_plural = "submuestras de torre"
        ordering = ["muestra", "fecha"]
        unique_together = [("muestra", "fecha")]

    def __str__(self):
        return f"{self.muestra} — {self.fecha}"
