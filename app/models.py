from django.db import models
from django.urls import reverse


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DatasetMetadata(TimestampedModel):
    name = models.CharField("nombre", max_length=180)
    source = models.CharField("fuente", max_length=240, blank=True)
    version = models.CharField(max_length=80, blank=True)
    publication_year = models.PositiveIntegerField("ano de publicacion", null=True, blank=True)
    description = models.TextField("descripcion", blank=True)
    license = models.CharField("licencia", max_length=120, blank=True)

    class Meta:
        verbose_name = "metadato de dataset"
        verbose_name_plural = "metadatos de datasets"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Region(TimestampedModel):
    COUNTRY = "country"
    DEPARTMENT = "department"
    MUNICIPALITY = "municipality"
    BASIN = "basin"
    REGION_TYPES = [
        (COUNTRY, "Pais"),
        (DEPARTMENT, "Departamento"),
        (MUNICIPALITY, "Municipio"),
        (BASIN, "Cuenca"),
    ]

    name = models.CharField("nombre", max_length=160)
    code = models.CharField("codigo", max_length=40, blank=True)
    region_type = models.CharField("tipo", max_length=24, choices=REGION_TYPES, default=DEPARTMENT)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")

    class Meta:
        verbose_name = "region"
        verbose_name_plural = "regiones"
        ordering = ["name"]
        unique_together = [("name", "region_type", "parent")]

    def __str__(self):
        return self.name


class Sector(TimestampedModel):
    name = models.CharField("nombre", max_length=160, unique=True)
    ipcc_code = models.CharField("codigo IPCC", max_length=40, blank=True)
    description = models.TextField("descripcion", blank=True)

    class Meta:
        verbose_name = "sector"
        verbose_name_plural = "sectores"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Gas(TimestampedModel):
    name = models.CharField("nombre", max_length=120)
    chemical_formula = models.CharField("formula", max_length=24, unique=True)
    gwp_100 = models.DecimalField("PCG 100 anos", max_digits=12, decimal_places=3, default=1)

    class Meta:
        verbose_name = "gas"
        verbose_name_plural = "gases"
        ordering = ["chemical_formula"]

    def __str__(self):
        return self.chemical_formula


class EmissionSource(TimestampedModel):
    name = models.CharField("nombre", max_length=180)
    sector = models.ForeignKey(Sector, on_delete=models.PROTECT, related_name="sources")
    description = models.TextField("descripcion", blank=True)

    class Meta:
        verbose_name = "fuente emisora"
        verbose_name_plural = "fuentes emisoras"
        ordering = ["sector__name", "name"]
        unique_together = [("name", "sector")]

    def __str__(self):
        return self.name


class EmissionRecord(TimestampedModel):
    ACTIVITY = "activity"
    MEASURED = "measured"
    ESTIMATED = "estimated"
    DATA_QUALITY = [
        (ACTIVITY, "Dato de actividad"),
        (MEASURED, "Medido"),
        (ESTIMATED, "Estimado"),
    ]

    dataset = models.ForeignKey(DatasetMetadata, on_delete=models.PROTECT, related_name="records")
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="records")
    sector = models.ForeignKey(Sector, on_delete=models.PROTECT, related_name="records")
    source = models.ForeignKey(EmissionSource, on_delete=models.PROTECT, related_name="records")
    gas = models.ForeignKey(Gas, on_delete=models.PROTECT, related_name="records")
    year = models.PositiveIntegerField("ano")
    value_tonnes = models.DecimalField("toneladas de gas", max_digits=18, decimal_places=3)
    co2e_tonnes = models.DecimalField("toneladas CO2e", max_digits=18, decimal_places=3)
    unit = models.CharField("unidad original", max_length=40, default="t")
    method = models.CharField("metodo", max_length=160, blank=True)
    data_quality = models.CharField("calidad del dato", max_length=24, choices=DATA_QUALITY, default=ESTIMATED)
    notes = models.TextField("notas", blank=True)

    class Meta:
        verbose_name = "registro de emision"
        verbose_name_plural = "registros de emisiones"
        ordering = ["-year", "region__name", "sector__name"]
        indexes = [
            models.Index(fields=["year"]),
            models.Index(fields=["region", "year"]),
            models.Index(fields=["sector", "year"]),
            models.Index(fields=["gas", "year"]),
        ]
        unique_together = [("dataset", "region", "sector", "source", "gas", "year")]

    def __str__(self):
        return f"{self.year} - {self.region} - {self.gas}"

    def get_absolute_url(self):
        return reverse("emission-detail", kwargs={"pk": self.pk})


