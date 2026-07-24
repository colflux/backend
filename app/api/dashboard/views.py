import json

from django.apps import apps
from django.http import JsonResponse
from django.views.generic import TemplateView

from app.models import CargaArchivo, FuenteDatos, Proyecto, Sitio, Usuario


class DashboardView(TemplateView):
    template_name = "app/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sitio_count"] = Sitio.objects.count()
        context["proyecto_count"] = Proyecto.objects.count()
        context["fuente_count"] = FuenteDatos.objects.count()
        context["carga_count"] = CargaArchivo.objects.count()
        context["latest_sources"] = FuenteDatos.objects.select_related("proyecto", "reportador")[:5]
        context["docs_data_url"] = "/docs/pages/data.html"
        return context


class VisualizerView(TemplateView):
    template_name = "app/visualizer.html"


class DataModelView(TemplateView):
    template_name = "app/data_model.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        colors = ["#18735d", "#4f7cac", "#d18b2f", "#8f5f9f", "#c94c4c", "#6f7d3c"]
        groups = []

        for index, model in enumerate(apps.get_app_config("app").get_models()):
            fields = []
            fk = None
            for field in model._meta.fields:
                field_type = field.get_internal_type()
                choices = [
                    {"value": value, "label": str(label)}
                    for value, label in (getattr(field, "choices", None) or [])
                ]
                fields.append(
                    {
                        "name": field.name,
                        "type": field_type,
                        "desc": getattr(field, "verbose_name", field.name),
                        "choices_json": json.dumps(choices, ensure_ascii=False),
                    }
                )
                if fk is None and field.many_to_one and getattr(field, "related_model", None):
                    fk = {"field": field.name, "target": field.related_model.__name__}

            groups.append(
                {
                    "id": model._meta.model_name,
                    "model": model.__name__,
                    "name": model._meta.verbose_name_plural.title(),
                    "fields": fields,
                    "fk": fk,
                    "color": colors[index % len(colors)],
                }
            )

        context["groups"] = groups
        return context


def chart_data(request):
    return JsonResponse(
        {
            "by_year": [],
            "by_gas": [],
            "by_sector": [
                {"label": "Proyectos", "value": Proyecto.objects.count()},
                {"label": "Sitios", "value": Sitio.objects.count()},
                {"label": "Fuentes", "value": FuenteDatos.objects.count()},
                {"label": "Usuarios", "value": Usuario.objects.count()},
            ],
        },
        json_dumps_params={"ensure_ascii": False},
    )
