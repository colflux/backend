import json

from django.db.models import Avg, Count, Max, Min, OuterRef, Subquery
from django.db.models.functions import TruncMonth, TruncYear
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from app.models import (
    Cobertura, Departamento, Disturbio, Municipio, MuestraBiomasa, Region, Sitio, SubmuestraGEI, SubmuestraSuelo,
    UnidadMuestreo, Vereda,
)

# Config por categoría de dato: qué modelo agregar y por qué cadena de FKs
# llegar a sitio/proyecto, para que resumen_geografico y sitios_geojson
# puedan tratar flujos/biomasa/cos de forma genérica. "campo_unidad" es un
# campo de la base (solo existe para flujos, vía UnidadMedida); las otras
# categorías no tienen unidad configurable en el modelo, así que se fija en
# "unidad_fija". "filtro_gas" solo aplica a flujos -biomasa y COS no
# distinguen gas-.
_CATEGORIA_CONFIG = {
    "flujos": {
        "modelo": SubmuestraGEI,
        "prefijo_sitio": "muestra__unidad_muestreo__sitio",
        "prefijo_proyecto": "muestra__unidad_muestreo__unidad_experimental__proyecto",
        "campo_valor": "valor",
        "campo_unidad": "muestra__unidad_medida__codigo",
        "unidad_fija": None,
        "filtro_gas": "muestra__gas",
        # False: se preserva el comportamiento histórico de resumen_geografico,
        # que no excluye por adelantado las filas con valor nulo (afecta
        # total_muestras/excluidos) — Avg/Min/Max ya las ignoran igual.
        "excluir_valor_nulo": False,
    },
    "biomasa": {
        "modelo": MuestraBiomasa,
        "prefijo_sitio": "unidad_muestreo__sitio",
        "prefijo_proyecto": "unidad_muestreo__unidad_experimental__proyecto",
        "campo_valor": "prom_tonc_ha",
        "campo_unidad": None,
        "unidad_fija": "tonc_ha",
        "filtro_gas": None,
        "excluir_valor_nulo": True,
    },
    "cos": {
        "modelo": SubmuestraSuelo,
        "prefijo_sitio": "unidad_muestreo__sitio",
        "prefijo_proyecto": "unidad_muestreo__unidad_experimental__proyecto",
        "campo_valor": "carbono_pct",
        "campo_unidad": None,
        "unidad_fija": "pct",
        "filtro_gas": None,
        # SubmuestraSuelo mezcla filas de COS (carbono_pct) y de densidad
        # aparente (densidad_aparente_g_cm3) en la misma tabla: sin este
        # exclude, "cos" contaría también filas que no son de COS.
        "excluir_valor_nulo": True,
    },
}


def _resumen_por_sitio_generico(queryset, campo_sitio, campo_valor):
    """Conteo, rango de fechas y última medición por sitio, para cualquier
    queryset de mediciones con "fecha" y un campo de valor propio (usado
    para biomasa y COS en sitios_geojson, análogo al bloque de flujos que
    ya traía su propia versión hecha a mano)."""
    resumen = {
        fila[campo_sitio]: {
            "total_muestras": fila["total"],
            "primera_fecha": fila["desde"],
            "ultima_fecha": fila["hasta"],
            "ultimo_valor": None,
        }
        for fila in queryset.values(campo_sitio).annotate(total=Count("id"), desde=Min("fecha"), hasta=Max("fecha"))
    }
    for fila in (
        queryset.order_by(campo_sitio, "-fecha", "-id").distinct(campo_sitio).values(campo_sitio, campo_valor)
    ):
        r = resumen.get(fila[campo_sitio])
        if r is not None:
            r["ultimo_valor"] = float(fila[campo_valor]) if fila[campo_valor] is not None else None
    return resumen


def _formatear_resumen_simple(resumen, unidad):
    """Da forma de {total_muestras, rango_fechas, ultima_medicion} a una
    entrada de _resumen_por_sitio_generico (o None si el sitio no tiene
    mediciones de esa categoría)."""
    if not resumen:
        return None
    return {
        "total_muestras": resumen["total_muestras"],
        "rango_fechas": {
            "desde": resumen["primera_fecha"].isoformat() if resumen["primera_fecha"] else None,
            "hasta": resumen["ultima_fecha"].isoformat() if resumen["ultima_fecha"] else None,
        },
        "ultima_medicion": (
            {"fecha": resumen["ultima_fecha"].isoformat(), "valor": resumen["ultimo_valor"], "unidad": unidad}
            if resumen["ultima_fecha"] else None
        ),
    }


