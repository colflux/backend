import json

from django.apps import apps


GRUPOS_CATALOGO = [
    {
        "nombre": "Publicaciones",
        "icono": "📄",
        "entidades": ["PublicacionType", "Publicacion", "Autor"],
    },
    {
        "nombre": "Geografía",
        "icono": "🗺️",
        "entidades": ["Region", "Departamento", "Municipio"],
    },
    {
        "nombre": "Sitio y Parcelas",
        "icono": "📍",
        "entidades": ["Sitio", "Parcela", "Transecto"],
    },
    {
        "nombre": "Cobertura y Vegetación",
        "icono": "🌿",
        "entidades": ["Cobertura", "Vegetacion", "Disturbio"],
    },
    {
        "nombre": "Suelo",
        "icono": "🪨",
        "entidades": ["CaracterizacionMuestreoSuelo", "MonitoreoSuelo"],
    },
    {
        "nombre": "Torre EC y Flujos",
        "icono": "📡",
        "entidades": ["TorreEc", "Equipo", "ConfiguracionSensorGas", "FlujoCamaras"],
    },
    {
        "nombre": "Proyecto",
        "icono": "🗂️",
        "entidades": ["Proyecto", "Institucion", "ProyectoInstitucion"],
    },
    {
        "nombre": "Usuarios, Roles y ETL",
        "icono": "📂",
        "entidades": ["Usuario", "RolUsuario", "UsuarioRol", "FuenteDatos", "CargaArchivo", "MapeoColumna"],
    },
]

ENTIDADES_SEMILLA = {
    "PublicacionType",
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
        field.attname
        for field in modelo_cls._meta.get_fields()
        if hasattr(field, "column")
    ]
    return list(modelo_cls.objects.values(*concrete_fields))


def campo_to_catalogo(field):
    tipo_raw = field.__class__.__name__
    return {
        "nombre": field.name,
        "verbose_name": str(getattr(field, "verbose_name", field.name)),
        "tipo": TIPO_MAP.get(tipo_raw, tipo_raw),
        "tipo_raw": tipo_raw,
        "requerido": not (
            getattr(field, "blank", True) or getattr(field, "null", True)
        ),
        "max_length": getattr(field, "max_length", None),
        "choices": [
            {"valor": valor, "etiqueta": etiqueta}
            for valor, etiqueta in (getattr(field, "choices", None) or [])
        ],
        "es_fk": tipo_raw == "ForeignKey",
        "modelo_fk": field.related_model.__name__ if tipo_raw == "ForeignKey" else None,
    }


def modelo_to_catalogo(nombre_modelo):
    modelo_cls = apps.get_model("app", nombre_modelo)
    campos = []

    for field in modelo_cls._meta.get_fields():
        if field.is_relation and not hasattr(field, "column"):
            continue
        if field.name in ("id", "created_at", "updated_at"):
            continue
        campos.append(campo_to_catalogo(field))

    entry = {
        "nombre": nombre_modelo,
        "verbose_name": str(modelo_cls._meta.verbose_name),
        "verbose_name_plural": str(modelo_cls._meta.verbose_name_plural),
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
            "entidades": entidades,
        })

    return {"grupos": grupos}


def escribir_catalogo_assets(output_dir):
    data = generar_catalogo_data()
    output_dir.mkdir(parents=True, exist_ok=True)

    json_out = output_dir / "catalogo.json"
    js_out = output_dir / "catalogo.js"

    json_out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    js_out.write_text(
        "window.CATALOGO = " + json.dumps(data, ensure_ascii=False) + ";",
        encoding="utf-8",
    )

    return data, json_out, js_out
