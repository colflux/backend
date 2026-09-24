import csv
import decimal
import io
import json
import logging
import math
import re
import urllib.request
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import FieldDoesNotExist
from django.db import models, transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from app.api.permisos import requiere_nivel
from app.models import CargaArchivo, FuenteDatos, MapeoColumna, Proyecto, TipoCobertura

from app.catalogo.generator import COLOR_POR_MODELO, GRUPOS_CATALOGO, campo_to_catalogo, fk_choices

logger = logging.getLogger(__name__)

# El wizard del ETL usa su propio agrupamiento de secciones, más fino que
# GRUPOS_CATALOGO (que sigue usándose tal cual para el catálogo de
# referencia en docs/):
# - Separa "Unidad Experimental" de "Unidad de Muestreo" porque en los
#   archivos reales primero se identifica la unidad experimental y solo
#   después se resuelve el tipo/unidad de muestreo/parcela que dependen de
#   ella (vía la FK a UnidadExperimental mapeada en la sección anterior).
# - Excluye "Geografía" (Region/Departamento/Municipio) salvo "Sitio", que
#   se saca de ese grupo y se deja como su propia sección al final: en el
#   catálogo vive junto a la geografía porque se georreferencia por
#   Municipio, pero en el wizard depende de que ya exista la Unidad de
#   Muestreo (no siempre se completa con datos del archivo).
# - Excluye "Publicaciones": es metadato bibliográfico del proyecto, no
#   datos fila por fila del archivo. Al quitarla, "Unidad Experimental"
#   queda como primera sección real del wizard.
# - Excluye temporalmente "Suelo", "Torre EC y Flujos", "Proyecto" y
#   "Usuarios, Roles y ETL": todavía no se está mapeando/importando esas
#   entidades desde el ETL. "Cobertura y Vegetación" se habilitó: Sitio ya
#   tiene FK a Cobertura/Vegetacion/Disturbio y _orden_topologico() las
#   ordena antes que Sitio por esa FK sin importar la posición de la sección
#   en este listado, así que el auto-link entre modelos de la misma fila
#   (ver _procesar_filas) funciona igual que con Unidad Muestreo→Parcela.
#   Quitar de esta lista cuando se retome cada una.
_GRUPOS_EXCLUIDOS_TEMPORAL = (
    "Suelo",
    "Torre EC y Flujos",
    "Proyecto",
    "Usuarios, Roles y ETL",
)
SECCIONES_ETL = []
for _grupo in GRUPOS_CATALOGO:
    if _grupo["nombre"] in ("Geografía", "Publicaciones") or _grupo["nombre"] in _GRUPOS_EXCLUIDOS_TEMPORAL:
        continue
    if _grupo["nombre"] == "Unidad de Muestreo y Experimental":
        SECCIONES_ETL.append({
            "nombre": "Unidad Experimental",
            "icono": "🧪",
            "entidades": ["UnidadExperimental"],
        })
        SECCIONES_ETL.append({
            "nombre": "Unidad de Muestreo",
            "icono": "📏",
            # Solo el modelo base: nombre, tipo (obligatorio, ver
            # _validar_obligatorios_unidad_muestreo), fecha de instalación,
            # compartimento. Parcela/Transecto quedan en la sección siguiente
            # porque cuáles de sus atributos aplican depende del valor que
            # se le haya dado acá a "tipo" -mostrarlos juntos hacía parecer
            # que un archivo con datos de Parcela Y de Transecto era normal,
            # cuando una unidad de muestreo solo puede ser de un tipo-.
            "entidades": ["UnidadMuestreo"],
        })
        SECCIONES_ETL.append({
            "nombre": "Detalles de muestreo",
            "icono": "📐",
            # UnidadMuestreoTipo no se incluye aquí a propósito: es un catálogo
            # cerrado de tipos (parcela, transecto, etc.), no datos que el ETL
            # deba crear o modificar. El campo "tipo" de UnidadMuestreo se
            # mapea en la sección anterior, como FK de solo selección entre
            # los tipos ya existentes (ver fk_choices en catalogo/generator.py).
            "entidades": ["Parcela", "Transecto"],
        })
        SECCIONES_ETL.append({
            "nombre": "Sitio",
            "icono": "📍",
            "entidades": ["Sitio"],
        })
        # Clima (MuestraAmbiental) se saca de "Muestras GEI" para poder
        # cargarse solo, sin depender de tener también datos de GEI en el
        # mismo archivo — solo necesita que ya exista la Unidad de Muestreo
        # a la que se va a vincular, por eso va justo después de "Sitio".
        SECCIONES_ETL.append({
            "nombre": "Clima",
            "icono": "🌦️",
            "entidades": ["MuestraAmbiental"],
        })
    elif _grupo["nombre"] == "Muestras GEI":
        # UnidadMedida, Equipo y TipoMuestra no se muestran como sección
        # propia: son catálogos que se cargan aparte, no datos fila por fila
        # del archivo. Sus valores igual se pueden asignar a MuestraGEI
        # (campos unidad_medida, analizador) como atributo fijo/columna dentro
        # de la sección MuestraGEI misma — mismo criterio que UnidadMuestreoTipo
        # más arriba.
        _EXCLUIDAS_MUESTRAS_GEI = ("MuestraAmbiental", "UnidadMedida", "Equipo", "TipoMuestra")
        SECCIONES_ETL.append({
            **_grupo,
            "entidades": [e for e in _grupo["entidades"] if e not in _EXCLUIDAS_MUESTRAS_GEI],
        })
    elif _grupo["nombre"] == "Cobertura y Vegetación":
        # TipoCobertura no se muestra como sección propia: es un catálogo
        # cerrado (CLC, IPCC, IGBP, …) que no se carga fila por fila, se
        # selecciona por mapeo (ver MapeoColumna.tipo_cobertura) — mismo
        # criterio que UnidadMuestreoTipo/UnidadMedida más arriba.
        SECCIONES_ETL.append({
            **_grupo,
            "entidades": [e for e in _grupo["entidades"] if e != "TipoCobertura"],
        })
    else:
        SECCIONES_ETL.append(_grupo)


def _infer_dtype(series):
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "number"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    return "string"


def _muestra(series, n=3):
    valores = series.dropna().head(n).tolist()
    return [str(v) for v in valores]


def _sugerencias_hora(valores_unicos):
    """Para columnas que puedan mapearse a un TimeField: de sus valores únicos,
    cuáles tienen forma de hora ambigua (24h + sufijo a. m./p. m. contradictorio)
    y qué interpretación se les podría sugerir al usuario para que la confirme
    o corrija en la UI (nunca se aplica sola)."""
    sugerencias = {}
    for val in valores_unicos:
        sugerencia = _sugerir_hora(val)
        if sugerencia is not None:
            sugerencias[val] = sugerencia
    return sugerencias


_RE_HORA_LAXA = re.compile(r"^\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?\s*([ap]\.?\s*m\.?)?\s*$", re.IGNORECASE)


def _interpretaciones_hora(valores_unicos):
    """Para toda columna con pinta de hora: cómo se interpretaría cada valor
    único en 24h (HH:MM:ss) tal como quedaría guardado en la base de datos.
    Se usa para mostrarle al usuario, antes de guardar, exactamente en qué se
    convierte cada valor de origen -incluidos los que ya son válidos y no
    requieren ninguna corrección- y así detectar ambigüedades a simple vista."""
    interpretaciones = {}
    for val in valores_unicos:
        if not _RE_HORA_LAXA.match(str(val).strip()):
            continue
        try:
            interpretaciones[val] = pd.to_datetime(val).strftime("%H:%M:%S")
            continue
        except Exception:
            pass
        sugerencia = _sugerir_hora(val)
        if sugerencia is not None:
            interpretaciones[val] = sugerencia
    return interpretaciones


def _columnas_desde_dataframe(df):
    columnas = []
    for col in df.columns:
        # Los valores únicos para el panel de choices se limitan a los
        # primeros max_n (rendimiento), pero la detección de horas ambiguas
        # necesita revisar TODOS los valores: un valor problemático puede
        # aparecer más adelante en la columna y quedar fuera de ese límite.
        todos_unicos = [str(v) for v in df[col].dropna().unique()]
        columnas.append({
            "nombre": col,
            "dtype": _infer_dtype(df[col]),
            "nulls": int(df[col].isna().sum()),
            "muestra": _muestra(df[col]),
            "valores_unicos": todos_unicos[:50],
            "sugerencias_hora": _sugerencias_hora(todos_unicos),
            "interpretaciones_hora": _interpretaciones_hora(todos_unicos),
        })
    return columnas


def _outliers_iqr(series_numerica):
    """Cantidad de valores fuera de [Q1 - 1.5·IQR, Q3 + 1.5·IQR] -método
    estándar de caja (boxplot) para columnas numéricas-. Con menos de 4
    valores no hay suficiente base para calcular cuartiles con sentido."""
    limpio = series_numerica.dropna()
    if len(limpio) < 4:
        return 0
    q1 = limpio.quantile(0.25)
    q3 = limpio.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0
    limite_inf = q1 - 1.5 * iqr
    limite_sup = q3 + 1.5 * iqr
    return int(((limpio < limite_inf) | (limpio > limite_sup)).sum())


def _top_valores(series, n=5):
    """Los `n` valores más frecuentes (no nulos) de una columna, para el
    resumen tipo `.describe()` de columnas categóricas/texto."""
    conteos = series.dropna().astype(str).value_counts().head(n)
    return [{"valor": str(v), "conteo": int(c)} for v, c in conteos.items()]


def _eda_columna(df, col):
    """Estadísticas descriptivas + señales de calidad de una sola columna,
    para el paso de análisis EDA del wizard (entre "Analizar fuente" y "Qué
    encontramos"): así el usuario decide si el archivo está listo para
    mapear antes de invertir tiempo en el mapeo."""
    serie = df[col]
    total = len(serie)
    nulls = int(serie.isna().sum())
    dtype = _infer_dtype(serie)
    valores_unicos = int(serie.nunique(dropna=True))

    stats = {
        "nombre": col,
        "dtype": dtype,
        "total": total,
        "nulls": nulls,
        "nulls_pct": round(100 * nulls / total, 1) if total else 0.0,
        "valores_unicos": valores_unicos,
        "minimo": None,
        "maximo": None,
        "promedio": None,
        "desviacion": None,
        "outliers": None,
        "top_valores": None,
        "hoja": None,
    }

    if dtype == "number":
        limpio = serie.dropna()
        if len(limpio):
            stats["minimo"] = _to_python(limpio.min())
            stats["maximo"] = _to_python(limpio.max())
            stats["promedio"] = _to_python(round(float(limpio.mean()), 4))
            stats["desviacion"] = _to_python(round(float(limpio.std()), 4)) if len(limpio) > 1 else 0.0
            stats["outliers"] = _outliers_iqr(limpio)
    elif dtype == "date":
        limpio = serie.dropna()
        if len(limpio):
            stats["minimo"] = str(limpio.min())
            stats["maximo"] = str(limpio.max())
    else:
        stats["top_valores"] = _top_valores(serie)

    return stats


def _eda_desde_dataframe(df):
    """Resumen EDA completo de la carga: estadística descriptiva por columna
    (similar a `df.describe()`) y señales de calidad de datos (nulos,
    outliers, duplicados) para mostrarse en el paso EDA del wizard antes de
    que el usuario decida el mapeo. Se calcula sobre el DataFrame completo
    -no solo la muestra que ya viaja en `columnas`- porque duplicados y
    outliers requieren verlo todo."""
    columnas = [_eda_columna(df, col) for col in df.columns]

    filas_duplicadas = int(df.duplicated().sum())
    columnas_con_muchos_nulos = [c["nombre"] for c in columnas if c["nulls_pct"] >= 30]
    columnas_con_outliers = [c["nombre"] for c in columnas if (c["outliers"] or 0) > 0]

    return {
        "total_filas": len(df),
        "total_columnas": len(df.columns),
        "columnas": columnas,
        "filas_duplicadas": filas_duplicadas,
        "columnas_con_muchos_nulos": columnas_con_muchos_nulos,
        "columnas_con_outliers": columnas_con_outliers,
    }


def _agregar_eda_y_columnas_otras_hojas(eda, path_archivo, sheets, hoja_activa, hojas_data, carga_id):
    """Agrega al EDA las columnas de las demás hojas del Excel, y llena
    `hojas_data` con `columnas_raw`/`total_filas` de cada una -no solo la
    hoja activa se mapea/importa: una misma carga puede mapear varias hojas
    del mismo archivo en un solo flujo (Sitio/UM/UE, mediciones GEI, Clima,
    etc.), así que hace falta esta info de cada una desde el primer
    análisis, sin tener que volver a leer el archivo por hoja. Se excluyen
    las hojas de "diccionario de datos" (no se mapean). Cada columna del EDA
    queda marcada con `hoja` para distinguir su origen; las señales de
    calidad (duplicados, nulos altos, outliers) se dejan acotadas a la hoja
    activa, que es la del EDA calculado por el llamador."""
    for c in eda["columnas"]:
        c["hoja"] = hoja_activa

    for otra_hoja in sheets:
        if otra_hoja == hoja_activa or "diccionario" in otra_hoja.lower():
            continue
        try:
            df_otra = pd.read_excel(path_archivo, sheet_name=otra_hoja)
        except Exception:
            logger.warning("No se pudo leer la hoja '%s' para el EDA", otra_hoja, exc_info=True)
            continue
        if df_otra.empty:
            continue
        columnas_otra = [_eda_columna(df_otra, col) for col in df_otra.columns]
        for c in columnas_otra:
            c["hoja"] = otra_hoja
        eda["columnas"].extend(columnas_otra)

        hojas_data[otra_hoja] = {
            "columnas_raw": _columnas_desde_dataframe(df_otra),
            "total_filas": len(df_otra),
        }
        cache.set(f"etl_carga_df_{carga_id}_{otra_hoja}", df_otra, timeout=None)

    eda["total_columnas"] = len(eda["columnas"])
    return eda


_EXTENSIONES_VALIDAS = (".xlsx", ".xls", ".csv")

_EXT_POR_CONTENT_TYPE = {
    "text/csv": ".csv",
    "application/csv": ".csv",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


def _descargar_archivo_remoto(fuente, url):
    cache_dir = Path(settings.MEDIA_ROOT) / "fuentes_datos_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "colflux-etl/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            content_type = resp.headers.get_content_type()
            data = resp.read()
    except Exception as exc:
        raise ValueError(f"No se pudo descargar el archivo remoto: {exc}") from exc

    ext = Path(urlparse(url).path).suffix.lower()
    if ext not in _EXTENSIONES_VALIDAS:
        ext = _EXT_POR_CONTENT_TYPE.get(content_type, "")
    if ext not in _EXTENSIONES_VALIDAS:
        raise ValueError(
            "No se pudo determinar el formato del archivo remoto (.xlsx, .xls o .csv)."
        )

    destino = cache_dir / f"fuente_{fuente.pk}{ext}"
    destino.write_bytes(data)
    return destino


def _guardar_archivo_subido(fuente, archivo):
    nombre = archivo.name.lower()
    if not nombre.endswith(_EXTENSIONES_VALIDAS):
        raise ValueError("Formato no permitido. Solo .xlsx, .xls o .csv")

    destino_dir = Path(settings.MEDIA_ROOT) / "fuentes_datos"
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / f"fuente_{fuente.pk}{Path(nombre).suffix}"

    with open(destino, "wb") as f:
        for chunk in archivo.chunks():
            f.write(chunk)

    fuente.url = str(destino.relative_to(settings.BASE_DIR))
    fuente.save(update_fields=["url"])
    return destino


def _detectar_separador(muestra):
    lineas = [l for l in muestra.splitlines()[:20] if l.strip()]
    if not lineas:
        return ","

    mejor_sep, mejor_puntaje = ",", -1
    for sep in (",", ";", "\t", "|"):
        conteos = [len(next(csv.reader([l], delimiter=sep))) - 1 for l in lineas]
        if min(conteos) == 0:
            continue
        # Preferimos el separador que produce más columnas de forma consistente
        consistentes = sum(1 for c in conteos if c == conteos[0])
        puntaje = conteos[0] * consistentes
        if puntaje > mejor_puntaje:
            mejor_sep, mejor_puntaje = sep, puntaje
    return mejor_sep


def _leer_csv(path, **kwargs):
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, encoding=encoding, newline="") as f:
                muestra = f.read(64 * 1024)
        except UnicodeDecodeError:
            continue

        sep = _detectar_separador(muestra)
        try:
            return pd.read_csv(path, encoding=encoding, sep=sep, **kwargs)
        except UnicodeDecodeError:
            continue
        except pd.errors.ParserError as exc:
            raise ValueError(
                "El archivo CSV tiene filas con distinta cantidad de columnas "
                f"(separador detectado: '{sep}'). Revisa que no tenga filas de "
                "título antes del encabezado ni celdas con el separador sin "
                f"comillas. Detalle: {exc}"
            ) from exc
    raise ValueError("No se pudo determinar la codificación del archivo CSV.")


def _leer_dataframe_carga(carga, hoja):
    """Lee el DataFrame de una hoja del archivo de una `carga`, cacheado por
    `carga.id` + `hoja` (una misma carga puede mapear varias hojas del mismo
    archivo a la vez). El archivo queda fijo desde `upload_archivo`, así que
    no hace falta releer/reparsear el Excel o CSV completo -ni redescargarlo
    si la fuente es remota- en cada validar/previsualizar/importar de
    sección: eso es lo que hacía lento cada clic de "Validar y guardar", sin
    importar cuántas columnas tuviera mapeadas esa sección.
    Devuelve una copia porque el llamador la muta in-place (ver
    `_aplicar_estrategia_nulos`)."""
    clave = f"etl_carga_df_{carga.id}_{hoja}"
    df = cache.get(clave)
    if df is None:
        path = _resolver_ruta_fuente(carga.fuente)
        nombre = str(path).lower()
        df = _leer_csv(path) if nombre.endswith(".csv") else pd.read_excel(path, sheet_name=hoja)
        cache.set(clave, df, timeout=None)
    return df.copy()