# ─── Flujo Cámara ────────────────────────────────────────────────────────────

class Proyecto(TimestampedModel):
    nombre = models.CharField("nombre del proyecto", max_length=255)
    codigo = models.CharField("código del proyecto", max_length=80, unique=True)

    class Meta:
        verbose_name = "proyecto"
        verbose_name_plural = "proyectos"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"


class SitioMonitoreo(TimestampedModel):
    REGION_ANDES = "andes"
    REGION_ORINOQUIA = "orinoquia"
    REGION_AMAZONAS = "amazonas"
    REGION_CARIBE = "caribe"
    REGION_PACIFICO = "pacifico"
    REGIONES = [
        (REGION_ANDES, "Andes"),
        (REGION_ORINOQUIA, "Orinoquia"),
        (REGION_AMAZONAS, "Amazonas"),
        (REGION_CARIBE, "Caribe"),
        (REGION_PACIFICO, "Pacífico"),
    ]

    ECO_PARAMO_SECO = "paramo_seco"
    ECO_TURBERA_ALTA = "turbera_alta_elevacion"
    ECO_BOSQUE_HUMEDO = "bosque_humedo_tropical"
    ECO_BOSQUE_NIEBLA = "bosque_de_niebla"
    ECO_BOSQUE_SECO = "bosque_seco_tropical"
    ECO_SABANA_SECA = "sabana_seca"
    ECO_SABANA_INUNDABLE = "sabana_inundable"
    ECO_TURBERA_BAJA = "turbera_baja_elevacion"
    ECO_PANTANO = "pantano_cienaga"
    ECO_LAGO = "lago_superficial"
    ECO_MANGLAR = "manglar"
    ECOSISTEMAS = [
        (ECO_PARAMO_SECO, "Páramo seco"),
        (ECO_TURBERA_ALTA, "Turbera de alta elevación"),
        (ECO_BOSQUE_HUMEDO, "Bosque húmedo tropical"),
        (ECO_BOSQUE_NIEBLA, "Bosque de niebla"),
        (ECO_BOSQUE_SECO, "Bosque seco tropical"),
        (ECO_SABANA_SECA, "Sabana seca"),
        (ECO_SABANA_INUNDABLE, "Sabana inundable"),
        (ECO_TURBERA_BAJA, "Turbera de baja elevación"),
        (ECO_PANTANO, "Pantano / ciénaga"),
        (ECO_LAGO, "Lago superficial"),
        (ECO_MANGLAR, "Manglar"),
    ]

    SRS_WGS84 = "EPSG:4326"
    SRS_MAGNA = "EPSG:4686"
    SRS_SIRGAS = "EPSG:4674"
    SRS_OTRO = "otro"
    SISTEMAS_REF = [
        (SRS_WGS84, "EPSG:4326 — WGS84"),
        (SRS_MAGNA, "EPSG:4686 — MAGNA-SIRGAS"),
        (SRS_SIRGAS, "EPSG:4674 — SIRGAS2000"),
        (SRS_OTRO, "Otro (indicar código EPSG)"),
    ]

    TOPO_CRESTA = "cresta_cima"
    TOPO_LADERA_SUP = "ladera_superior"
    TOPO_LADERA_MED = "ladera_media"
    TOPO_LADERA_INF = "ladera_inferior"
    TOPO_VALLE = "valle_fondo"
    TOPO_PLANO = "plano"
    TOPOGRAFIAS = [
        (TOPO_CRESTA, "Cresta / cima"),
        (TOPO_LADERA_SUP, "Ladera superior"),
        (TOPO_LADERA_MED, "Ladera media"),
        (TOPO_LADERA_INF, "Ladera inferior"),
        (TOPO_VALLE, "Valle / fondo"),
        (TOPO_PLANO, "Plano"),
    ]

    PEND_PLANO = "plano"
    PEND_ONDULADO = "ondulado_variable"
    PEND_SUAVE = "pendiente_suave"
    PEND_MEDIA = "pendiente_media"
    PEND_SIGNIFICATIVA = "pendiente_significativa"
    PEND_FUERTE = "pendiente_fuerte"
    PEND_CRESTA = "cresta_cima"
    PENDIENTES = [
        (PEND_PLANO, "Plano"),
        (PEND_ONDULADO, "Ondulado / variable"),
        (PEND_SUAVE, "Pendiente suave (<2%)"),
        (PEND_MEDIA, "Pendiente media (2–5%)"),
        (PEND_SIGNIFICATIVA, "Pendiente significativa (5–10%)"),
        (PEND_FUERTE, "Pendiente fuerte (>10%)"),
        (PEND_CRESTA, "Cresta / cima"),
    ]

    DEPARTAMENTOS = [
        ("amazonas", "Amazonas"), ("antioquia", "Antioquia"), ("arauca", "Arauca"),
        ("atlantico", "Atlántico"), ("bolivar", "Bolívar"), ("boyaca", "Boyacá"),
        ("caldas", "Caldas"), ("caqueta", "Caquetá"), ("casanare", "Casanare"),
        ("cauca", "Cauca"), ("cesar", "Cesar"), ("choco", "Chocó"),
        ("cordoba", "Córdoba"), ("cundinamarca", "Cundinamarca"), ("guainia", "Guainía"),
        ("guaviare", "Guaviare"), ("huila", "Huila"), ("la_guajira", "La Guajira"),
        ("magdalena", "Magdalena"), ("meta", "Meta"), ("narino", "Nariño"),
        ("norte_de_santander", "Norte de Santander"), ("putumayo", "Putumayo"),
        ("quindio", "Quindío"), ("risaralda", "Risaralda"),
        ("san_andres", "San Andrés, Providencia y Santa Catalina"),
        ("santander", "Santander"), ("sucre", "Sucre"), ("tolima", "Tolima"),
        ("valle_del_cauca", "Valle del Cauca"), ("vaupes", "Vaupés"),
        ("vichada", "Vichada"),
    ]

    proyecto = models.ForeignKey(Proyecto, on_delete=models.PROTECT, related_name="sitios")
    codigo_sitio = models.CharField("código del sitio", max_length=80)
    unidad_muestreo = models.CharField("unidad de muestreo", max_length=80, blank=True)

    region_natural = models.CharField("región natural", max_length=24, choices=REGIONES)
    ecosistema = models.CharField("ecosistema", max_length=40, choices=ECOSISTEMAS)
    departamento = models.CharField("departamento", max_length=40, choices=DEPARTAMENTOS)
    sitio_urbano_cercano = models.CharField("sitio urbano cercano", max_length=160, blank=True)

    latitud = models.DecimalField("latitud", max_digits=10, decimal_places=7)
    longitud = models.DecimalField("longitud", max_digits=10, decimal_places=7)
    sistema_referencia = models.CharField("sistema de referencia", max_length=16, choices=SISTEMAS_REF, default=SRS_WGS84)
    altitud = models.DecimalField("altitud (m.s.n.m.)", max_digits=8, decimal_places=2, null=True, blank=True)
    pendiente = models.CharField("pendiente", max_length=30, choices=PENDIENTES, blank=True)
    topografia = models.CharField("topografía", max_length=24, choices=TOPOGRAFIAS, blank=True)

    class Meta:
        verbose_name = "sitio de monitoreo"
        verbose_name_plural = "sitios de monitoreo"
        ordering = ["proyecto", "codigo_sitio"]
        unique_together = [("proyecto", "codigo_sitio")]

    def __str__(self):
        return f"{self.proyecto.codigo} / {self.codigo_sitio}"


