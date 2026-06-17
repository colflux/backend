import json

from django.contrib import messages
from django.db.models import Sum
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .forms import EmissionRecordForm
from .models import EmissionRecord, Gas, Region, Sector


class DashboardView(TemplateView):
    template_name = "app/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_co2e"] = EmissionRecord.objects.aggregate(total=Sum("co2e_tonnes"))["total"] or 0
        context["record_count"] = EmissionRecord.objects.count()
        context["region_count"] = Region.objects.count()
        context["gas_count"] = Gas.objects.count()
        context["sector_count"] = Sector.objects.count()
        context["latest_records"] = EmissionRecord.objects.select_related(
            "region", "sector", "source", "gas"
        )[:8]
        return context


class EmissionRecordListView(ListView):
    model = EmissionRecord
    template_name = "app/emission_list.html"
    context_object_name = "records"
    paginate_by = 20

    def get_queryset(self):
        queryset = EmissionRecord.objects.select_related("dataset", "region", "sector", "source", "gas")
        year = self.request.GET.get("year")
        sector = self.request.GET.get("sector")
        region = self.request.GET.get("region")
        if year:
            queryset = queryset.filter(year=year)
        if sector:
            queryset = queryset.filter(sector_id=sector)
        if region:
            queryset = queryset.filter(region_id=region)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sectors"] = Sector.objects.all()
        context["regions"] = Region.objects.all()
        context["selected"] = self.request.GET
        return context


class EmissionRecordDetailView(DetailView):
    model = EmissionRecord
    template_name = "app/emission_detail.html"
    context_object_name = "record"


class EmissionRecordCreateView(CreateView):
    model = EmissionRecord
    form_class = EmissionRecordForm
    template_name = "app/emission_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Registro creado correctamente.")
        return super().form_valid(form)


class EmissionRecordUpdateView(UpdateView):
    model = EmissionRecord
    form_class = EmissionRecordForm
    template_name = "app/emission_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Registro actualizado correctamente.")
        return super().form_valid(form)


class EmissionRecordDeleteView(DeleteView):
    model = EmissionRecord
    template_name = "app/emission_confirm_delete.html"
    success_url = reverse_lazy("emission-list")

    def form_valid(self, form):
        messages.success(self.request, "Registro eliminado correctamente.")
        return super().form_valid(form)


class VisualizerView(TemplateView):
    template_name = "app/visualizer.html"


class DataModelView(TemplateView):
    template_name = "app/data_model.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Serializar choices a JSON para uso seguro en data attributes del template
        groups = []
        for group in DATA_MODEL_GROUPS:
            g = dict(group)
            g["fields"] = [_serialize_field(f) for f in group.get("fields", [])]
            if "sections" in group:
                g["sections"] = [
                    {**s, "fields": [_serialize_field(f) for f in s["fields"]]}
                    for s in group["sections"]
                ]
            groups.append(g)
        context["groups"] = groups
        return context


def _serialize_field(field):
    f = dict(field)
    f["choices_json"] = json.dumps(field.get("choices", []), ensure_ascii=False)
    return f


def _c(*pairs):
    """Convierte pares (valor, descripción) en lista de dicts para choices."""
    return [{"value": v, "desc": d} for v, d in pairs]