@require_GET
def sitios_geojson(request):
    """GeoJSON (FeatureCollection) de los Sitio georreferenciados, con sus
    unidades de muestreo, proyecto(s) y un resumen de sus mediciones como
    metadata: un resumen agregado de flujos (todos los gases, campos *_co2
    por compatibilidad hacia atrás), uno desagregado por gas en
    "resumen_por_gas" (CO2/CH4/N2O), y uno por cada otra categoría de dato en
    "resumen_biomasa" y "resumen_cos" (ninguna de las dos se desagrega más:
    a diferencia de flujos, no tienen un sub-filtro como el gas). Pensado
    para consumirse directo desde un cliente Leaflet (L.geoJSON(url)).

    Los campos "ultima_medicion_co2", la ultima medicion de cada gas en
    "resumen_por_gas" y las de "resumen_biomasa"/"resumen_cos" toman la
    lectura de mayor fecha; ante empate (varias lecturas el mismo dia) se
    resuelve por el id mayor, para que el resultado sea estable entre
    ejecuciones."""
    sitios = (
        Sitio.objects
        .select_related("vereda", "vereda__municipio", "vereda__municipio__departamento")
        .prefetch_related(
            "unidades_muestreo__tipo",
            "unidades_muestreo__unidad_experimental__proyecto",
        )
    )

    # Última lectura, conteo y rango de fechas por sitio y por gas, en una
    # sola pasada (evita N+1: una query para todas las submuestras en vez de
    # una por sitio). Se acumula tanto el resumen agregado (todos los gases,
    # para no romper clientes que ya consumen total_muestras_co2 /
    # ultima_medicion_co2) como el resumen desagregado por gas.
    SITIO = "muestra__unidad_muestreo__sitio_id"
    base = SubmuestraGEI.objects.exclude(fecha=None).exclude(**{SITIO: None})

    # Conteo y rango de fechas por sitio, agregados en la base.
    resumen_por_sitio = {
        fila[SITIO]: {
            "total_muestras": fila["total"],
            "primera_fecha": fila["desde"],
            "ultima_fecha": fila["hasta"],
            "ultimo_valor": None,
            "ultima_unidad": None,
        }
        for fila in base.values(SITIO).annotate(total=Count("id"), desde=Min("fecha"), hasta=Max("fecha"))
    }

    # Ultima medicion por sitio con DISTINCT ON; ante empate de fecha gana el
    # id mayor, para que el resultado sea estable entre ejecuciones.
    for fila in base.order_by(SITIO, "-fecha", "-id").distinct(SITIO).values(SITIO, "valor", "muestra__unidad_medida__codigo"):
        r = resumen_por_sitio.get(fila[SITIO])
        if r is not None:
            r["ultimo_valor"] = float(fila["valor"]) if fila["valor"] is not None else None
            r["ultima_unidad"] = fila["muestra__unidad_medida__codigo"]

    con_gas = base.exclude(muestra__gas="").exclude(muestra__gas=None)

    resumen_por_sitio_y_gas = {}
    for fila in con_gas.values(SITIO, "muestra__gas").annotate(total=Count("id"), desde=Min("fecha"), hasta=Max("fecha")):
        resumen_por_sitio_y_gas.setdefault(fila[SITIO], {})[fila["muestra__gas"]] = {
            "total_muestras": fila["total"],
            "primera_fecha": fila["desde"],
            "ultima_fecha": fila["hasta"],
            "ultimo_valor": None,
            "ultima_unidad": None,
        }

    for fila in con_gas.order_by(SITIO, "muestra__gas", "-fecha", "-id").distinct(SITIO, "muestra__gas").values(SITIO, "muestra__gas", "valor", "muestra__unidad_medida__codigo"):
        r = resumen_por_sitio_y_gas.get(fila[SITIO], {}).get(fila["muestra__gas"])
        if r is not None:
            r["ultimo_valor"] = float(fila["valor"]) if fila["valor"] is not None else None
            r["ultima_unidad"] = fila["muestra__unidad_medida__codigo"]

    resumen_biomasa_por_sitio = _resumen_por_sitio_generico(
        MuestraBiomasa.objects.exclude(fecha=None).exclude(unidad_muestreo__sitio_id=None),
        "unidad_muestreo__sitio_id",
        "prom_tonc_ha",
    )
    resumen_cos_por_sitio = _resumen_por_sitio_generico(
        SubmuestraSuelo.objects.exclude(fecha=None).exclude(carbono_pct=None).exclude(unidad_muestreo__sitio_id=None),
        "unidad_muestreo__sitio_id",
        "carbono_pct",
    )

    features = []
    for sitio in sitios:
        proyectos = {}
        unidades_muestreo = []
        for um in sitio.unidades_muestreo.all():
            unidades_muestreo.append({
                "id": um.pk,
                "nombre": um.nombre,
                "tipo": um.tipo.nombre if um.tipo_id else None,
            })
            ue = um.unidad_experimental
            if ue is not None and ue.proyecto_id and ue.proyecto_id not in proyectos:
                proyectos[ue.proyecto_id] = {"id": ue.proyecto_id, "nombre": ue.proyecto.nombre}

        resumen = resumen_por_sitio.get(sitio.pk, {})
        resumen_gases = resumen_por_sitio_y_gas.get(sitio.pk, {})

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(sitio.longitud), float(sitio.latitud)],
            },
            "properties": {
                "id": sitio.pk,
                "nombre": sitio.nombre,
                "vereda": sitio.vereda.nombre if sitio.vereda_id else None,
                "municipio": (
                    sitio.vereda.municipio.nombre
                    if sitio.vereda_id and sitio.vereda.municipio_id else None
                ),
                "departamento": (
                    sitio.vereda.municipio.departamento.nombre
                    if sitio.vereda_id and sitio.vereda.municipio_id and sitio.vereda.municipio.departamento_id
                    else None
                ),
                "altitud": float(sitio.altitud) if sitio.altitud is not None else None,
                "uso_actual": sitio.get_uso_actual_display() if sitio.uso_actual else None,
                "proyectos": list(proyectos.values()),
                "unidades_muestreo": unidades_muestreo,
                "total_muestras_co2": resumen.get("total_muestras", 0),
                "rango_fechas": {
                    "desde": resumen["primera_fecha"].isoformat() if resumen.get("primera_fecha") else None,
                    "hasta": resumen["ultima_fecha"].isoformat() if resumen.get("ultima_fecha") else None,
                },
                "ultima_medicion_co2": (
                    {"fecha": resumen["ultima_fecha"].isoformat(), "valor": resumen["ultimo_valor"], "unidad": resumen["ultima_unidad"]}
                    if resumen.get("ultima_fecha") else None
                ),
                # Resumen desagregado por gas (CO2/CH4/N2O), para las tarjetas
                # del panel RESUMEN y el filtrado por gas en el mapa. Solo
                # incluye los gases con muestras registradas en el sitio.
                "resumen_por_gas": {
                    gas: {
                        "total_muestras": r["total_muestras"],
                        "rango_fechas": {
                            "desde": r["primera_fecha"].isoformat() if r["primera_fecha"] else None,
                            "hasta": r["ultima_fecha"].isoformat() if r["ultima_fecha"] else None,
                        },
                        "ultima_medicion": (
                            {"fecha": r["ultima_fecha"].isoformat(), "valor": r["ultimo_valor"], "unidad": r["ultima_unidad"]}
                            if r["ultima_fecha"] else None
                        ),
                    }
                    for gas, r in resumen_gases.items()
                },
                # Resumen de las otras categorías de dato (sin sub-filtro
                # propio, a diferencia de flujos/gas). None si el sitio no
                # tiene mediciones de esa categoría.
                "resumen_biomasa": _formatear_resumen_simple(resumen_biomasa_por_sitio.get(sitio.pk), "tonc_ha"),
                "resumen_cos": _formatear_resumen_simple(resumen_cos_por_sitio.get(sitio.pk), "pct"),
            },
        })

    return JsonResponse({"type": "FeatureCollection", "features": features})