class RegistroFlujoCamara(TimestampedModel):
    sitio = models.ForeignKey(SitioMonitoreo, on_delete=models.PROTECT, related_name="registros")
    codigo_metadatos = models.CharField("código de metadatos", max_length=80, unique=True)

    class Meta:
        verbose_name = "registro flujo cámara"
        verbose_name_plural = "registros flujo cámara"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["sitio"])]

    def __str__(self):
        return f"{self.codigo_metadatos} — {self.sitio}"


class Cobertura(TimestampedModel):
    HUMEDAL_CHOICES = [
        ("turbera_musgo", "Turbera de musgo (bog)"),
        ("turbera_pantanosa", "Turbera pantanosa (fen)"),
        ("pantano_arbolado", "Pantano arbolado (swamp)"),
        ("marisma", "Marisma / estuario"),
        ("manglar", "Manglar"),
        ("lago_laguna", "Lago / laguna"),
        ("rio_ripario", "Río / zona riparia"),
        ("sabana_inundable", "Sabana inundable"),
        ("arrozal", "Arrozal"),
        ("no_aplica", "No aplica"),
    ]
    KOEPPEN_CHOICES = [
        ("selva_tropical_lluviosa", "Selva tropical lluviosa"),
        ("monzon_tropical", "Monzón tropical"),
        ("sabana_tropical", "Sabana tropical"),
        ("desierto_IC", "Desierto (IC)"),
        ("desierto_IF", "Desierto (IF)"),
        ("oceanico_VC", "Oceánico costa occidental (VC)"),
        ("oceanico_VF", "Oceánico costa occidental (VF)"),
        ("montania_VC", "Templado de montaña (VC)"),
        ("montania_VF", "Templado de montaña (VF)"),
        ("continental_humedo", "Continental húmedo"),
        ("continental_verano_calido", "Continental verano cálido"),
        ("continental_seco_VC", "Continental seco (VC)"),
        ("continental_seco_VF", "Continental seco (VF)"),
        ("tundra", "Tundra"),
        ("casquete_hielo", "Casquete de hielo"),
    ]

    registro = models.OneToOneField(RegistroFlujoCamara, on_delete=models.CASCADE, related_name="cobertura", null=True, blank=True)
    registro_biomasa = models.OneToOneField("RegistroBiomasa", on_delete=models.CASCADE, related_name="cobertura", null=True, blank=True)
    cobertura_ipcc = models.CharField("cobertura IPCC", max_length=120, blank=True)
    cobertura_clc = models.CharField("cobertura CLC (Corine Land Cover)", max_length=120, blank=True)
    cobertura_igbp = models.CharField("cobertura IGBP", max_length=120, blank=True)
    cobertura_nom_comun = models.CharField("nombre común de cobertura", max_length=160, blank=True)
    cobertura_humedal = models.CharField("cobertura de humedal", max_length=30, choices=HUMEDAL_CHOICES, blank=True)
    clima_koeppen = models.CharField("clima Köppen", max_length=30, choices=KOEPPEN_CHOICES, blank=True)

    class Meta:
        verbose_name = "cobertura"
        verbose_name_plural = "coberturas"

    def __str__(self):
        return f"Cobertura — {self.registro}"


