import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from .models import FuenteDatos, Proyecto, Reportador, Sitio


class DashboardView(TemplateView):
    template_name = "app/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sitio_count"] = Sitio.objects.count()
        context["proyecto_count"] = Proyecto.objects.count()
        return context


def fuentes_datos_api(request):
    proyecto_id = request.GET.get("proyecto")
    qs = FuenteDatos.objects.select_related("proyecto", "reportador")
    if proyecto_id:
        qs = qs.filter(proyecto_id=proyecto_id)

    fuentes = []
    for f in qs:
        fuentes.append({
            "id": f.id,
            "nombre": f.nombre,
            "descripcion": f.descripcion,
            "tipo": f.tipo,
            "tipo_label": f.get_tipo_display(),
            "url": f.url,
            "estado": f.estado,
            "estado_label": f.get_estado_display(),
            "responsable": f.reportador.nombre if f.reportador else "",
            "fecha_datos": f.fecha_recepcion.isoformat() if f.fecha_recepcion else None,
            "notas": f.notas,
            "proyecto": {"id": f.proyecto.id, "codigo": f.proyecto.codigo, "nombre": f.proyecto.nombre} if f.proyecto else None,
            "sitio": None,
            "created_at": f.created_at.isoformat(),
        })

    proyectos = []
    for p in Proyecto.objects.all():
        proyectos.append({"id": p.id, "codigo": p.codigo, "nombre": p.nombre})

    return JsonResponse({"fuentes": fuentes, "proyectos": proyectos}, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def crear_fuente_datos(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    nombre = (body.get("nombre") or "").strip()
    if not nombre:
        return JsonResponse({"error": "El nombre es obligatorio"}, status=400)

    proyecto_id = body.get("proyecto_id") or None
    proyecto = None
    if proyecto_id:
        try:
            proyecto = Proyecto.objects.get(pk=proyecto_id)
        except Proyecto.DoesNotExist:
            return JsonResponse({"error": "Proyecto no encontrado"}, status=404)

    responsable = (body.get("responsable") or "").strip()
    reportador = None
    if responsable:
        reportador, _ = Reportador.objects.get_or_create(nombre=responsable)

    fuente = FuenteDatos.objects.create(
        nombre=nombre,
        descripcion=body.get("descripcion", ""),
        url=body.get("url", ""),
        tipo=body.get("tipo", "excel"),
        estado=body.get("estado", "pendiente"),
        reportador=reportador,
        proyecto=proyecto,
    )

    return JsonResponse({
        "id": fuente.id,
        "nombre": fuente.nombre,
        "tipo": fuente.tipo,
        "tipo_label": fuente.get_tipo_display(),
        "estado": fuente.estado,
        "estado_label": fuente.get_estado_display(),
        "url": fuente.url,
        "descripcion": fuente.descripcion,
        "responsable": fuente.reportador.nombre if fuente.reportador else "",
        "proyecto": {"id": proyecto.id, "codigo": proyecto.codigo, "nombre": proyecto.nombre} if proyecto else None,
        "sitio": None,
        "fecha_datos": None,
        "notas": "",
        "created_at": fuente.created_at.isoformat(),
    }, status=201, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def crear_proyecto(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    codigo = (body.get("codigo") or "").strip()
    nombre = (body.get("nombre") or "").strip()
    if not codigo:
        return JsonResponse({"error": "El código es obligatorio"}, status=400)
    if not nombre:
        return JsonResponse({"error": "El nombre es obligatorio"}, status=400)
    if Proyecto.objects.filter(codigo=codigo).exists():
        return JsonResponse({"error": f"Ya existe un proyecto con el código «{codigo}»"}, status=400)

    proyecto = Proyecto.objects.create(
        codigo=codigo,
        nombre=nombre,
        coordinador=body.get("coordinador", ""),
        correo_coordinador=body.get("correo_coordinador", ""),
        escala_espacial=body.get("escala_espacial", ""),
        objetivo_general=body.get("objetivo_general", ""),
        fecha_inicio=body.get("fecha_inicio") or None,
        fecha_fin=body.get("fecha_fin") or None,
    )

    return JsonResponse({
        "id": proyecto.id,
        "codigo": proyecto.codigo,
        "nombre": proyecto.nombre,
        "coordinador": proyecto.coordinador,
        "correo_coordinador": proyecto.correo_coordinador,
        "escala_espacial": proyecto.escala_espacial,
        "objetivo_general": proyecto.objetivo_general,
        "fecha_inicio": proyecto.fecha_inicio.isoformat() if proyecto.fecha_inicio else None,
        "fecha_fin": proyecto.fecha_fin.isoformat() if proyecto.fecha_fin else None,
    }, status=201, json_dumps_params={"ensure_ascii": False})