@require_GET
def series_co2(request):
    """Lecturas crudas de flujo de gas (una fila por SubmuestraGEI con fecha),
    con filtros opcionales por año o rango de fechas, gas (CO2/CH4/N2O),
    sitio, proyecto, vereda, municipio, departamento y región. Sin ?gas=
    devuelve los tres gases mezclados -cada resultado trae su propio campo
    "gas" para que el cliente filtre/agrupe-. No agrega ni convierte unidades
    -eso queda a criterio de quien consuma la serie-, solo devuelve el dato
    tal como está en la base para que el geoportal (u otro cliente) arme sus
    propios gráficos de tendencia/agregados."""
    qs = (
        SubmuestraGEI.objects
        .exclude(fecha=None)
        .select_related(
            "muestra__unidad_medida",
            "muestra__unidad_muestreo__sitio__vereda__municipio__departamento__region",
            "muestra__unidad_muestreo__unidad_experimental__proyecto",
        )
        .order_by("fecha")
    )

    anio = request.GET.get("anio")
    if anio:
        qs = qs.filter(fecha__year=anio)

    desde = request.GET.get("desde")
    if desde:
        qs = qs.filter(fecha__gte=desde)

    hasta = request.GET.get("hasta")
    if hasta:
        qs = qs.filter(fecha__lte=hasta)

    gas = request.GET.get("gas")
    if gas:
        qs = qs.filter(muestra__gas=gas.upper())

    sitio_id = request.GET.get("sitio")
    if sitio_id:
        qs = qs.filter(muestra__unidad_muestreo__sitio_id=sitio_id)

    proyecto_id = request.GET.get("proyecto")
    if proyecto_id:
        qs = qs.filter(muestra__unidad_muestreo__unidad_experimental__proyecto_id=proyecto_id)

    vereda_id = request.GET.get("vereda")
    if vereda_id:
        qs = qs.filter(muestra__unidad_muestreo__sitio__vereda_id=vereda_id)

    municipio_id = request.GET.get("municipio")
    if municipio_id:
        qs = qs.filter(muestra__unidad_muestreo__sitio__vereda__municipio_id=municipio_id)

    departamento_id = request.GET.get("departamento")
    if departamento_id:
        qs = qs.filter(muestra__unidad_muestreo__sitio__vereda__municipio__departamento_id=departamento_id)

    region_id = request.GET.get("region")
    if region_id:
        qs = qs.filter(muestra__unidad_muestreo__sitio__vereda__municipio__departamento__region_id=region_id)

    campos = qs.values(
        "fecha",
        "valor",
        "muestra__unidad_medida__codigo",
        "muestra__gas",
        "muestra__unidad_muestreo__sitio_id",
        "muestra__unidad_muestreo__sitio__nombre",
        "muestra__unidad_muestreo__sitio__vereda_id",
        "muestra__unidad_muestreo__sitio__vereda__nombre",
        "muestra__unidad_muestreo__sitio__vereda__municipio__departamento_id",
        "muestra__unidad_muestreo__sitio__vereda__municipio__departamento__nombre",
        "muestra__unidad_muestreo__unidad_experimental__proyecto_id",
        "muestra__unidad_muestreo__unidad_experimental__proyecto__nombre",
    )

    resultados = [
        {
            "fecha": f["fecha"].isoformat(),
            "valor": float(f["valor"]) if f["valor"] is not None else None,
            "unidad": f["muestra__unidad_medida__codigo"],
            "gas": f["muestra__gas"] or None,
            "sitio_id": f["muestra__unidad_muestreo__sitio_id"],
            "sitio_nombre": f["muestra__unidad_muestreo__sitio__nombre"],
            "vereda_id": f["muestra__unidad_muestreo__sitio__vereda_id"],
            "vereda": f["muestra__unidad_muestreo__sitio__vereda__nombre"],
            "departamento_id": f["muestra__unidad_muestreo__sitio__vereda__municipio__departamento_id"],
            "departamento": f["muestra__unidad_muestreo__sitio__vereda__municipio__departamento__nombre"],
            "proyecto_id": f["muestra__unidad_muestreo__unidad_experimental__proyecto_id"],
            "proyecto_nombre": f["muestra__unidad_muestreo__unidad_experimental__proyecto__nombre"],
        }
        for f in campos
    ]

    return JsonResponse({"count": len(resultados), "resultados": resultados})


