import csv
import json
import math
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from django.apps import apps
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from app.models import CargaArchivo, FuenteDatos, MapeoColumna

from app.catalogo.generator import GRUPOS_CATALOGO, campo_to_catalogo


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


def _valores_unicos(series, max_n=50):
    unicos = series.dropna().unique()
    return [str(v) for v in unicos[:max_n]]


def _columnas_desde_dataframe(df):
    columnas = []
    for col in df.columns:
        columnas.append({
            "nombre": col,
            "dtype": _infer_dtype(df[col]),
            "nulls": int(df[col].isna().sum()),
            "muestra": _muestra(df[col]),
            "valores_unicos": _valores_unicos(df[col]),
        })
    return columnas


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
        raise FileNotFoundError("No se encontró el archivo registrado en la fuente.")

    return path


@csrf_exempt
def archivo_fuente(request, fuente_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        fuente = FuenteDatos.objects.get(pk=fuente_id)
    except FuenteDatos.DoesNotExist:
        return JsonResponse({"error": "Fuente de datos no encontrada"}, status=404)

    archivo_subido = request.FILES.get("archivo")
    if not archivo_subido:
        return JsonResponse({"error": "No se recibió ningún archivo"}, status=400)

    try:
        _guardar_archivo_subido(fuente, archivo_subido)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"url": fuente.url})