def _resolver_ruta_fuente(fuente):
    raw_path = (fuente.url or "").strip()
    if not raw_path:
        raise ValueError("La fuente no tiene enlace o ruta de archivo registrada.")

    parsed = urlparse(raw_path)
    if parsed.scheme in ("http", "https"):
        return _descargar_archivo_remoto(fuente, raw_path)
    if parsed.scheme == "file":
        raw_path = parsed.path
    elif parsed.scheme:
        raise ValueError("El enlace de la fuente usa un esquema no soportado.")

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path(settings.BASE_DIR) / path
    path = path.resolve()

    if not path.is_file():
        raise FileNotFoundError(
            "No se encontró el archivo registrado en la fuente (la ruta guardada ya no existe "
            "en el servidor). Usa \"O sube el archivo directamente\" para volver a cargarlo."
        )

    return path


@csrf_exempt
@requiere_nivel("reportador")
def archivo_fuente(request, fuente_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        fuente = FuenteDatos.objects.get(pk=fuente_id)
    except FuenteDatos.DoesNotExist:
        return JsonResponse({"error": "Fuente de datos no encontrada"}, status=404)

    if fuente.estado == "completo":
        return JsonResponse(
            {"error": "Esta fuente ya tiene datos cargados: el archivo no se puede reemplazar."}, status=409,
        )

    archivo_subido = request.FILES.get("archivo")
    if not archivo_subido:
        return JsonResponse({"error": "No se recibió ningún archivo"}, status=400)

    try:
        _guardar_archivo_subido(fuente, archivo_subido)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"url": fuente.url})


