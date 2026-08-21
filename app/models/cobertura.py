from django.db import models

from .base import TimestampedModel


class TipoCobertura(TimestampedModel):
    """Catálogo de sistemas de clasificación de cobertura (CLC, IPCC, IGBP, Köppen, Suelo IPCC, nombre local)."""

    codigo = models.CharField("código", max_length=30, unique=True)
    nombre = models.CharField("nombre", max_length=120)

    class Meta:
        verbose_name = "tipo de cobertura"
        verbose_name_plural = "tipos de cobertura"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Cobertura(TimestampedModel):
    """Un valor de cobertura reportado para un sitio, según un sistema de clasificación.

    Un mismo sitio puede tener varias filas: una por sistema de clasificación,
    o varias del mismo sistema cuando distintas fuentes reportan valores en
    conflicto para el mismo sitio (no hay forma de saber cuál es "el
    correcto", así que se guardan todas en vez de que una pise a la otra).
    """

    sitio = models.ForeignKey(
        "app.Sitio", on_delete=models.CASCADE, related_name="coberturas", verbose_name="sitio",
    )
    tipo = models.ForeignKey(
        TipoCobertura, on_delete=models.PROTECT, related_name="coberturas",
        null=True, blank=True, verbose_name="tipo",
        help_text="Sistema de clasificación de este valor. Vacío si el valor de origen no matchea ningún sistema conocido.",
    )
    nombre = models.CharField("nombre reportado", max_length=160)

    class Meta:
        verbose_name = "cobertura"
        verbose_name_plural = "coberturas"
        ordering = ["sitio", "tipo"]
        constraints = [
            models.UniqueConstraint(
                fields=["sitio", "tipo", "nombre"],
                name="cobertura_unica_por_sitio_tipo_nombre",
            ),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.tipo or 'sin tipo'})"


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
    """Evento de disturbio que afecta un sitio (fuego, sequía, pastoreo, …), con fechas y estado actual del ecosistema."""

    TIPO_CHOICES = [
        ("Agricultura", "Agricultura"),
        ("Sequia", "Sequía"),
        ("Fuego", "Fuego"),
        ("Silvicultura", "Silvicultura"),
        ("Pastoreo", "Pastoreo"),
        ("Evento_hidrologico", "Evento hidrológico"),
        ("Cambio_en_cobertura_del_suelo", "Cambio en cobertura del suelo"),
        ("Plagas_y_enfermedades", "Plagas y enfermedades"),
        ("Tormenta_o_viento", "Tormenta o viento"),
        ("Extremos_de_temperatura", "Extremos de temperatura"),
        ("Sin_disturbio", "Sin disturbio"),
    ]
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
    # Distinto de ESTADO_CHOICES/estado_actual (severidad de degradación):
    # esta es la taxonomía de manejo del vocabulario IDEAM ("Estado
    # conservación"), sobre si el ecosistema tiene manejo humano y de qué
    # tipo -no calza con las opciones de estado_actual, así que va aparte
    # en vez de forzar una traducción incorrecta entre ambas.
    ESTADO_CONSERVACION_CHOICES = [
        ("Natural", "Natural (sin manejo humano significativo)"),
        ("Seminatural", "Seminatural (manejo bajo, regeneración natural dominante)"),
        ("Manejado", "Manejado (aprovechamiento, ganadería, agroforestería)"),
        ("Plantacion", "Plantación (vegetación establecida y manejada)"),
        ("Artificial_Urbano", "Artificial / Urbano (superficie no natural)"),
    ]

    descripcion = models.TextField("descripción", blank=True)
    fecha_inicio = models.DateField("fecha de inicio", null=True, blank=True)
    fecha_fin = models.DateField("fecha de fin", null=True, blank=True)
    incertidumbre_anios = models.PositiveIntegerField("incertidumbre (años)", null=True, blank=True)
    tipo = models.CharField("tipo de disturbio", max_length=40, choices=TIPO_CHOICES, default="Sin_disturbio")
    anios_disturbio = models.PositiveIntegerField("años de disturbio", null=True, blank=True)
    anios_desde_fin = models.PositiveIntegerField("años desde fin del disturbio", null=True, blank=True)
    estado_actual = models.CharField("estado actual", max_length=30, choices=ESTADO_CHOICES, blank=True)
    estado_conservacion = models.CharField(
        "estado de conservación", max_length=20, choices=ESTADO_CONSERVACION_CHOICES, blank=True,
        help_text="Estado del ecosistema frente a la presencia de manejo humano (taxonomía del vocabulario IDEAM).",
    )
    proteccion_legal = models.TextField(
        "protección legal", blank=True,
        help_text="Si el sitio está bajo alguna figura de reserva, parque, santuario, etc.",
    )

    class Meta:
        verbose_name = "disturbio"
        verbose_name_plural = "disturbios"
        indexes = [models.Index(fields=["tipo"])]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.fecha_inicio or 'sin fecha'}"