DATA_MODEL_GROUPS = [
    # ── Modelo: Proyecto ───────────────────────────────────────────────────────
    {
        "id": "proyecto",
        "model": "Proyecto",
        "name": "Proyecto",
        "color": "#18735d",
        "fields": [
            {"name": "nombre", "type": "CharField", "desc": "Nombre oficial del proyecto de monitoreo. max_length=255."},
            {"name": "codigo", "type": "CharField · unique", "desc": "Identificador único del proyecto. max_length=80."},
            {"name": "created_at", "type": "DateTimeField", "desc": "Fecha y hora de creación del registro (auto)."},
            {"name": "updated_at", "type": "DateTimeField", "desc": "Fecha y hora de última modificación (auto)."},
        ],
    },
    # ── Modelo: SitioMonitoreo ─────────────────────────────────────────────────
    {
        "id": "sitio",
        "model": "SitioMonitoreo",
        "name": "Sitio Monitoreo",
        "color": "#1a6e9b",
        "pk": "id",
        "fk": {"field": "proyecto", "to": "proyecto"},
        "fields": [
            {"name": "proyecto", "type": "FK → Proyecto", "desc": "Proyecto al que pertenece este sitio. on_delete=PROTECT."},
            {"name": "codigo_sitio", "type": "CharField", "desc": "Código identificador del sitio de monitoreo. max_length=80. Único por proyecto."},
            {"name": "unidad_muestreo", "type": "CharField", "desc": "Código de la unidad o parcela de muestreo. max_length=80. Opcional."},
            {"name": "region_natural", "type": "CharField · choices", "desc": "Región biogeográfica o administrativa del sitio de monitoreo.",
             "choices": _c(
                 ("Andes", "Región andina de Colombia."),
                 ("Orinoquia", "Región de los llanos orientales."),
                 ("Amazonas", "Región amazónica colombiana."),
                 ("Caribe", "Región caribe (costa norte)."),
                 ("Pacifico", "Región pacífica colombiana."),
             )},
            {"name": "ecosistema", "type": "CharField · choices", "desc": "Tipo de ecosistema donde se ubica el sitio de monitoreo.",
             "choices": _c(
                 ("Paramo_seco", "Ecosistema altoandino frío con vegetación adaptada a baja humedad y alta radiación."),
                 ("Turbera_de_alta_elevacion", "Humedal de montaña donde se acumula materia orgánica saturada de agua."),
                 ("Bosque_humedo_tropical", "Bosque cálido y lluvioso con alta biodiversidad y vegetación densa."),
                 ("Bosque_de_niebla", "Bosque montano húmedo con presencia frecuente de neblina y alta humedad."),
                 ("Bosque_seco_tropical", "Bosque cálido con temporada seca marcada y vegetación adaptada a la escasez de agua."),
                 ("Sabana_seca", "Ecosistema abierto de pastizales y árboles dispersos con baja disponibilidad de agua."),
                 ("Sabana_inundable", "Sabana que se inunda temporalmente por lluvias o desbordamientos."),
                 ("Turbera_de_baja_elevacion", "Humedal en zonas bajas con suelos saturados y acumulación de materia orgánica."),
                 ("Pantano/cienaga", "Humedal de aguas poco profundas con vegetación acuática o semiacuática."),
                 ("Lago_superficial", "Cuerpo de agua continental poco profundo con interacción directa entre agua, sedimentos y vegetación."),
                 ("Manglar", "Ecosistema costero tropical con árboles tolerantes a la salinidad e influencia de mareas."),
             )},
            {"name": "departamento", "type": "CharField · choices", "desc": "Departamento colombiano (32 opciones) donde se ubica el sitio.",
             "choices": _c(
                 ("Amazonas", "Amazonas"), ("Antioquia", "Antioquia"), ("Arauca", "Arauca"),
                 ("Atlantico", "Atlántico"), ("Bolivar", "Bolívar"), ("Boyaca", "Boyacá"),
                 ("Caldas", "Caldas"), ("Caqueta", "Caquetá"), ("Casanare", "Casanare"),
                 ("Cauca", "Cauca"), ("Cesar", "Cesar"), ("Choco", "Chocó"),
                 ("Cordoba", "Córdoba"), ("Cundinamarca", "Cundinamarca"), ("Guainia", "Guainía"),
                 ("Guaviare", "Guaviare"), ("Huila", "Huila"), ("La_Guajira", "La Guajira"),
                 ("Magdalena", "Magdalena"), ("Meta", "Meta"), ("Narinio", "Nariño"),
                 ("Norte_de_Santander", "Norte de Santander"), ("Putumayo", "Putumayo"),
                 ("Quindio", "Quindío"), ("Risaralda", "Risaralda"),
                 ("San_Andres", "San Andrés, Providencia y Santa Catalina"),
                 ("Santander", "Santander"), ("Sucre", "Sucre"), ("Tolima", "Tolima"),
                 ("Valle_del_Cauca", "Valle del Cauca"), ("Vaupes", "Vaupés"), ("Vichada", "Vichada"),
             )},
            {"name": "sitio_urbano_cercano", "type": "CharField", "desc": "Nombre del sitio urbano más cercano al punto de muestreo. max_length=160. Opcional."},
            {"name": "latitud", "type": "DecimalField", "desc": "Coordenada latitudinal del sitio. max_digits=10, decimal_places=7."},
            {"name": "longitud", "type": "DecimalField", "desc": "Coordenada longitudinal del sitio. max_digits=10, decimal_places=7."},
            {"name": "sistema_referencia", "type": "CharField · choices", "desc": "Sistema geodésico de referencia para las coordenadas. Default: EPSG:4326.",
             "choices": _c(
                 ("EPSG:4326", "Sistema geodésico global estándar; coordenadas geográficas en latitud y longitud. (WGS84)"),
                 ("EPSG:4686", "Sistema geodésico oficial de Colombia, compatible con WGS84. (MAGNA-SIRGAS)"),
                 ("EPSG:4674", "Sistema geodésico regional usado en América del Sur. (SIRGAS2000)"),
                 ("otro", "Sistema de referencia distinto; se debe indicar el código EPSG."),
             )},
            {"name": "altitud", "type": "DecimalField · null", "desc": "Elevación sobre el nivel del mar en metros (m.s.n.m.). max_digits=8, decimal_places=2. Opcional."},
            {"name": "pendiente", "type": "CharField · choices", "desc": "Inclinación del terreno en el sitio de monitoreo.",
             "choices": _c(
                 ("plano", "Superficie con pendiente mínima."),
                 ("ondulado_variable", "Relieve irregular con pendientes variables."),
                 ("pendiente_suave", "Pendiente muy baja (<2%)."),
                 ("pendiente_media", "Pendiente moderada (2–5%)."),
                 ("pendiente_significativa", "Pendiente marcada (5–10%)."),
                 ("pendiente_fuerte", "Pendiente pronunciada (>10%)."),
                 ("cresta_cima", "Parte alta o divisoria del relieve."),
                 ("valle_fondo", "Zona baja del relieve con acumulación."),
             )},
            {"name": "topografia", "type": "CharField · choices", "desc": "Forma general del relieve local en el sitio.",
             "choices": _c(
                 ("cresta_cima", "Parte más alta del relieve; zona de divergencia de escorrentía."),
                 ("ladera_superior", "Tramo alto de la ladera; drenaje rápido y baja acumulación."),
                 ("ladera_media", "Tramo intermedio de la ladera; tránsito de agua y sedimentos."),
                 ("ladera_inferior", "Tramo bajo de la ladera; mayor acumulación de agua y materiales."),
                 ("valle_fondo", "Zona baja del relieve; acumulación de agua y sedimentos."),
                 ("plano", "Superficie con pendiente mínima y escasa redistribución lateral."),
             )},
            {"name": "created_at", "type": "DateTimeField", "desc": "Fecha y hora de creación del registro (auto)."},
            {"name": "updated_at", "type": "DateTimeField", "desc": "Fecha y hora de última modificación (auto)."},
        ],
    },
    # ── Modelo: RegistroFlujoCamara ────────────────────────────────────────────
    {
        "id": "registro",
        "model": "RegistroFlujoCamara",
        "name": "Registro Flujo Camara",
        "color": "#6b4f9e",
        "fk": {"field": "sitio", "to": "sitio"},
        "fields": [
            {"name": "sitio", "type": "FK -> SitioMonitoreo", "desc": "Sitio de monitoreo al que pertenece este registro. on_delete=PROTECT."},
            {"name": "codigo_metadatos", "type": "CharField - unique", "desc": "Codigo unico del registro de metadatos. max_length=80."},
            {"name": "created_at", "type": "DateTimeField", "desc": "Fecha y hora de creacion del registro (auto)."},
            {"name": "updated_at", "type": "DateTimeField", "desc": "Fecha y hora de ultima modificacion (auto)."},
        ],
    },
    # -- Modelo: Cobertura --
    {
        "id": "cobertura",
        "model": "Cobertura",
        "name": "Cobertura",
        "color": "#1a6e9b",
        "fk": {"field": "registro", "to": "registro"},
        "fields": [
            {"name": "registro", "type": "O2O -> RegistroFlujoCamara", "desc": "Registro al que pertenece esta cobertura. Relacion uno a uno. on_delete=CASCADE."},
            {"name": "cobertura_ipcc", "type": "CharField", "desc": "Categoria de cobertura del suelo segun el IPCC. max_length=120. Opcional."},
            {"name": "cobertura_clc", "type": "CharField", "desc": "Categoria Corine Land Cover Nivel 4. max_length=120. Opcional."},
            {"name": "cobertura_igbp", "type": "CharField", "desc": "Categoria segun el International Geosphere-Biosphere Programme. max_length=120. Opcional."},
            {"name": "cobertura_nom_comun", "type": "CharField", "desc": "Nombre local o nacional de la cobertura vegetal. max_length=160. Opcional."},
            {"name": "cobertura_humedal", "type": "CharField choices", "desc": "Tipo de cobertura de humedal segun clasificacion funcional del sitio.",
             "choices": _c(
                 ("turbera_musgo", "Turbera de musgo (bog): humedal ombrotrofico, alimentado solo por lluvia, muy acido y pobre en nutrientes."),
                 ("turbera_pantanosa", "Turbera pantanosa (fen): humedal minerotrofico, conectado a aguas subterraneas o superficiales."),
                 ("pantano_arbolado", "Pantano arbolado (swamp): humedal con vegetacion lenosa dominante, inundado estacional o permanentemente."),
                 ("marisma", "Marisma / estuario: humedal costero de agua salobre con influencia de mareas."),
                 ("manglar", "Manglar: ecosistema costero tropical con arboles halofitos e influencia mareal."),
                 ("lago_laguna", "Lago / laguna: cuerpo de agua continental, permanente o semipermanente."),
                 ("rio_ripario", "Rio / zona riparia: franja de vegetacion asociada a cursos de agua."),
                 ("sabana_inundable", "Sabana inundable: pastizal que se inunda estacionalmente."),
                 ("arrozal", "Arrozal: cultivo inundado de arroz con dinamica similar a humedal artificial."),
                 ("no_aplica", "No aplica: el sitio no corresponde a una categoria de humedal."),
             )},
            {"name": "clima_koeppen", "type": "CharField choices", "desc": "Clasificacion climatica de Koeppen del sitio.",
             "choices": _c(
                 ("selva_tropical_lluviosa", "Clima calido y humedo todo el anio, sin estacion seca. Favorece bosques densos y siempreverdes."),
                 ("monzon_tropical", "Clima calido con estacion humeda intensa y estacion seca corta."),
                 ("sabana_tropical", "Clima calido con estacion seca bien definida. Pastizales y bosques abiertos."),
                 ("desierto_IC", "Clima extremadamente arido, precipitaciones <250 mm/anio. Vegetacion xerofitica."),
                 ("desierto_IF", "Clima arido con inviernos frios y veranos calidos. Vegetacion muy limitada."),
                 ("oceanico_VC", "Clima templado con precipitaciones constantes y veranos calidos. Influencia maritima."),
                 ("oceanico_VF", "Clima templado-frio con veranos frescos e inviernos suaves. Frecuente nubosidad."),
                 ("montania_VC", "Clima templado de altitud. Invierno seco, verano lluvioso."),
                 ("montania_VF", "Clima de montania mas frio, inviernos secos y veranos frescos."),
                 ("continental_humedo", "Inviernos frios y veranos calurosos. Precipitaciones distribuidas todo el anio."),
                 ("continental_verano_calido", "Clima continental con inviernos frios y veranos templados a calidos."),
                 ("continental_seco_VC", "Estacion seca en invierno y veranos calurosos. Alta amplitud termica."),
                 ("continental_seco_VF", "Estacion seca y veranos frescos. Inviernos frios."),
                 ("tundra", "Clima polar frio, temperatura del mes mas calido <10 grados C. Vegetacion baja."),
                 ("casquete_hielo", "Clima polar extremo, temperatura media mensual nunca supera 0 grados C."),
             )},
        ],
    },
    # -- Modelo: Disturbio --
    {
        "id": "disturbio",
        "model": "Disturbio",
        "name": "Disturbio",
        "color": "#c0392b",
        "fk": {"field": "registro", "to": "registro"},
        "fields": [
            {"name": "registro", "type": "O2O -> RegistroFlujoCamara", "desc": "Registro al que pertenece este disturbio. Relacion uno a uno. on_delete=CASCADE."},
            {"name": "tipo_disturbio", "type": "CharField choices", "desc": "Tipo principal de disturbio ocurrido en el sitio. Default: Sin disturbio.",
             "choices": _c(
                 ("agricultura", "Manejo agricola: cultivo (labranza, arado, rastra), cosecha, riego, pesticidas, siembra o encalado."),
                 ("sequia", "Sequia: Deficiencia prolongada de agua; sequia hidrologica o climatica."),
                 ("fuego", "Fuego: Incendios forestales o quemas controladas."),
                 ("silvicultura", "Silvicultura: aprovechamiento maderero, plantaciones o aplicacion de herbicidas."),
                 ("pastoreo", "Pastoreo: Herbivoria o ramoneo por mamiferos, manejados o silvestres."),
                 ("evento_hidrologico", "Evento hidrologico: Drenaje, inundacion persistente o cronica."),
                 ("cambio_cobertura", "Cambio en cobertura del suelo; invasiones biologicas; expansion lenosa o urbana."),
                 ("plagas_enfermedades", "Plagas y enfermedades: dano por plagas, insectos, patogenos o tizones."),
                 ("tormenta_viento", "Tormenta o viento: precipitacion extrema o vientos fuertes (huracanes, tornados)."),
                 ("extremos_temperatura", "Extremos de temperatura: Olas de calor o heladas."),
                 ("sin_disturbio", "Sin disturbio: No se ha registrado disturbio ni manejo en el sitio."),
             )},
            {"name": "anios_disturbio", "type": "PositiveIntegerField null", "desc": "Duracion o periodo del disturbio en anios. Opcional."},
            {"name": "anios_desde_fin_disturbio", "type": "PositiveIntegerField null", "desc": "Anios transcurridos desde el fin del disturbio. Opcional."},
            {"name": "uso_actual", "type": "CharField choices", "desc": "Uso actual del suelo en el sitio de monitoreo.",
             "choices": _c(
                 ("bosque_primario", "Bosque nativo sin intervencion humana significativa; mantiene estructura ecologica original."),
                 ("bosque_secundario", "Bosque regenerado naturalmente despues de un disturbio."),
                 ("plantacion_forestal", "Area forestada artificialmente con una o pocas especies, con fines productivos."),
                 ("agricultura_intensiva", "Cultivo agricola con fertilizantes o mecanizacion."),
                 ("agricultura_tradicional", "Cultivo agricola sin insumos intensivos."),
                 ("pastura", "Area dominada por gramineas usada para pastoreo."),
                 ("humedal_natural", "Ecosistema con suelos saturados o inundados periodicamente."),
                 ("humedal_intervenido", "Humedal con alteraciones hidrologicas (drenaje, canalizacion, compactacion)."),
                 ("area_protegida", "Territorio legalmente designado para conservacion bajo categoria oficial."),
                 ("sistema_agroforestal", "Sistema que integra arboles con cultivos y/o ganado en la misma unidad espacial."),
                 ("abandonado", "Area previamente usada para agricultura o pastura sin manejo activo actual."),
                 ("restauracion_activa", "Area en proceso formal de restauracion ecologica con intervencion planificada."),
             )},
            {"name": "estado_actual", "type": "CharField choices", "desc": "Condicion ecologica actual del sitio.",
             "choices": _c(
                 ("intacto", "Sin senales evidentes de degradacion estructural o funcional."),
                 ("ligeramente_degradado", "Alteraciones leves sin perdida significativa de funciones ecologicas."),
                 ("moderadamente_degradado", "Reduccion clara en biodiversidad o cambios hidrologicos parciales."),
                 ("severamente_degradado", "Perdida significativa de cobertura vegetal y alteracion del ciclo hidrologico."),
                 ("en_recuperacion_natural", "En regeneracion tras disturbio sin intervencion intensiva."),
                 ("en_restauracion_activa", "Con intervencion planificada que ha alcanzado estabilidad funcional."),
                 ("estable", "Mantiene estructura y funcion constantes bajo el regimen actual."),
                 ("en_transicion", "En cambio activo entre estados (ej. pastura a bosque secundario)."),
             )},
            {"name": "propiedad_tierra", "type": "CharField choices", "desc": "Figura de propiedad o regimen legal de la tierra.",
             "choices": _c(
                 ("publica", "Terreno de propiedad del Estado o entidad publica."),
                 ("privada", "Terreno de propiedad privada o comunitaria no estatal."),
             )},
        ],
    },
    # -- Modelo: Caracterizacion --
    {
        "id": "caracterizacion",
        "model": "Caracterizacion",
        "name": "Caracterizacion",
        "color": "#d35400",
        "fk": {"field": "registro", "to": "registro"},
        "fields": [
            {"name": "registro", "type": "O2O -> RegistroFlujoCamara", "desc": "Registro al que pertenece esta caracterizacion. Relacion uno a uno. on_delete=CASCADE."},
            {"name": "tipo_de_suelo", "type": "CharField choices", "desc": "Tipo dominante de suelo en el sitio.",
             "choices": _c(
                 ("mineral", "Suelo dominado por particulas minerales (arena, limo, arcilla) con bajo contenido de materia organica."),
                 ("organico", "Suelo con alto contenido de materia organica acumulada, formado en condiciones saturadas de agua."),
             )},
            {"name": "microtopografia", "type": "CharField choices", "desc": "Variaciones del relieve a pequenia escala dentro de la parcela.",
             "choices": _c(
                 ("hummock", "Hummock: Cojines (elevaciones pequenias sobre la superficie)."),
                 ("hollow", "Hollow: Depresiones humedas entre cojines."),
                 ("pool", "Pool: Charcos, piscinas o mediciones sobre agua."),
                 ("lawns", "Lawns: Lugares planos, sin micro-relieve pronunciado."),
             )},
            {"name": "diametro_anillo", "type": "DecimalField null", "desc": "Diametro del anillo evaluado en cm (disenos concentricos/circulares). max_digits=8, decimal_places=2. Opcional."},
            {"name": "tratamiento", "type": "CharField", "desc": "Condicion experimental o de manejo aplicada al sitio (ej. control, quema, exclusion). max_length=255. Opcional."},
            {"name": "pozo_nivel_freatico", "type": "CharField", "desc": "Profundidad (m) desde la superficie hasta el nivel donde el agua satura los poros del suelo. max_length=80. Opcional."},
        ],
    },
    # -- Modelo: CaracterizacionMuestreo --
    {
        "id": "caracterizacion_muestreo",
        "model": "CaracterizacionMuestreo",
        "name": "Caracterizacion Muestreo",
        "color": "#7f8c8d",
        "fk": {"field": "registro", "to": "registro"},
        "fields": [
            {"name": "registro", "type": "O2O -> RegistroFlujoCamara", "desc": "Registro al que pertenece este muestreo de suelo. Relacion uno a uno. on_delete=CASCADE."},
            {"name": "profundidad_perfil", "type": "DecimalField null", "desc": "Profundidad total del perfil de suelo muestreado en cm. Opcional."},
            {"name": "intervalos_perfil", "type": "DecimalField null", "desc": "Tamano de los intervalos de muestreo dentro del perfil en cm (ej. 10 cm, 20 cm). Opcional."},
            {"name": "monitoreo_macrofosiles", "type": "BooleanField", "desc": "Indica si se realiza monitoreo de macrofosiles en el sitio. Default: False."},
            {"name": "protocolo_macrofosiles", "type": "CharField", "desc": "Descripcion o nombre del protocolo para muestreo de macrofosiles. max_length=255. Opcional."},
            {"name": "monitoreo_datacion", "type": "BooleanField", "desc": "Indica si se realizan analisis de datacion (ej. radiocarbono, Pb-210). Default: False."},
            {"name": "protocolo_datacion", "type": "CharField", "desc": "Descripcion o nombre del protocolo de datacion utilizado. max_length=255. Opcional."},
            {"name": "monitoreo_densidad_aparente", "type": "BooleanField", "desc": "Indica si se mide la densidad aparente del suelo. Default: False."},
            {"name": "protocolo_densidad_aparente", "type": "CharField choices", "desc": "Metodo estandar para medir la densidad aparente del suelo.",
             "choices": _c(
                 ("anillo_volumetrico", "Anillo volumetrico (core ring): extraccion de nucleo de volumen conocido para determinar masa seca."),
                 ("terron_parafina", "Terron parafinado: impermeabilizacion con parafina para medir volumen por desplazamiento de agua."),
                 ("cilindro_driving", "Cilindro tipo driving: hincado mecanico para obtener nucleos de suelo no perturbados."),
                 ("otro", "Otro: metodo no listado, especificar en notas del registro."),
             )},
            {"name": "monitoreo_cos", "type": "BooleanField", "desc": "Indica si se mide el Carbono Organico del Suelo (COS). Default: False."},
            {"name": "protocolo_cos", "type": "CharField choices", "desc": "Metodo analitico para determinar el Carbono Organico del Suelo (COS).",
             "choices": _c(
                 ("loss_on_ignition", "Perdida por ignicion (LOI): calcinacion a 550 C para estimar materia organica por perdida de masa."),
                 ("walkley_black", "Walkley-Black (oxidacion humeda): oxidacion con dicromato de potasio en medio acido."),
                 ("combustion_seca", "Combustion seca: analisis elemental en horno a alta temperatura (analizador CHN/CHNS)."),
                 ("espectroscopia_nir", "Espectroscopia NIR/MIR: estimacion por reflectancia infrarroja, requiere calibracion previa."),
                 ("otro", "Otro: metodo no listado, especificar en notas del registro."),
             )},
        ],
    },
    # -- Modelo: VegetacionAnillo --
    {
        "id": "vegetacion_anillo",
        "model": "VegetacionAnillo",
        "name": "Vegetacion Anillo",
        "color": "#27ae60",
        "fk": {"field": "registro", "to": "registro"},
        "fields": [
            {"name": "registro", "type": "O2O -> RegistroFlujoCamara", "desc": "Registro al que pertenece esta vegetacion. Relacion uno a uno. on_delete=CASCADE."},
            {"name": "cobertura_vegetal_primaria", "type": "CharField", "desc": "Estrato o tipo de cobertura dominante en la unidad de muestreo. max_length=160."},
            {"name": "porcentaje_cob_veg_pri", "type": "DecimalField null", "desc": "% de suelo cubierto por la proyeccion vertical de la cobertura primaria. max_digits=5, decimal_places=2."},
            {"name": "cobertura_vegetal_secundaria", "type": "CharField", "desc": "Segundo estrato o tipo de cobertura en importancia. max_length=160."},
            {"name": "porcentaje_cob_veg_sec", "type": "DecimalField null", "desc": "% de ocupacion espacial del segundo estrato identificado. max_digits=5, decimal_places=2."},
            {"name": "cobertura_vegetal_terciaria", "type": "CharField", "desc": "Tercer nivel de cobertura, usualmente herbaceo o rasante. max_length=160."},
            {"name": "porcentaje_cob_veg_ter", "type": "DecimalField null", "desc": "% de ocupacion espacial del tercer estrato. max_digits=5, decimal_places=2."},
        ],
    },
    # -- Modelo: Distancias --
    {
        "id": "distancias",
        "model": "Distancias",
        "name": "Distancias",
        "color": "#2c3e50",
        "fk": {"field": "registro", "to": "registro"},
        "fields": [
            {"name": "registro", "type": "O2O -> RegistroFlujoCamara", "desc": "Registro al que pertenece este bloque de distancias. Relacion uno a uno. on_delete=CASCADE."},
            {"name": "distancia_drenaje", "type": "DecimalField null", "desc": "Distancia (m) desde el centro de la parcela hasta el cuerpo de agua o canal de drenaje mas cercano. Determina el gradiente de humedad."},
            {"name": "distancia_fuego", "type": "DecimalField null", "desc": "Distancia (m) a la evidencia mas cercana de quema o cicatriz de incendio forestal."},
            {"name": "distancia_pastoreo", "type": "DecimalField null", "desc": "Distancia (m) a zonas de actividad ganadera o senderos de ganado (afectan compactacion y regeneracion)."},
            {"name": "distancia_cultivo", "type": "DecimalField null", "desc": "Distancia (m) desde el borde de la parcela hasta la frontera agricola activa mas cercana."},
        ],
    },
    # ── Modelo: RegistroBiomasa ────────────────────────────────────────────────
    {
        "id": "registro_biomasa",
        "model": "RegistroBiomasa",
        "name": "Registro Biomasa",
        "color": "#8e44ad",
        "fk": {"field": "sitio", "to": "sitio"},
        "fields": [
            {"name": "sitio", "type": "FK -> SitioMonitoreo", "desc": "Sitio de monitoreo al que pertenece este registro. Reutiliza el modelo SitioMonitoreo existente. on_delete=PROTECT."},
            {"name": "codigo_metadatos", "type": "CharField unique", "desc": "Codigo unico del registro de metadatos de biomasa. max_length=80."},
            {"name": "parcela", "type": "CharField", "desc": "Codigo identificador de la parcela dentro del sitio de monitoreo. max_length=80. Opcional."},
            {"name": "created_at", "type": "DateTimeField", "desc": "Fecha y hora de creacion del registro (auto)."},
            {"name": "updated_at", "type": "DateTimeField", "desc": "Fecha y hora de ultima modificacion (auto)."},
        ],
        "shared_note": "Cobertura y Disturbio son modelos compartidos con FlujoCamara. Se vinculan via registro_biomasa (OneToOneField nullable).",
    },
    # ── Modelo: CaracterizacionParcela ─────────────────────────────────────────
    {
        "id": "caracterizacion_parcela",
        "model": "CaracterizacionParcela",
        "name": "Caracterizacion Parcela",
        "color": "#16a085",
        "fk": {"field": "registro", "to": "registro_biomasa"},
        "fields": [
            {"name": "registro", "type": "O2O -> RegistroBiomasa", "desc": "Registro de biomasa al que pertenece esta caracterizacion. Relacion uno a uno. on_delete=CASCADE."},
            {"name": "unidad_de_muestreo", "type": "CharField choices", "desc": "Tipo de unidad espacial usada para el muestreo de biomasa.",
             "choices": _c(
                 ("parcela_circular", "Parcela circular: unidad de muestreo con forma de circulo y radio fijo."),
                 ("parcela_cuadrada", "Parcela cuadrada: unidad rectangular con area definida."),
                 ("transecto", "Transecto lineal: linea de muestreo con ancho y longitud definidos."),
                 ("punto_radio_fijo", "Punto de radio fijo: muestreo desde un centro con radio variable segun DAP."),
                 ("banda", "Banda / franja: unidad de muestreo alargada para inventario de vegetacion."),
                 ("otra", "Otra: unidad no listada, especificar en notas."),
             )},
            {"name": "area", "type": "DecimalField null", "desc": "Area de la unidad de muestreo en metros cuadrados (m2). max_digits=12, decimal_places=2. Opcional."},
            {"name": "estatus_parcela", "type": "CharField choices", "desc": "Estado operativo actual de la parcela de monitoreo.",
             "choices": _c(
                 ("activa", "Activa: en monitoreo regular y con acceso garantizado."),
                 ("inactiva", "Inactiva: sin monitoreo activo temporalmente."),
                 ("abandonada", "Abandonada: sin posibilidad de continuar el monitoreo."),
                 ("nueva", "Nueva: instalada pero sin mediciones registradas aun."),
                 ("en_restauracion", "En restauracion: bajo proceso de restauracion ecologica activa."),
             )},
            {"name": "fecha_instalacion", "type": "PositiveIntegerField null", "desc": "Anio de instalacion de la parcela (ej. 2021). Opcional."},
            {"name": "monitoreo_biomasa_aerea", "type": "BooleanField", "desc": "Indica si se realiza monitoreo de biomasa aerea (arboles, arbustos, herbaceas). Default: False."},
            {"name": "protocolo_biomasa_aerea", "type": "CharField choices", "desc": "Protocolo o metodo utilizado para estimar la biomasa aerea.",
             "choices": _c(
                 ("ecuaciones_alometricas", "Ecuaciones alometricas: modelos matematicos que relacionan DAP, altura y densidad de madera con biomasa."),
                 ("inventario_forestal_completo", "Inventario forestal completo: medicion de DAP, altura total y densidad de todas las especies."),
                 ("cosecha_destructiva", "Cosecha destructiva: colecta, pesaje y secado en horno de toda la biomasa de la parcela."),
                 ("teledeteccion_lidar", "Teledeteccion / LiDAR: estimacion remota de estructura vegetal y biomasa por sensores activos o pasivos."),
                 ("otro", "Otro: metodo no listado, especificar en notas."),
             )},
            {"name": "monitoreo_biomasa_subterranea", "type": "BooleanField", "desc": "Indica si se realiza monitoreo de biomasa subterranea (raices, rizomas). Default: False."},
            {"name": "protocolo_biomasa_subterranea", "type": "CharField", "desc": "Descripcion del protocolo de muestreo de biomasa subterranea (ej. monolito, barreno, fraccion de raices). max_length=255. Opcional."},
            {"name": "monitoreo_flora", "type": "BooleanField", "desc": "Indica si se realiza inventario o monitoreo de flora vascular en la parcela. Default: False."},
            {"name": "protocolo_flora", "type": "CharField", "desc": "Descripcion del protocolo de inventario floristico (ej. cuadrantes anidados, transecto de Whittaker). max_length=255. Opcional."},
            {"name": "monitoreo_rasgos_funcionales", "type": "BooleanField", "desc": "Indica si se miden rasgos funcionales de plantas (SLA, LDMC, altura, area foliar, etc.). Default: False."},
            {"name": "protocolo_rasgos_funcionales", "type": "CharField", "desc": "Descripcion del protocolo para medicion de rasgos funcionales de plantas (ej. manual TRY, LEDA). max_length=255. Opcional."},
        ],
    },
]


def chart_data(request):
    by_year = (
        EmissionRecord.objects.values("year")
        .annotate(total=Sum("co2e_tonnes"))
        .order_by("year")
    )
    by_sector = (
        EmissionRecord.objects.values("sector__name")
        .annotate(total=Sum("co2e_tonnes"))
        .order_by("-total")[:12]
    )
    by_gas = (
        EmissionRecord.objects.values("gas__chemical_formula")
        .annotate(total=Sum("co2e_tonnes"))
        .order_by("-total")
    )
    return JsonResponse(
        {
            "by_year": [{"label": item["year"], "value": float(item["total"])} for item in by_year],
            "by_sector": [
                {"label": item["sector__name"], "value": float(item["total"])}
                for item in by_sector
            ],
            "by_gas": [
                {"label": item["gas__chemical_formula"], "value": float(item["total"])}
                for item in by_gas
            ],
        }
    )