def _aplicar_filtros_comunes(qs, request, categoria="flujos"):
    """Filtros de fecha/gas/ubicación que comparten resumen_geografico,
    resumen_categorico y (parcialmente) series_co2. "categoria" decide de
    qué modelo -y por lo tanto qué cadena de FKs hasta sitio/proyecto- se
    trata (ver _CATEGORIA_CONFIG); el filtro de gas solo aplica cuando la
    categoría lo soporta (hoy, solo flujos)."""
    config = _CATEGORIA_CONFIG[categoria]
    prefijo_sitio = config["prefijo_sitio"]
    prefijo_proyecto = config["prefijo_proyecto"]

    if config["filtro_gas"]:
        gas = request.GET.get("gas")
        if gas:
            qs = qs.filter(**{config["filtro_gas"]: gas.upper()})

    desde = request.GET.get("desde")
    if desde:
        qs = qs.filter(fecha__gte=desde)

    hasta = request.GET.get("hasta")
    if hasta:
        qs = qs.filter(fecha__lte=hasta)

    proyecto_id = request.GET.get("proyecto")
    if proyecto_id:
        qs = qs.filter(**{f"{prefijo_proyecto}_id": proyecto_id})

    vereda_id = request.GET.get("vereda")
    if vereda_id:
        qs = qs.filter(**{f"{prefijo_sitio}__vereda_id": vereda_id})

    municipio_id = request.GET.get("municipio")
    if municipio_id:
        qs = qs.filter(**{f"{prefijo_sitio}__vereda__municipio_id": municipio_id})

    departamento_id = request.GET.get("departamento")
    if departamento_id:
        qs = qs.filter(**{f"{prefijo_sitio}__vereda__municipio__departamento_id": departamento_id})

    region_id = request.GET.get("region")
    if region_id:
        qs = qs.filter(**{f"{prefijo_sitio}__vereda__municipio__departamento__region_id": region_id})

    sitio_id = request.GET.get("sitio")
    if sitio_id:
        qs = qs.filter(**{f"{prefijo_sitio}_id": sitio_id})

    return qs