class Disturbio(TimestampedModel):
    DIST_NINGUNO = "sin_disturbio"
    DISTURBIOS = [
        ("agricultura", "Agricultura"),
        ("sequia", "Sequía"),
        ("fuego", "Fuego"),
        ("silvicultura", "Silvicultura"),
        ("pastoreo", "Pastoreo"),
        ("evento_hidrologico", "Evento hidrológico"),
        ("cambio_cobertura", "Cambio en cobertura del suelo"),
        ("plagas_enfermedades", "Plagas y enfermedades"),
        ("tormenta_viento", "Tormenta o viento"),
        ("extremos_temperatura", "Extremos de temperatura"),
        (DIST_NINGUNO, "Sin disturbio"),
    ]
    USO_CHOICES = [
        ("bosque_primario", "Bosque primario"),
        ("bosque_secundario", "Bosque secundario"),
        ("plantacion_forestal", "Plantación forestal"),
        ("agricultura_intensiva", "Agricultura intensiva"),
        ("agricultura_tradicional", "Agricultura tradicional"),
        ("pastura", "Pastura"),
        ("humedal_natural", "Humedal natural"),
        ("humedal_intervenido", "Humedal intervenido"),
        ("area_protegida", "Área protegida"),
        ("sistema_agroforestal", "Sistema agroforestal"),
        ("abandonado", "Abandonado"),
        ("restauracion_activa", "Restauración activa"),
    ]
    ESTADO_CHOICES = [
        ("intacto", "Intacto"),
        ("ligeramente_degradado", "Ligeramente degradado"),
        ("moderadamente_degradado", "Moderadamente degradado"),
        ("severamente_degradado", "Severamente degradado"),
        ("en_recuperacion_natural", "En recuperación natural"),
        ("en_restauracion_activa", "En restauración activa"),
        ("estable", "Estable"),
        ("en_transicion", "En transición"),
    ]
    PROPIEDAD_CHOICES = [
        ("publica", "Pública"),
        ("privada", "Privada"),
    ]

    registro = models.OneToOneField(RegistroFlujoCamara, on_delete=models.CASCADE, related_name="disturbio", null=True, blank=True)
    registro_biomasa = models.OneToOneField("RegistroBiomasa", on_delete=models.CASCADE, related_name="disturbio", null=True, blank=True)
    tipo_disturbio = models.CharField("tipo de disturbio", max_length=30, choices=DISTURBIOS, default=DIST_NINGUNO)
    anios_disturbio = models.PositiveIntegerField("años de disturbio", null=True, blank=True)
    anios_desde_fin_disturbio = models.PositiveIntegerField("años desde fin del disturbio", null=True, blank=True)
    uso_actual = models.CharField("uso actual del suelo", max_length=30, choices=USO_CHOICES, blank=True)
    estado_actual = models.CharField("estado actual", max_length=30, choices=ESTADO_CHOICES, blank=True)
    propiedad_tierra = models.CharField("propiedad de la tierra", max_length=10, choices=PROPIEDAD_CHOICES, blank=True)

    class Meta:
        verbose_name = "disturbio"
        verbose_name_plural = "disturbios"
        indexes = [
            models.Index(fields=["tipo_disturbio"]),
            models.Index(fields=["uso_actual"]),
        ]

    def __str__(self):
        return f"Disturbio — {self.registro}"


