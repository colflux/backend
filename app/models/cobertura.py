from django.db import models

from .base import TimestampedModel


class Cobertura(TimestampedModel):
    KOEPPEN_CHOICES = [
        ("Selva_tropical_lluviosa", "Selva tropical lluviosa"),
        ("Monzon_tropical", "Monzón tropical"),
        ("Sabana_tropical", "Sabana tropical"),
        ("Desierto_IC", "Desierto (IC)"),
        ("Desierto_IF", "Desierto (IF)"),
        ("Oceanico_de_la_costa_occidental_VC", "Oceánico costa occidental (VC)"),
        ("Oceanico_de_la_costa_occidental_VF", "Oceánico costa occidental (VF)"),
        ("Templado_de_montania_VC", "Templado de montaña (VC)"),
        ("Templado_de_montania_VF", "Templado de montaña (VF)"),
        ("Continental_humedo", "Continental húmedo"),
        ("Continental_de_verano_calido", "Continental verano cálido"),
        ("Continental_seco_VC", "Continental seco (VC)"),
        ("Continental_de_verano_calido_2", "Continental verano cálido (2)"),
        ("Continental_seco_VF", "Continental seco (VF)"),
        ("Continental_humedo_1", "Continental húmedo (1)"),
        ("Continental_de_verano_calido_3", "Continental verano cálido (3)"),
        ("Casquete_de_hielo", "Casquete de hielo"),
        ("Tundra", "Tundra"),
    ]

    IGBP_CHOICES = [
        ("Vegetacion_escasa_o_suelo_desnudo", "Vegetación escasa o suelo desnudo"),
        ("Cultivos", "Cultivos"),
        ("Matorrales_cerrados", "Matorrales cerrados"),
        ("Mosaico_de_cultivos_y_vegetacion_natural", "Mosaico de cultivos y vegetación natural"),
        ("Bosques_latifoliados_caducifolios", "Bosques latifoliados caducifolios"),
        ("Bosques_de_coniferas_caducifolias", "Bosques de coníferas caducifolias"),
        ("Bosques_latifoliados_siempreverdes", "Bosques latifoliados siempreverdes"),
        ("Bosques_de_coniferas_siempreverdes", "Bosques de coníferas siempreverdes"),
        ("Pastizales", "Pastizales"),
        ("Bosques_mixtos", "Bosques mixtos"),
        ("Matorrales_abiertos", "Matorrales abiertos"),
        ("Sabanas", "Sabanas"),
        ("Nieve_y_hielo", "Nieve y hielo"),
        ("Areas_urbanas_y_construidas", "Áreas urbanas y construidas"),
        ("Cuerpos_de_agua", "Cuerpos de agua"),
        ("Humedales_permanentes", "Humedales permanentes"),
        ("Sabanas_arboladas", "Sabanas arboladas"),
    ]

    cobertura_clc = models.CharField("cobertura CLC (Corine Land Cover)", max_length=120, blank=True)
    cobertura_nombre_comun = models.CharField("nombre común de cobertura", max_length=160, blank=True)
    clima_koeppen = models.CharField("clima Köppen", max_length=50, choices=KOEPPEN_CHOICES, blank=True)
    cobertura_igbp = models.CharField("cobertura IGBP", max_length=60, choices=IGBP_CHOICES, blank=True)

    class Meta:
        verbose_name = "cobertura"
        verbose_name_plural = "coberturas"

    def __str__(self):
        return self.cobertura_nombre_comun or self.cobertura_clc or f"Cobertura {self.pk}"


class Vegetacion(TimestampedModel):
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

    descripcion = models.TextField("descripción", blank=True)
    fecha_inicio = models.DateField("fecha de inicio", null=True, blank=True)
    fecha_fin = models.DateField("fecha de fin", null=True, blank=True)
    incertidumbre_anios = models.PositiveIntegerField("incertidumbre (años)", null=True, blank=True)
    tipo = models.CharField("tipo de disturbio", max_length=40, choices=TIPO_CHOICES, default="Sin_disturbio")
    anios_disturbio = models.PositiveIntegerField("años de disturbio", null=True, blank=True)
    anios_desde_fin = models.PositiveIntegerField("años desde fin del disturbio", null=True, blank=True)
    estado_actual = models.CharField("estado actual", max_length=30, choices=ESTADO_CHOICES, blank=True)

    class Meta:
        verbose_name = "disturbio"
        verbose_name_plural = "disturbios"
        indexes = [models.Index(fields=["tipo"])]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.fecha_inicio or 'sin fecha'}"
