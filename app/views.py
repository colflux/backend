from django.http import JsonResponse
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
