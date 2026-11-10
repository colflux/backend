from django.db import models

from .base import TimestampedModel


class CoberturaManual(TimestampedModel):
    """Un valor de cobertura reportado para una unidad de muestreo, según un sistema de clasificación.

    Una misma unidad puede tener varias filas: una por sistema de clasificación,
    o varias del mismo sistema cuando distintas fuentes reportan valores en
    conflicto (no hay forma de saber cuál es "el correcto", así que se guardan
    todas en vez de que una pise a la otra). También así se reporta
    cobertura_vegetal_primaria/secundaria/terciaria: tres filas con
    tipo=Vegetación funcional y distinto orden_dominancia.
    """

    unidad_muestreo = models.ForeignKey(
        "app.UnidadMuestreo", on_delete=models.CASCADE, related_name="coberturas", verbose_name="unidad de muestreo",
    )
    tipo = models.ForeignKey(
        "app.ClasificacionTipo", on_delete=models.PROTECT, related_name="coberturas_reportadas",
        null=True, blank=True, verbose_name="tipo",
        help_text="Sistema de clasificación de este valor. Vacío si el valor de origen no matchea ningún sistema conocido.",
    )
    valor = models.ForeignKey(
        "app.ValorClasificacionTipo", on_delete=models.PROTECT, related_name="coberturas_reportadas",
        null=True, blank=True, verbose_name="valor",
        help_text="Vacío si el texto de origen no matchea ningún valor conocido del catálogo (ver valor_texto).",
    )
    ORDEN_DOMINANCIA_CHOICES = [
        ("Primaria", "Primaria"),
        ("Secundaria", "Secundaria"),
        ("Terciaria", "Terciaria"),
    ]
    porcentaje = models.DecimalField(
        "% cobertura", max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Porcentaje de cobertura que representa este tipo de vegetación dentro de la unidad de muestreo (ver orden_dominancia para distinguir primaria/secundaria/terciaria).",
    )
    orden_dominancia = models.CharField(
        "orden de dominancia", max_length=12, choices=ORDEN_DOMINANCIA_CHOICES, blank=True,
    )
    valor_texto = models.CharField(
        "valor (texto original)", max_length=160, blank=True,
        help_text="Texto tal como llegó en el import. Se llena siempre; valor queda vacío si no matcheó ningún catálogo.",
    )

    class Meta:
        verbose_name = "cobertura"
        verbose_name_plural = "coberturas"
        ordering = ["unidad_muestreo", "tipo"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidad_muestreo", "tipo", "valor"],
                name="cobertura_unica_por_unidad_tipo_valor",
            ),
        ]

    def __str__(self):
        return f"{self.valor} ({self.tipo or 'sin tipo'})"


