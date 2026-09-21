from django.db.models import Avg, Count
from django.db.models.functions import TruncMonth, TruncYear
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from app.models import IndividuoArboreo, MuestraBiomasa, MuestraMOM, SubmuestraSuelo

_DIMENSIONES_BIOMASA = ("familia", "genero", "especie")


@require_GET
def biomasa_por_taxon(request):
    """Conteo de individuos arbóreos agrupados por taxón:
    ?dimension=familia|genero|especie (default familia). Agregado en la
    base de datos (values + annotate), sin cargar filas individuales.

    El carbono de biomasa (MuestraBiomasa.contenido_carbono / prom_tonc_ha)
    se reporta a nivel de parcela, no por individuo/especie, así que no se
    puede calcular una "acumulación de carbono por especie" exacta con el
    esquema actual: se usa el conteo de individuos como proxy -a validar
    con el equipo si hace falta trackear carbono por individuo-."""
    dimension = request.GET.get("dimension", "familia")
    if dimension not in _DIMENSIONES_BIOMASA:
        return JsonResponse(
            {"error": f"dimension debe ser uno de: {', '.join(_DIMENSIONES_BIOMASA)}"}, status=400,
        )

    qs = (
        IndividuoArboreo.objects
        .exclude(**{dimension: ""})
        .values(dimension)
        .annotate(
            total_individuos=Count("id"),
            dap_promedio_cm=Avg("dap_analisis_cm"),
            altura_promedio_m=Avg("altura_total_m"),
        )
        .order_by("-total_individuos")
    )

    resultados = [
        {
            "nombre": fila[dimension],
            "total_individuos": fila["total_individuos"],
            "dap_promedio_cm": fila["dap_promedio_cm"],
            "altura_promedio_m": fila["altura_promedio_m"],
        }
        for fila in qs
    ]

    return JsonResponse({
        "dimension": dimension, "metrica": "conteo_individuos", "resultados": resultados,
    })


@require_GET
def biomasa_produccion(request):
    """Serie de producción de biomasa por evento de muestreo (una fila por
    MuestraBiomasa, no por individuo): fecha, producción, carbono promedio
    y ubicación del sitio. Pensada para un scatter producción vs. fecha.
    A diferencia de /api/geo/series/, el volumen es por parcela/evento, no
    por toma de flujo, así que devolver la lista completa sin agregar es
    seguro en cuanto a tamaño de respuesta.

    Usa .values() en vez de instanciar MuestraBiomasa/Sitio/Municipio: un
    select_related hasta Departamento arrastra su columna "geom" (polígono
    PostGIS pesado) en cada fila aunque no se use, lo que sobre una base de
    datos remota hace la consulta mucho más lenta de lo que el volumen de
    filas (unos pocos cientos) haría esperar."""
    qs = MuestraBiomasa.objects.exclude(fecha=None).order_by("fecha")

    proyecto_id = request.GET.get("proyecto")
    if proyecto_id:
        qs = qs.filter(unidad_muestreo__unidad_experimental__proyecto_id=proyecto_id)

    sitio_id = request.GET.get("sitio")
    if sitio_id:
        qs = qs.filter(unidad_muestreo__sitio_id=sitio_id)

    campos = qs.values(
        "fecha",
        "prod_biomasa_g",
        "prom_tonc_ha",
        "unidad_muestreo__sitio_id",
        "unidad_muestreo__sitio__nombre",
        "unidad_muestreo__sitio__vereda__municipio__departamento__nombre",
    )

    resultados = [
        {
            "fecha": f["fecha"].isoformat(),
            "prod_biomasa_g": float(f["prod_biomasa_g"]) if f["prod_biomasa_g"] is not None else None,
            "prom_tonc_ha": float(f["prom_tonc_ha"]) if f["prom_tonc_ha"] is not None else None,
            "sitio_id": f["unidad_muestreo__sitio_id"],
            "sitio_nombre": f["unidad_muestreo__sitio__nombre"],
            "departamento": f["unidad_muestreo__sitio__vereda__municipio__departamento__nombre"],
        }
        for f in campos
    ]

    return JsonResponse({"count": len(resultados), "resultados": resultados})


# Rangos de profundidad estándar de perfiles de suelo (cm), usados para
# bucketizar SubmuestraSuelo.profundidad_desde_cm. Django ORM no bucketiza
# rangos arbitrarios en una sola annotate, y el volumen de submuestras de
# suelo es pequeño, así que se agrupa en Python sin riesgo de rendimiento.
_RANGOS_PROFUNDIDAD_CM = [(0, 10), (10, 20), (20, 30), (30, 50), (50, 100), (100, None)]


def _rango_profundidad(desde_cm):
    for inicio, fin in _RANGOS_PROFUNDIDAD_CM:
        if fin is None or desde_cm < fin:
            if desde_cm >= inicio:
                return f"{inicio}-{fin} cm" if fin is not None else f"{inicio}+ cm"
    return "Sin clasificar"


@require_GET
def cos_por_profundidad(request):
    """% de carbono orgánico del suelo promedio por rango de profundidad
    (0-10, 10-20, 20-30, 30-50, 50-100, 100+ cm)."""
    qs = SubmuestraSuelo.objects.exclude(profundidad_desde_cm=None).exclude(carbono_pct=None)

    proyecto_id = request.GET.get("proyecto")
    if proyecto_id:
        qs = qs.filter(unidad_muestreo__unidad_experimental__proyecto_id=proyecto_id)

    sitio_id = request.GET.get("sitio")
    if sitio_id:
        qs = qs.filter(unidad_muestreo__sitio_id=sitio_id)

    grupos = {}
    for sub in qs.only("profundidad_desde_cm", "carbono_pct"):
        rango = _rango_profundidad(float(sub.profundidad_desde_cm))
        grupos.setdefault(rango, []).append(float(sub.carbono_pct))

    orden = [f"{i}-{f} cm" if f is not None else f"{i}+ cm" for i, f in _RANGOS_PROFUNDIDAD_CM]
    resultados = [
        {
            "rango_profundidad": rango,
            "carbono_pct_promedio": sum(valores) / len(valores),
            "total_muestras": len(valores),
        }
        for rango in orden
        if (valores := grupos.get(rango))
    ]

    return JsonResponse({"resultados": resultados})


@require_GET
def mom_tendencia(request):
    """Promedio de carbono en hojarasca (g/m²) por mes (default) o año:
    ?agrupar=mes|anio. Agregado en la base de datos."""
    agrupar = request.GET.get("agrupar", "mes")
    if agrupar not in ("mes", "anio"):
        return JsonResponse({"error": "agrupar debe ser mes o anio"}, status=400)

    qs = MuestraMOM.objects.exclude(fecha=None).exclude(carbono_hojarasca_g_m2=None)

    proyecto_id = request.GET.get("proyecto")
    if proyecto_id:
        qs = qs.filter(unidad_muestreo__unidad_experimental__proyecto_id=proyecto_id)

    trunc = TruncMonth("fecha") if agrupar == "mes" else TruncYear("fecha")
    filas = (
        qs.annotate(periodo=trunc)
        .values("periodo")
        .annotate(carbono_hojarasca_g_m2_promedio=Avg("carbono_hojarasca_g_m2"), total_muestras=Count("id"))
        .order_by("periodo")
    )

    resultados = [
        {
            "periodo": fila["periodo"].isoformat(),
            "carbono_hojarasca_g_m2_promedio": fila["carbono_hojarasca_g_m2_promedio"],
            "total_muestras": fila["total_muestras"],
        }
        for fila in filas
    ]

    return JsonResponse({"agrupar": agrupar, "resultados": resultados})