@require_GET
def resumen_geografico(request):
    """Resumen agregado (conteo, promedio, mínimo, máximo, última medición)
    de una categoría de dato (?categoria=flujos -default, SubmuestraGEI-,
    biomasa -MuestraBiomasa- o cos -SubmuestraSuelo-), agrupado por un nivel
    geográfico: ?nivel=departamento (default), municipio, vereda, region o
    sitio. Acepta los mismos filtros que /api/geo/series/ (gas -solo aplica
    a flujos-, desde, hasta, proyecto, departamento, municipio, vereda,
    región) para acotar antes de agregar. Pensado para mapas tipo
    choropleth y tarjetas de resumen del geoportal.

    "region" no tiene geometría propia en el modelo (solo departamento,
    municipio, vereda y sitio la tienen): sus features salen con
    geometry=null y una lista "departamentos" con los departamentos que la
    componen, para que el cliente los dibuje/resalte.

    "ultima_medicion" es la lectura de mayor fecha del grupo; ante empate de
    fecha (lo habitual: varias lecturas el mismo dia -y, para flujos sin
    filtro de gas, de varios gases-) se toma la de mayor id, para que el
    resultado sea estable entre ejecuciones."""
    nivel = request.GET.get("nivel", "departamento")
    if nivel not in ("departamento", "municipio", "vereda", "region", "sitio"):
        return JsonResponse(
            {"error": "nivel debe ser uno de: departamento, municipio, vereda, region, sitio"}, status=400,
        )

    categoria = request.GET.get("categoria", "flujos")
    if categoria not in _CATEGORIA_CONFIG:
        return JsonResponse(
            {"error": f"categoria debe ser una de: {', '.join(_CATEGORIA_CONFIG)}"}, status=400,
        )
    config = _CATEGORIA_CONFIG[categoria]
    prefijo_sitio = config["prefijo_sitio"]
    campo_valor = config["campo_valor"]

    qs = config["modelo"].objects.exclude(fecha=None)
    if config["excluir_valor_nulo"]:
        qs = qs.exclude(**{campo_valor: None})
    select_related = [f"{prefijo_sitio}__vereda__municipio__departamento__region", config["prefijo_proyecto"]]
    if config["campo_unidad"]:
        select_related.append(config["campo_unidad"].rsplit("__", 1)[0])
    qs = qs.select_related(*select_related)

    qs = _aplicar_filtros_comunes(qs, request, categoria)

    CAMPO_POR_NIVEL = {
        "sitio": prefijo_sitio,
        "vereda": f"{prefijo_sitio}__vereda",
        "municipio": f"{prefijo_sitio}__vereda__municipio",
        "departamento": f"{prefijo_sitio}__vereda__municipio__departamento",
        "region": f"{prefijo_sitio}__vereda__municipio__departamento__region",
    }
    campo = CAMPO_POR_NIVEL[nivel]
    campo_id = campo + "_id"
    campo_dep = f"{prefijo_sitio}__vereda__municipio__departamento"

    # Agregar en la base en vez de materializar cada medicion en Python: una
    # consulta con GROUP BY devuelve una fila por grupo, no una por medicion.
    base = qs.exclude(**{campo_id: None})
    excluidos = qs.count() - base.count()

    agregados = list(
        base.values(campo_id).annotate(
            total_muestras=Count("id"),
            promedio=Avg(campo_valor),
            minimo=Min(campo_valor),
            maximo=Max(campo_valor),
            primera_fecha=Min("fecha"),
            ultima_fecha=Max("fecha"),
        )
    )
    claves = [fila[campo_id] for fila in agregados]

    # Ultima medicion por grupo con DISTINCT ON de Postgres: una sola consulta
    # en vez de recorrer todas las filas comparando fechas.
    campos_ultima = [campo_id, "fecha", campo_valor]
    if config["campo_unidad"]:
        campos_ultima.append(config["campo_unidad"])
    ultimas = {
        fila[campo_id]: fila
        for fila in base.filter(**{campo_id + "__in": claves})
        .order_by(campo_id, "-fecha", "-id")
        .distinct(campo_id)
        .values(*campos_ultima)
    }

    if nivel == "sitio":
        objetos = {o.pk: o for o in Sitio.objects.filter(pk__in=claves).select_related("vereda__municipio__departamento")}
    elif nivel == "vereda":
        objetos = {o.pk: o for o in Vereda.objects.filter(pk__in=claves).select_related("municipio__departamento")}
    elif nivel == "municipio":
        objetos = {o.pk: o for o in Municipio.objects.filter(pk__in=claves).select_related("departamento")}
    elif nivel == "departamento":
        objetos = {o.pk: o for o in Departamento.objects.filter(pk__in=claves).select_related("region")}
    else:
        objetos = {o.pk: o for o in Region.objects.filter(pk__in=claves)}

    departamentos_por_region = {}
    if nivel == "region":
        for fila in base.filter(**{campo_id + "__in": claves}).values(campo_id, campo_dep + "_id", campo_dep + "__nombre").distinct():
            departamentos_por_region.setdefault(fila[campo_id], {})[fila[campo_dep + "_id"]] = fila[campo_dep + "__nombre"]

    features = []
    for fila in agregados:
        clave = fila[campo_id]
        obj = objetos.get(clave)
        if obj is None:
            continue

        if nivel == "sitio":
            vereda = obj.vereda if obj.vereda_id else None
            municipio = vereda.municipio if vereda and vereda.municipio_id else None
            departamento = municipio.departamento if municipio and municipio.departamento_id else None
            nombre = obj.nombre
            geom = {"type": "Point", "coordinates": [float(obj.longitud), float(obj.latitud)]}
            extra = {
                "vereda_id": vereda.pk if vereda else None,
                "vereda": vereda.nombre if vereda else None,
                "municipio_id": municipio.pk if municipio else None,
                "municipio": municipio.nombre if municipio else None,
                "departamento_id": departamento.pk if departamento else None,
                "departamento": departamento.nombre if departamento else None,
            }
        elif nivel == "vereda":
            municipio = obj.municipio if obj.municipio_id else None
            departamento = municipio.departamento if municipio and municipio.departamento_id else None
            nombre, geom = obj.nombre, obj.geom
            extra = {
                "municipio_id": municipio.pk if municipio else None,
                "municipio": municipio.nombre if municipio else None,
                "departamento_id": departamento.pk if departamento else None,
                "departamento": departamento.nombre if departamento else None,
            }
        elif nivel == "municipio":
            departamento = obj.departamento if obj.departamento_id else None
            nombre, geom = obj.nombre, obj.geom
            extra = {
                "departamento_id": departamento.pk if departamento else None,
                "departamento": departamento.nombre if departamento else None,
            }
        elif nivel == "departamento":
            nombre, geom = obj.nombre, obj.geom
            extra = {
                "region_id": obj.region_id,
                "region": obj.region.get_nombre_display() if obj.region_id else None,
            }
        else:
            nombre, geom = obj.get_nombre_display(), None
            extra = {}

        ultima = ultimas.get(clave)
        properties = {
            "id": clave,
            "nombre": nombre,
            "total_muestras": fila["total_muestras"],
            "promedio": float(fila["promedio"]) if fila["promedio"] is not None else None,
            "minimo": float(fila["minimo"]) if fila["minimo"] is not None else None,
            "maximo": float(fila["maximo"]) if fila["maximo"] is not None else None,
            "rango_fechas": {
                "desde": fila["primera_fecha"].isoformat() if fila["primera_fecha"] else None,
                "hasta": fila["ultima_fecha"].isoformat() if fila["ultima_fecha"] else None,
            },
            "ultima_medicion": (
                {
                    "fecha": ultima["fecha"].isoformat(),
                    "valor": float(ultima[campo_valor]) if ultima[campo_valor] is not None else None,
                    "unidad": ultima[config["campo_unidad"]] if config["campo_unidad"] else config["unidad_fija"],
                }
                if ultima and ultima["fecha"] else None
            ),
            **extra,
        }
        if nivel == "region":
            properties["departamentos"] = [
                {"id": pk, "nombre": nom}
                for pk, nom in sorted(departamentos_por_region.get(clave, {}).items(), key=lambda x: x[1])
            ]

        geometry = json.loads(geom.geojson) if hasattr(geom, "geojson") else geom
        features.append({"type": "Feature", "geometry": geometry, "properties": properties})

    return JsonResponse({
        "type": "FeatureCollection",
        "features": features,
        "excluidos": excluidos,
        "categoria": categoria,
        # Unidad fija de la categoría (biomasa/cos); null en flujos, donde la
        # unidad puede variar por grupo según el gas -va en cada
        # "ultima_medicion" en su lugar-.
        "unidad": config["unidad_fija"],
    })


