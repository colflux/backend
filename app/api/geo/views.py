import json

from django.db.models import Avg, Count, Max, Min
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from app.models import Departamento, Municipio, Region, Sitio, SubmuestraGEI, Vereda


@require_GET
def sitios_geojson(request):
    """GeoJSON (FeatureCollection) de los Sitio georreferenciados, con sus
    unidades de muestreo, proyecto(s) y un resumen de sus mediciones como
    metadata: un resumen agregado (todos los gases, campos *_co2 por
    compatibilidad hacia atrás) y uno desagregado por gas en
    "resumen_por_gas" (CO2/CH4/N2O). Pensado para consumirse directo desde
    un cliente Leaflet (L.geoJSON(url))."""
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
    def _actualizar(resumen, sub):
        resumen["total_muestras"] += 1
        if resumen["primera_fecha"] is None or sub.fecha < resumen["primera_fecha"]:
            resumen["primera_fecha"] = sub.fecha
        if resumen["ultima_fecha"] is None or sub.fecha >= resumen["ultima_fecha"]:
            resumen["ultima_fecha"] = sub.fecha
            resumen["ultimo_valor"] = float(sub.valor) if sub.valor is not None else None
            resumen["ultima_unidad"] = sub.muestra.unidad_medida.codigo if sub.muestra.unidad_medida_id else None

    resumen_por_sitio = {}
    resumen_por_sitio_y_gas = {}
    submuestras = (
        SubmuestraGEI.objects
        .exclude(fecha=None)
        .select_related("muestra__unidad_muestreo", "muestra__unidad_medida")
        .order_by("fecha")
    )
    for sub in submuestras:
        sitio_id = sub.muestra.unidad_muestreo_id and sub.muestra.unidad_muestreo.sitio_id
        if sitio_id is None:
            continue
        gas = sub.muestra.gas or None

        _actualizar(resumen_por_sitio.setdefault(sitio_id, {
            "total_muestras": 0, "primera_fecha": None, "ultima_fecha": None,
            "ultimo_valor": None, "ultima_unidad": None,
        }), sub)
        if gas is not None:
            _actualizar(resumen_por_sitio_y_gas.setdefault(sitio_id, {}).setdefault(gas, {
                "total_muestras": 0, "primera_fecha": None, "ultima_fecha": None,
                "ultimo_valor": None, "ultima_unidad": None,
            }), sub)

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

    resultados = []
    for sub in qs:
        um = sub.muestra.unidad_muestreo
        sitio = um.sitio if um else None
        ue = um.unidad_experimental if um else None
        vereda = sitio.vereda if sitio and sitio.vereda_id else None
        municipio = vereda.municipio if vereda and vereda.municipio_id else None
        resultados.append({
            "fecha": sub.fecha.isoformat(),
            "valor": float(sub.valor) if sub.valor is not None else None,
            "unidad": sub.muestra.unidad_medida.codigo if sub.muestra.unidad_medida_id else None,
            "gas": sub.muestra.gas or None,
            "sitio_id": sitio.pk if sitio else None,
            "sitio_nombre": sitio.nombre if sitio else None,
            "vereda_id": vereda.pk if vereda else None,
            "vereda": vereda.nombre if vereda else None,
            "departamento_id": municipio.departamento_id if municipio and municipio.departamento_id else None,
            "departamento": (
                municipio.departamento.nombre
                if municipio and municipio.departamento_id else None
            ),
            "proyecto_id": ue.proyecto_id if ue else None,
            "proyecto_nombre": ue.proyecto.nombre if ue and ue.proyecto_id else None,
        })

    return JsonResponse({"count": len(resultados), "resultados": resultados})


@require_GET
def resumen_geografico(request):
    """Resumen agregado (conteo, promedio, mínimo, máximo, última medición)
    de SubmuestraGEI, agrupado por un nivel geográfico: ?nivel=departamento
    (default), municipio, vereda, region o sitio. Acepta los mismos filtros
    que /api/geo/series/ (gas, desde, hasta, proyecto, departamento,
    municipio, vereda, región) para acotar antes de agregar. Pensado para
    mapas tipo choropleth y tarjetas de resumen del geoportal.

    "region" no tiene geometría propia en el modelo (solo departamento,
    municipio, vereda y sitio la tienen): sus features salen con
    geometry=null y una lista "departamentos" con los departamentos que la
    componen, para que el cliente los dibuje/resalte.

    "ultima_medicion" es la lectura de mayor fecha del grupo; ante empate de
    fecha (lo habitual: varias lecturas y varios gases el mismo dia) se toma
    la de mayor id, para que el resultado sea estable entre ejecuciones. Si
    no se filtra por gas, esa lectura puede ser de cualquiera de los tres,
    con su propia unidad."""
    nivel = request.GET.get("nivel", "departamento")
    if nivel not in ("departamento", "municipio", "vereda", "region", "sitio"):
        return JsonResponse(
            {"error": "nivel debe ser uno de: departamento, municipio, vereda, region, sitio"}, status=400,
        )

    qs = (
        SubmuestraGEI.objects
        .exclude(fecha=None)
        .select_related(
            "muestra__unidad_medida",
            "muestra__unidad_muestreo__sitio__vereda__municipio__departamento__region",
            "muestra__unidad_muestreo__unidad_experimental__proyecto",
        )
    )

    gas = request.GET.get("gas")
    if gas:
        qs = qs.filter(muestra__gas=gas.upper())

    desde = request.GET.get("desde")
    if desde:
        qs = qs.filter(fecha__gte=desde)

    hasta = request.GET.get("hasta")
    if hasta:
        qs = qs.filter(fecha__lte=hasta)

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

    sitio_id = request.GET.get("sitio")
    if sitio_id:
        qs = qs.filter(muestra__unidad_muestreo__sitio_id=sitio_id)

    CAMPO_POR_NIVEL = {
        "sitio": "muestra__unidad_muestreo__sitio",
        "vereda": "muestra__unidad_muestreo__sitio__vereda",
        "municipio": "muestra__unidad_muestreo__sitio__vereda__municipio",
        "departamento": "muestra__unidad_muestreo__sitio__vereda__municipio__departamento",
        "region": "muestra__unidad_muestreo__sitio__vereda__municipio__departamento__region",
    }
    campo = CAMPO_POR_NIVEL[nivel]
    campo_id = campo + "_id"
    campo_dep = "muestra__unidad_muestreo__sitio__vereda__municipio__departamento"

    # Agregar en la base en vez de materializar cada medicion en Python: una
    # consulta con GROUP BY devuelve una fila por grupo, no una por medicion.
    base = qs.exclude(**{campo_id: None})
    excluidos = qs.count() - base.count()

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

    # Ultima medicion por grupo con DISTINCT ON de Postgres: una sola consulta
    # en vez de recorrer todas las filas comparando fechas.
    ultimas = {
        fila[campo_id]: fila
        for fila in base.filter(**{campo_id + "__in": claves})
        .order_by(campo_id, "-fecha", "-id")
        .distinct(campo_id)
        .values(campo_id, "fecha", "valor", "muestra__unidad_medida__codigo")
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
                    "valor": float(ultima["valor"]) if ultima["valor"] is not None else None,
                    "unidad": ultima["muestra__unidad_medida__codigo"],
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
    })
