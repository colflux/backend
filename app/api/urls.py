from django.urls import include, path
from rest_framework.routers import DefaultRouter

from app.api.dashboard.views import DashboardView
from app.api.datos.views import FuenteDatosViewSet, fuentes_datos_api
from app.api.etl.views import campos_destino, mapeo_carga, upload_archivo, validar_carga
from app.api.institucion.views import InstitucionViewSet
from app.api.proyecto.views import ProyectoViewSet
from app.api.reportador.views import ReportadorViewSet

router = DefaultRouter()
router.register("api/fuentes-datos-crud", FuenteDatosViewSet, basename="fuentes-datos-crud")
router.register("api/proyectos", ProyectoViewSet, basename="proyectos")
router.register("api/responsables", ReportadorViewSet, basename="responsables")
router.register("api/instituciones", InstitucionViewSet, basename="instituciones")

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("api/fuentes-datos/", fuentes_datos_api, name="fuentes-datos-api"),
    path("api/fuentes-datos/crear/", FuenteDatosViewSet.as_view({"post": "create"}), name="fuentes-datos-crear"),
    path("api/fuentes-datos/<int:fuente_id>/upload/", upload_archivo, name="fuentes-datos-upload"),
    path("api/proyectos/crear/", ProyectoViewSet.as_view({"post": "create"}), name="proyectos-crear"),
    path("api/responsables/crear/", ReportadorViewSet.as_view({"post": "create"}), name="responsables-crear"),
    path("api/etl/campos-destino/", campos_destino, name="etl-campos-destino"),
    path("api/fuentes-datos/<int:fuente_id>/carga/<int:carga_id>/mapeo/", mapeo_carga, name="mapeo-carga"),
    path("api/fuentes-datos/<int:fuente_id>/carga/<int:carga_id>/validar/", validar_carga, name="validar-carga"),
    path("", include(router.urls)),
]
