import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from .models import FuenteDatos, Proyecto, Sitio


class DashboardView(TemplateView):
    template_name = "app/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sitio_count"] = Sitio.objects.count()
        context["proyecto_count"] = Proyecto.objects.count()
        return context


def fuentes_datos_api(request):
    proyecto_id = request.GET.get("proyecto")
    qs = FuenteDatos.objects.select_related("proyecto", "sitio")
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
            "responsable": f.responsable,
            "fecha_datos": f.fecha_datos.isoformat() if f.fecha_datos else None,
            "notas": f.notas,
            "proyecto": {"id": f.proyecto.id, "codigo": f.proyecto.codigo, "nombre": f.proyecto.nombre} if f.proyecto else None,
            "sitio": {"id": f.sitio.id, "nombre": f.sitio.nombre} if f.sitio else None,
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

    fuente = FuenteDatos.objects.create(
        nombre=nombre,
        descripcion=body.get("descripcion", ""),
        url=body.get("url", ""),
        tipo=body.get("tipo", "excel"),
        estado=body.get("estado", "pendiente"),
        responsable=body.get("responsable", ""),
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
        "responsable": fuente.responsable,
        "proyecto": {"id": proyecto.id, "codigo": proyecto.codigo, "nombre": proyecto.nombre} if proyecto else None,
        "sitio": None,
        "fecha_datos": None,
        "notas": "",
        "created_at": fuente.created_at.isoformat(),
    }, status=201, json_dumps_params={"ensure_ascii": False})
