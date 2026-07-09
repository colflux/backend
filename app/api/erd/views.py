from django.apps import apps
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


MODELOS_ERD = [
    "Region", "Departamento", "Municipio",
    "Cobertura", "Vegetacion", "Disturbio",
    "Sitio", "Parcela", "Transecto", "MonitoreoParcela",
    "Proyecto", "Aliado",
    "PublicacionType", "Publicacion", "Autor", "PublicacionSitio", "ResultadoPublicacion",
    "CaracterizacionMuestreoSuelo", "MonitoreoSuelo",
    "TorreEc", "Equipo", "ConfiguracionSensorGas", "FlujoCamaras",
    "FuenteDatos", "Reportador",
]

TIPO_MAP_ERD = {
    "CharField": "string", "TextField": "string", "URLField": "string",
    "EmailField": "string", "SlugField": "string",
    "IntegerField": "int", "SmallIntegerField": "int", "PositiveIntegerField": "int",
    "FloatField": "float", "DecimalField": "decimal",
    "DateField": "date", "DateTimeField": "datetime",
    "BooleanField": "boolean",
    "JSONField": "json",
    "FileField": "string",
    "ForeignKey": "int",
}


def generar_mermaid_erd():
    lines = ["erDiagram"]
    relaciones = []

    for nombre_modelo in MODELOS_ERD:
        try:
            modelo_cls = apps.get_model("app", nombre_modelo)
        except LookupError:
            continue

        campos_erd = ["    %s {" % nombre_modelo]

        for field in modelo_cls._meta.get_fields():
            if field.is_relation and not hasattr(field, "column"):
                continue
            if field.name in ("id", "created_at", "updated_at"):
                continue

            tipo_raw = field.__class__.__name__
            tipo_erd = TIPO_MAP_ERD.get(tipo_raw, "string")
            nombre_campo = field.name

            if tipo_raw == "ForeignKey":
                nombre_campo = field.name + "_id"
                modelo_destino = field.related_model.__name__
                if modelo_destino in MODELOS_ERD:
                    card_izq = "}o" if getattr(field, "null", False) else "}|"
                    card_der = "o|" if getattr(field, "null", False) else "||"
                    relaciones.append(
                        f'    {nombre_modelo} {card_izq}--{card_der} {modelo_destino} : "{field.name}"'
                    )

            campos_erd.append(f"        {tipo_erd} {nombre_campo}")

        campos_erd.append("    }")
        lines.extend(campos_erd)

    lines.extend(relaciones)
    return "\n".join(lines)


@csrf_exempt
def db_erd(request):
    try:
        mermaid_str = generar_mermaid_erd()
        return JsonResponse({
            "mermaid": mermaid_str,
            "total_modelos": len(MODELOS_ERD),
            "generado_en": __import__("datetime").datetime.now().isoformat(),
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
