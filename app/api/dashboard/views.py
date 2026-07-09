from django.views.generic import TemplateView

from app.models import Proyecto, Sitio


class DashboardView(TemplateView):
    template_name = "app/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sitio_count"] = Sitio.objects.count()
        context["proyecto_count"] = Proyecto.objects.count()
        return context