_DIMENSIONES_CATEGORICAS = ("proyecto", "ecosistema", "estado_conservacion", "analizador", "condicion_luz")

_CONDICION_LUZ_LABELS = dict(SubmuestraGEI.CONDICION_LUZ_CHOICES)
_ESTADO_CONSERVACION_LABELS = dict(Disturbio.ESTADO_CONSERVACION_CHOICES)

# Config por dimensión: campo por el que se agrupa. "ecosistema" no es un
# campo directo -se anota vía Subquery antes de agregar-.
_CAMPO_ID_POR_DIMENSION = {
    "proyecto": "muestra__unidad_muestreo__unidad_experimental__proyecto_id",
    "analizador": "muestra__analizador_id",
    "condicion_luz": "condicion_luz",
    "estado_conservacion": "muestra__unidad_muestreo__sitio__disturbio__estado_conservacion",
    "ecosistema": "ecosistema",
}


@require_GET
def resumen_categorico(request):
    """Resumen agregado (conteo, promedio, mínimo, máximo, última medición)
    de SubmuestraGEI, agrupado por una dimensión no geográfica:
    ?dimension=proyecto|ecosistema|estado_conservacion|analizador|condicion_luz.
    Acepta los mismos filtros que /api/geo/resumen/ (gas, desde, hasta,
    proyecto, departamento, municipio, vereda, región, sitio). Igual que
    resumen_geografico, agrega en la base de datos (GROUP BY), no en Python.

    "ecosistema" usa la primera Cobertura reportada del sitio (ordenada por
    tipo de clasificación y nombre, vía Subquery) como aproximación: un
    sitio puede tener varias filas de Cobertura -una por sistema de
    clasificación CLC/IPCC/IGBP/etc., o duplicados en conflicto entre
    fuentes- y no hay un campo de vigencia para elegir "la" cobertura
    vigente. A validar con el equipo si hace falta un criterio más preciso."""
    dimension = request.GET.get("dimension")
    if dimension not in _DIMENSIONES_CATEGORICAS:
        return JsonResponse(
            {"error": f"dimension debe ser uno de: {', '.join(_DIMENSIONES_CATEGORICAS)}"}, status=400,
        )

    qs = SubmuestraGEI.objects.exclude(fecha=None).select_related("muestra__unidad_medida")
    qs = _aplicar_filtros_comunes(qs, request)

    campo_id = _CAMPO_ID_POR_DIMENSION[dimension]

    if dimension == "ecosistema":
        cobertura_sub = (
            Cobertura.objects
            .filter(sitio_id=OuterRef("muestra__unidad_muestreo__sitio_id"))
            .order_by("tipo_id", "nombre")
            .values("nombre")[:1]
        )
        qs = qs.annotate(ecosistema=Subquery(cobertura_sub))

    base = qs.exclude(**{campo_id: None})
    if dimension in ("condicion_luz", "estado_conservacion"):
        base = base.exclude(**{campo_id: ""})

    agregados = list(
        base.values(campo_id).annotate(
            total_muestras=Count("id"),
            promedio=Avg("valor"),
            minimo=Min("valor"),
            maximo=Max("valor"),
            primera_fecha=Min("fecha"),
            ultima_fecha=Max("fecha"),
        )
    )
    claves = [fila[campo_id] for fila in agregados]

    ultimas = {
        fila[campo_id]: fila
        for fila in base.filter(**{campo_id + "__in": claves})
        .order_by(campo_id, "-fecha", "-id")
        .distinct(campo_id)
        .values(campo_id, "fecha", "valor", "muestra__unidad_medida__codigo")
    }

    # Nombres legibles por clave, según la dimensión.
    if dimension == "proyecto":
        nombres = dict(
            base.filter(**{campo_id + "__in": claves})
            .values_list(campo_id, "muestra__unidad_muestreo__unidad_experimental__proyecto__nombre")
            .distinct()
        )
    elif dimension == "analizador":
        nombres = dict(
            base.filter(**{campo_id + "__in": claves})
            .values_list(campo_id, "muestra__analizador__modelo")
            .distinct()
        )
    elif dimension == "condicion_luz":
        nombres = {clave: _CONDICION_LUZ_LABELS.get(clave, clave) for clave in claves}
    elif dimension == "estado_conservacion":
        nombres = {clave: _ESTADO_CONSERVACION_LABELS.get(clave, clave) for clave in claves}
    else:  # ecosistema
        nombres = {clave: clave for clave in claves}

    resultados = []
    for fila in agregados:
        clave = fila[campo_id]
        ultima = ultimas.get(clave)
        resultados.append({
            "id": clave,
            "nombre": nombres.get(clave) or str(clave),
            "total_muestras": fila["total_muestras"],
            "promedio": float(fila["promedio"]) if fila["promedio"] is not None else None,
            "minimo": float(fila["minimo"]) if fila["minimo"] is not None else None,
            "maximo": float(fila["maximo"]) if fila["maximo"] is not None else None,
            "rango_fechas": {
                "desde": fila["primera_fecha"].isoformat() if fila["primera_fecha"] else None,
                "hasta": fila["ultima_fecha"].isoformat() if fila["ultima_fecha"] else None,
            },
            "ultima_medicion": (
                {
                    "fecha": ultima["fecha"].isoformat(),
                    "valor": float(ultima["valor"]) if ultima["valor"] is not None else None,
                    "unidad": ultima["muestra__unidad_medida__codigo"],
                }
                if ultima and ultima["fecha"] else None
            ),
        })

    resultados.sort(key=lambda r: r["total_muestras"], reverse=True)

    return JsonResponse({"dimension": dimension, "resultados": resultados})