class Caracterizacion(TimestampedModel):
    SUELO_CHOICES = [
        ("mineral", "Mineral"),
        ("organico", "Orgánico"),
    ]
    MICROTOPO_CHOICES = [
        ("hummock", "Hummock (cojines)"),
        ("hollow", "Hollow (depresiones húmedas)"),
        ("pool", "Pool (charcos / sobre agua)"),
        ("lawns", "Lawns (lugares planos)"),
    ]

    registro = models.OneToOneField(RegistroFlujoCamara, on_delete=models.CASCADE, related_name="caracterizacion")
    tipo_de_suelo = models.CharField("tipo de suelo", max_length=10, choices=SUELO_CHOICES, blank=True)
    microtopografia = models.CharField("microtopografía", max_length=10, choices=MICROTOPO_CHOICES, blank=True)
    diametro_anillo = models.DecimalField("diámetro del anillo (cm)", max_digits=8, decimal_places=2, null=True, blank=True)
    tratamiento = models.CharField("tratamiento", max_length=255, blank=True)
    pozo_nivel_freatico = models.CharField("pozo / nivel freático", max_length=80, blank=True)

    class Meta:
        verbose_name = "caracterización"
        verbose_name_plural = "caracterizaciones"

    def __str__(self):
        return f"Caracterización — {self.registro}"


