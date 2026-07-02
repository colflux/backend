from django.db import models

from .base import TimestampedModel
from .geo import Municipio, SistemaReferencia
from .cobertura import Cobertura, Disturbio, Vegetacion


class Sitio(TimestampedModel):
    PENDIENTE_CHOICES = [
        ("plano", "Plano"),
        ("ondulado_variable", "Ondulado / variable"),
        ("valle_fondo", "Valle / fondo"),
        ("pendiente_suave", "Pendiente suave (<2%)"),
        ("pendiente_media", "Pendiente media (2–5%)"),
        ("pendiente_significativa", "Pendiente significativa (5–10%)"),
        ("pendiente_fuerte", "Pendiente fuerte (>10%)"),
        ("cresta_cima", "Cresta / cima"),
    ]
    TOPOGRAFIA_CHOICES = [
        ("cresta_cima", "Cresta / cima"),
        ("ladera_superior", "Ladera superior"),
        ("ladera_media", "Ladera media"),
        ("ladera_inferior", "Ladera inferior"),
        ("valle_fondo", "Valle / fondo"),
        ("plano", "Plano"),
    ]
    USO_ACTUAL_CHOICES = [
        ("Bosque_primario", "Bosque primario"),
        ("Bosque_secundario", "Bosque secundario"),
        ("Plantacion_forestal", "Plantación forestal"),
        ("Agricultura_intensiva", "Agricultura intensiva"),
        ("Agricultura_tradicional", "Agricultura tradicional"),
        ("Pastura", "Pastura"),
        ("Humedal_natural", "Humedal natural"),
        ("Humedal_intervenido", "Humedal intervenido"),
        ("Area_protegida", "Área protegida"),
        ("Sistema_agroforestal", "Sistema agroforestal"),
        ("Abandonado", "Abandonado"),
        ("Restauracion_activa", "Restauración activa"),
    ]
    PROPIEDAD_CHOICES = [
        ("publica", "Pública"),
        ("privada", "Privada"),
    ]

    codigo_metadatos = models.CharField("código de metadatos", max_length=80, blank=True)
    nombre = models.CharField("nombre", max_length=255)

    latitud = models.DecimalField("latitud", max_digits=10, decimal_places=7)
    longitud = models.DecimalField("longitud", max_digits=10, decimal_places=7)
    sistema_referencia = models.ForeignKey(
        SistemaReferencia, on_delete=models.PROTECT, related_name="sitios",
        null=True, blank=True,
    )
    altitud = models.DecimalField("altitud (m.s.n.m.)", max_digits=8, decimal_places=2, null=True, blank=True)
    pendiente = models.CharField("pendiente", max_length=30, choices=PENDIENTE_CHOICES, blank=True)
    topografia = models.CharField("topografía", max_length=24, choices=TOPOGRAFIA_CHOICES, blank=True)
    uso_actual = models.CharField("uso actual del suelo", max_length=30, choices=USO_ACTUAL_CHOICES, blank=True)
    propiedad_tierra = models.CharField("propiedad de la tierra", max_length=10, choices=PROPIEDAD_CHOICES, blank=True)
    intervenido = models.BooleanField("intervenido", default=False)

    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name="sitios", null=True, blank=True)
    disturbio = models.ForeignKey(Disturbio, on_delete=models.SET_NULL, related_name="sitios", null=True, blank=True)
    vegetacion = models.ForeignKey(Vegetacion, on_delete=models.SET_NULL, related_name="sitios", null=True, blank=True)
    cobertura = models.ForeignKey(Cobertura, on_delete=models.SET_NULL, related_name="sitios", null=True, blank=True)

    class Meta:
        verbose_name = "sitio"
        verbose_name_plural = "sitios"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Parcela(TimestampedModel):
    UNIDAD_CHOICES = [
        ("Parcela_permanente_cuadrada", "Parcela permanente cuadrada"),
        ("Parcela_permanente_rectangular", "Parcela permanente rectangular"),
        ("Parcela_circular", "Parcela circular"),
        ("Transecto_lineal", "Transecto lineal"),
        ("Puntos_de_muestreo_aleatorios", "Puntos de muestreo aleatorios"),
        ("Conglomerado", "Conglomerado"),
    ]
    ESTATUS_CHOICES = [
        ("Activa", "Activa"),
        ("Inactiva", "Inactiva"),
        ("Abandonada", "Abandonada"),
        ("Finalizada", "Finalizada"),
    ]

    sitio = models.ForeignKey(Sitio, on_delete=models.PROTECT, related_name="parcelas")
    unidad_muestreo = models.CharField("unidad de muestreo", max_length=40, choices=UNIDAD_CHOICES, blank=True)
    area = models.DecimalField("área (m²)", max_digits=12, decimal_places=2, null=True, blank=True)
    estatus = models.CharField("estatus", max_length=20, choices=ESTATUS_CHOICES, blank=True)
    fecha_instalacion = models.PositiveIntegerField("año de instalación", null=True, blank=True)

    class Meta:
        verbose_name = "parcela"
        verbose_name_plural = "parcelas"
        ordering = ["sitio", "pk"]

    def __str__(self):
        return f"Parcela {self.pk} — {self.sitio}"


class Transecto(TimestampedModel):
    nombre = models.CharField("nombre", max_length=255)
    descripcion = models.CharField("descripción", max_length=255, blank=True)
    sitio = models.ForeignKey(Sitio, on_delete=models.PROTECT, related_name="transectos")
    parcela = models.ForeignKey(Parcela, on_delete=models.SET_NULL, related_name="transectos", null=True, blank=True)

    class Meta:
        verbose_name = "transecto"
        verbose_name_plural = "transectos"
        ordering = ["sitio", "nombre"]

    def __str__(self):
        return f"{self.nombre} — {self.sitio}"


class MonitoreoParcela(TimestampedModel):
    TIPO_CHOICES = [
        ("Biomasa_Aerea", "Biomasa aérea"),
        ("Biomasa_Subterranea", "Biomasa subterránea"),
        ("Flora", "Flora"),
        ("Rasgos_Funcionales", "Rasgos funcionales"),
    ]
    PROTOCOLO_CHOICES = [
        ("Alometria_destructiva", "Alometría destructiva"),
        ("Alometria_no_destructiva", "Alometría no destructiva"),
        ("LiDAR_terrestre", "LiDAR terrestre"),
        ("LiDAR_aerotransportado", "LiDAR aerotransportado"),
    ]

    parcela = models.ForeignKey(Parcela, on_delete=models.PROTECT, related_name="monitoreos")
    tipo_monitoreo = models.CharField("tipo de monitoreo", max_length=30, choices=TIPO_CHOICES)
    activo = models.BooleanField("activo", default=True)
    protocolo = models.CharField("protocolo", max_length=40, choices=PROTOCOLO_CHOICES, blank=True)

    class Meta:
        verbose_name = "monitoreo de parcela"
        verbose_name_plural = "monitoreos de parcela"
        unique_together = [("parcela", "tipo_monitoreo")]

    def __str__(self):
        return f"{self.get_tipo_monitoreo_display()} — {self.parcela}"
