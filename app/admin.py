from django.contrib import admin

from .models import (
    DatasetMetadata, EmissionRecord, EmissionSource, Gas, Region, Sector,
    Proyecto, SitioMonitoreo, RegistroFlujoCamara,
    Cobertura, Disturbio, Caracterizacion, CaracterizacionMuestreo,
    VegetacionAnillo, Distancias,
    RegistroBiomasa, CaracterizacionParcela,
)


@admin.register(DatasetMetadata)
class DatasetMetadataAdmin(admin.ModelAdmin):
    list_display = ("name", "source", "version", "publication_year")
    search_fields = ("name", "source", "description")


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "region_type", "parent")
    list_filter = ("region_type",)
    search_fields = ("name", "code")


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ("name", "ipcc_code")
    search_fields = ("name", "ipcc_code")


@admin.register(Gas)
class GasAdmin(admin.ModelAdmin):
    list_display = ("chemical_formula", "name", "gwp_100")
    search_fields = ("name", "chemical_formula")


@admin.register(EmissionSource)
class EmissionSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "sector")
    list_filter = ("sector",)
    search_fields = ("name", "description")


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ("year", "region", "sector", "source", "gas", "co2e_tonnes", "data_quality")
    list_filter = ("year", "region", "sector", "gas", "data_quality")
    search_fields = ("region__name", "sector__name", "source__name", "notes")


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "created_at")
    search_fields = ("codigo", "nombre")


@admin.register(SitioMonitoreo)
class SitioMonitoreoAdmin(admin.ModelAdmin):
    list_display = ("codigo_sitio", "proyecto", "region_natural", "ecosistema", "departamento", "latitud", "longitud")
    list_filter = ("region_natural", "ecosistema", "departamento", "pendiente")
    search_fields = ("codigo_sitio", "proyecto__codigo", "sitio_urbano_cercano")
    raw_id_fields = ("proyecto",)


@admin.register(RegistroFlujoCamara)
class RegistroFlujoCamaraAdmin(admin.ModelAdmin):
    list_display = ("codigo_metadatos", "sitio", "created_at")
    search_fields = ("codigo_metadatos", "sitio__codigo_sitio")
    raw_id_fields = ("sitio",)


@admin.register(Cobertura)
class CoberturaAdmin(admin.ModelAdmin):
    list_display = ("registro", "cobertura_ipcc", "cobertura_clc", "cobertura_humedal", "clima_koeppen")
    list_filter = ("cobertura_humedal", "clima_koeppen")
    search_fields = ("registro__codigo_metadatos", "cobertura_nom_comun")
    raw_id_fields = ("registro",)


@admin.register(Disturbio)
class DisturbioAdmin(admin.ModelAdmin):
    list_display = ("registro", "tipo_disturbio", "uso_actual", "estado_actual", "propiedad_tierra")
    list_filter = ("tipo_disturbio", "uso_actual", "estado_actual", "propiedad_tierra")
    search_fields = ("registro__codigo_metadatos",)
    raw_id_fields = ("registro",)


@admin.register(Caracterizacion)
class CaracterizacionAdmin(admin.ModelAdmin):
    list_display = ("registro", "tipo_de_suelo", "microtopografia", "diametro_anillo")
    list_filter = ("tipo_de_suelo", "microtopografia")
    search_fields = ("registro__codigo_metadatos", "tratamiento")
    raw_id_fields = ("registro",)


@admin.register(CaracterizacionMuestreo)
class CaracterizacionMuestreoAdmin(admin.ModelAdmin):
    list_display = ("registro", "profundidad_perfil", "intervalos_perfil",
                    "monitoreo_macrofosiles", "monitoreo_datacion",
                    "monitoreo_densidad_aparente", "monitoreo_cos")
    list_filter = ("monitoreo_macrofosiles", "monitoreo_datacion",
                   "monitoreo_densidad_aparente", "monitoreo_cos",
                   "protocolo_densidad_aparente", "protocolo_cos")
    search_fields = ("registro__codigo_metadatos", "protocolo_macrofosiles", "protocolo_datacion")
    raw_id_fields = ("registro",)
    fieldsets = (
        ("Identificación", {"fields": ("registro",)}),
        ("Perfil", {"fields": ("profundidad_perfil", "intervalos_perfil")}),
        ("Macrofósiles", {"fields": ("monitoreo_macrofosiles", "protocolo_macrofosiles")}),
        ("Datación", {"fields": ("monitoreo_datacion", "protocolo_datacion")}),
        ("Densidad Aparente", {"fields": ("monitoreo_densidad_aparente", "protocolo_densidad_aparente")}),
        ("Carbono Orgánico del Suelo (COS)", {"fields": ("monitoreo_cos", "protocolo_cos")}),
    )


@admin.register(VegetacionAnillo)
class VegetacionAnilloAdmin(admin.ModelAdmin):
    list_display = ("registro", "cobertura_vegetal_primaria", "porcentaje_cob_veg_pri",
                    "cobertura_vegetal_secundaria", "porcentaje_cob_veg_sec")
    search_fields = ("registro__codigo_metadatos", "cobertura_vegetal_primaria")
    raw_id_fields = ("registro",)


@admin.register(Distancias)
class DistanciasAdmin(admin.ModelAdmin):
    list_display = ("registro", "distancia_drenaje", "distancia_fuego",
                    "distancia_pastoreo", "distancia_cultivo")
    search_fields = ("registro__codigo_metadatos",)
    raw_id_fields = ("registro",)


@admin.register(RegistroBiomasa)
class RegistroBiomasaAdmin(admin.ModelAdmin):
    list_display = ("codigo_metadatos", "sitio", "parcela", "created_at")
    search_fields = ("codigo_metadatos", "sitio__codigo_sitio", "parcela")
    raw_id_fields = ("sitio",)


@admin.register(CaracterizacionParcela)
class CaracterizacionParcelaAdmin(admin.ModelAdmin):
    list_display = ("registro", "unidad_de_muestreo", "area", "estatus_parcela",
                    "fecha_instalacion", "monitoreo_biomasa_aerea", "monitoreo_flora")
    list_filter = ("estatus_parcela", "unidad_de_muestreo",
                   "monitoreo_biomasa_aerea", "monitoreo_biomasa_subterranea",
                   "monitoreo_flora", "monitoreo_rasgos_funcionales")
    search_fields = ("registro__codigo_metadatos",)
    raw_id_fields = ("registro",)
    fieldsets = (
        ("Identificación", {"fields": ("registro",)}),
        ("Parcela", {"fields": ("unidad_de_muestreo", "area", "estatus_parcela", "fecha_instalacion")}),
        ("Biomasa Aérea", {"fields": ("monitoreo_biomasa_aerea", "protocolo_biomasa_aerea")}),
        ("Biomasa Subterránea", {"fields": ("monitoreo_biomasa_subterranea", "protocolo_biomasa_subterranea")}),
        ("Flora", {"fields": ("monitoreo_flora", "protocolo_flora")}),
        ("Rasgos Funcionales", {"fields": ("monitoreo_rasgos_funcionales", "protocolo_rasgos_funcionales")}),
    )