@require_GET
def tendencia_instalacion(request):
    """Conteo de UnidadMuestreo por fecha de instalación, agrupado por mes
    (default) o año: ?agrupar=mes|anio. Filtro opcional ?proyecto=. Agregado
    en la base de datos (TruncMonth/TruncYear + Count), no en Python: el
    volumen de unidades de muestreo es independiente del de submuestras."""
    agrupar = request.GET.get("agrupar", "mes")
    if agrupar not in ("mes", "anio"):
        return JsonResponse({"error": "agrupar debe ser mes o anio"}, status=400)

    qs = UnidadMuestreo.objects.exclude(fecha_instalacion=None)

    proyecto_id = request.GET.get("proyecto")
    if proyecto_id:
        qs = qs.filter(unidad_experimental__proyecto_id=proyecto_id)

    trunc = TruncMonth("fecha_instalacion") if agrupar == "mes" else TruncYear("fecha_instalacion")
    filas = (
        qs.annotate(periodo=trunc)
        .values("periodo")
        .annotate(total=Count("id"))
        .order_by("periodo")
    )

    resultados = [
        {"periodo": fila["periodo"].isoformat(), "total": fila["total"]}
        for fila in filas
    ]

    return JsonResponse({"agrupar": agrupar, "resultados": resultados})
