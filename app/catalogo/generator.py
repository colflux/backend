import json

from django.apps import apps


# "color" es la fuente única de verdad para el color de cada categoría: la
# usan tanto el diagrama ERD del frontend (/db, vía catalogo.json) como el
# Excel exportado (app/api/etl/views.py, ver COLOR_POR_MODELO más abajo).
# Definida a mano por Viviana — incluye 2 pares con el mismo color a
# propósito (Suelo/COS en naranja; Torre EC y Flujos/Muestras GEI en azul):
# esos no chocan porque Suelo y Torre EC y Flujos no aparecen en el Excel
# hoy. Geografía y "Unidad de Muestreo y Experimental" sí chocan en la hoja
# real ("Unidad Muestreo-Experimental" tiene columnas de ambas categorías),
# así que se les puso colores distintos: Geografía en rojo camarón/coral,
# "Unidad de Muestreo y Experimental" en violeta.
GRUPOS_CATALOGO = [
    {
        "nombre": "Publicaciones",
        "icono": "📄",
        "color": "#475569",
        "entidades": ["PublicacionType", "Publicacion", "Autor"],
    },
    {
        "nombre": "Geografía",
        "icono": "🗺️",
        "color": "#ff6f61",  # rojo camarón / coral — distinto de Unidad de Muestreo y Experimental
        "entidades": ["Region", "Departamento", "Municipio", "Sitio"],
    },
    {
        "nombre": "Unidad de Muestreo y Experimental",
        "icono": "📍",
        "color": "#7c3aed",  # violeta
        "entidades": ["UnidadMuestreoTipo", "UnidadMuestreo", "UnidadExperimental", "Parcela", "Transecto"],
    },
    # Nota: el ETL (app/api/etl/views.py) usa su propio SECCIONES_ETL, que
    # divide este grupo en "Unidad Experimental" y "Unidad de Muestreo" (y
    # separa "Sitio" de Geografía en su propia sección) para reflejar el
    # orden real de carga: primero se define la unidad experimental, luego
    # la unidad de muestreo (que depende de ella), y por último el sitio.
    # Este agrupamiento se mantiene tal cual para el catálogo de referencia.
    {
        "nombre": "Cobertura y Vegetación",
        "icono": "🌿",
        "color": "#0f8139",
        "entidades": ["TipoCobertura", "Cobertura", "Vegetacion", "Disturbio"],
    },
    {
        "nombre": "Suelo",
        "icono": "🪨",
        "color": "#e69138",
        "entidades": ["CaracterizacionMuestreoSuelo", "MonitoreoSuelo"],
    },
    {
        # Grupo aparte de "Suelo": CaracterizacionMuestreoSuelo/MonitoreoSuelo
        # son protocolo/metadata con FK a Sitio (no compatibles con el ETL
        # por fila, ver _GRUPOS_EXCLUIDOS_TEMPORAL en app/api/etl/views.py).
        # SubmuestraSuelo sí tiene FK a UnidadMuestreo y guarda el valor
        # medido (profundidad, densidad aparente, % carbono), así que puede
        # cargarse fila por fila igual que MuestraGEI/SubmuestraGEI.
        "nombre": "Carbono Orgánico del Suelo (COS)",
        "icono": "🧫",
        "color": "#e69138",
        "entidades": ["SubmuestraSuelo"],
    },
    {
        "nombre": "Biomasa",
        "icono": "🌳",
        "color": "#88bb72",
        "entidades": ["MuestraBiomasa", "IndividuoArboreo"],
    },
    {
        "nombre": "Materia Orgánica Muerta (MOM)",
        "icono": "🍂",
        "color": "#c36c2d",
        "entidades": ["MuestraMOM"],
    },
    {
        "nombre": "Torre EC y Flujos",
        "icono": "📡",
        "color": "#3c78d8",
        "entidades": ["TorreEc", "ConfiguracionSensorGas"],
    },
    {
        "nombre": "Muestras GEI",
        "icono": "🫧",
        "color": "#3c78d8",
        "entidades": [
            "UnidadMedida", "Equipo", "TipoMuestra",
            "MuestraAmbiental", "MuestraGEI", "SubmuestraGEI",
        ],
    },
    {
        "nombre": "Proyecto",
        "icono": "🗂️",
        "color": "#333faf",
        "entidades": ["Proyecto", "Institucion", "ProyectoInstitucion", "ProyectoUsuario"],
    },
    {
        "nombre": "Usuarios, Roles y ETL",
        "icono": "📂",
        "color": "#ffd966",
        "entidades": ["Usuario", "RolUsuario", "FuenteDatos", "CargaArchivo", "MapeoColumna"],
    },
]

