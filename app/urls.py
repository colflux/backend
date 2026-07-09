from django.urls import path

from . import views

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("api/fuentes-datos/", views.fuentes_datos_api, name="fuentes-datos-api"),
    path("api/fuentes-datos/crear/", views.crear_fuente_datos, name="fuentes-datos-crear"),
    path("api/fuentes-datos/<int:fuente_id>/upload/", views.upload_archivo, name="fuentes-datos-upload"),
    path("api/proyectos/crear/", views.crear_proyecto, name="proyectos-crear"),
    path("api/etl/campos-destino/", views.campos_destino, name="etl-campos-destino"),
    path("api/fuentes-datos/<int:fuente_id>/carga/<int:carga_id>/mapeo/", views.mapeo_carga, name="mapeo-carga"),
    path("api/fuentes-datos/<int:fuente_id>/carga/<int:carga_id>/validar/", views.validar_carga, name="validar-carga"),
    path("api/catalogo-tecnico/", views.catalogo_tecnico, name="catalogo-tecnico"),
    path("api/db-erd/", views.db_erd, name="db-erd"),
]