class CaracterizacionMuestreo(TimestampedModel):
    PROT_DA_CHOICES = [
        ("anillo_volumetrico", "Anillo volumétrico (core ring)"),
        ("terron_parafina", "Terrón parafinado"),
        ("cilindro_driving", "Cilindro tipo driving"),
        ("otro", "Otro (especificar en notas)"),
    ]
    PROT_COS_CHOICES = [
        ("loss_on_ignition", "Pérdida por ignición (LOI)"),
        ("walkley_black", "Walkley-Black (oxidación húmeda)"),
        ("combustion_seca", "Combustión seca (analizador elemental)"),
        ("espectroscopia_nir", "Espectroscopía NIR/MIR"),
        ("otro", "Otro (especificar en notas)"),
    ]

    registro = models.OneToOneField(RegistroFlujoCamara, on_delete=models.CASCADE, related_name="caracterizacion_muestreo")
    profundidad_perfil = models.DecimalField("profundidad del perfil (cm)", max_digits=8, decimal_places=2, null=True, blank=True)
    intervalos_perfil = models.DecimalField("intervalos del perfil (cm)", max_digits=8, decimal_places=2, null=True, blank=True)
    monitoreo_macrofosiles = models.BooleanField("monitoreo de macrofósiles", default=False)
    protocolo_macrofosiles = models.CharField("protocolo macrofósiles", max_length=255, blank=True)
    monitoreo_datacion = models.BooleanField("monitoreo de datación", default=False)
    protocolo_datacion = models.CharField("protocolo datación", max_length=255, blank=True)
    monitoreo_densidad_aparente = models.BooleanField("monitoreo de densidad aparente", default=False)
    protocolo_densidad_aparente = models.CharField("protocolo densidad aparente", max_length=30, choices=PROT_DA_CHOICES, blank=True)
    monitoreo_cos = models.BooleanField("monitoreo de carbono orgánico del suelo (COS)", default=False)
    protocolo_cos = models.CharField("protocolo COS", max_length=30, choices=PROT_COS_CHOICES, blank=True)

    class Meta:
        verbose_name = "caracterización muestreo"
        verbose_name_plural = "caracterizaciones muestreo"

    def __str__(self):
        return f"Muestreo Suelo — {self.registro}"


class VegetacionAnillo(TimestampedModel):
    registro = models.OneToOneField(RegistroFlujoCamara, on_delete=models.CASCADE, related_name="vegetacion_anillo")
    cobertura_vegetal_primaria = models.CharField("cobertura vegetal primaria", max_length=160, blank=True)
    porcentaje_cob_veg_pri = models.DecimalField("% cobertura primaria", max_digits=5, decimal_places=2, null=True, blank=True)
    cobertura_vegetal_secundaria = models.CharField("cobertura vegetal secundaria", max_length=160, blank=True)
    porcentaje_cob_veg_sec = models.DecimalField("% cobertura secundaria", max_digits=5, decimal_places=2, null=True, blank=True)
    cobertura_vegetal_terciaria = models.CharField("cobertura vegetal terciaria", max_length=160, blank=True)
    porcentaje_cob_veg_ter = models.DecimalField("% cobertura terciaria", max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "vegetación anillo"
        verbose_name_plural = "vegetaciones anillo"

    def __str__(self):
        return f"Vegetación — {self.registro}"


class Distancias(TimestampedModel):
    registro = models.OneToOneField(RegistroFlujoCamara, on_delete=models.CASCADE, related_name="distancias")
    distancia_drenaje = models.DecimalField("distancia a drenaje (m)", max_digits=10, decimal_places=2, null=True, blank=True)
    distancia_fuego = models.DecimalField("distancia a fuego (m)", max_digits=10, decimal_places=2, null=True, blank=True)
    distancia_pastoreo = models.DecimalField("distancia a pastoreo (m)", max_digits=10, decimal_places=2, null=True, blank=True)
    distancia_cultivo = models.DecimalField("distancia a cultivo (m)", max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "distancias"
        verbose_name_plural = "distancias"

    def __str__(self):
        return f"Distancias — {self.registro}"


# ─── Biomasa ─────────────────────────────────────────────────────────────────

class RegistroBiomasa(TimestampedModel):
    sitio = models.ForeignKey(SitioMonitoreo, on_delete=models.PROTECT, related_name="registros_biomasa")
    codigo_metadatos = models.CharField("código de metadatos", max_length=80, unique=True)
    parcela = models.CharField("parcela", max_length=80, blank=True)

    class Meta:
        verbose_name = "registro biomasa"
        verbose_name_plural = "registros biomasa"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["sitio"])]

    def __str__(self):
        return f"{self.codigo_metadatos} — {self.sitio}"


