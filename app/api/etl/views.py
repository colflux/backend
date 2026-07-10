import json
import math
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


def _resolver_ruta_fuente(fuente):
    raw_path = (fuente.url or "").strip()
    if not raw_path:
        raise ValueError("La fuente no tiene enlace o ruta de archivo registrada.")

    parsed = urlparse(raw_path)
    if parsed.scheme in ("http", "https"):
        raise ValueError(
            "La carga automática desde URLs remotas no está habilitada. "
            "Registra una ruta local accesible por el backend en la fuente de datos."
        )
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


def _crear_carga_desde_fuente(fuente):
    source_path = _resolver_ruta_fuente(fuente)
    carga = CargaArchivo.objects.create(fuente=fuente)
    return carga, source_path, source_path.name.lower()


@csrf_exempt
def upload_archivo(request, fuente_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        fuente = FuenteDatos.objects.get(pk=fuente_id)
    except FuenteDatos.DoesNotExist:
        return JsonResponse({"error": "Fuente de datos no encontrada"}, status=404)

    if request.FILES.get("archivo"):
        return JsonResponse(
            {"error": "La fuente de datos maneja un único archivo. Edita la fuente para cambiarlo."},
            status=400,
        )

    nombre = (fuente.url or "").lower()
    if not (nombre.endswith(".xlsx") or nombre.endswith(".xls") or nombre.endswith(".csv")):
        return JsonResponse({"error": "Formato no permitido. Solo .xlsx, .xls o .csv"}, status=400)

    try:
        carga, path_archivo, nombre_archivo = _crear_carga_desde_fuente(fuente)

        if nombre_archivo.endswith(".csv"):
            df = pd.read_csv(path_archivo)
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

        return JsonResponse({
            "carga_id": carga.pk,
            "sheets": sheets,
            "hoja_activa": hoja_activa,
            "total_filas": total_filas,
            "columnas": columnas,
        }, json_dumps_params={"ensure_ascii": False})

    except (ValueError, FileNotFoundError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


def campos_destino(request):
    modelos = {}
    for grupo in GRUPOS_CATALOGO:
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
    return JsonResponse({"modelos": modelos}, json_dumps_params={"ensure_ascii": False})


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
            df = pd.read_csv(path)
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