# Modelo -> color de su categoría, para colorear encabezados en el Excel
# exportado (ver app/api/etl/views.py). Se deriva de GRUPOS_CATALOGO en vez
# de duplicar la asignación.
COLOR_POR_MODELO = {
    nombre_modelo: grupo["color"]
    for grupo in GRUPOS_CATALOGO
    for nombre_modelo in grupo["entidades"]
}

ENTIDADES_SEMILLA = {
    "PublicacionType",
    "Region",
    "Departamento",
    "UnidadMedida",
    "Equipo",
    "TipoMuestra",
}

TIPO_MAP = {
    "CharField": "Texto",
    "TextField": "Texto largo",
    "IntegerField": "Entero",
    "FloatField": "Decimal",
    "DecimalField": "Decimal",
    "DateField": "Fecha",
    "DateTimeField": "Fecha y hora",
    "BooleanField": "Booleano",
    "URLField": "URL",
    "EmailField": "Correo",
    "JSONField": "JSON",
    "FileField": "Archivo",
    "ForeignKey": "FK (relación)",
}


def semilla_rows(modelo_cls):
    concrete_fields = [
        field
        for field in modelo_cls._meta.get_fields()
        if hasattr(field, "column") and field.name not in ("created_at", "updated_at", "geom")
    ]
    fk_names = [f.name for f in concrete_fields if f.is_relation]

    rows = []
    for obj in modelo_cls.objects.select_related(*fk_names):
        row = {}
        for field in concrete_fields:
            valor = getattr(obj, field.name)
            row[field.name] = str(valor) if field.is_relation and valor is not None else valor
        rows.append(row)
    return rows


# Cómo llegar del modelo relacionado hasta Proyecto, para poder filtrar las
# opciones de un FK a lo ya cargado en el mismo proyecto (y no mezclar con lo
# de otros proyectos). Sitio y los catálogos cerrados (UnidadMuestreoTipo,
# UnidadMedida, …) quedan fuera a propósito: son globales/reutilizables entre
# proyectos, no pertenecen a uno solo.
_FILTRO_PROYECTO_POR_MODELO = {
    "UnidadExperimental": "proyecto",
    "UnidadMuestreo": "unidad_experimental__proyecto",
    "MuestraAmbiental": "unidad_muestreo__unidad_experimental__proyecto",
    "MuestraGEI": "unidad_muestreo__unidad_experimental__proyecto",
}



# Tope de instancias que se listan como choices de un FK: sin esto, un
# modelo con catálogo masivo (p. ej. Vereda, ~550k filas del MGN) satura la
# respuesta y el worker termina en OOM/SIGKILL construyendo el str() de cada
# fila. Por encima del tope, el usuario sigue pudiendo escribir el valor a
# mano/vía lookup en el wizard; esto solo acota el dropdown de sugerencias.
_FK_CHOICES_LIMITE = 500


def fk_choices(field, proyecto=None):
    """Instancias existentes del modelo relacionado, para usar como opciones de un FK.

    Si se pasa `proyecto` y el modelo relacionado tiene forma de acotarse a un
    proyecto (ver `_FILTRO_PROYECTO_POR_MODELO`), solo se listan las instancias
    de ese proyecto — así se reutilizan las unidades ya cargadas en vez de
    mostrar (y potencialmente duplicar) las de todos los proyectos.
    """
    modelo_cls = field.related_model
    try:
        qs = modelo_cls.objects.all()
        filtro = _FILTRO_PROYECTO_POR_MODELO.get(modelo_cls.__name__)
        if proyecto is not None and filtro:
            qs = qs.filter(**{filtro: proyecto})
        # select_related de las FK directas: evita N+1 al armar str(obj) para
        # modelos cuyo __str__ recorre una relación (p. ej. Vereda -> Municipio).
        fk_names = [
            f.name for f in modelo_cls._meta.get_fields()
            if getattr(f, "is_relation", False) and hasattr(f, "column")
        ]
        if fk_names:
            qs = qs.select_related(*fk_names)
        qs = qs[:_FK_CHOICES_LIMITE]
        return [{"valor": str(obj.pk), "etiqueta": str(obj)} for obj in qs]
    except Exception:
        # La tabla puede no existir aún (p. ej. generación del catálogo antes de migrar).
        return []


# Campos que el ETL llena solo (ver app/api/etl/views.py, kwargs.setdefault),
# aunque el modelo los marque como requeridos: el wizard no debe pedirle al
# usuario que los mapee, porque ya se resuelven desde la fuente/carga.
CAMPOS_AUTOMATICOS_ETL = {
    ("UnidadExperimental", "proyecto"),
    ("UnidadMuestreo", "fuente_datos"),
    ("UnidadMuestreo", "unidad_experimental"),
    ("MuestraAmbiental", "fuente_datos"),
    # Igual que UnidadMuestreo.unidad_experimental: se resuelve solo,
    # vinculando cada SubmuestraGEI con la MuestraGEI ya creada para esa
    # misma fila dentro de la sección "Muestras GEI" -no tiene sentido
    # pedirle al usuario que mapee una columna de origen para esto.
    ("SubmuestraGEI", "muestra"),
}

