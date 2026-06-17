from django.urls import path

from . import views


urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("emisiones/", views.EmissionRecordListView.as_view(), name="emission-list"),
    path("emisiones/nueva/", views.EmissionRecordCreateView.as_view(), name="emission-create"),
    path("emisiones/<int:pk>/", views.EmissionRecordDetailView.as_view(), name="emission-detail"),
    path("emisiones/<int:pk>/editar/", views.EmissionRecordUpdateView.as_view(), name="emission-update"),
    path("emisiones/<int:pk>/eliminar/", views.EmissionRecordDeleteView.as_view(), name="emission-delete"),
    path("visualizador/", views.VisualizerView.as_view(), name="visualizer"),
    path("api/chart-data/", views.chart_data, name="chart-data"),
    path("modelo-datos/", views.DataModelView.as_view(), name="data-model"),
]
