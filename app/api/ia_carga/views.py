"""Endpoint de carga para el flujo de "Formulario web" (mapeo propuesto por IA, confirmado por chat).

Vive separado de `app.api.etl` y `app.api.datos` a propósito: no reutiliza ni
el endpoint de upload manual (`upload_archivo`, usado por Gestión de Datos)
ni los de consulta (`fuentes_datos_api`, `datos_carga`, `datos_proyecto`).
El flujo conversacional con `ia-functions` guarda su propio avance de mapeo
sin pisar el estado del flujo manual campo a campo.
"""

import json

import pandas as pd
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from app.api.etl.views import _EXTENSIONES_VALIDAS, _columnas_desde_dataframe, _guardar_archivo_subido, _leer_csv
from app.api.permisos import requiere_nivel, usuario_del_token
from app.models import CargaArchivo, FuenteDatos, MapeoColumna, Proyecto


@csrf_exempt
@requiere_nivel("reportador")
def iniciar_carga_ia(request):
    """Recibe un archivo desde el Formulario web, crea la `FuenteDatos`/`CargaArchivo`
    correspondientes (marcadas `origen_mapeo="ia_chat"`) e inspecciona sus columnas.

    No propone el mapeo todavía — eso lo hace `ia-functions` en el paso
    siguiente del chat, a partir de las columnas devueltas aquí.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    archivo_subido = request.FILES.get("archivo")
    if not archivo_subido:
        return JsonResponse({"error": "No se recibió ningún archivo"}, status=400)

    nombre_archivo = archivo_subido.name.lower()
    if not nombre_archivo.endswith(_EXTENSIONES_VALIDAS):
        return JsonResponse({"error": "Formato no permitido. Solo .xlsx, .xls o .csv"}, status=400)

    nombre_fuente = (request.POST.get("nombre_fuente") or archivo_subido.name).strip()
    proyecto_id = request.POST.get("proyecto_id")
    proyecto = None
    if proyecto_id:
        try:
            proyecto = Proyecto.objects.get(pk=proyecto_id)
        except Proyecto.DoesNotExist:
            return JsonResponse({"error": "Proyecto no encontrado"}, status=404)

    reportador = usuario_del_token(request)
    tipo = "csv" if nombre_archivo.endswith(".csv") else "excel"

    fuente = FuenteDatos.objects.create(
        nombre=nombre_fuente, tipo=tipo, proyecto=proyecto, reportador=reportador,
    )

    try:
        path_archivo = _guardar_archivo_subido(fuente, archivo_subido)

        if nombre_archivo.endswith(".csv"):
            df = _leer_csv(path_archivo)
            hoja_activa = ""
        else:
            import openpyxl

            wb = openpyxl.load_workbook(path_archivo, read_only=True, data_only=True)
            hoja_activa = wb.sheetnames[0]
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                if ws.max_row and ws.max_row > 1:
                    hoja_activa = sheet_name
                    break
            df = pd.read_excel(path_archivo, sheet_name=hoja_activa)
            wb.close()
    except ValueError as exc:
        fuente.delete()
        return JsonResponse({"error": str(exc)}, status=400)

    columnas = _columnas_desde_dataframe(df)
    total_filas = len(df)

    carga = CargaArchivo.objects.create(
        fuente=fuente,
        hoja_activa=hoja_activa,
        columnas_raw=columnas,
        total_filas=total_filas,
        origen_mapeo="ia_chat",
    )

    return JsonResponse(
        {
            "fuente_id": fuente.pk,
            "carga_id": carga.pk,
            "columnas": columnas,
            "total_filas": total_filas,
        },
        json_dumps_params={"ensure_ascii": False},
    )


@requiere_nivel("reportador")
def columnas_carga_ia(request, carga_id):
    """Devuelve las columnas inspeccionadas de una carga iniciada por el
    Formulario web, para que `ia-functions` las use al proponer el mapeo
    en el chat."""
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        carga = CargaArchivo.objects.select_related("fuente").get(pk=carga_id, origen_mapeo="ia_chat")
    except CargaArchivo.DoesNotExist:
        return JsonResponse({"error": "Carga no encontrada"}, status=404)

    return JsonResponse(
        {
            "carga_id": carga.pk,
            "fuente_id": carga.fuente_id,
            "estado": carga.estado,
            "columnas": carga.columnas_raw,
            "total_filas": carga.total_filas,
        },
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
@requiere_nivel("reportador")
def confirmar_mapeo_ia(request, carga_id):
    """Aplica el mapeo de columnas que la persona confirmó en el chat: crea
    los `MapeoColumna` de la carga y la deja en estado `mapeado`, lista para
    los mismos pasos de validación/importación que usa el flujo manual
    (`validar_carga`/`importar_carga` en `app.api.etl.views`)."""
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        carga = CargaArchivo.objects.get(pk=carga_id, origen_mapeo="ia_chat")
    except CargaArchivo.DoesNotExist:
        return JsonResponse({"error": "Carga no encontrada"}, status=404)

    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    mapeos = body.get("mapeos")
    if not isinstance(mapeos, list) or not mapeos:
        return JsonResponse({"error": "Se requiere una lista 'mapeos' con al menos un elemento"}, status=400)

    columnas_validas = {c["nombre"] for c in carga.columnas_raw}
    nuevos = []
    for mapeo in mapeos:
        columna_origen = mapeo.get("columna_origen")
        if columna_origen not in columnas_validas:
            return JsonResponse(
                {"error": f"'{columna_origen}' no es una columna de esta carga"}, status=400,
            )
        nuevos.append(MapeoColumna(
            carga=carga,
            columna_origen=columna_origen,
            modelo_destino=mapeo.get("modelo_destino", ""),
            campo_destino=mapeo.get("campo_destino", ""),
            transformacion=mapeo.get("transformacion") or "directo",
            mapeo_valores=mapeo.get("mapeo_valores") or {},
        ))

    carga.mapeos.all().delete()
    MapeoColumna.objects.bulk_create(nuevos)
    carga.estado = "mapeado"
    carga.save(update_fields=["estado"])

    return JsonResponse({"carga_id": carga.pk, "estado": carga.estado, "mapeos_creados": len(nuevos)})