@csrf_exempt
def upload_archivo(request, fuente_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        fuente = FuenteDatos.objects.get(pk=fuente_id)
    except FuenteDatos.DoesNotExist:
        return JsonResponse({"error": "Fuente de datos no encontrada"}, status=404)

    archivo_subido = request.FILES.get("archivo")

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

        carga.hoja_activa = hoja_activa
        carga.columnas_raw = columnas
        carga.total_filas = total_filas
        carga.save(update_fields=["hoja_activa", "columnas_raw", "total_filas"])

        # Recuperar el avance de mapeo de la última carga de esta fuente,
        # copiándolo a la carga nueva (solo columnas que siguen existiendo).
        mapeos_previos = []
        carga_previa = (
            CargaArchivo.objects.filter(fuente=fuente, mapeos__isnull=False)
            .exclude(pk=carga.pk)
            .order_by("-created_at")
            .first()
        )
        if carga_previa:
            nombres_actuales = {c["nombre"] for c in columnas}
            copias = [
                m for m in carga_previa.mapeos.all()
                if m.columna_origen in nombres_actuales
            ]
            MapeoColumna.objects.bulk_create([
                MapeoColumna(
                    carga=carga,
                    columna_origen=m.columna_origen,
                    modelo_destino=m.modelo_destino,
                    campo_destino=m.campo_destino,
                    transformacion=m.transformacion,
                    mapeo_valores=m.mapeo_valores,
                )
                for m in copias
            ])
            mapeos_previos = [
                {
                    "columna_origen": m.columna_origen,
                    "modelo_destino": m.modelo_destino,
                    "campo_destino": m.campo_destino,
                    "transformacion": m.transformacion,
                    "mapeo_valores": m.mapeo_valores,
                }
                for m in copias
            ]

        return JsonResponse({
            "carga_id": carga.pk,
            "sheets": sheets,
            "hoja_activa": hoja_activa,
            "total_filas": total_filas,
            "columnas": columnas,
            "mapeos": mapeos_previos,
        }, json_dumps_params={"ensure_ascii": False})

    except (ValueError, FileNotFoundError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


def campos_destino(request):
    modelos = {}
    grupos = {}
    for orden, grupo in enumerate(GRUPOS_CATALOGO):
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
                campos.append(campo_to_catalogo(field))
            if campos:
                modelos[nombre] = campos
                grupos[nombre] = {
                    "nombre": grupo["nombre"],
                    "icono": grupo["icono"],
                    "orden": orden,
                }
    return JsonResponse({"modelos": modelos, "grupos": grupos}, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def mapeo_carga(request, fuente_id, carga_id):
    try:
        carga = CargaArchivo.objects.get(pk=carga_id, fuente_id=fuente_id)
    except CargaArchivo.DoesNotExist:
        return JsonResponse({"error": "Carga no encontrada"}, status=404)

    if request.method == "GET":
        mapeos = list(
            carga.mapeos.values("columna_origen", "modelo_destino", "campo_destino", "transformacion", "mapeo_valores")
        )
        return JsonResponse({"carga_id": carga.pk, "mapeos": mapeos}, json_dumps_params={"ensure_ascii": False})

    if request.method == "POST":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido"}, status=400)

        items = body.get("mapeos")
        if not isinstance(items, list):
            return JsonResponse({"error": "Se esperaba un array en 'mapeos'"}, status=400)

        # parcial=True: guardado incremental de columnas sueltas; no cambia el estado
        parcial = bool(body.get("parcial"))

        try:
            guardados = 0
            for item in items:
                columna_origen = (item.get("columna_origen") or "").strip()
                if not columna_origen:
                    continue
                MapeoColumna.objects.update_or_create(
                    carga=carga,
                    columna_origen=columna_origen,
                    defaults={
                        "modelo_destino": item.get("modelo_destino", ""),
                        "campo_destino": item.get("campo_destino", ""),
                        "transformacion": item.get("transformacion", "directo"),
                        "mapeo_valores": item.get("mapeo_valores") or {},
                    },
                )
                guardados += 1

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
    return False


def _validar_columna(df, columna_origen, modelo_destino, campo_destino):
    try:
        modelo_cls = apps.get_model("app", modelo_destino)
    except LookupError:
        return {"advertencia": "modelo_o_campo_no_encontrado"}

    try:
        field = modelo_cls._meta.get_field(campo_destino)
    except Exception:
        return {"advertencia": "modelo_o_campo_no_encontrado"}

    if columna_origen not in df.columns:
        return {"advertencia": "modelo_o_campo_no_encontrado"}

    serie = df[columna_origen]
    errores = []

    campo_requerido = not getattr(field, "blank", True) and not getattr(field, "null", True)
    max_length = getattr(field, "max_length", None)
    choices = getattr(field, "choices", None)
    choices_valores = {c[0] for c in choices} if choices else None

    tipo_campo = type(field).__name__

    for idx, val in serie.items():
        fila = int(idx) + 2
        py_val = _to_python(val)

        if _es_vacio(val):
            if campo_requerido:
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


@csrf_exempt
def validar_carga(request, fuente_id, carga_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        carga = CargaArchivo.objects.get(pk=carga_id, fuente_id=fuente_id)
    except CargaArchivo.DoesNotExist:
        return JsonResponse({"error": "Carga no encontrada"}, status=404)

    try:
        path = _resolver_ruta_fuente(carga.fuente)
        nombre = str(path).lower()
        if nombre.endswith(".csv"):
            df = _leer_csv(path)
        else:
            df = pd.read_excel(path, sheet_name=carga.hoja_activa)

        mapeos = carga.mapeos.exclude(modelo_destino="")

        resultados = []
        filas_con_error = set()

        for mapeo in mapeos:
            resultado = _validar_columna(df, mapeo.columna_origen, mapeo.modelo_destino, mapeo.campo_destino)
            if "advertencia" not in resultado:
                for e in resultado["errores"]:
                    filas_con_error.add(e["fila"])
            resultados.append(resultado)

        columnas_con_errores = sum(
            1 for r in resultados
            if "advertencia" not in r and len(r["errores"]) > 0
        )
        total_errores = sum(
            len(r["errores"]) for r in resultados if "advertencia" not in r
        )

        return JsonResponse({
            "resumen": {
                "total_filas": carga.total_filas,
                "columnas_mapeadas": mapeos.count(),
                "columnas_con_errores": columnas_con_errores,
                "total_errores": total_errores,
                "filas_limpias": carga.total_filas - len(filas_con_error),
                "filas_con_errores": len(filas_con_error),
            },
            "columnas": resultados,
        }, json_dumps_params={"ensure_ascii": False})

    except (ValueError, FileNotFoundError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)
