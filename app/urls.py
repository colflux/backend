from django.urls import path

from . import views

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("api/fuentes-datos/", views.fuentes_datos_api, name="fuentes-datos-api"),
]
