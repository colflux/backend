from django.apps import apps
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


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
        "entidades": ["Proyecto", "Aliado"],
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


def _semilla_rows(modelo_cls):
    concrete_fields = [
        f.attname for f in modelo_cls._meta.get_fields()
        if hasattr(f, "column")
    ]
    return list(modelo_cls.objects.values(*concrete_fields))


@csrf_exempt
def catalogo_tecnico(request):
    grupos = []
    for grupo_def in GRUPOS_CATALOGO:
        entidades = []
        for nombre_entidad in grupo_def["entidades"]:
            try:
                modelo_cls = apps.get_model("app", nombre_entidad)
            except LookupError:
                continue

            campos = []
            for field in modelo_cls._meta.get_fields():
                if field.is_relation and not hasattr(field, "column"):
                    continue
                if field.name in ("id", "created_at", "updated_at"):
                    continue

                tipo_raw = field.__class__.__name__
                tipo_legible = TIPO_MAP.get(tipo_raw, tipo_raw)

                campos.append({
                    "nombre": field.name,
                    "verbose_name": str(getattr(field, "verbose_name", field.name)),
                    "tipo": tipo_legible,
                    "tipo_raw": tipo_raw,
                    "requerido": not (getattr(field, "blank", True) or getattr(field, "null", True)),
                    "max_length": getattr(field, "max_length", None),
                    "choices": [{"valor": c[0], "etiqueta": c[1]} for c in getattr(field, "choices", []) or []],
                    "es_fk": tipo_raw == "ForeignKey",
                    "modelo_fk": field.related_model.__name__ if tipo_raw == "ForeignKey" else None,
                })

            entry = {
                "nombre": nombre_entidad,
                "verbose_name": str(modelo_cls._meta.verbose_name),
                "verbose_name_plural": str(modelo_cls._meta.verbose_name_plural),
                "total_campos": len(campos),
                "campos": campos,
            }
            if nombre_entidad in ENTIDADES_SEMILLA:
                entry["datos_semilla"] = _semilla_rows(modelo_cls)
            entidades.append(entry)

        grupos.append({
            "nombre": grupo_def["nombre"],
            "icono": grupo_def["icono"],
            "entidades": entidades,
        })

    return JsonResponse({"grupos": grupos}, json_dumps_params={"ensure_ascii": False})