# Caso inverso a CAMPOS_AUTOMATICOS_ETL: campos que el modelo permite en
# blanco (para no romper otros flujos de escritura) pero que el wizard debe
# pedir como obligatorios, porque sin ellos la fila no aporta nada -una
# SubmuestraGEI sin valor de flujo no es una medición.
CAMPOS_OBLIGATORIOS_ETL = {
    ("SubmuestraGEI", "valor"),
}


def campo_to_catalogo(field, proyecto=None, incluir_instancias_fk=False, nombre_modelo=None):
    """`incluir_instancias_fk` solo debe pedirlo el ETL (campos_destino), que
    necesita ofrecer instancias reales ya cargadas (p. ej. qué UnidadMuestreo
    ya existen) para que el usuario elija una al mapear una columna. El
    catálogo público (modelo_to_catalogo/docs) documenta el *tipo* de dato
    -qué modelo referencia un FK, qué opciones tiene un choices= estático-,
    no instancias creadas dinámicamente al cargar datos: UnidadMuestreo,
    UnidadExperimental, etc. no son parte del tipado, son datos de negocio."""
    tipo_raw = field.__class__.__name__
    es_fk = tipo_raw == "ForeignKey"
    choices = [
        {"valor": valor, "etiqueta": etiqueta}
        for valor, etiqueta in (getattr(field, "choices", None) or [])
    ]
    if es_fk and not choices and incluir_instancias_fk:
        choices = fk_choices(field, proyecto=proyecto)
    return {
        "nombre": field.name,
        "verbose_name": str(getattr(field, "verbose_name", field.name)),
        "help_text": str(getattr(field, "help_text", "") or ""),
        "tipo": TIPO_MAP.get(tipo_raw, tipo_raw),
        "tipo_raw": tipo_raw,
        "requerido": (
            not (getattr(field, "blank", True) or getattr(field, "null", True))
            or (nombre_modelo, field.name) in CAMPOS_OBLIGATORIOS_ETL
        ),
        "automatico": (nombre_modelo, field.name) in CAMPOS_AUTOMATICOS_ETL,
        "max_length": getattr(field, "max_length", None),
        "choices": choices,
        "es_fk": es_fk,
        "modelo_fk": field.related_model.__name__ if es_fk else None,
    }


def descripcion_modelo(modelo_cls):
    doc = (modelo_cls.__doc__ or "").strip()
    # Django genera "Modelo(id, campo, ...)" cuando no hay docstring propio
    if not doc or doc.startswith(modelo_cls.__name__ + "("):
        return ""
    return " ".join(doc.split())


def modelo_to_catalogo(nombre_modelo):
    modelo_cls = apps.get_model("app", nombre_modelo)
    campos = []

    for field in modelo_cls._meta.get_fields():
        if field.is_relation and not hasattr(field, "column"):
            continue
        if field.name in ("id", "created_at", "updated_at"):
            continue
        campos.append(campo_to_catalogo(field, nombre_modelo=nombre_modelo))

    entry = {
        "nombre": nombre_modelo,
        "verbose_name": str(modelo_cls._meta.verbose_name),
        "verbose_name_plural": str(modelo_cls._meta.verbose_name_plural),
        "descripcion": descripcion_modelo(modelo_cls),
        "total_campos": len(campos),
        "campos": campos,
    }
    if nombre_modelo in ENTIDADES_SEMILLA:
        entry["datos_semilla"] = semilla_rows(modelo_cls)
    return entry


def generar_catalogo_data():
    grupos = []

    for grupo in GRUPOS_CATALOGO:
        entidades = []
        for nombre_modelo in grupo["entidades"]:
            try:
                entidades.append(modelo_to_catalogo(nombre_modelo))
            except LookupError:
                continue

        grupos.append({
            "nombre": grupo["nombre"],
            "icono": grupo["icono"],
            "color": grupo["color"],
            "entidades": entidades,
        })

    return {"grupos": grupos}


def escribir_catalogo_assets(output_dir):
    data = generar_catalogo_data()
    output_dir.mkdir(parents=True, exist_ok=True)

    json_out = output_dir / "catalogo.json"
    js_out = output_dir / "catalogo.js"

    json_out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    js_out.write_text(
        "window.CATALOGO = " + json.dumps(data, ensure_ascii=False, default=str) + ";",
        encoding="utf-8",
    )

    return data, json_out, js_out