@csrf_exempt
@requiere_nivel("reportador")
def upload_archivo(request, fuente_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        fuente = FuenteDatos.objects.get(pk=fuente_id)
    except FuenteDatos.DoesNotExist:
        return JsonResponse({"error": "Fuente de datos no encontrada"}, status=404)

    archivo_subido = request.FILES.get("archivo")
    hoja_solicitada = (request.POST.get("hoja") or "").strip()

    try:
        if archivo_subido:
            path_archivo = _guardar_archivo_subido(fuente, archivo_subido)
        else:
            path_archivo = _resolver_ruta_fuente(fuente)

        nombre_archivo = path_archivo.name.lower()
        if not nombre_archivo.endswith(_EXTENSIONES_VALIDAS):
            return JsonResponse({"error": "Formato no permitido. Solo .xlsx, .xls o .csv"}, status=400)

        carga = CargaArchivo.objects.create(fuente=fuente)

        if nombre_archivo.endswith(".csv"):
            df = _leer_csv(path_archivo)
            sheets = []
            hoja_activa = ""
            total_filas = len(df)
            columnas = _columnas_desde_dataframe(df)
        else:
            import openpyxl
            wb = openpyxl.load_workbook(path_archivo, read_only=True, data_only=True)
            sheets = wb.sheetnames

            if hoja_solicitada and hoja_solicitada in sheets:
                # El usuario eligió explícitamente qué hoja mapear en esta
                # carga (p. ej. para registrar CO2/CH4/Clima además de la
                # hoja principal) -no se aplica la detección automática de
                # abajo, que siempre cae en la primera hoja con datos-.
                hoja_activa = hoja_solicitada
            else:
                hoja_activa = sheets[0]
                for sheet_name in sheets:
                    ws = wb[sheet_name]
                    if ws.max_row and ws.max_row > 1:
                        hoja_activa = sheet_name
                        break

            df = pd.read_excel(path_archivo, sheet_name=hoja_activa)
            total_filas = len(df)
            columnas = _columnas_desde_dataframe(df)
            wb.close()

        # Precarga la caché con el DataFrame que ya se leyó acá, para que el
        # primer "Validar y guardar" de esta carga tampoco lo tenga que releer.
        cache.set(f"etl_carga_df_{carga.pk}_{hoja_activa}", df, timeout=None)

        # `hojas_data` reúne columnas_raw/total_filas por hoja -no solo la
        # activa- para que el asistente pueda mapear varias hojas del mismo
        # archivo (Sitio/UM/UE, CO2, CH4, Clima, ...) en un solo flujo, sin
        # tener que volver a analizar el archivo por cada una.
        hojas_data = {hoja_activa: {"columnas_raw": columnas, "total_filas": total_filas}}

        # EDA sobre el DataFrame completo (no la muestra de `columnas`): se
        # calcula acá, aprovechando que el archivo ya está leído en memoria,
        # para el paso "Análisis EDA" del wizard (antes de decidir el mapeo).
        eda = _eda_desde_dataframe(df)
        if sheets:
            eda = _agregar_eda_y_columnas_otras_hojas(eda, path_archivo, sheets, hoja_activa, hojas_data, carga.pk)

        carga.hoja_activa = hoja_activa
        carga.columnas_raw = columnas
        carga.total_filas = total_filas
        carga.hojas = hojas_data
        carga.save(update_fields=["hoja_activa", "columnas_raw", "total_filas", "hojas"])

        # Recuperar el avance de mapeo de la última carga de esta fuente,
        # copiándolo a la carga nueva (solo columnas que siguen existiendo),
        # por cada hoja analizada acá.
        mapeos_previos_por_hoja = {}
        carga_previa = (
            CargaArchivo.objects.filter(fuente=fuente, mapeos__isnull=False)
            .exclude(pk=carga.pk)
            .order_by("-created_at")
            .first()
        )
        if carga_previa:
            nuevos_mapeos = []
            for hoja_nombre, info in hojas_data.items():
                nombres_actuales = {c["nombre"] for c in info["columnas_raw"]}
                # Los atributos manuales (constantes) no dependen de las
                # columnas del archivo, así que siempre se conservan.
                copias = [
                    m for m in carga_previa.mapeos.filter(hoja=hoja_nombre)
                    if m.columna_origen in nombres_actuales or m.transformacion == "constante"
                ]
                if not copias and carga_previa.hoja_activa == hoja_nombre:
                    # Cargas previas a esta migración no tenían `hoja` en sus
                    # MapeoColumna (queda ""): si esa carga previa solo
                    # mapeaba justo esta hoja, se asume que son suyos.
                    copias = [
                        m for m in carga_previa.mapeos.filter(hoja="")
                        if m.columna_origen in nombres_actuales or m.transformacion == "constante"
                    ]
                nuevos_mapeos.extend(
                    MapeoColumna(
                        carga=carga,
                        hoja=hoja_nombre,
                        columna_origen=m.columna_origen,
                        modelo_destino=m.modelo_destino,
                        campo_destino=m.campo_destino,
                        transformacion=m.transformacion,
                        regex_patron=m.regex_patron,
                        mapeo_valores=m.mapeo_valores,
                        valor_constante=m.valor_constante,
                        estrategia_nulos=m.estrategia_nulos,
                        valor_relleno_manual=m.valor_relleno_manual,
                    )
                    for m in copias
                )
                mapeos_previos_por_hoja[hoja_nombre] = [
                    {
                        "columna_origen": m.columna_origen,
                        "modelo_destino": m.modelo_destino,
                        "campo_destino": m.campo_destino,
                        "transformacion": m.transformacion,
                        "regex_patron": m.regex_patron,
                        "mapeo_valores": m.mapeo_valores,
                        "valor_constante": m.valor_constante,
                        "estrategia_nulos": m.estrategia_nulos,
                        "valor_relleno_manual": m.valor_relleno_manual,
                    }
                    for m in copias
                ]
            MapeoColumna.objects.bulk_create(nuevos_mapeos)

        return JsonResponse({
            "carga_id": carga.pk,
            "sheets": sheets,
            "hoja_activa": hoja_activa,
            "total_filas": total_filas,
            "columnas": columnas,
            "mapeos": mapeos_previos_por_hoja.get(hoja_activa, []),
            "eda": eda,
            "hojas": {
                hoja_nombre: {
                    "total_filas": info["total_filas"],
                    "columnas": info["columnas_raw"],
                    "mapeos": mapeos_previos_por_hoja.get(hoja_nombre, []),
                }
                for hoja_nombre, info in hojas_data.items()
            },
        }, json_dumps_params={"ensure_ascii": False})

    except (ValueError, FileNotFoundError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        logger.exception("Error inesperado al analizar la fuente %s", fuente_id)
        return JsonResponse({
            "error": (
                "No se pudo leer el archivo por un error inesperado. Verifica que no esté dañado, "
                "protegido con contraseña o abierto en otro programa, y vuelve a subirlo. "
                f"Detalle técnico: {exc}"
            )
        }, status=500)


def campos_destino(request):
    # Antes esta vista incluía las instancias existentes de cada campo FK
    # (incluir_instancias_fk=True), lo que dispara una consulta a la BD por
    # cada campo FK de cada modelo del catálogo — con ~13 secciones eso tardaba
    # ~54s (ver hallazgo de rendimiento). Ahora solo devuelve la estructura
    # estática (nombre, tipo, choices fijos) y las instancias de FK se piden
    # aparte, por campo, bajo demanda: ver fk_choices_view.
    modelos = {}
    grupos = {}
    orden_modelo = 0
    for orden, grupo in enumerate(SECCIONES_ETL):
        for nombre in grupo["entidades"]:
            try:
                modelo_cls = apps.get_model("app", nombre)
            except LookupError:
                continue
            campos = []
            for field in modelo_cls._meta.get_fields():
                if field.is_relation and not hasattr(field, "column"):
                    continue
                if field.name in ("id", "created_at", "updated_at"):
                    continue
                # Cobertura.sitio se auto-vincula al Sitio de la misma fila (igual
                # que Parcela -> UnidadMuestreo) y Cobertura.tipo se resuelve
                # aparte, desde el selector "tipo_cobertura" del mapeo (ver
                # _procesar_fila_cobertura): no tiene sentido ofrecerlos como
                # campo_destino normal, un solo MapeoColumna de Cobertura ya no
                # produce una única fila por modelo/fila de origen.
                if nombre == "Cobertura" and field.name in ("sitio", "tipo"):
                    continue
                # UnidadMuestreo.sitio se vincula solo (igual que Cobertura.sitio
                # arriba): al guardar la sección Sitio, _procesar_filas la
                # reprocesa junto con Unidad Experimental/Unidad de Muestreo y
                # engancha por la fila del archivo, sin que el usuario mapee una
                # columna acá.
                if nombre == "UnidadMuestreo" and field.name == "sitio":
                    continue
                campos.append(campo_to_catalogo(field, nombre_modelo=nombre))
            if campos:
                modelos[nombre] = campos
                grupos[nombre] = {
                    "nombre": grupo["nombre"],
                    "icono": grupo["icono"],
                    "orden": orden,
                    "orden_modelo": orden_modelo,
                }
                orden_modelo += 1

    # Para el selector "sistema de clasificación" que el wizard muestra junto
    # a Cobertura.nombre (ver _procesar_fila_cobertura): se manda acá, junto
    # con el resto de los metadatos de mapeo, para no agregar un fetch aparte.
    tipos_cobertura = list(TipoCobertura.objects.values("id", "codigo", "nombre"))

    return JsonResponse(
        {"modelos": modelos, "grupos": grupos, "tipos_cobertura": tipos_cobertura},
        json_dumps_params={"ensure_ascii": False},
    )


def fk_choices_view(request):
    """Instancias existentes de un solo campo FK, pedidas bajo demanda por el
    wizard (al mostrar el selector de ese campo) en vez de precargarse todas
    de una vez en campos_destino."""
    modelo_nombre = request.GET.get("modelo")
    campo_nombre = request.GET.get("campo")
    if not modelo_nombre or not campo_nombre:
        return JsonResponse({"error": "Se requieren los parámetros 'modelo' y 'campo'."}, status=400)

    try:
        modelo_cls = apps.get_model("app", modelo_nombre)
    except LookupError:
        return JsonResponse({"error": f"El modelo '{modelo_nombre}' no existe."}, status=404)

    try:
        field = modelo_cls._meta.get_field(campo_nombre)
    except FieldDoesNotExist:
        return JsonResponse({"error": f"El campo '{campo_nombre}' no existe en '{modelo_nombre}'."}, status=404)

    if field.__class__.__name__ != "ForeignKey":
        return JsonResponse({"error": f"'{campo_nombre}' no es un campo FK."}, status=400)

    proyecto = None
    fuente_id = request.GET.get("fuente")
    if fuente_id:
        proyecto = (
            FuenteDatos.objects.filter(pk=fuente_id)
            .values_list("proyecto_id", flat=True)
            .first()
        )

    return JsonResponse(
        {"choices": fk_choices(field, proyecto=proyecto)},
        json_dumps_params={"ensure_ascii": False},
    )


# Campos donde tiene sentido "¿ya existe esto en el proyecto?": ambos se
# identifican por nombre dentro del proyecto (UnidadMuestreo vía su
# UnidadExperimental), que es justo lo que un regex de extracción intenta
# reproducir para reusar el registro en vez de duplicarlo.
_RESOLVERS_EXISTENCIA = {
    ("UnidadExperimental", "nombre"): lambda proyecto_id, valores: set(
        apps.get_model("app", "UnidadExperimental")
        .objects.filter(proyecto_id=proyecto_id, nombre__in=valores)
        .values_list("nombre", flat=True)
    ),
    ("UnidadMuestreo", "nombre"): lambda proyecto_id, valores: set(
        apps.get_model("app", "UnidadMuestreo")
        .objects.filter(unidad_experimental__proyecto_id=proyecto_id, nombre__in=valores)
        .values_list("nombre", flat=True)
    ),
}


@csrf_exempt
def verificar_existencia(request):
    """Para valores ya resueltos en el navegador (p. ej. el resultado de aplicar
    un regex), dice cuáles coinciden con un registro que ya existe en el
    proyecto de la fuente. Se usa en la vista previa del regex del paso 2 para
    avisar si el mapeo actual va a reutilizar una unidad existente o crear una
    nueva. Solo soporta los campos de `_RESOLVERS_EXISTENCIA`; el resto
    responde `soportado: false` para que el frontend no muestre nada.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    fuente_id = body.get("fuente_id")
    modelo = body.get("modelo", "")
    campo = body.get("campo", "")
    valores = [str(v) for v in (body.get("valores") or []) if str(v).strip()]

    resolver = _RESOLVERS_EXISTENCIA.get((modelo, campo))
    if not fuente_id or not valores or not resolver:
        return JsonResponse({"existentes": [], "soportado": bool(resolver)})

    proyecto_id = FuenteDatos.objects.filter(pk=fuente_id).values_list("proyecto_id", flat=True).first()
    if not proyecto_id:
        return JsonResponse({"existentes": [], "soportado": True})

    existentes = resolver(proyecto_id, set(valores))
    return JsonResponse({"existentes": sorted(existentes), "soportado": True})


def regex_sugerido(request):
    """Busca, dentro del mismo proyecto, el último regex que otra carga ya usó
    para llenar el mismo campo destino (p. ej. `UnidadExperimental.nombre`) y
    lo propone como punto de partida. Evita que cada carga nueva del mismo
    proyecto tenga que redescubrir a mano el patrón que separa sus columnas
    compuestas (ej. `SWAMP_<gas>_<unidad>_<n>`).
    """
    fuente_id = request.GET.get("fuente")
    modelo = request.GET.get("modelo", "")
    campo = request.GET.get("campo", "")
    if not fuente_id or not modelo or not campo:
        return JsonResponse({"regex_patron": None})

    proyecto_id = FuenteDatos.objects.filter(pk=fuente_id).values_list("proyecto_id", flat=True).first()
    if not proyecto_id:
        return JsonResponse({"regex_patron": None})

    mapeo = (
        MapeoColumna.objects
        .filter(
            carga__fuente__proyecto_id=proyecto_id,
            modelo_destino=modelo,
            campo_destino=campo,
            transformacion="regex",
        )
        .exclude(regex_patron="")
        .order_by("-created_at")
        .values("regex_patron", "columna_origen", "carga__fuente__nombre")
        .first()
    )
    if not mapeo:
        return JsonResponse({"regex_patron": None})

    return JsonResponse({
        "regex_patron": mapeo["regex_patron"],
        "columna_origen": mapeo["columna_origen"],
        "fuente_nombre": mapeo["carga__fuente__nombre"],
    }, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@requiere_nivel("reportador")
def mapeo_carga(request, fuente_id, carga_id):
    try:
        carga = CargaArchivo.objects.get(pk=carga_id, fuente_id=fuente_id)
    except CargaArchivo.DoesNotExist:
        return JsonResponse({"error": "Carga no encontrada"}, status=404)

    if request.method == "GET":
        # `hoja` es opcional: sin ella se mantiene el comportamiento previo
        # (todos los mapeos de la carga, columnas_raw/total_filas de la hoja
        # activa) para no romper la vista de solo lectura EtlMapeo.tsx; con
        # ella, se acota a esa hoja -la que usa el asistente de mapeo, que
        # ahora puede tener varias hojas mapeadas en una misma carga-.
        hoja = request.GET.get("hoja")
        mapeos_qs = carga.mapeos if hoja is None else carga.mapeos.filter(hoja=hoja)
        mapeos = list(
            mapeos_qs.values(
                "columna_origen", "modelo_destino", "campo_destino",
                "transformacion", "regex_patron", "factor_escala", "mapeo_valores", "valor_constante",
                "estrategia_nulos", "valor_relleno_manual", "tipo_cobertura", "gas_fijo",
                tipo_cobertura_nombre=models.F("tipo_cobertura__nombre"),
            )
        )
        info_hoja = carga.hojas.get(hoja) if hoja is not None else None
        return JsonResponse({
            "carga_id": carga.pk,
            "fuente_id": carga.fuente_id,
            "fuente_nombre": carga.fuente.nombre,
            "estado": carga.estado,
            "columnas_raw": info_hoja["columnas_raw"] if info_hoja else carga.columnas_raw,
            "total_filas": info_hoja["total_filas"] if info_hoja else carga.total_filas,
            "mapeos": mapeos,
        }, json_dumps_params={"ensure_ascii": False})

    if request.method == "POST":
        if carga.estado == "importado":
            return JsonResponse(
                {"error": "Esta carga ya fue importada: el mapeo no se puede modificar."}, status=409,
            )

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido"}, status=400)

        items = body.get("mapeos")
        if not isinstance(items, list):
            return JsonResponse({"error": "Se esperaba un array en 'mapeos'"}, status=400)

        # Hoja a la que pertenece este lote de mapeos -el asistente guarda de
        # a una hoja por vez, aunque la carga en conjunto pueda tener varias-.
        hoja = body.get("hoja", "")

        # parcial=True: guardado incremental de columnas sueltas; no cambia el estado
        parcial = bool(body.get("parcial"))

        try:
            guardados = 0
            # Clave (columna_origen, modelo_destino, campo_destino): una misma
            # columna origen puede mapear a más de un destino (p. ej. "ID" como
            # nombre de UnidadExperimental vía regex, y completo como nombre de
            # UnidadMuestreo), así que ya no alcanza con columna_origen sola.
            enviados = set()
            for item in items:
                columna_origen = (item.get("columna_origen") or "").strip()
                if not columna_origen:
                    continue
                modelo_destino = item.get("modelo_destino", "")
                campo_destino = item.get("campo_destino", "")
                factor_escala_raw = item.get("factor_escala")
                if factor_escala_raw in (None, ""):
                    factor_escala = None
                else:
                    try:
                        factor_escala = decimal.Decimal(str(factor_escala_raw))
                    except decimal.InvalidOperation:
                        return JsonResponse(
                            {"error": f'factor_escala inválido para la columna "{columna_origen}": {factor_escala_raw!r}'},
                            status=400,
                        )
                tipo_cobertura_raw = item.get("tipo_cobertura")
                tipo_cobertura_id = None
                if modelo_destino == "Cobertura" and not _es_vacio(tipo_cobertura_raw):
                    try:
                        tipo_cobertura_id = int(tipo_cobertura_raw)
                    except (TypeError, ValueError):
                        return JsonResponse(
                            {"error": f'tipo_cobertura inválido para la columna "{columna_origen}": {tipo_cobertura_raw!r}'},
                            status=400,
                        )

                gas_fijo_raw = item.get("gas_fijo") or ""
                gas_fijo = ""
                if modelo_destino == "SubmuestraGEI" and campo_destino == "valor" and gas_fijo_raw:
                    if gas_fijo_raw not in dict(MapeoColumna.GAS_CHOICES_MAPEO):
                        return JsonResponse(
                            {"error": f'gas_fijo inválido para la columna "{columna_origen}": {gas_fijo_raw!r}'},
                            status=400,
                        )
                    gas_fijo = gas_fijo_raw

                MapeoColumna.objects.update_or_create(
                    carga=carga,
                    hoja=hoja,
                    columna_origen=columna_origen,
                    modelo_destino=modelo_destino,
                    campo_destino=campo_destino,
                    defaults={
                        "transformacion": item.get("transformacion", "directo"),
                        "regex_patron": item.get("regex_patron", ""),
                        "factor_escala": factor_escala,
                        "mapeo_valores": item.get("mapeo_valores") or {},
                        "valor_constante": item.get("valor_constante", ""),
                        "estrategia_nulos": item.get("estrategia_nulos")
                        if item.get("estrategia_nulos") in dict(MapeoColumna.ESTRATEGIA_NULOS_CHOICES)
                        else "dejar_null",
                        "valor_relleno_manual": item.get("valor_relleno_manual", ""),
                        "tipo_cobertura_id": tipo_cobertura_id,
                        "gas_fijo": gas_fijo,
                    },
                )
                enviados.add((columna_origen, modelo_destino, campo_destino))
                guardados += 1

            # El frontend siempre envía el estado completo DE ESTA HOJA (columnas +
            # atributos manuales): lo que ya no venga se elimina (p. ej. un atributo
            # manual que se quitó o se re-apuntó a otro campo, o un destino extra
            # removido). Acotado a `hoja`: si no, borraría los mapeos de las demás
            # hojas de esta misma carga, que no vienen en este payload.
            claves_actuales = set(
                carga.mapeos.filter(hoja=hoja).values_list("columna_origen", "modelo_destino", "campo_destino")
            )
            for columna, modelo, campo in claves_actuales - enviados:
                carga.mapeos.filter(
                    hoja=hoja, columna_origen=columna, modelo_destino=modelo, campo_destino=campo,
                ).delete()

            if not parcial:
                carga.estado = "mapeado"
                carga.save(update_fields=["estado"])

            return JsonResponse({"ok": True, "guardados": guardados})
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse({"error": "Método no permitido"}, status=405)


def _to_python(val):
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    try:
        import numpy as np
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.floating,)):
            return None if math.isnan(float(val)) else float(val)
        if isinstance(val, (np.bool_,)):
            return bool(val)
    except ImportError:
        pass
    return val


def _es_vacio(val):
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    # pandas representa una fecha/hora faltante como NaT (no como None ni
    # NaN), p. ej. tras un pd.to_datetime(..., errors="coerce"). Sin este
    # chequeo, un NaT se cuela como valor "real" y revienta más adelante en
    # _coercionar_valor con "NaTType does not support utcoffset".
    if pd.isna(val):
        return True
    return False


def _es_fk(field):
    """True para ForeignKey y OneToOneField (esta última no aparece con ese
    nombre de clase, pero se comporta igual como relación N:1 con columna)."""
    return type(field).__name__ in ("ForeignKey", "OneToOneField")


def _choices_de_campo(field):
    """Choices efectivas de un campo: las declaradas en Django, o -para FK sin
    choices propias- las instancias existentes del modelo relacionado."""
    choices = getattr(field, "choices", None)
    if choices:
        return [(str(valor), etiqueta) for valor, etiqueta in choices]
    if _es_fk(field):
        return [(c["valor"], c["etiqueta"]) for c in fk_choices(field)]
    return None


_RE_HORA_MERIDIANO = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}(?:\.\d+)?))?\s*([ap]\.?\s*m\.?)\s*$", re.IGNORECASE)


def _sugerir_hora(valor):
    """Si `valor` tiene forma de hora con sufijo a. m./p. m. pero el formato
    estricto (el que exige Django) lo rechaza -por contradicción entre la
    hora en 24h y el sufijo, p. ej. "14:29:00 a. m."-, devuelve una
    *sugerencia* de interpretación (ignorando el sufijo) para que el usuario
    la confirme o la corrija en la UI. No se aplica automáticamente. Si el
    valor no aplica o ya es válido tal cual, devuelve None."""
    match = _RE_HORA_MERIDIANO.match(str(valor).strip())
    if not match:
        return None
    try:
        pd.to_datetime(valor)
        return None  # ya es válido en formato estricto, no hay ambigüedad
    except Exception:
        pass
    hora, minuto, segundo = match.group(1), match.group(2), match.group(3) or "00"
    candidato = f"{hora}:{minuto}:{segundo}"
    try:
        return pd.to_datetime(candidato).strftime("%H:%M:%S")
    except Exception:
        return None


def _aplicar_estrategia_nulos(df, mapeos):
    """Aplica sobre el propio DataFrame -antes de validar/previsualizar/
    importar- lo que el usuario eligió para los nulos de cada columna
    mapeada: 'rellenar' repite hacia abajo el último valor visto; 'manual'
    usa un valor fijo. 'dejar_null' e 'ignorar_fila' no tocan el DataFrame
    ('ignorar_fila' se resuelve fila por fila en _procesar_filas)."""
    for mapeo in mapeos:
        if mapeo.columna_origen not in df.columns:
            continue
        if mapeo.estrategia_nulos == "rellenar":
            df[mapeo.columna_origen] = df[mapeo.columna_origen].ffill()
        elif mapeo.estrategia_nulos == "manual" and not _es_vacio(mapeo.valor_relleno_manual):
            df[mapeo.columna_origen] = df[mapeo.columna_origen].fillna(mapeo.valor_relleno_manual)


def _resolver_valor_columna(val, mapeo):
    """Aplica la transformación de la columna (regex, escala) y/o la
    traducción de mapeo_valores (origen -> destino) de una columna mapeada a
    un campo con choices, igual que hace la UI antes de guardar."""
    if _es_vacio(val):
        return None
    if mapeo.transformacion == "regex" and mapeo.regex_patron:
        try:
            match = re.search(mapeo.regex_patron, str(val))
        except re.error as exc:
            # Python (a diferencia de JS, que se usa en la vista previa del
            # frontend) exige que los lookbehind sean de ancho fijo, entre
            # otras restricciones propias de su motor de regex.
            raise ValueError(
                f'El patrón regex de la columna "{mapeo.columna_origen}" no es válido para Python: {exc}'
            ) from exc
        if not match:
            return None
        val = match.group(1) if match.lastindex else match.group(0)
    if mapeo.transformacion == "escala" and mapeo.factor_escala is not None:
        # Convierte unidades multiplicando por el factor (p. ej. 0.01 para
        # centímetros -> metros). Acepta coma decimal (notación española)
        # además de punto, igual que muchos de los archivos fuente reales.
        texto = str(val).strip().replace(",", ".")
        try:
            val = float(texto) * float(mapeo.factor_escala)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f'La columna "{mapeo.columna_origen}" tiene un valor no numérico ("{val}") '
                f"y no se le puede aplicar el factor de escala."
            ) from exc
    if mapeo.mapeo_valores:
        return mapeo.mapeo_valores.get(str(val), val)
    return val


def _validar_columna(df, mapeo):
    columna_origen = mapeo.columna_origen
    modelo_destino = mapeo.modelo_destino
    campo_destino = mapeo.campo_destino
    try:
        modelo_cls = apps.get_model("app", modelo_destino)
    except LookupError:
        return {"advertencia": "modelo_o_campo_no_encontrado", "columna": columna_origen, "errores": []}

    try:
        field = modelo_cls._meta.get_field(campo_destino)
    except Exception:
        return {"advertencia": "modelo_o_campo_no_encontrado", "columna": columna_origen, "errores": []}

    if columna_origen not in df.columns:
        return {"advertencia": "modelo_o_campo_no_encontrado", "columna": columna_origen, "errores": []}

    serie = df[columna_origen]
    errores = []

    campo_requerido = not getattr(field, "blank", True) and not getattr(field, "null", True)
    max_length = getattr(field, "max_length", None)
    choices = _choices_de_campo(field)
    choices_valores = {v for v, _ in choices} if choices else None

    tipo_campo = type(field).__name__

    for idx, val_crudo in serie.items():
        fila = int(idx) + 2
        try:
            val = _resolver_valor_columna(val_crudo, mapeo)
        except ValueError as exc:
            errores.append({
                "fila": fila,
                "valor": _to_python(val_crudo),
                "tipo": "tipo_invalido",
                "mensaje": str(exc),
            })
            continue
        py_val = _to_python(val)

        if val is None:
            # "ignorar_fila": el usuario ya decidió que estas filas no crean
            # el registro, así que no es un error de validación bloqueante.
            if campo_requerido and mapeo.estrategia_nulos != "ignorar_fila":
                errores.append({
                    "fila": fila,
                    "valor": None,
                    "tipo": "nulo_obligatorio",
                    "mensaje": "Campo requerido vacío",
                })
            continue

        if tipo_campo in ("FloatField", "DecimalField"):
            try:
                float(val)
            except (ValueError, TypeError):
                errores.append({
                    "fila": fila,
                    "valor": py_val,
                    "tipo": "tipo_invalido",
                    "mensaje": "No se puede convertir a número",
                })
                continue

        elif tipo_campo in ("IntegerField", "PositiveIntegerField", "PositiveSmallIntegerField",
                            "SmallIntegerField", "BigIntegerField"):
            try:
                int(float(val))
            except (ValueError, TypeError):
                errores.append({
                    "fila": fila,
                    "valor": py_val,
                    "tipo": "tipo_invalido",
                    "mensaje": "No se puede convertir a entero",
                })
                continue

        elif tipo_campo in ("DateField", "DateTimeField"):
            try:
                pd.to_datetime(val)
            except Exception:
                errores.append({
                    "fila": fila,
                    "valor": py_val,
                    "tipo": "tipo_invalido",
                    "mensaje": "No se puede interpretar como fecha",
                })
                continue

        elif tipo_campo == "TimeField":
            try:
                pd.to_datetime(val)
            except Exception:
                errores.append({
                    "fila": fila,
                    "valor": py_val,
                    "tipo": "tipo_invalido",
                    "mensaje": "No se puede interpretar como hora",
                })
                continue

        if max_length is not None:
            if len(str(val)) > max_length:
                errores.append({
                    "fila": fila,
                    "valor": py_val,
                    "tipo": "longitud_excedida",
                    "mensaje": f"Longitud {len(str(val))} supera el máximo de {max_length}",
                })
                continue

        if choices_valores is not None:
            if val not in choices_valores and str(val) not in choices_valores:
                errores.append({
                    "fila": fila,
                    "valor": py_val,
                    "tipo": "fuera_de_vocabulario",
                    "mensaje": f"Valor no permitido. Opciones: {sorted(str(v) for v in choices_valores)}",
                })

    total = len(serie)
    return {
        "columna": columna_origen,
        "modelo_destino": modelo_destino,
        "campo_destino": campo_destino,
        "total": total,
        "ok": total - len(errores),
        "errores": errores,
    }


def _validar_constante(mapeo, total_filas):
    """Valida el valor fijo de un atributo manual contra el campo destino (una sola vez, aplica a todas las filas)."""
    try:
        modelo_cls = apps.get_model("app", mapeo.modelo_destino)
        field = modelo_cls._meta.get_field(mapeo.campo_destino)
    except Exception:
        return {"advertencia": "modelo_o_campo_no_encontrado", "columna": mapeo.columna_origen, "errores": []}

    val = mapeo.valor_constante
    errores = []
    campo_requerido = not getattr(field, "blank", True) and not getattr(field, "null", True)
    max_length = getattr(field, "max_length", None)
    choices = _choices_de_campo(field)
    tipo_campo = type(field).__name__

    if _es_vacio(val):
        if campo_requerido:
            errores.append({"fila": None, "valor": None, "tipo": "nulo_obligatorio", "mensaje": "Campo requerido vacío"})
    else:
        if tipo_campo in ("FloatField", "DecimalField"):
            try:
                float(val)
            except (ValueError, TypeError):
                errores.append({"fila": None, "valor": val, "tipo": "tipo_invalido", "mensaje": "No se puede convertir a número"})
        elif tipo_campo in ("IntegerField", "PositiveIntegerField", "PositiveSmallIntegerField",
                            "SmallIntegerField", "BigIntegerField"):
            try:
                int(float(val))
            except (ValueError, TypeError):
                errores.append({"fila": None, "valor": val, "tipo": "tipo_invalido", "mensaje": "No se puede convertir a entero"})
        elif tipo_campo in ("DateField", "DateTimeField"):
            try:
                pd.to_datetime(val)
            except Exception:
                errores.append({"fila": None, "valor": val, "tipo": "tipo_invalido", "mensaje": "No se puede interpretar como fecha"})
        elif tipo_campo == "TimeField":
            try:
                pd.to_datetime(val)
            except Exception:
                errores.append({"fila": None, "valor": val, "tipo": "tipo_invalido", "mensaje": "No se puede interpretar como hora"})
        if not errores and max_length is not None and len(str(val)) > max_length:
            errores.append({"fila": None, "valor": val, "tipo": "longitud_excedida", "mensaje": f"Longitud {len(str(val))} supera el máximo de {max_length}"})
        if not errores and choices is not None and str(val) not in {v for v, _ in choices}:
            errores.append({"fila": None, "valor": val, "tipo": "fuera_de_vocabulario", "mensaje": f"Valor no permitido. Opciones: {sorted(v for v, _ in choices)}"})

    return {
        "columna": mapeo.columna_origen,
        "modelo_destino": mapeo.modelo_destino,
        "campo_destino": mapeo.campo_destino,
        "total": total_filas,
        "ok": 0 if errores else total_filas,
        "errores": errores,
    }


def _valores_fila_modelo(df, mapeos_modelo, fila_idx):
    """Valores {campo_destino: valor} que tendría una instancia del modelo en
    una fila dada, según sus mapeos (columna directa o constante)."""
    valores = {}
    for m in mapeos_modelo:
        if m.transformacion == "constante":
            valor = None if _es_vacio(m.valor_constante) else m.valor_constante
        else:
            val_crudo = df[m.columna_origen].iloc[fila_idx]
            valor = _resolver_valor_columna(val_crudo, m)
        valores[m.campo_destino] = valor
    return valores


def _validar_obligatorios_unidad_muestreo(mapeos, modelos_incluidos, total_filas):
    """Reglas de negocio de UnidadMuestreo que no se derivan de blank/null del
    modelo (por eso _validar_columna/_validar_constante no las cubren):
    - 'nombre' es obligatorio para toda unidad de muestreo, así que debe
      quedar mapeado (columna o atributo manual) antes de guardar la sección.
    - 'tipo' también es obligatorio (parcela/transecto/...): sin este check,
      el error real -not-null constraint de la columna tipo_id- solo aparecía
      como un error crudo de Postgres al momento de guardar.
    - 'unidad_experimental' debe quedar resuelto sí o sí: mapeado explícito,
      o heredado automáticamente porque 'UnidadExperimental' se importa en la
      misma tanda (ver el vínculo automático por fila en importar_carga)."""
    if "UnidadMuestreo" not in modelos_incluidos:
        return None

    campos_um = {m.campo_destino for m in mapeos if m.modelo_destino == "UnidadMuestreo"}
    errores = []

    if "nombre" not in campos_um:
        errores.append({
            "fila": None, "valor": None, "tipo": "campo_obligatorio_sin_mapear",
            "mensaje": (
                "El campo 'nombre' de Unidad de Muestreo no está mapeado (ni por "
                "columna ni como atributo manual). Es obligatorio: toda unidad de "
                "muestreo necesita un nombre."
            ),
        })

    if "tipo" not in campos_um:
        errores.append({
            "fila": None, "valor": None, "tipo": "campo_obligatorio_sin_mapear",
            "mensaje": (
                "El campo 'tipo' de Unidad de Muestreo no está mapeado (ni por "
                "columna ni como atributo manual). Es obligatorio: toda unidad de "
                "muestreo debe ser de un tipo (parcela, transecto, etc.)."
            ),
        })

    if "unidad_experimental" not in campos_um and "UnidadExperimental" not in modelos_incluidos:
        errores.append({
            "fila": None, "valor": None, "tipo": "campo_obligatorio_sin_mapear",
            "mensaje": (
                "Unidad de Muestreo no tiene 'unidad_experimental' mapeada, y la "
                "sección 'Unidad Experimental' no forma parte de esta importación, "
                "así que no se puede vincular automáticamente. Mapea la columna, o "
                "guarda primero la sección Unidad Experimental."
            ),
        })

    return {
        "columna": "Unidad de Muestreo (campos obligatorios)",
        "modelo_destino": "UnidadMuestreo",
        "campo_destino": "",
        "total": total_filas,
        "ok": 0 if errores else total_filas,
        "errores": errores,
    }


def _validar_obligatorios_unidad_experimental(mapeos, modelos_incluidos, total_filas):
    """'nombre' es obligatorio para toda unidad experimental (es, junto con
    'proyecto', su clave de unicidad). Si no queda mapeado, get_or_create()
    terminaría buscando solo por 'proyecto' y podría devolver más de una
    fila cuando el proyecto ya tiene varias unidades experimentales."""
    if "UnidadExperimental" not in modelos_incluidos:
        return None

    campos_ue = {m.campo_destino for m in mapeos if m.modelo_destino == "UnidadExperimental"}
    errores = []

    if "nombre" not in campos_ue:
        errores.append({
            "fila": None, "valor": None, "tipo": "campo_obligatorio_sin_mapear",
            "mensaje": (
                "El campo 'nombre' de Unidad Experimental no está mapeado (ni por "
                "columna ni como atributo manual). Es obligatorio: identifica a la "
                "unidad experimental dentro de su proyecto."
            ),
        })

    return {
        "columna": "Unidad Experimental (campos obligatorios)",
        "modelo_destino": "UnidadExperimental",
        "campo_destino": "",
        "total": total_filas,
        "ok": 0 if errores else total_filas,
        "errores": errores,
    }


def _validar_unicidad_unidad_experimental(carga, df, mapeos):
    """Unidad Experimental es única por (proyecto, nombre): la fuente debe
    tener un proyecto asociado, y si ese nombre ya existe en el proyecto con
    otros datos (p. ej. otra descripción), se avisa acá en vez de fallar con
    un error de base de datos al intentar crearla.
    `mapeos` viene acotado a la hoja de `df` -no se re-consulta carga.mapeos-,
    porque una misma carga puede mapear varias hojas a la vez y cada hoja
    tiene su propio DataFrame."""
    mapeos_ue = [m for m in mapeos if m.modelo_destino == "UnidadExperimental"]
    mapeo_nombre = next((m for m in mapeos_ue if m.campo_destino == "nombre"), None)
    if mapeo_nombre is None:
        return None

    errores = []
    proyecto = carga.fuente.proyecto
    if proyecto is None:
        errores.append({
            "fila": None, "valor": None, "tipo": "sin_proyecto",
            "mensaje": "La fuente de datos no tiene un proyecto asociado. Asigna un proyecto a la fuente antes de continuar.",
        })
    else:
        UnidadExperimental = apps.get_model("app", "UnidadExperimental")
        vistos = {}
        filas = []  # (fila, nombre, valores) — se recorre dos veces: primero
        # para juntar los nombres a buscar, luego para comparar contra lo
        # existente, así se hace UNA sola consulta en vez de una por fila
        # (346 consultas contra una BD remota son ~1 minuto, suficiente para
        # que el worker de gunicorn mate la request por timeout).
        for fila_idx in range(len(df)):
            valores = _valores_fila_modelo(df, mapeos_ue, fila_idx)
            nombre = valores.get("nombre")
            if _es_vacio(nombre):
                continue
            fila = fila_idx + 2
            filas.append((fila, nombre, valores))

            previo = vistos.get(nombre)
            if previo is not None and previo != valores:
                errores.append({
                    "fila": fila, "valor": nombre, "tipo": "conflicto_unicidad",
                    "mensaje": f"'{nombre}' aparece con datos distintos en otra fila de este mismo archivo.",
                })
            vistos[nombre] = valores

        existentes = {
            obj.nombre: obj
            for obj in UnidadExperimental.objects.filter(proyecto=proyecto, nombre__in=set(vistos))
        }
        for fila, nombre, valores in filas:
            existente = existentes.get(nombre)
            if existente is not None:
                for campo, valor in valores.items():
                    # 'nombre' y 'proyecto' ya están garantizados por el filtro
                    # de arriba; compararlos de nuevo aquí siempre "coincide".
                    if campo in ("nombre", "proyecto") or valor is None:
                        continue
                    valor_existente = getattr(existente, campo)
                    if _es_fk(UnidadExperimental._meta.get_field(campo)):
                        valor_existente = getattr(valor_existente, "pk", None)
                    if str(valor_existente) != str(valor):
                        errores.append({
                            "fila": fila, "valor": nombre, "tipo": "conflicto_unicidad",
                            "mensaje": (
                                f"Ya existe una Unidad Experimental '{nombre}' en el proyecto "
                                f"'{proyecto.nombre}' con datos distintos (campo '{campo}'). "
                                "Cambia el nombre o corrige el valor para que coincida."
                            ),
                        })
                        break

    filas_con_error = {e["fila"] for e in errores if e["fila"] is not None}
    ok = 0 if any(e["tipo"] == "sin_proyecto" for e in errores) else len(df) - len(filas_con_error)
    return {
        "columna": "Unidad Experimental (nombre único por proyecto)",
        "modelo_destino": "UnidadExperimental",
        "campo_destino": "nombre",
        "total": len(df),
        "ok": ok,
        "errores": errores,
    }


@csrf_exempt
@requiere_nivel("reportador")
def validar_carga(request, fuente_id, carga_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        carga = CargaArchivo.objects.get(pk=carga_id, fuente_id=fuente_id)
    except CargaArchivo.DoesNotExist:
        return JsonResponse({"error": "Carga no encontrada"}, status=404)

    try:
        # `validar_carga` valida toda la carga de una vez (no por sección) y
        # no la usa el asistente de mapeo (que valida por sección vía
        # `_validar_seccion`, sí multi-hoja) — se deja acotada a hoja_activa.
        df = _leer_dataframe_carga(carga, carga.hoja_activa)

        mapeos = list(carga.mapeos.filter(hoja=carga.hoja_activa).exclude(modelo_destino=""))
        _aplicar_estrategia_nulos(df, mapeos)

        resultados = []
        filas_con_error = set()

        for mapeo in mapeos:
            if mapeo.transformacion == "constante":
                resultado = _validar_constante(mapeo, len(df))
            else:
                resultado = _validar_columna(df, mapeo)
            if "advertencia" not in resultado:
                for e in resultado["errores"]:
                    filas_con_error.add(e["fila"])
            resultados.append(resultado)

        resultado_ue = _validar_unicidad_unidad_experimental(carga, df, mapeos)
        if resultado_ue is not None:
            for e in resultado_ue["errores"]:
                filas_con_error.add(e["fila"])
            resultados.append(resultado_ue)

        modelos_incluidos = {m.modelo_destino for m in mapeos}
        resultado_ue_obl = _validar_obligatorios_unidad_experimental(mapeos, modelos_incluidos, len(df))
        if resultado_ue_obl is not None:
            for e in resultado_ue_obl["errores"]:
                filas_con_error.add(e["fila"])
            resultados.append(resultado_ue_obl)

        resultado_um = _validar_obligatorios_unidad_muestreo(mapeos, modelos_incluidos, len(df))
        if resultado_um is not None:
            for e in resultado_um["errores"]:
                filas_con_error.add(e["fila"])
            resultados.append(resultado_um)

        columnas_con_errores = sum(
            1 for r in resultados
            if "advertencia" not in r and len(r["errores"]) > 0
        )
        total_errores = sum(
            len(r["errores"]) for r in resultados if "advertencia" not in r
        )

        return JsonResponse({
            "resumen": {
                "total_filas": len(df),
                "columnas_mapeadas": len(mapeos),
                "columnas_con_errores": columnas_con_errores,
                "total_errores": total_errores,
                "filas_limpias": len(df) - len(filas_con_error),
                "filas_con_errores": len(filas_con_error),
            },
            "columnas": resultados,
        }, json_dumps_params={"ensure_ascii": False})

    except (ValueError, FileNotFoundError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


_ORDEN_GRUPO_MODELO = {
    nombre: orden
    for orden, grupo in enumerate(SECCIONES_ETL)
    for nombre in grupo["entidades"]
}


def _grupo_de_modelo(modelo):
    return _ORDEN_GRUPO_MODELO.get(modelo, len(SECCIONES_ETL))


def _orden_topologico(modelos):
    """Ordena `modelos` (nombres) de forma que cada uno quede después de
    cualquier otro modelo de la misma lista al que referencia por FK, para
    poder crearlos en ese orden (p. ej. UnidadMuestreo antes que Parcela)."""
    dependencias = {}
    for modelo in modelos:
        try:
            modelo_cls = apps.get_model("app", modelo)
        except LookupError:
            dependencias[modelo] = set()
            continue
        dependencias[modelo] = {
            field.related_model.__name__
            for field in modelo_cls._meta.get_fields()
            if _es_fk(field) and field.related_model.__name__ in modelos
        }

    ordenados = []
    vistos = set()

    def visitar(modelo):
        if modelo in vistos:
            return
        vistos.add(modelo)
        for dependencia in dependencias.get(modelo, ()):
            visitar(dependencia)
        ordenados.append(modelo)

    for modelo in modelos:
        visitar(modelo)
    return ordenados


def _coercionar_valor(valor, field):
    tipo_campo = type(field).__name__
    if tipo_campo == "FloatField":
        return float(valor)
    if tipo_campo == "DecimalField":
        # Decimal(str(valor)), no float(valor): dejar esto en float (como
        # antes) rompe cualquier cuenta que el modelo haga con Decimal más
        # adelante -p. ej. Parcela._calcular_area(), que multiplica por
        # Decimal("3.14159265") y no acepta operar con float-. Pasar por str()
        # en vez de Decimal(valor) directo evita además la imprecisión
        # binaria de construir un Decimal desde un float (Decimal(45.1) ->
        # 45.09999999999999857891452847979962825775146484375).
        try:
            return decimal.Decimal(str(valor))
        except decimal.InvalidOperation:
            return decimal.Decimal(str(float(valor)))
    if tipo_campo in ("IntegerField", "PositiveIntegerField", "PositiveSmallIntegerField",
                      "SmallIntegerField", "BigIntegerField"):
        return int(float(valor))
    if tipo_campo in ("DateField", "DateTimeField"):
        ts = pd.to_datetime(valor)
        return ts.date() if tipo_campo == "DateField" else ts.to_pydatetime()
    if tipo_campo == "TimeField":
        return pd.to_datetime(valor).time()
    if tipo_campo == "BooleanField":
        if isinstance(valor, bool):
            return valor
        return str(valor).strip().lower() in ("1", "true", "verdadero", "si", "sí", "x")
    return valor


_PREVIEW_MAX_POR_MODELO = 200


def _representar_kwargs(kwargs):
    """Convierte los kwargs de creación de una instancia (que pueden incluir
    otras instancias de modelo como valores de FK) en algo serializable y
    legible para mostrar en la tabla de vista previa."""
    out = {}
    for k, v in kwargs.items():
        if hasattr(v, "pk"):
            out[k] = str(v)
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# Campos que identifican de forma real a una fila de este modelo (más allá de
# un OneToOneField), para usar en update_or_create en vez de que
# get_or_create(**kwargs) use TODOS los campos mapeados como filtro -y
# fragmente en duplicados apenas se mapee/agregue un campo nuevo, o se
# rompa con "get() returned more than one" si varias filas ya comparten esos
# valores por coincidencia-. Solo se usa cuando la fila trae valor real en
# TODOS estos campos (ver el uso más abajo); si falta alguno, no hay forma
# confiable de identificarla y se trata como en _MODELOS_EVENTO.
_CAMPOS_IDENTIDAD = {
    "UnidadMuestreo": ("nombre", "tipo", "unidad_experimental"),
    # Mismo criterio que el UniqueConstraint de MuestraAmbiental en el
    # modelo: identifica una lectura real solo si trae fecha Y hora (hora
    # casi nunca viene cargada hoy, así que la mayoría de las filas caen en
    # _MODELOS_EVENTO en vez de acá).
    "MuestraAmbiental": ("fecha", "hora", "fuente_datos"),
    # Sin esto, get_or_create(**kwargs) usa TODOS los campos mapeados de
    # Sitio como filtro: apenas una carga nueva mapea un campo que las
    # cargas anteriores no mapeaban (p. ej. tipo_localizacion, o ahora
    # Cobertura/Vegetacion/Disturbio vía Cobertura y Vegetación), deja de
    # matchear el Sitio ya existente y crea uno duplicado -pasó dos veces
    # en la práctica esta sesión (COS/Biomasa con tipo_localizacion), hubo
    # que fusionarlos a mano-. Va `nombre` + coordenadas, no solo
    # coordenadas: dos filas pueden compartir lat/lon pero representar el
    # mismo punto físico usado por unidades experimentales distintas (dos
    # "sitios" lógicos separados a propósito), así que las coordenadas
    # solas no alcanzan como identidad -decisión explícita, no asumir
    # fusión automática solo por coincidencia de coordenadas-.
    "Sitio": ("nombre", "latitud", "longitud"),
}

# Modelos "evento": cada fila del archivo es una medición real distinta, no
# un lugar/entidad que se busca y reutiliza (a diferencia de UnidadMuestreo,
# UnidadExperimental o Sitio). Se usa como respaldo de _CAMPOS_IDENTIDAD: si
# el modelo no tiene una identidad completa en esta fila, _procesar_filas lo
# crea siempre, sin get_or_create -ver el comentario donde se usa este set-.
# MuestraGEI/SubmuestraGEI no lo necesitaron (siempre tienen un `valor` que
# diferencia filas), pero MuestraMOM sí: la mayoría de sus columnas vienen
# vacías en la fuente real (solo carbono en hojarasca suele traer dato), así
# que varias filas de una misma UnidadMuestreo terminan con kwargs idénticos
# y get_or_create() revienta con "get() returned more than one".
_MODELOS_EVENTO = {"MuestraAmbiental", "MuestraMOM"}


def _clave_cache_objeto(modelo, campos):
    """Clave hasheable para `cache_objetos` a partir de los kwargs de
    lookup de un get_or_create — los valores de FK ya son instancias de
    modelo (hasheables por su pk una vez guardadas). None si algún valor no
    es hasheable (no debería pasar para los campos escalares/FK que arma
    _procesar_filas, pero mejor no cachear que reventar)."""
    try:
        return (modelo, tuple(sorted(campos.items())))
    except TypeError:
        return None


def _clave_identidad(campos_clave):
    """Clave hasheable y comparable para un dict campo->valor de identidad
    (campos_clave de update_or_create): los FK quedan representados por su
    pk, así una instancia recién traída de la BD y una instancia ya resuelta
    en memoria para la misma fila producen la MISMA clave."""
    return tuple(
        (nombre, valor.pk if hasattr(valor, "pk") else valor)
        for nombre, valor in sorted(campos_clave.items())
    )


def _clave_identidad_obj(modelo_cls, campos, obj):
    """Igual que _clave_identidad pero leyendo los valores de una instancia
    ya guardada en la BD (usa "<campo>_id" en FK para no disparar una
    consulta adicional por objeto)."""
    valores = {}
    for campo in campos:
        field = modelo_cls._meta.get_field(campo)
        valores[campo] = getattr(obj, f"{campo}_id") if _es_fk(field) else getattr(obj, campo)
    return tuple(sorted(valores.items()))


def _buscar_existentes_por_identidad(modelo_cls, campos_clave_por_fila):
    """Trae en UNA sola consulta todos los objetos que ya existan con
    alguna de las identidades en `campos_clave_por_fila` (lista de dicts
    campo->valor, todos con el mismo conjunto de claves) — reemplaza el
    round-trip por fila que hacía update_or_create() cuando se llamaba una
    vez por cada una de las 346 filas del archivo. Devuelve un dict
    clave_identidad -> objeto (mismo formato que _clave_identidad)."""
    if not campos_clave_por_fila:
        return {}
    campos = list(campos_clave_por_fila[0])

    vistos = set()
    unicos = []
    for campos_clave in campos_clave_por_fila:
        h = _clave_identidad(campos_clave)
        if h in vistos:
            continue
        vistos.add(h)
        unicos.append(campos_clave)

    if len(campos) == 1:
        campo = campos[0]
        queryset = modelo_cls.objects.filter(**{f"{campo}__in": [c[campo] for c in unicos]})
    else:
        condicion = models.Q(**unicos[0])
        for campos_clave in unicos[1:]:
            condicion |= models.Q(**campos_clave)
        queryset = modelo_cls.objects.filter(condicion)

    return {_clave_identidad_obj(modelo_cls, campos, obj): obj for obj in queryset}


def _campos_clave_de_fila(modelo, modelo_cls, kwargs):
    """Mismo criterio de antes para decidir si una fila tiene identidad
    propia: primero un OneToOneField (p. ej. Parcela -> unidad_muestreo), y
    si no hay, los campos de _CAMPOS_IDENTIDAD -solo si la fila trae TODOS
    esos campos con valor real-."""
    campos_clave = {
        nombre: valor
        for nombre, valor in kwargs.items()
        if type(modelo_cls._meta.get_field(nombre)).__name__ == "OneToOneField"
    }
    if not campos_clave and modelo in _CAMPOS_IDENTIDAD:
        identidad = _CAMPOS_IDENTIDAD[modelo]
        if all(kwargs.get(c) is not None for c in identidad):
            campos_clave = {c: kwargs[c] for c in identidad}
    return campos_clave


def _armar_kwargs_modelo_fila(df, fila_idx, mapeos, modelo_cls, resueltos, cache_fk):
    """Arma los kwargs de una fila para un modelo a partir de sus mapeos:
    resuelve transformaciones/constantes, FKs (por pk mapeado explícitamente
    o auto-vinculados a otro modelo ya resuelto en esta misma fila) y
    coerciona tipos. Devuelve None si a la fila le falta algún valor
    requerido (columna vacía en un campo obligatorio, "ignorar_fila", FK que
    no resuelve, etc.) o si no queda ningún campo. Extraído de la Fase 1 de
    `_procesar_filas` para reutilizarlo también en `_procesar_fila_gei_flujo`."""
    kwargs = {}
    incompleto = False

    for mapeo in mapeos:
        field = modelo_cls._meta.get_field(mapeo.campo_destino)

        if mapeo.transformacion == "constante":
            valor = None if _es_vacio(mapeo.valor_constante) else mapeo.valor_constante
        else:
            val_crudo = df[mapeo.columna_origen].iloc[fila_idx]
            try:
                valor = _resolver_valor_columna(val_crudo, mapeo)
            except ValueError:
                incompleto = True
                continue

        if valor is None:
            # "ignorar_fila": el usuario decidió explícitamente no crear el
            # registro de este modelo cuando esta columna viene vacía, sin
            # importar si el campo admite nulos.
            if mapeo.estrategia_nulos == "ignorar_fila" or not (
                getattr(field, "blank", True) or getattr(field, "null", True)
            ):
                incompleto = True
            continue

        if _es_fk(field):
            fk_modelo = field.related_model.__name__
            if fila_idx in resueltos.get(fk_modelo, {}):
                kwargs[mapeo.campo_destino] = resueltos[fk_modelo][fila_idx]
            else:
                # Resolución por pk memoizada: a diferencia del FK
                # auto-vinculado de arriba (que varía por fila), esto es un
                # .get(pk=valor) de solo lectura -mismo pk siempre da el
                # mismo objeto-, así que cachearlo es seguro incluso si
                # "valor" se repite en muchas filas (p. ej. un atributo
                # constante, o una columna con pocos valores distintos como
                # "tipo"): sin esto, se repetía la misma consulta una vez
                # por fila.
                clave_fk = (fk_modelo, valor)
                if clave_fk in cache_fk:
                    kwargs[mapeo.campo_destino] = cache_fk[clave_fk]
                else:
                    try:
                        obj_fk = field.related_model.objects.get(pk=valor)
                    except (field.related_model.DoesNotExist, ValueError, TypeError):
                        incompleto = True
                    else:
                        cache_fk[clave_fk] = obj_fk
                        kwargs[mapeo.campo_destino] = obj_fk
        else:
            try:
                kwargs[mapeo.campo_destino] = _coercionar_valor(valor, field)
            except (ValueError, TypeError):
                incompleto = True

    # Vincular automáticamente los FK hacia otros modelos ya resueltos para
    # esta misma fila, aunque el usuario no haya mapeado esa columna
    # explícitamente (p. ej. Parcela se asocia solo a la UnidadMuestreo de
    # su misma fila).
    for field in modelo_cls._meta.get_fields():
        if not _es_fk(field) or field.name in kwargs:
            continue
        fk_modelo = field.related_model.__name__
        if fila_idx in resueltos.get(fk_modelo, {}):
            kwargs[field.name] = resueltos[fk_modelo][fila_idx]

    if incompleto or not kwargs:
        return None
    return kwargs


def _resolver_get_or_create(modelo_cls, nombre_modelo, campos, cache_objetos):
    """get_or_create con memoización en `cache_objetos` y el mismo fallback
    de MultipleObjectsReturned que usa la rama "genérico" de _procesar_filas
    -filtro parcial que matchea más de un objeto existente: se usa cualquiera
    de los que ya matchean en vez de romper la carga entera-. Devuelve
    (obj, creado)."""
    clave = _clave_cache_objeto(nombre_modelo, campos)
    if clave is not None and clave in cache_objetos:
        return cache_objetos[clave], False
    try:
        obj, creado = modelo_cls.objects.get_or_create(**campos)
    except modelo_cls.MultipleObjectsReturned:
        obj = modelo_cls.objects.filter(**campos).first()
        creado = False
    if clave is not None:
        cache_objetos[clave] = obj
    return obj, creado


def _procesar_fila_gei_flujo(
    df, fila_idx, mapeos_muestra_gei, mapeos_submuestra_resto, mapeos_valor_fijo,
    resueltos, cache_fk, resumen_modelos, pks_por_modelo, detalle, cache_objetos,
):
    """Resuelve MuestraGEI+SubmuestraGEI para una fila cuando el archivo trae
    el flujo de cada gas en su propia columna (formato ancho): a diferencia
    del camino normal (que fusiona todos los mapeos de un modelo en un único
    kwargs, formato largo con columna 'gas' + columna 'valor'), acá cada
    MapeoColumna en `mapeos_valor_fijo` (campo_destino='valor' con gas_fijo)
    produce su PROPIO par MuestraGEI/SubmuestraGEI, etiquetado con el gas fijo
    de ese mapeo. Si a la fila le falta el valor de un gas, ese gas se salta
    sin afectar a los demás."""
    MuestraGEI = apps.get_model("app", "MuestraGEI")
    SubmuestraGEI = apps.get_model("app", "SubmuestraGEI")

    kwargs_base_muestra = _armar_kwargs_modelo_fila(
        df, fila_idx, mapeos_muestra_gei, MuestraGEI, resueltos, cache_fk
    )
    if kwargs_base_muestra is None:
        kwargs_base_muestra = {}
    kwargs_base_submuestra = _armar_kwargs_modelo_fila(
        df, fila_idx, mapeos_submuestra_resto, SubmuestraGEI, resueltos, cache_fk
    )
    if kwargs_base_submuestra is None:
        kwargs_base_submuestra = {}

    for mapeo in mapeos_valor_fijo:
        if mapeo.transformacion == "constante":
            valor = None if _es_vacio(mapeo.valor_constante) else mapeo.valor_constante
        else:
            val_crudo = df[mapeo.columna_origen].iloc[fila_idx]
            try:
                valor = _resolver_valor_columna(val_crudo, mapeo)
            except ValueError:
                continue
        if _es_vacio(valor):
            continue
        try:
            valor = _coercionar_valor(valor, SubmuestraGEI._meta.get_field("valor"))
        except (ValueError, TypeError):
            continue

        campos_muestra = {**kwargs_base_muestra, "gas": mapeo.gas_fijo}
        obj_muestra, creado_muestra = _resolver_get_or_create(
            MuestraGEI, "MuestraGEI", campos_muestra, cache_objetos
        )
        resumen_modelos["MuestraGEI"]["creados" if creado_muestra else "reutilizados"] += 1
        pks_por_modelo.setdefault("MuestraGEI", set()).add(obj_muestra.pk)

        campos_submuestra = {**kwargs_base_submuestra, "valor": valor, "muestra": obj_muestra}
        obj_submuestra, creado_submuestra = _resolver_get_or_create(
            SubmuestraGEI, "SubmuestraGEI", campos_submuestra, cache_objetos
        )
        resumen_modelos["SubmuestraGEI"]["creados" if creado_submuestra else "reutilizados"] += 1
        pks_por_modelo.setdefault("SubmuestraGEI", set()).add(obj_submuestra.pk)

        if detalle is not None:
            for nombre_modelo, obj, creado, campos in (
                ("MuestraGEI", obj_muestra, creado_muestra, campos_muestra),
                ("SubmuestraGEI", obj_submuestra, creado_submuestra, campos_submuestra),
            ):
                bucket = detalle.setdefault(nombre_modelo, {})
                if obj.pk not in bucket and len(bucket) < _PREVIEW_MAX_POR_MODELO:
                    bucket[obj.pk] = {
                        "accion": "creado" if creado else "reutilizado",
                        "campos": _representar_kwargs(campos),
                    }


def _procesar_fila_cobertura(df, fila_idx, mapeos, sitio, resumen_modelos, pks_por_modelo, detalle, cache_objetos):
    """Resuelve los mapeos de Cobertura para una fila: a diferencia de
    _procesar_filas (que fusiona todos los mapeos de un modelo en un único
    kwargs), acá cada MapeoColumna con campo_destino="nombre" produce su
    propia fila de Cobertura, etiquetada con el `tipo_cobertura` fijo de ese
    mapeo (ver comentario en MapeoColumna.tipo_cobertura). `sitio` siempre es
    el Sitio ya resuelto para esta misma fila -no se mapea manualmente,
    mismo criterio que Parcela -> UnidadMuestreo-."""
    Cobertura = apps.get_model("app", "Cobertura")

    if sitio is None:
        return

    for mapeo in mapeos:
        if mapeo.campo_destino != "nombre":
            continue

        if mapeo.transformacion == "constante":
            valor = None if _es_vacio(mapeo.valor_constante) else mapeo.valor_constante
        else:
            val_crudo = df[mapeo.columna_origen].iloc[fila_idx]
            try:
                valor = _resolver_valor_columna(val_crudo, mapeo)
            except ValueError:
                continue

        if _es_vacio(valor):
            continue

        campos_cobertura = {"sitio": sitio, "tipo": mapeo.tipo_cobertura, "nombre": str(valor)}
        clave = _clave_cache_objeto("Cobertura", campos_cobertura)
        if clave is not None and clave in cache_objetos:
            obj, creado = cache_objetos[clave], False
        else:
            obj, creado = Cobertura.objects.get_or_create(**campos_cobertura)
            if clave is not None:
                cache_objetos[clave] = obj
        resumen_modelos["Cobertura"]["creados" if creado else "reutilizados"] += 1
        pks_por_modelo.setdefault("Cobertura", set()).add(obj.pk)

        if detalle is not None:
            bucket = detalle.setdefault("Cobertura", {})
            if obj.pk not in bucket and len(bucket) < _PREVIEW_MAX_POR_MODELO:
                bucket[obj.pk] = {
                    "accion": "creado" if creado else "reutilizado",
                    "campos": _representar_kwargs({
                        "sitio": sitio, "tipo": mapeo.tipo_cobertura, "nombre": valor,
                    }),
                }


def _procesar_filas(df, orden, mapeos_por_modelo, carga, resumen_modelos, capturar_detalle=False):
    """Recorre cada modelo en `orden` (uno a la vez, sobre TODAS las filas) y
    crea/reutiliza sus instancias en lote, vinculando por FK las que ya se
    resolvieron para modelos anteriores en la misma fila. Se usa tanto para
    importar de verdad como, dentro de una transacción que se revierte, para
    la vista previa (capturar_detalle=True) sin escribir nada permanente.

    Antes esto procesaba fila por fila (para cada fila, para cada modelo):
    para modelos con identidad propia (UnidadMuestreo, Sitio, MuestraAmbiental,
    Parcela/Transecto vía OneToOne) eso significaba un update_or_create -varios
    round-trips- POR FILA. Con una base remota, 346 filas únicas (sin nada que
    memoizar, a diferencia de UnidadExperimental que se repite entre filas)
    superaban el timeout de gunicorn y mataban el worker a mitad de
    transacción. Ahora se recorre modelo por modelo: primero se arman los
    kwargs de TODAS las filas de ese modelo (sin tocar la BD, salvo resolver
    por pk un FK mapeado explícitamente a una columna), luego UNA consulta
    trae los que ya existen, y UN bulk_create/bulk_update escribe el resto.
    El orden topológico (`orden`) sigue garantizando que un modelo se procesa
    después de aquellos a los que referencia por FK, así que sus instancias
    ya están resueltas (con pk real) cuando se necesitan."""
    detalle = {} if capturar_detalle else None
    # A diferencia de `detalle` (limitado a _PREVIEW_MAX_POR_MODELO para la
    # UI de vista previa), esto guarda TODOS los pk tocados por esta corrida,
    # sin límite, para poder filtrar después "solo lo de esta carga".
    pks_por_modelo = {}
    # Memoiza get_or_create() de esta corrida para el branch "genérico" (ver
    # más abajo): filas repetidas con los mismos valores (p. ej. el mismo
    # TipoCobertura en muchas filas) no necesitan un round-trip a la BD cada
    # una. No se usa para _MODELOS_EVENTO (cada fila es una medición real
    # distinta a propósito) ni para los modelos con identidad propia (donde
    # "última fila gana" sobre los demás campos y cachear cambiaría ese
    # comportamiento) -esos dos casos ahora van en lote, ver abajo-.
    cache_objetos = {}
    # Memoiza la resolución de FK por pk (ver más abajo, en Fase 1) — de
    # solo lectura, así que es seguro compartirla entre modelos.
    cache_fk = {}
    total_filas = len(df)
    # resueltos[modelo][fila_idx] = instancia ya creada/reutilizada para esa
    # fila y ese modelo -reemplaza a instancias_fila de la versión anterior
    # (que solo vivía durante una fila): acá vive durante todo el paso por
    # ese modelo, porque ahora se procesa un modelo a la vez, no una fila a
    # la vez-.
    resueltos = {modelo: {} for modelo in orden}

    for modelo in orden:
        modelo_cls = apps.get_model("app", modelo)
        mapeos = mapeos_por_modelo.get(modelo, [])

        # Caso especial: a diferencia del resto de los modelos, una fila de
        # origen puede traer varias columnas de Cobertura (CLC, IPCC, IGBP,
        # Köppen, nombre local, Suelo IPCC), y cada una se vuelve una fila de
        # Cobertura DISTINTA -no se fusionan en una sola instancia como el
        # resto de este loop-, todas ligadas al Sitio de esa misma fila. Se
        # deja fila por fila (ya memoizado vía cache_objetos, y Cobertura no
        # suele ser el cuello de botella).
        if modelo == "Cobertura":
            for fila_idx in range(total_filas):
                _procesar_fila_cobertura(
                    df, fila_idx, mapeos, resueltos.get("Sitio", {}).get(fila_idx),
                    resumen_modelos, pks_por_modelo, detalle, cache_objetos,
                )
            continue

        # Caso especial: archivo en formato ancho (el flujo de cada gas en su
        # propia columna, ver MapeoColumna.gas_fijo) en vez de una columna
        # 'gas' + una columna 'valor'. Cada columna con gas_fijo produce su
        # propio par MuestraGEI/SubmuestraGEI por fila -no se puede fusionar
        # en el único kwargs por fila que arma el resto de este loop-.
        mapeos_valor_fijo = [
            m for m in mapeos_por_modelo.get("SubmuestraGEI", [])
            if m.campo_destino == "valor" and m.gas_fijo
        ]
        if modelo == "MuestraGEI" and mapeos_valor_fijo:
            # Se arma dentro del branch de SubmuestraGEI de abajo, uno por gas.
            continue
        if modelo == "SubmuestraGEI" and mapeos_valor_fijo:
            mapeos_resto = [m for m in mapeos if m not in mapeos_valor_fijo]
            for fila_idx in range(total_filas):
                _procesar_fila_gei_flujo(
                    df, fila_idx, mapeos_por_modelo.get("MuestraGEI", []),
                    mapeos_resto, mapeos_valor_fijo, resueltos, cache_fk,
                    resumen_modelos, pks_por_modelo, detalle, cache_objetos,
                )
            continue

        # Fase 1: arma los kwargs de cada fila sin tocar la BD -salvo
        # resolver por pk un FK mapeado explícitamente a una columna, que
        # sigue siendo por fila porque el pk viene del archivo, no de algo
        # que ya calculamos-.
        filas_kwargs = {}
        for fila_idx in range(total_filas):
            kwargs = _armar_kwargs_modelo_fila(df, fila_idx, mapeos, modelo_cls, resueltos, cache_fk)
            if kwargs is None:
                continue

            if modelo == "UnidadMuestreo":
                kwargs.setdefault("fuente_datos", carga.fuente)

            if modelo == "UnidadExperimental":
                kwargs.setdefault("proyecto", carga.fuente.proyecto)

            if modelo == "MuestraAmbiental":
                kwargs.setdefault("fuente_datos", carga.fuente)

            filas_kwargs[fila_idx] = kwargs

        if not filas_kwargs:
            continue

        # Fase 2: agrupa las filas por el tipo de escritura que necesitan
        # -mismo criterio que antes, solo que ahora se ejecuta en lote por
        # grupo en vez de una vez por fila-.
        grupos_identidad = {}
        filas_evento = []
        filas_generico = []
        for fila_idx, kwargs in filas_kwargs.items():
            campos_clave = _campos_clave_de_fila(modelo, modelo_cls, kwargs)
            if campos_clave:
                defaults = {k: v for k, v in kwargs.items() if k not in campos_clave}
                grupos_identidad.setdefault(frozenset(campos_clave), []).append((fila_idx, campos_clave, defaults))
            elif modelo in _MODELOS_EVENTO:
                # A diferencia de UnidadMuestreo/UnidadExperimental/Sitio
                # (lugares que se reutilizan entre filas y cargas), cada fila
                # de un modelo "evento" es una medición real distinta -dos
                # lecturas pueden compartir todos sus valores mapeados sin
                # ser la misma-. Sin una identidad completa (ver arriba),
                # buscar "si ya existe" puede fusionar lecturas distintas por
                # coincidencia. Se crea siempre una fila nueva; si se re-sube
                # el mismo archivo dos veces, se duplican las lecturas que no
                # tengan la identidad completa (fecha+hora acá), igual que no
                # las protege el UniqueConstraint en BD.
                filas_evento.append((fila_idx, kwargs))
            else:
                filas_generico.append((fila_idx, kwargs))

        accion_por_fila = {}

        # --- Identidad propia / OneToOne: update_or_create en lote ---
        for filas in grupos_identidad.values():
            existentes = _buscar_existentes_por_identidad(modelo_cls, [c for _, c, _ in filas])
            pendientes_nuevos = {}
            a_actualizar = {}
            campos_actualizar = set()

            for fila_idx, campos_clave, defaults in filas:
                clave_hash = _clave_identidad(campos_clave)
                obj_existente = existentes.get(clave_hash)
                if obj_existente is not None:
                    for k, v in defaults.items():
                        setattr(obj_existente, k, v)
                    campos_actualizar.update(defaults.keys())
                    a_actualizar[obj_existente.pk] = obj_existente
                    resueltos[modelo][fila_idx] = obj_existente
                    accion_por_fila[fila_idx] = "reutilizados"
                    continue

                obj = pendientes_nuevos.get(clave_hash)
                if obj is None:
                    obj = modelo_cls(**campos_clave, **defaults)
                    pendientes_nuevos[clave_hash] = obj
                    accion_por_fila[fila_idx] = "creados"
                else:
                    # Dos filas de este archivo apuntan a la misma identidad
                    # que todavía no existe en la BD: mismo criterio de
                    # "última fila gana" que antes tenía update_or_create
                    # fila por fila.
                    for k, v in defaults.items():
                        setattr(obj, k, v)
                    accion_por_fila[fila_idx] = "reutilizados"
                resueltos[modelo][fila_idx] = obj

            if pendientes_nuevos:
                modelo_cls.objects.bulk_create(list(pendientes_nuevos.values()))
            if a_actualizar and campos_actualizar:
                modelo_cls.objects.bulk_update(list(a_actualizar.values()), list(campos_actualizar))

        # --- Evento: create en lote ---
        if filas_evento:
            instancias = [modelo_cls(**kwargs) for _, kwargs in filas_evento]
            modelo_cls.objects.bulk_create(instancias)
            for (fila_idx, _kwargs), obj in zip(filas_evento, instancias):
                resueltos[modelo][fila_idx] = obj
                accion_por_fila[fila_idx] = "creados"

        # --- Genérico (modelos "perfil" sin identidad propia, p. ej.
        # Disturbio/Vegetación): get_or_create con memoización, sin cambios
        # de fondo -no es el cuello de botella, y el manejo de
        # MultipleObjectsReturned (filtro parcial que matchea más de uno) es
        # más simple de mantener fila por fila-.
        for fila_idx, kwargs in filas_generico:
            clave = _clave_cache_objeto(modelo, kwargs)
            if clave is not None and clave in cache_objetos:
                obj, creado = cache_objetos[clave], False
            else:
                try:
                    obj, creado = modelo_cls.objects.get_or_create(**kwargs)
                except modelo_cls.MultipleObjectsReturned:
                    # kwargs es un subconjunto parcial de los campos del
                    # modelo (los que esta fila trae con valor real): si dos
                    # filas distintas ya crearon variantes que coinciden en
                    # ese subconjunto pero difieren en un campo que esta fila
                    # no trae, el filtro parcial matchea a más de uno. No hay
                    # forma de saber cuál es "el correcto" con la información
                    # de esta fila, así que se toma cualquiera de los que ya
                    # matchean en vez de romper la carga entera.
                    obj = modelo_cls.objects.filter(**kwargs).first()
                    creado = False
                if clave is not None:
                    cache_objetos[clave] = obj
            resueltos[modelo][fila_idx] = obj
            accion_por_fila[fila_idx] = "creados" if creado else "reutilizados"

        for fila_idx, accion in accion_por_fila.items():
            resumen_modelos[modelo][accion] += 1

        for obj in resueltos[modelo].values():
            pks_por_modelo.setdefault(modelo, set()).add(obj.pk)

        if detalle is not None:
            bucket = detalle.setdefault(modelo, {})
            for fila_idx in sorted(resueltos[modelo]):
                if len(bucket) >= _PREVIEW_MAX_POR_MODELO:
                    break
                obj = resueltos[modelo][fila_idx]
                if obj.pk in bucket:
                    continue
                bucket[obj.pk] = {
                    "accion": "creado" if accion_por_fila[fila_idx] == "creados" else "reutilizado",
                    "campos": _representar_kwargs(filas_kwargs[fila_idx]),
                }

    return detalle, pks_por_modelo


def _preparar_importacion(carga, hasta_grupo_solicitado):
    """Validaciones y datos comunes a importar_carga y previsualizar_carga:
    resuelve `hasta_grupo`, arma los mapeos de la sección y valida el archivo.
    Devuelve (mapeos, hasta_grupo, grupo_maximo, error_response) — si hay
    error, todo lo demás es None y `error_response` ya es el JsonResponse a
    devolver tal cual."""
    todos_mapeos = list(carga.mapeos.exclude(modelo_destino=""))
    if not todos_mapeos:
        return None, None, None, JsonResponse({"error": "La carga no tiene mapeos definidos."}, status=400)

    grupo_maximo = max(_grupo_de_modelo(m.modelo_destino) for m in todos_mapeos)
    hasta_grupo = hasta_grupo_solicitado if hasta_grupo_solicitado is not None else grupo_maximo
    try:
        hasta_grupo = int(hasta_grupo)
    except (TypeError, ValueError):
        return None, None, None, JsonResponse({"error": "hasta_grupo inválido"}, status=400)

    mapeos = [m for m in todos_mapeos if _grupo_de_modelo(m.modelo_destino) <= hasta_grupo]
    if not mapeos:
        return None, None, None, JsonResponse({"error": "No hay mapeos para esta sección."}, status=400)

    return mapeos, hasta_grupo, grupo_maximo, None


def _validar_seccion(carga, df, mapeos):
    """Corre todas las validaciones (por columna + reglas de negocio) sobre
    el subconjunto `mapeos` de esta sección -ya acotado a UNA hoja por el
    llamador (`_leer_y_validar_multihoja`), así que `df` y `mapeos` siempre
    se corresponden entre sí-. Devuelve (resultados, total_errores,
    filas_con_error)."""
    resultados = []
    filas_con_error = set()
    for mapeo in mapeos:
        if mapeo.transformacion == "constante":
            resultado = _validar_constante(mapeo, len(df))
        else:
            resultado = _validar_columna(df, mapeo)
        if "advertencia" not in resultado:
            for e in resultado["errores"]:
                filas_con_error.add(e["fila"])
        resultados.append(resultado)

    resultado_ue = _validar_unicidad_unidad_experimental(carga, df, mapeos)
    if resultado_ue is not None:
        for e in resultado_ue["errores"]:
            filas_con_error.add(e["fila"])
        resultados.append(resultado_ue)

    modelos_incluidos = {m.modelo_destino for m in mapeos}
    resultado_ue_obl = _validar_obligatorios_unidad_experimental(mapeos, modelos_incluidos, len(df))
    if resultado_ue_obl is not None:
        for e in resultado_ue_obl["errores"]:
            filas_con_error.add(e["fila"])
        resultados.append(resultado_ue_obl)

    resultado_um = _validar_obligatorios_unidad_muestreo(mapeos, modelos_incluidos, len(df))
    if resultado_um is not None:
        for e in resultado_um["errores"]:
            filas_con_error.add(e["fila"])
        resultados.append(resultado_um)

    total_errores = sum(len(r["errores"]) for r in resultados if "advertencia" not in r)
    return resultados, total_errores, filas_con_error


def _leer_y_validar_multihoja(carga, mapeos):
    """Agrupa `mapeos` (de una sección, potencialmente de varias hojas) por
    `hoja`, corre `_validar_seccion` por cada una con su propio DataFrame, y
    fusiona los resultados. Devuelve (resultados, total_errores,
    total_filas_combinado, filas_con_error_combinado, dfs_por_hoja)
    -`dfs_por_hoja` se reutiliza después al importar, para no releer-."""
    resultados = []
    total_errores = 0
    total_filas_combinado = 0
    filas_con_error_combinado = 0
    dfs_por_hoja = {}
    for hoja in sorted({m.hoja for m in mapeos}):
        mapeos_hoja = [m for m in mapeos if m.hoja == hoja]
        df = _leer_dataframe_carga(carga, hoja)
        _aplicar_estrategia_nulos(df, mapeos_hoja)
        dfs_por_hoja[hoja] = df

        resultados_hoja, errores_hoja, filas_hoja = _validar_seccion(carga, df, mapeos_hoja)
        resultados.extend(resultados_hoja)
        total_errores += errores_hoja
        total_filas_combinado += len(df)
        filas_con_error_combinado += len(filas_hoja)

    return resultados, total_errores, total_filas_combinado, filas_con_error_combinado, dfs_por_hoja


def _procesar_filas_multihoja(carga, mapeos, orden, resumen_modelos, dfs_por_hoja, capturar_detalle=False):
    """Como `_procesar_filas`, pero corriendo una vez por cada hoja presente
    en `mapeos` (con su propio DataFrame) y fusionando detalle/pks — una
    misma sección puede tener columnas mapeadas desde más de una hoja."""
    detalle_combinado = {} if capturar_detalle else None
    pks_combinado = {}
    for hoja in sorted({m.hoja for m in mapeos}):
        mapeos_hoja = [m for m in mapeos if m.hoja == hoja]
        modelos_hoja = {m.modelo_destino for m in mapeos_hoja}
        orden_hoja = [modelo for modelo in orden if modelo in modelos_hoja]
        mapeos_por_modelo_hoja = {}
        for m in mapeos_hoja:
            mapeos_por_modelo_hoja.setdefault(m.modelo_destino, []).append(m)

        detalle_hoja, pks_hoja = _procesar_filas(
            dfs_por_hoja[hoja], orden_hoja, mapeos_por_modelo_hoja, carga, resumen_modelos, capturar_detalle,
        )
        if detalle_hoja:
            for modelo, bucket in detalle_hoja.items():
                detalle_combinado.setdefault(modelo, {}).update(bucket)
        for modelo, pks in pks_hoja.items():
            pks_combinado.setdefault(modelo, set()).update(pks)

    return detalle_combinado, pks_combinado


@csrf_exempt
@requiere_nivel("reportador")
def previsualizar_carga(request, fuente_id, carga_id):
    """Simula la importación de esta sección (mismo orden de creación/vínculo
    por FK que importar_carga) sin escribir nada permanente en la base, para
    mostrar en el wizard qué se va a crear/reutilizar y con qué referencias
    antes de confirmar el guardado."""
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        carga = CargaArchivo.objects.get(pk=carga_id, fuente_id=fuente_id)
    except CargaArchivo.DoesNotExist:
        return JsonResponse({"error": "Carga no encontrada"}, status=404)

    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    mapeos, hasta_grupo, grupo_maximo, error_response = _preparar_importacion(carga, body.get("hasta_grupo"))
    if error_response is not None:
        return error_response

    try:
        resultados, total_errores, total_filas, filas_con_error, dfs_por_hoja = _leer_y_validar_multihoja(carga, mapeos)
        if total_errores > 0:
            return JsonResponse({
                "ok": False,
                "resumen": {
                    "total_filas": total_filas,
                    "columnas_mapeadas": len(mapeos),
                    "total_errores": total_errores,
                    "filas_limpias": total_filas - filas_con_error,
                    "filas_con_errores": filas_con_error,
                },
                "columnas": resultados,
            }, status=400, json_dumps_params={"ensure_ascii": False})

        modelos_incluidos = sorted({m.modelo_destino for m in mapeos})
        orden = _orden_topologico(modelos_incluidos)

        resumen_modelos = {m: {"creados": 0, "reutilizados": 0} for m in modelos_incluidos}

        with transaction.atomic():
            sid = transaction.savepoint()
            detalle, _pks = _procesar_filas_multihoja(
                carga, mapeos, orden, resumen_modelos, dfs_por_hoja, capturar_detalle=True,
            )
            transaction.savepoint_rollback(sid)

        modelos_preview = {
            modelo: {
                "registros": list(bucket.values()),
                "total": resumen_modelos[modelo]["creados"] + resumen_modelos[modelo]["reutilizados"],
                # Conteo real (sobre TODAS las filas, no solo las de la
                # muestra de `bucket`, que está recortada a
                # _PREVIEW_MAX_POR_MODELO para no mandar miles de filas al
                # navegador). El frontend debe mostrar estos, no derivarlos
                # de `registros` — con archivos grandes, la muestra recortada
                # no representa la proporción real de nuevos/reutilizados.
                "creados": resumen_modelos[modelo]["creados"],
                "reutilizados": resumen_modelos[modelo]["reutilizados"],
                "truncado": (resumen_modelos[modelo]["creados"] + resumen_modelos[modelo]["reutilizados"]) > len(bucket),
            }
            for modelo, bucket in (detalle or {}).items()
        }

        return JsonResponse({
            "ok": True,
            "hasta_grupo": hasta_grupo,
            "completo": hasta_grupo >= grupo_maximo,
            "modelos": resumen_modelos,
            "detalle": modelos_preview,
        }, json_dumps_params={"ensure_ascii": False})

    except (ValueError, FileNotFoundError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
@requiere_nivel("reportador")
def importar_carga(request, fuente_id, carga_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        carga = CargaArchivo.objects.get(pk=carga_id, fuente_id=fuente_id)
    except CargaArchivo.DoesNotExist:
        return JsonResponse({"error": "Carga no encontrada"}, status=404)

    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    mapeos, hasta_grupo, grupo_maximo, error_response = _preparar_importacion(carga, body.get("hasta_grupo"))
    if error_response is not None:
        return error_response

    if carga.estado == "importado" or carga.fuente.estado == "completo":
        # La carga (o la fuente, si esto es una carga nueva creada para
        # corregir una fuente ya completa -ver upload_archivo, que copia los
        # mapeos previos-) ya se importó por completo. Es seguro reprocesar
        # los modelos con identidad propia
        # (UnidadExperimental, UnidadMuestreo, Sitio, Parcela/Transecto,
        # etc.): _procesar_filas los reutiliza por su clave y sobreescribe
        # los campos recién mapeados en el registro existente, no crea
        # duplicados. Los modelos "evento" (_MODELOS_EVENTO) sí duplicarían
        # una medición por cada corrida, así que esos quedan bloqueados acá.
        modelos_solicitados = {m.modelo_destino for m in mapeos}
        modelos_evento_incluidos = modelos_solicitados & _MODELOS_EVENTO
        if modelos_evento_incluidos:
            return JsonResponse({
                "error": (
                    "Esta carga ya fue importada. No se pueden registrar ahora columnas que "
                    f"generen nuevas mediciones ({', '.join(sorted(modelos_evento_incluidos))}) porque "
                    "duplicarían las que ya existen; solo se pueden completar campos de entidades "
                    "como Sitio, Unidad de Muestreo o Unidad Experimental."
                ),
            }, status=409)

    try:
        # 1) Validar solo el subconjunto de mapeos de esta sección (por cada
        # hoja involucrada); no se escribe nada en la base si queda error.
        resultados, total_errores, total_filas, filas_con_error, dfs_por_hoja = _leer_y_validar_multihoja(carga, mapeos)
        if total_errores > 0:
            return JsonResponse({
                "ok": False,
                "resumen": {
                    "total_filas": total_filas,
                    "columnas_mapeadas": len(mapeos),
                    "total_errores": total_errores,
                    "filas_limpias": total_filas - filas_con_error,
                    "filas_con_errores": filas_con_error,
                },
                "columnas": resultados,
            }, status=400, json_dumps_params={"ensure_ascii": False})

        # 2) Importar: crear/reutilizar instancias, en orden de dependencia FK.
        modelos_incluidos = sorted({m.modelo_destino for m in mapeos})
        orden = _orden_topologico(modelos_incluidos)

        resumen_modelos = {m: {"creados": 0, "reutilizados": 0} for m in modelos_incluidos}

        with transaction.atomic():
            _, pks_por_modelo = _procesar_filas_multihoja(carga, mapeos, orden, resumen_modelos, dfs_por_hoja)

            # Acumula (no reemplaza) los pk tocados por esta sección con los de
            # secciones anteriores de la misma carga, para poder mostrar luego
            # "solo lo de esta carga" en el panel de visualización.
            acumulado = carga.pks_importados or {}
            for modelo, pks in pks_por_modelo.items():
                existentes = set(acumulado.get(modelo, []))
                acumulado[modelo] = sorted(existentes | pks)
            carga.pks_importados = acumulado

            campos_actualizar = ["pks_importados"]
            if hasta_grupo >= grupo_maximo:
                carga.estado = "importado"
                campos_actualizar.append("estado")
            carga.save(update_fields=campos_actualizar)

            if hasta_grupo >= grupo_maximo and carga.fuente.estado != "completo":
                carga.fuente.estado = "completo"
                carga.fuente.save(update_fields=["estado"])

        return JsonResponse({
            "ok": True,
            "hasta_grupo": hasta_grupo,
            "completo": hasta_grupo >= grupo_maximo,
            "modelos": resumen_modelos,
        }, json_dumps_params={"ensure_ascii": False})

    except (ValueError, FileNotFoundError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


# ── Panel de visualización: tabla desnormalizada de lo importado ───────────
# Cada "vista" define, para un modelo base, la cadena de FKs hacia arriba que
# se aplana en columnas prefijadas por modelo. Cada tupla de la cadena es
# (nombre_modelo, ruta_de_atributos_desde_el_modelo_base).
#
# "submuestra_gei" llega a UnidadMuestreo/UnidadExperimental/Sitio por el
# vínculo directo MuestraGEI.unidad_muestreo. "unidad_muestreo" es una vista
# aparte para cargas que todavía no tienen MuestraGEI/SubmuestraGEI
# importadas (solo unidad de muestreo/experimental).
#
# SubmuestraGEI ya no tiene un campo `unidad_medida` propio (todas sus tomas
# comparten la unidad reportada por la fuente para la muestra completa): el
# campo vive en MuestraGEI.unidad_medida (ver app/models/co2.py). TipoMuestra
# (equipo → gas → unidad habitual) es solo catálogo de referencia, no la
# fuente de este dato. `fecha` sí es propia de cada SubmuestraGEI (cada toma
# puede caer en un día distinto, p. ej. cobija nocturna cruzando medianoche).
# Compartido por las hojas de metodología (MOM, COS, Biomasa): unidad
# experimental, unidad muestral y coordenadas primero, como referencia para
# cruzar con la hoja "Unidad Muestreo-Experimental" (que ya trae el detalle
# completo del sitio y la unidad); acá solo se repiten esos datos de
# contexto, no todo Sitio/UnidadExperimental/Parcela — el resto de columnas
# de cada hoja es la medición propia de esa metodología.
_CAMPOS_METODOLOGIA = {
    "UnidadMuestreo": {"alias": {"nombre": "nombre unidad de muestreo"}},
    "UnidadExperimental": {"incluir": ["nombre"], "alias": {"nombre": "nombre unidad experimental"}},
    "Parcela": {"alias": {"descripcion": "descripción parcela"}},
    "Sitio": {"incluir": ["latitud", "longitud"]},
}
_ORDEN_COLUMNAS_METODOLOGIA = [
    "UnidadExperimental.nombre", "UnidadMuestreo.nombre", "Sitio.latitud", "Sitio.longitud",
]


_VISTAS_DESNORMALIZADAS = {
    "submuestra_gei": {
        "modelo_base": "SubmuestraGEI",
        "orden": ["fecha", "muestra_id", "n_toma"],
        "cadena": [
            ("UnidadExperimental", ["muestra", "unidad_muestreo", "unidad_experimental"]),
            ("Equipo", ["muestra", "analizador"]),
            ("UnidadMuestreo", ["muestra", "unidad_muestreo"]),
            ("SubmuestraGEI", []),
            ("MuestraGEI", ["muestra"]),
            ("UnidadMedida", ["muestra", "unidad_medida"]),
            ("Parcela", ["muestra", "unidad_muestreo", "parcela"]),
            ("Sitio", ["muestra", "unidad_muestreo", "sitio"]),
        ],
        # Parcela y Sitio quedan en la cadena (se necesitan para el
        # select_related y para el filtro por sitio_id del geoportal — ver
        # `ruta_sitio` en `_preparar_vista_pks`), pero esta hoja ya no
        # muestra su detalle: eso vive en la pestaña "Unidad
        # Muestreo-Experimental". Solo se dejan `UnidadMuestreo.nombre` y
        # `UnidadExperimental.nombre` al inicio como referencia para cruzar
        # con esa otra hoja. `código`, `descripción` y `magnitud` de
        # UnidadMedida se colapsan en `simbolo` ("unidad del flujo");
        # `Equipo.serial`/`descripción` quedan fuera porque en los datos
        # reales de IDEAM siempre están vacíos (ver revisar-datos-ideam.md).
        "campos": {
            "UnidadMuestreo": {"incluir": ["nombre"], "alias": {"nombre": "nombre unidad de muestreo"}},
            "UnidadExperimental": {"incluir": ["nombre"], "alias": {"nombre": "nombre unidad experimental"}},
            "UnidadMedida": {"incluir": ["simbolo"]},
            "Equipo": {"incluir": ["modelo"]},
            # n_toma: nunca llega poblado desde IDEAM (100% NULL, confirmado
            # en CO2 y CH4) — se queda en el modelo (lo usa el orden interno
            # y la regla de autollenado de horas) pero no aporta nada visible
            # en esta hoja, así que no se muestra.
            "SubmuestraGEI": {"excluir": ["n_toma"]},
            "Parcela": {"incluir": []},
            "Sitio": {"incluir": ["latitud", "longitud"]},
        },
        # Unidad experimental, unidad muestral y coordenadas primero, como
        # en el resto de hojas de metodología (MOM/COS/Biomasa) — el resto
        # de columnas de esta hoja (analizador, fecha, hora, condición de
        # luz, valor del flujo, ...) queda después, en su orden natural.
        "orden_columnas": _ORDEN_COLUMNAS_METODOLOGIA,
    },
    "unidad_muestreo": {
        "modelo_base": "UnidadMuestreo",
        "orden": ["unidad_experimental__nombre", "nombre"],
        "cadena": [
            ("UnidadMuestreo", []),
            ("UnidadExperimental", ["unidad_experimental"]),
            ("UnidadMuestreoTipo", ["unidad_experimental", "tipo"]),
            ("Parcela", ["parcela"]),
            ("Sitio", ["sitio"]),
        ],
        # Cadena de 5 modelos, cada uno con su propio "nombre"/"descripción":
        # sin alias, el Excel exportado mostraba 4 columnas "nombre" y 2
        # "descripción" indistinguibles entre sí.
        "campos": {
            "UnidadMuestreo": {"alias": {"nombre": "nombre unidad de muestreo"}},
            "UnidadExperimental": {"alias": {
                "nombre": "nombre unidad experimental",
                "descripcion": "descripción unidad experimental",
            }},
            "UnidadMuestreoTipo": {"alias": {"nombre": "tipo de unidad de muestreo"}},
            "Parcela": {"alias": {"descripcion": "descripción parcela"}},
            "Sitio": {"alias": {"nombre": "nombre sitio"}},
        },
        # Orden pedido para esta pestaña/hoja (distinto del orden natural de
        # la cadena, que agrupa todo por modelo): primero identificar la
        # unidad experimental y la unidad de muestreo, luego cuándo se
        # instaló y de qué tipo es; el resto de columnas queda después, en
        # su orden natural.
        "orden_columnas": [
            "UnidadExperimental.nombre",
            "UnidadMuestreo.nombre",
            "UnidadMuestreo.fecha_instalacion",
            "UnidadMuestreoTipo.nombre",
        ],
    },
    "clima": {
        "modelo_base": "MuestraAmbiental",
        "orden": ["fecha", "hora"],
        "cadena": [
            ("MuestraAmbiental", []),
            ("UnidadMuestreo", ["unidad_muestreo"]),
            ("UnidadExperimental", ["unidad_muestreo", "unidad_experimental"]),
            ("Sitio", ["unidad_muestreo", "sitio"]),
        ],
    },
    "mom": {
        "modelo_base": "MuestraMOM",
        "orden": ["unidad_muestreo__unidad_experimental__nombre", "fecha"],
        "cadena": [
            ("MuestraMOM", []),
            ("UnidadMuestreo", ["unidad_muestreo"]),
            ("UnidadExperimental", ["unidad_muestreo", "unidad_experimental"]),
            ("Parcela", ["unidad_muestreo", "parcela"]),
            ("Sitio", ["unidad_muestreo", "sitio"]),
        ],
        "campos": _CAMPOS_METODOLOGIA,
        "orden_columnas": _ORDEN_COLUMNAS_METODOLOGIA,
    },
    "cos": {
        "modelo_base": "SubmuestraSuelo",
        "orden": ["unidad_muestreo__unidad_experimental__nombre", "fecha", "profundidad_desde_cm"],
        "cadena": [
            ("SubmuestraSuelo", []),
            ("UnidadMuestreo", ["unidad_muestreo"]),
            ("UnidadExperimental", ["unidad_muestreo", "unidad_experimental"]),
            ("Parcela", ["unidad_muestreo", "parcela"]),
            ("Sitio", ["unidad_muestreo", "sitio"]),
        ],
        "campos": _CAMPOS_METODOLOGIA,
        "orden_columnas": _ORDEN_COLUMNAS_METODOLOGIA,
    },
    # Base "MuestraBiomasa", no "IndividuoArboreo": en los datos reales de
    # IDEAM, IndividuoArboreo siempre queda vacío (la fuente no trae
    # individuos arbóreos, solo el agregado de producción/carbono por
    # parcela) — con IndividuoArboreo como base, la vista quedaba
    # permanentemente "sin registros" pese a haber 646 MuestraBiomasa reales
    # importadas. IndividuoArboreo es 1:N con MuestraBiomasa (reversa), no
    # se puede aplanar como columnas de la misma fila con este mecanismo de
    # `ruta` (solo sigue FKs hacia adelante); si algún día llega ese detalle,
    # necesita su propia vista con IndividuoArboreo como base, análoga a
    # submuestra_gei.
    "biomasa": {
        "modelo_base": "MuestraBiomasa",
        "orden": ["unidad_muestreo__unidad_experimental__nombre", "fecha"],
        "cadena": [
            ("MuestraBiomasa", []),
            ("UnidadMuestreo", ["unidad_muestreo"]),
            ("UnidadExperimental", ["unidad_muestreo", "unidad_experimental"]),
            ("Parcela", ["unidad_muestreo", "parcela"]),
            ("Sitio", ["unidad_muestreo", "sitio"]),
        ],
        "campos": _CAMPOS_METODOLOGIA,
        "orden_columnas": _ORDEN_COLUMNAS_METODOLOGIA,
    },
}


def _select_related_de_cadena(cadena):
    return ["__".join(ruta) for _modelo, ruta in cadena if ruta]


def _campos_planos(modelo_cls, opciones=None):
    """Campos propios de un modelo (sin FKs/relaciones, geometría, ni id/timestamps),
    listos para aplanar como columnas de la tabla desnormalizada.

    No filtramos por `editable`: excluye campos calculados legítimos que sí
    queremos mostrar (p. ej. `Parcela.area`). En cambio excluimos geometría
    explícitamente (p. ej. `Sitio.geom`) — nunca se vuelca cruda a la tabla.

    `opciones` (de `vista["campos"][modelo_nombre]`) deja que una vista
    recorte qué campos de un modelo se ven como columna sin sacarlo de la
    cadena (sigue disponible para joins/filtros): `{"incluir": [...]}` es
    allowlist explícita (`[]` = ninguno, útil para modelos que solo están en
    la cadena por el join, p. ej. Sitio en `submuestra_gei`); `{"excluir": [...]}`
    es denylist sobre el set por defecto."""
    campos = [
        f for f in modelo_cls._meta.get_fields()
        if hasattr(f, "column") and not f.is_relation
        and f.get_internal_type() not in ("PointField", "MultiPolygonField", "PolygonField", "GeometryField")
        and f.name not in ("id", "created_at", "updated_at")
    ]
    if opciones and "incluir" in opciones:
        campos = [f for f in campos if f.name in opciones["incluir"]]
    elif opciones and "excluir" in opciones:
        campos = [f for f in campos if f.name not in opciones["excluir"]]
    return campos


def _resolver_ruta(obj, ruta):
    for attr in ruta:
        if obj is None:
            return None
        obj = getattr(obj, attr, None)
    return obj


def _valor_campo_plano(obj, field):
    if obj is None:
        return None
    valor = getattr(obj, field.name, None)
    if valor is None:
        return None
    if getattr(field, "choices", None):
        display = getattr(obj, f"get_{field.name}_display", None)
        if callable(display):
            return display()
    return valor


def _preparar_vista_carga(carga, nombre_vista, filtros_raw):
    """Resuelve vista + queryset filtrado/ordenado para una carga, compartido
    entre `datos_carga` (paginado, JSON) y `exportar_carga` (completo, CSV)."""
    vista = _VISTAS_DESNORMALIZADAS.get(nombre_vista)
    if vista is None:
        return None, None, None, f"Vista desconocida: {nombre_vista}"

    pks = (carga.pks_importados or {}).get(vista["modelo_base"], [])
    return _preparar_vista_pks(pks, nombre_vista, filtros_raw)


def _preparar_vista_proyecto(proyecto_id, nombre_vista, filtros_raw, sitio_id=None, geo_filtros=None):
    """Resuelve vista + queryset para TODOS los datos reales del proyecto,
    filtrando directo por la cadena de FKs hasta UnidadExperimental.proyecto
    -mismo criterio que ya usan el mapa (/api/geo/*) y los reportes
    (/api/reportes/*)-, no solo los que pasaron por el wizard de importación
    de ETL (`CargaArchivo.pks_importados`).

    Antes esta vista solo mostraba filas con esa trazabilidad de importación,
    lo que la desincronizaba del mapa: un sitio podía verse con muestras en
    el mapa/gráficas y aparecer "sin datos" acá si esas filas se cargaron por
    otro medio (ej. una migración/fixture inicial, como pasó con varios
    sitios de IDEAM que tenían SubmuestraGEI real sin ninguna CargaArchivo en
    estado "importado" detrás). `_preparar_vista_carga` (ver arriba) sigue
    necesitando `pks_importados` -es la única forma de saber qué filas
    vinieron de UN archivo específico-, pero acá basta con "pertenece a este
    proyecto" para mostrar todo lo real que haya."""
    vista = _VISTAS_DESNORMALIZADAS.get(nombre_vista)
    if vista is None:
        return None, None, None, f"Vista desconocida: {nombre_vista}"

    columnas, ruta_orm_por_clave, ruta_sitio, ruta_ue = _metadatos_vista(vista)
    if ruta_ue is None:
        return vista, None, None, None

    ModeloBase = apps.get_model("app", vista["modelo_base"])
    qs = (
        ModeloBase.objects
        .filter(**{"__".join(ruta_ue + ["proyecto_id"]): proyecto_id})
        .select_related(*_select_related_de_cadena(vista["cadena"]))
    )
    qs = _aplicar_filtros_vista(qs, vista, ruta_orm_por_clave, ruta_sitio, filtros_raw, sitio_id, geo_filtros)
    return vista, columnas, qs, None


def _reordenar_columnas(columnas, orden_prioridad):
    """Antepone las columnas listadas en `orden_prioridad` (una lista de
    claves "Modelo.campo", en el orden deseado) y deja el resto de columnas
    después, en su orden original."""
    por_clave = {c["clave"]: c for c in columnas}
    primero = [por_clave[clave] for clave in orden_prioridad if clave in por_clave]
    resto = [c for c in columnas if c["clave"] not in orden_prioridad]
    return primero + resto


def _columnas_de_vista(vista):
    """Columnas de una vista (clave, modelo, campo, verbose_name/alias), en
    el mismo orden en el que se ven en la página/Excel — incluye el alias y
    el `orden_columnas` de la vista. No depende de datos: solo mira la
    definición de la vista, así que también la usa el diccionario de datos
    para saber en qué orden documentar cada atributo."""
    cadena = vista["cadena"]
    campos_por_modelo = vista.get("campos", {})
    columnas = [
        {"clave": f"{modelo_nombre}.{f.name}", "modelo": modelo_nombre, "campo": f.name,
         "verbose_name": campos_por_modelo.get(modelo_nombre, {}).get("alias", {}).get(f.name, str(f.verbose_name))}
        for modelo_nombre, _ruta in cadena
        for f in _campos_planos(apps.get_model("app", modelo_nombre), campos_por_modelo.get(modelo_nombre))
    ]
    orden_columnas = vista.get("orden_columnas")
    if orden_columnas:
        columnas = _reordenar_columnas(columnas, orden_columnas)
    return columnas


def _metadatos_vista(vista):
    """columnas / mapa clave→ruta ORM / ruta a Sitio / ruta a UnidadExperimental
    de una vista -comunes a cualquier forma de armar su queryset, sea por pks
    de una carga (`_preparar_vista_pks`) o por proyecto entero
    (`_preparar_vista_proyecto`)-."""
    cadena = vista["cadena"]
    campos_por_modelo = vista.get("campos", {})
    columnas = _columnas_de_vista(vista)
    # Mapa clave ("Modelo.campo") -> ruta ORM, para poder traducir los filtros
    # del usuario a filter(**{"ruta__campo__icontains": ...}).
    ruta_orm_por_clave = {}
    ruta_sitio = None
    ruta_ue = None
    for modelo_nombre, ruta in cadena:
        for f in _campos_planos(apps.get_model("app", modelo_nombre), campos_por_modelo.get(modelo_nombre)):
            ruta_orm_por_clave[f"{modelo_nombre}.{f.name}"] = ruta + [f.name]
        if modelo_nombre == "Sitio":
            ruta_sitio = ruta
        if modelo_nombre == "UnidadExperimental":
            ruta_ue = ruta
    return columnas, ruta_orm_por_clave, ruta_sitio, ruta_ue


def _aplicar_filtros_vista(qs, vista, ruta_orm_por_clave, ruta_sitio, filtros_raw, sitio_id, geo_filtros):
    """Filtro exacto por sitio, geográficos/fecha y de texto libre por
    columna -comunes a cualquier forma de armar el queryset de una vista-.

    "geo_filtros" (dict opcional con claves vereda/municipio/departamento/
    region/desde/hasta) replica para esta tabla genérica los mismos filtros
    del panel de filtros que ya soportan /api/geo/resumen/ y /api/geo/series/
    -así el panel de "Datos detallados" queda coherente con el mapa-. Los
    geográficos se aplican vía la ruta a Sitio ya calculada para el filtro de
    "sitio_id"; desde/hasta solo si el modelo base de la vista tiene un campo
    "fecha" propio (no todas lo tienen, ej. unidad_muestreo usa
    fecha_instalacion)."""
    ModeloBase = apps.get_model("app", vista["modelo_base"])

    # Filtro exacto por sitio (usado por el geoportal al elegir un marcador
    # en el mapa): a diferencia de los filtros de texto de abajo, este es un
    # match exacto de pk, no icontains.
    if sitio_id and ruta_sitio is not None:
        qs = qs.filter(**{f"{'__'.join(ruta_sitio + ['pk'])}": sitio_id})

    geo_filtros = geo_filtros or {}
    if ruta_sitio is not None:
        for campo, sufijo in (
            ("vereda", "vereda_id"),
            ("municipio", "vereda__municipio_id"),
            ("departamento", "vereda__municipio__departamento_id"),
            ("region", "vereda__municipio__departamento__region_id"),
        ):
            valor = geo_filtros.get(campo)
            if valor:
                qs = qs.filter(**{"__".join(ruta_sitio + [sufijo]): valor})

    desde, hasta = geo_filtros.get("desde"), geo_filtros.get("hasta")
    if desde or hasta:
        try:
            ModeloBase._meta.get_field("fecha")
        except FieldDoesNotExist:
            pass
        else:
            if desde:
                qs = qs.filter(fecha__gte=desde)
            if hasta:
                qs = qs.filter(fecha__lte=hasta)

    try:
        filtros = json.loads(filtros_raw or "{}")
    except json.JSONDecodeError:
        filtros = {}
    for clave, texto in filtros.items():
        ruta_orm = ruta_orm_por_clave.get(clave)
        if not ruta_orm or not str(texto).strip():
            continue
        qs = qs.filter(**{f"{'__'.join(ruta_orm)}__icontains": texto})

    return qs.order_by(*vista["orden"])


def _preparar_vista_pks(pks, nombre_vista, filtros_raw, sitio_id=None, geo_filtros=None):
    """Resuelve vista + queryset filtrado/ordenado a partir de una lista de
    pks del modelo base ya calculada (por una carga específica -ver
    `_preparar_vista_carga`, la única consumidora hoy-)."""
    vista = _VISTAS_DESNORMALIZADAS.get(nombre_vista)
    if vista is None:
        return None, None, None, f"Vista desconocida: {nombre_vista}"

    if not pks:
        return vista, None, None, None

    columnas, ruta_orm_por_clave, ruta_sitio, _ruta_ue = _metadatos_vista(vista)
    ModeloBase = apps.get_model("app", vista["modelo_base"])
    qs = ModeloBase.objects.filter(pk__in=pks).select_related(*_select_related_de_cadena(vista["cadena"]))
    qs = _aplicar_filtros_vista(qs, vista, ruta_orm_por_clave, ruta_sitio, filtros_raw, sitio_id, geo_filtros)
    return vista, columnas, qs, None


def _fila_desde_objeto(obj, cadena, campos_por_modelo=None):
    campos_por_modelo = campos_por_modelo or {}
    fila = {}
    for modelo_nombre, ruta in cadena:
        related_obj = obj if not ruta else _resolver_ruta(obj, ruta)
        for f in _campos_planos(apps.get_model("app", modelo_nombre), campos_por_modelo.get(modelo_nombre)):
            fila[f"{modelo_nombre}.{f.name}"] = _valor_campo_plano(related_obj, f)
    return fila


def _respuesta_datos_vista(request, vista, columnas, qs, advertencia_sin_datos):
    if qs is None:
        return JsonResponse({
            "total": 0, "columnas": [], "filas": [], "vistas": list(_VISTAS_DESNORMALIZADAS.keys()),
            "advertencia": advertencia_sin_datos,
        }, json_dumps_params={"ensure_ascii": False})

    try:
        offset = max(int(request.GET.get("offset", 0)), 0)
    except ValueError:
        offset = 0
    try:
        limite = min(max(int(request.GET.get("limite", 500)), 1), 2000)
    except ValueError:
        limite = 500

    total = qs.count()
    cadena = vista["cadena"]
    campos_por_modelo = vista.get("campos", {})
    filas = [_fila_desde_objeto(obj, cadena, campos_por_modelo) for obj in qs[offset:offset + limite]]

    return JsonResponse({
        "total": total,
        "offset": offset,
        "limite": limite,
        "columnas": columnas,
        "filas": filas,
        "vistas": list(_VISTAS_DESNORMALIZADAS.keys()),
    }, json_dumps_params={"ensure_ascii": False})


def datos_carga(request, fuente_id, carga_id):
    try:
        carga = CargaArchivo.objects.get(pk=carga_id, fuente_id=fuente_id)
    except CargaArchivo.DoesNotExist:
        return JsonResponse({"error": "Carga no encontrada"}, status=404)

    nombre_vista = request.GET.get("vista", "submuestra_gei")
    vista, columnas, qs, error = _preparar_vista_carga(carga, nombre_vista, request.GET.get("filtros"))
    if error:
        return JsonResponse({"error": error}, status=400)

    return _respuesta_datos_vista(
        request, vista, columnas, qs,
        f"Esta carga todavía no tiene {vista['modelo_base']} importado.",
    )


_GEO_FILTROS_GET = ("vereda", "municipio", "departamento", "region", "desde", "hasta")


def datos_proyecto(request, proyecto_id):
    if not Proyecto.objects.filter(pk=proyecto_id).exists():
        return JsonResponse({"error": "Proyecto no encontrado"}, status=404)

    nombre_vista = request.GET.get("vista", "submuestra_gei")
    sitio_id = request.GET.get("sitio") or None
    geo_filtros = {k: request.GET.get(k) for k in _GEO_FILTROS_GET if request.GET.get(k)}
    vista, columnas, qs, error = _preparar_vista_proyecto(
        proyecto_id, nombre_vista, request.GET.get("filtros"), sitio_id=sitio_id, geo_filtros=geo_filtros,
    )
    if error:
        return JsonResponse({"error": error}, status=400)

    return _respuesta_datos_vista(
        request, vista, columnas, qs,
        f"Este proyecto todavía no tiene {vista['modelo_base']} importado.",
    )


# Hojas del Excel exportado: misma partición y orden que las pestañas del
# front (Unidad Muestreo-Experimental / CO₂ / CH₄ / Clima / MOM / COS /
# Biomasa) en vez de una hoja combinada por vista — ver DatosTabs.tsx (TABS)
# en el frontend React. Unidad Muestreo-Experimental va primero: es la que
# define el contexto (dónde/qué unidad) del resto de hojas.
_HOJAS_EXPORT = [
    {"nombre_vista": "unidad_muestreo", "gas": None, "hoja": "Unidad Muestreo-Experimental"},
    {"nombre_vista": "submuestra_gei", "gas": "CO2", "hoja": "CO2 (detalle)"},
    {"nombre_vista": "submuestra_gei", "gas": "CH4", "hoja": "CH4 (detalle)"},
    {"nombre_vista": "clima", "gas": None, "hoja": "Clima"},
    {"nombre_vista": "mom", "gas": None, "hoja": "MOM"},
    {"nombre_vista": "cos", "gas": None, "hoja": "COS"},
    {"nombre_vista": "biomasa", "gas": None, "hoja": "Biomasa"},
]

_TIPOS_DATO_LEGIBLES = {
    "CharField": "Texto", "TextField": "Texto largo",
    "DecimalField": "Numérico (decimal)", "FloatField": "Numérico (decimal)",
    "IntegerField": "Numérico (entero)", "PositiveIntegerField": "Numérico (entero)",
    "PositiveSmallIntegerField": "Numérico (entero)", "SmallIntegerField": "Numérico (entero)",
    "BooleanField": "Sí/No", "DateField": "Fecha", "DateTimeField": "Fecha y hora",
    "TimeField": "Hora", "EmailField": "Texto (email)", "URLField": "Texto (URL)",
    "JSONField": "JSON",
}


def _tipo_dato_legible(field):
    return _TIPOS_DATO_LEGIBLES.get(field.get_internal_type(), field.get_internal_type())


def _dataframe_diccionario_datos(hojas):
    """Una fila por cada columna real de cada hoja del Excel que se está
    generando en esta descarga — recibe `hojas` (la misma lista
    `[(nombre_hoja, df, columnas), ...]` que ya se armó en
    `exportar_carga`/`exportar_proyecto`, después de saltarse las hojas sin
    datos y de `_quitar_columnas_vacias`), no la metadata estática de todas
    las vistas posibles: si esta descarga no trae ninguna fila para "Clima"
    (por eso no se agrega esa hoja), o si una columna quedó vacía y se
    descartó, el diccionario tampoco los menciona.

    No se deduplica entre hojas: si un atributo aparece en varias (ej.
    "nombre unidad experimental" en Unidad Muestreo-Experimental, CO2 y
    CH4), sale una fila por cada una — así cada pestaña queda completa por
    sí sola en el diccionario, sin tener que ir a buscar el resto de sus
    atributos en el bloque de otra pestaña. Las filas quedan en el mismo
    orden en que aparecen las columnas en el Excel: hoja por hoja (en el
    orden en que se agregaron a `hojas`), y dentro de cada hoja en el orden
    real de sus columnas. "Campo" usa el texto literal del encabezado que
    sale en la hoja (el alias ya aplicado, ej. "nombre unidad
    experimental"), no el nombre base del campo en Django (que sería
    "nombre" para varios modelos distintos). Devuelve (dataframe,
    colores_por_fila): la primera columna del dataframe queda vacía a
    propósito, para pintarla después según la categoría del atributo (ver
    `_colorear_columna_categoria`)."""
    filas = []
    colores = []
    for nombre_hoja, _df, columnas in hojas:
        for columna in columnas:
            modelo_nombre, campo_nombre = columna["modelo"], columna["campo"]
            modelo_cls = apps.get_model("app", modelo_nombre)
            f = modelo_cls._meta.get_field(campo_nombre)
            valores_permitidos = ", ".join(str(label) for _valor, label in f.choices) if getattr(f, "choices", None) else ""
            filas.append({
                "": "",
                "Pestaña": nombre_hoja,
                "Campo": columna["verbose_name"] or columna["campo"],
                "Tipo de dato": _tipo_dato_legible(f),
                "Descripción": str(f.help_text) if f.help_text else "",
                "Entidad.atributo (Modelo de Datos COLFLUX)": f"{modelo_nombre}.{campo_nombre}",
                "Valores permitidos (si aplica)": valores_permitidos,
            })
            colores.append(COLOR_POR_MODELO.get(modelo_nombre))

    df = pd.DataFrame(filas, columns=[
        "", "Pestaña", "Campo", "Tipo de dato", "Descripción",
        "Entidad.atributo (Modelo de Datos COLFLUX)", "Valores permitidos (si aplica)",
    ])
    return df, colores


def _colorear_columna_categoria(worksheet, colores):
    """Pinta la primera columna (vacía) de `worksheet`, fila por fila, según
    el color de categoría de esa fila — ver `_colorear_encabezados` para el
    equivalente por columna en las otras hojas."""
    from openpyxl.styles import PatternFill

    for idx, color in enumerate(colores, start=2):  # fila 1 es el encabezado
        if not color:
            continue
        celda = worksheet.cell(row=idx, column=1)
        celda.fill = PatternFill(start_color=color.lstrip("#"), end_color=color.lstrip("#"), fill_type="solid")


def _agregar_hoja_diccionario_datos(writer, hojas):
    df, colores = _dataframe_diccionario_datos(hojas)
    df.to_excel(writer, sheet_name="Diccionario de datos", index=False)
    _colorear_columna_categoria(writer.sheets["Diccionario de datos"], colores)


def _quitar_columnas_vacias(df, columnas):
    """Descarta las columnas que no tienen ningún valor en todo el archivo
    exportado (None/NaN o cadena vacía en todas las filas) — solo aplica a
    la descarga: la vista paginada de la página sí las deja, porque una
    columna puede estar vacía en la página actual y tener datos en otra."""
    vacia = df.isna() | (df.astype(str).apply(lambda s: s.str.strip()) == "")
    mantener = ~vacia.all(axis=0)
    df = df.loc[:, mantener]
    columnas = [c for c, keep in zip(columnas, mantener) if keep]
    return df, columnas


def _colorear_encabezados(worksheet, columnas):
    """Pinta la fila de encabezados de `worksheet` según la categoría
    (`COLOR_POR_MODELO`, derivada de GRUPOS_CATALOGO) del modelo de cada
    columna — mismo color que usa el diagrama ERD de /db para esa
    categoría."""
    from openpyxl.styles import Font, PatternFill

    for idx, columna in enumerate(columnas, start=1):
        color = COLOR_POR_MODELO.get(columna["modelo"])
        if not color:
            continue
        celda = worksheet.cell(row=1, column=idx)
        celda.fill = PatternFill(start_color=color.lstrip("#"), end_color=color.lstrip("#"), fill_type="solid")
        celda.font = Font(color="FFFFFF", bold=True)


@requiere_nivel("investigador")
def exportar_carga(request, fuente_id, carga_id):
    """Descarga en un único Excel todos los datos importados por esta carga:
    una pestaña por cada pestaña del front (_HOJAS_EXPORT)."""
    try:
        carga = CargaArchivo.objects.get(pk=carga_id, fuente_id=fuente_id)
    except CargaArchivo.DoesNotExist:
        return JsonResponse({"error": "Carga no encontrada"}, status=404)

    hojas = []
    for hoja_def in _HOJAS_EXPORT:
        filtros_raw = json.dumps({"MuestraGEI.gas": hoja_def["gas"]}) if hoja_def["gas"] else None
        vista, columnas, qs, error = _preparar_vista_carga(carga, hoja_def["nombre_vista"], filtros_raw)
        if error or qs is None:
            continue
        cadena = vista["cadena"]
        campos_por_modelo = vista.get("campos", {})
        claves = [c["clave"] for c in columnas]
        encabezados = [c["verbose_name"] or c["campo"] for c in columnas]
        filas = [_fila_desde_objeto(obj, cadena, campos_por_modelo) for obj in qs.iterator()]
        df = pd.DataFrame([[fila[clave] for clave in claves] for fila in filas], columns=encabezados)
        df, columnas = _quitar_columnas_vacias(df, columnas)
        hojas.append((hoja_def["hoja"][:31], df, columnas))

    # openpyxl exige al menos una hoja visible: si no hay datos, ni siquiera
    # se abre el ExcelWriter (si no, revienta con IndexError al cerrarlo sin
    # haber escrito nada).
    if not hojas:
        return JsonResponse({"error": "Esta carga todavía no tiene datos importados."}, status=404)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for nombre_hoja, df, columnas in hojas:
            df.to_excel(writer, sheet_name=nombre_hoja, index=False)
            _colorear_encabezados(writer.sheets[nombre_hoja], columnas)
        _agregar_hoja_diccionario_datos(writer, hojas)

    buffer.seek(0)
    response = HttpResponse(
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="carga_{carga_id}.xlsx"'
    return response


@requiere_nivel("investigador")
def exportar_proyecto(request, proyecto_id):
    """Descarga en un único Excel todos los datos importados del proyecto
    (todas sus cargas ya importadas combinadas): una pestaña por cada
    pestaña del front (_HOJAS_EXPORT)."""
    if not Proyecto.objects.filter(pk=proyecto_id).exists():
        return JsonResponse({"error": "Proyecto no encontrado"}, status=404)

    hojas = []
    for hoja_def in _HOJAS_EXPORT:
        filtros_raw = json.dumps({"MuestraGEI.gas": hoja_def["gas"]}) if hoja_def["gas"] else None
        vista, columnas, qs, error = _preparar_vista_proyecto(proyecto_id, hoja_def["nombre_vista"], filtros_raw)
        if error or qs is None:
            continue
        cadena = vista["cadena"]
        campos_por_modelo = vista.get("campos", {})
        claves = [c["clave"] for c in columnas]
        encabezados = [c["verbose_name"] or c["campo"] for c in columnas]
        filas = [_fila_desde_objeto(obj, cadena, campos_por_modelo) for obj in qs.iterator()]
        df = pd.DataFrame([[fila[clave] for clave in claves] for fila in filas], columns=encabezados)
        df, columnas = _quitar_columnas_vacias(df, columnas)
        hojas.append((hoja_def["hoja"][:31], df, columnas))

    if not hojas:
        return JsonResponse({"error": "Este proyecto todavía no tiene datos importados."}, status=404)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for nombre_hoja, df, columnas in hojas:
            df.to_excel(writer, sheet_name=nombre_hoja, index=False)
            _colorear_encabezados(writer.sheets[nombre_hoja], columnas)
        _agregar_hoja_diccionario_datos(writer, hojas)

    buffer.seek(0)
    response = HttpResponse(
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="proyecto_{proyecto_id}.xlsx"'
    return response