class CaracterizacionParcela(TimestampedModel):
    UNIDAD_CHOICES = [
        ("parcela_circular", "Parcela circular"),
        ("parcela_cuadrada", "Parcela cuadrada"),
        ("transecto", "Transecto lineal"),
        ("punto_radio_fijo", "Punto de radio fijo"),
        ("banda", "Banda / franja"),
        ("otra", "Otra (especificar en notas)"),
    ]
    ESTATUS_CHOICES = [
        ("activa", "Activa — en monitoreo regular"),
        ("inactiva", "Inactiva — sin monitoreo activo"),
        ("abandonada", "Abandonada — sin posibilidad de continuar"),
        ("nueva", "Nueva — instalada pero sin mediciones"),
        ("en_restauracion", "En restauración"),
    ]
    PROT_BIOMASA_AEREA_CHOICES = [
        ("ecuaciones_alometricas", "Ecuaciones alométricas (modelos regionales o locales)"),
        ("inventario_forestal_completo", "Inventario forestal completo (DAP, altura, densidad)"),
        ("cosecha_destructiva", "Cosecha destructiva (pesaje de biomasa fresca y seca)"),
        ("teledeteccion_lidar", "Teledetección / LiDAR (estimación remota de estructura)"),
        ("otro", "Otro (especificar en notas)"),
    ]

    registro = models.OneToOneField(RegistroBiomasa, on_delete=models.CASCADE, related_name="caracterizacion_parcela")
    unidad_de_muestreo = models.CharField("unidad de muestreo", max_length=30, choices=UNIDAD_CHOICES, blank=True)
    area = models.DecimalField("área (m²)", max_digits=12, decimal_places=2, null=True, blank=True)
    estatus_parcela = models.CharField("estatus de la parcela", max_length=20, choices=ESTATUS_CHOICES, blank=True)
    fecha_instalacion = models.PositiveIntegerField("año de instalación", null=True, blank=True)

    monitoreo_biomasa_aerea = models.BooleanField("monitoreo de biomasa aérea", default=False)
    protocolo_biomasa_aerea = models.CharField("protocolo biomasa aérea", max_length=40, choices=PROT_BIOMASA_AEREA_CHOICES, blank=True)
    monitoreo_biomasa_subterranea = models.BooleanField("monitoreo de biomasa subterránea", default=False)
    protocolo_biomasa_subterranea = models.CharField("protocolo biomasa subterránea", max_length=255, blank=True)
    monitoreo_flora = models.BooleanField("monitoreo de flora", default=False)
    protocolo_flora = models.CharField("protocolo flora", max_length=255, blank=True)
    monitoreo_rasgos_funcionales = models.BooleanField("monitoreo de rasgos funcionales", default=False)
    protocolo_rasgos_funcionales = models.CharField("protocolo rasgos funcionales", max_length=255, blank=True)

    class Meta:
        verbose_name = "caracterización de parcela"
        verbose_name_plural = "caracterizaciones de parcela"

    def __str__(self):
        return f"Parcela — {self.registro}"