class Vegetacion(TimestampedModel):
    """Caracterización de la vegetación de un sitio: tipo, especies dominantes, altura del dosel y estado sucesional."""

    TIPO_CHOICES = [
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

    tipo_cobertura = models.CharField("tipo de cobertura", max_length=40, choices=TIPO_CHOICES, blank=True)
    especies_dominantes = models.TextField("especies dominantes", blank=True)
    altura_dosel = models.DecimalField("altura del dosel (m)", max_digits=8, decimal_places=2, null=True, blank=True)
    porcentaje_cobertura = models.DecimalField("% cobertura", max_digits=5, decimal_places=2, null=True, blank=True)
    edad_cobertura = models.TextField("edad de la cobertura", blank=True)
    estado_sucesional = models.CharField("estado sucesional", max_length=120, blank=True)

    class Meta:
        verbose_name = "vegetación"
        verbose_name_plural = "vegetaciones"

    def __str__(self):
        return self.tipo_cobertura or f"Vegetación {self.pk}"


class Disturbio(TimestampedModel):
    """Catálogo de tipos de disturbio (fuego, sequía, pastoreo, …)."""

    nombre = models.CharField("nombre", max_length=60, unique=True)

    class Meta:
        verbose_name = "tipo de disturbio"
        verbose_name_plural = "tipos de disturbio"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class DisturbioManual(TimestampedModel):
    """Disturbio reportado para una unidad de muestreo (fechas, estado del ecosistema, si es el disturbio dominante).

    Mismo patrón de nombre que CoberturaManual/EcosistemaManual ("dato
    digitado" por el equipo de campo); antes se llamaba
    UnidadMuestreoDisturbio."""

    ESTADO_CHOICES = [
        ("Intacto", "Intacto"),
        ("Ligeramente_degradado", "Ligeramente degradado"),
        ("Moderadamente_degradado", "Moderadamente degradado"),
        ("Severamente_degradado", "Severamente degradado"),
        ("En_recuperacion_natural", "En recuperación natural"),
        ("En_restauracion_activa", "En restauración activa"),
        ("Estable", "Estable"),
        ("En_transicion", "En transición"),
    ]
    unidad_muestreo = models.ForeignKey(
        "app.UnidadMuestreo", on_delete=models.CASCADE, related_name="disturbios",
        verbose_name="unidad de muestreo",
    )
    tipo = models.ForeignKey(
        "app.ClasificacionTipo", on_delete=models.PROTECT, related_name="disturbios_unidad",
        null=True, blank=True, verbose_name="tipo",
    )
    valor = models.ForeignKey(
        "app.ValorClasificacionTipo", on_delete=models.PROTECT, related_name="disturbios_unidad",
        null=True, blank=True, verbose_name="valor",
        help_text="Vacío si el texto de origen no matchea ningún valor conocido del catálogo (ver valor_texto).",
    )
    valor_texto = models.CharField(
        "valor (texto original)", max_length=160, blank=True,
        help_text="Texto tal como llegó en el import. Se llena siempre; valor queda vacío si no matcheó ningún catálogo.",
    )
    descripcion = models.TextField("descripción", blank=True)
    fecha_inicio = models.DateField("fecha de inicio", null=True, blank=True)
    fecha_fin = models.DateField("fecha de fin", null=True, blank=True)
    incertidumbre_anios = models.PositiveIntegerField("incertidumbre (años)", null=True, blank=True)
    fecha_reporte = models.DateField("fecha de reporte", null=True, blank=True)
    anios_disturbio = models.PositiveIntegerField(
        "años de disturbio", null=True, blank=True,
        help_text="Cantidad de años que duró o lleva el disturbio.",
    )
    anios_desde_fin = models.PositiveIntegerField(
        "años desde fin del disturbio", null=True, blank=True,
        help_text="Cantidad de años transcurridos desde que terminó el disturbio (vacío si sigue activo).",
    )
    estado_actual = models.CharField("estado actual", max_length=30, choices=ESTADO_CHOICES, blank=True)
    es_dominante = models.BooleanField(
        "es el disturbio dominante", default=False,
        help_text="Si es el disturbio/manejo principal reportado para la unidad de muestreo, cuando hay varios registrados.",
    )

    class Meta:
        verbose_name = "disturbio de unidad de muestreo"
        verbose_name_plural = "disturbios de unidad de muestreo"
        ordering = ["unidad_muestreo", "tipo"]

    def __str__(self):
        return f"{self.valor or self.valor_texto} — {self.unidad_muestreo} ({self.fecha_inicio or 'sin fecha'})"


class FuenteExterna(TimestampedModel):
    """Catálogo de fuentes externas de disturbio (fuego, pastoreo, cultivo, drenaje) cuya cercanía a una unidad de muestreo se reporta como distancia."""

    nombre = models.CharField("nombre", max_length=40, unique=True)

    class Meta:
        verbose_name = "fuente externa"
        verbose_name_plural = "fuentes externas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class ExposicionExterna(TimestampedModel):
    """Qué tan cerca está una unidad de muestreo de una fuente de alteración ubicada en otro lugar (no un disturbio ocurrido en la unidad misma)."""

    unidad_muestreo = models.ForeignKey(
        "app.UnidadMuestreo", on_delete=models.CASCADE, related_name="exposiciones_externas",
        verbose_name="unidad de muestreo",
    )
    fuente = models.ForeignKey(
        FuenteExterna, on_delete=models.PROTECT, related_name="exposiciones",
        verbose_name="fuente externa",
    )
    distancia_m = models.DecimalField(
        "distancia (m)", max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Distancia en metros desde la unidad de muestreo hasta la fuente externa indicada (ver fuente).",
    )

    class Meta:
        verbose_name = "exposición externa"
        verbose_name_plural = "exposiciones externas"
        ordering = ["unidad_muestreo", "fuente"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidad_muestreo", "fuente"],
                name="exposicion_externa_unica_por_unidad_fuente",
            ),
        ]

    def __str__(self):
        return f"{self.fuente} — {self.distancia_m} m ({self.unidad_muestreo})"
