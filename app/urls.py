from django.urls import path

from . import views

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("api/fuentes-datos/", views.fuentes_datos_api, name="fuentes-datos-api"),
    path("api/fuentes-datos/crear/", views.crear_fuente_datos, name="fuentes-datos-crear"),
    path("api/proyectos/crear/", views.crear_proyecto, name="proyectos-crear"),
]
