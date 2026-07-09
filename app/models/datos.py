from django.db import models

from .base import TimestampedModel


class Reportador(TimestampedModel):
    nombre = models.CharField("nombre", max_length=255)
    correo_institucional = models.EmailField("correo institucional", blank=True)
    correo = models.EmailField("correo personal", blank=True)
    institucion_asociada = models.CharField("institución asociada", max_length=255, blank=True)

    class Meta:
        verbose_name = "reportador"
        verbose_name_plural = "reportadores"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class FuenteDatos(TimestampedModel):
    TIPO_CHOICES = [
        ("excel", "Excel (.xlsx / .xls)"),
        ("csv", "CSV"),
        ("shapefile", "Shapefile (.shp)"),
        ("geojson", "GeoJSON"),
        ("api", "API externa"),
        ("base_de_datos", "Base de datos"),
        ("otro", "Otro"),
    ]
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente — sin procesar"),
        ("en_proceso", "En proceso"),
        ("completo", "Completo"),
        ("con_errores", "Con errores"),
    ]

    proyecto = models.ForeignKey(
        "app.Proyecto", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fuentes_datos", verbose_name="proyecto",
    )
    reportador = models.ForeignKey(
        Reportador, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fuentes_datos", verbose_name="reportador",
    )

    nombre = models.CharField("nombre", max_length=255)
    descripcion = models.TextField("descripción", blank=True)
    tipo = models.CharField("tipo", max_length=20, choices=TIPO_CHOICES, default="excel")
    url = models.URLField("enlace al archivo", max_length=2048, blank=True)
    estado = models.CharField("estado", max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    fecha_recepcion = models.DateField("fecha de recepción", null=True, blank=True)
    notas = models.TextField("notas", blank=True)

    class Meta:
        verbose_name = "fuente de datos"
        verbose_name_plural = "fuentes de datos"
        ordering = ["proyecto", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"


class CargaArchivo(TimestampedModel):
    ESTADO_CHOICES = [
        ("subido", "Archivo subido"),
        ("mapeado", "Mapeo definido"),
        ("validado", "Validación completada"),
        ("importado", "Importado a BD"),
    ]

    fuente = models.ForeignKey(
        FuenteDatos, on_delete=models.CASCADE,
        related_name="cargas", verbose_name="fuente de datos",
    )
    archivo = models.FileField("archivo", upload_to="cargas/%Y/%m/")
    hoja_activa = models.CharField("hoja activa", max_length=255, blank=True)
    estado = models.CharField("estado", max_length=20, choices=ESTADO_CHOICES, default="subido")
    columnas_raw = models.JSONField("columnas inspeccionadas", default=list)
    total_filas = models.IntegerField("total de filas", default=0)

    class Meta:
        verbose_name = "carga de archivo"
        verbose_name_plural = "cargas de archivos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Carga #{self.pk} — {self.fuente.nombre}"


class MapeoColumna(TimestampedModel):
    TRANSFORMACION_CHOICES = [
        ("directo", "Directo"),
        ("lookup", "Lookup / FK"),
        ("split", "Split"),
        ("fecha", "Parsear fecha"),
        ("ignorar", "Ignorar"),
    ]

    carga           = models.ForeignKey(
        CargaArchivo, on_delete=models.CASCADE,
        related_name="mapeos", verbose_name="carga",
    )
    columna_origen  = models.CharField("columna origen", max_length=255)
    modelo_destino  = models.CharField("modelo destino", max_length=100, blank=True)
    campo_destino   = models.CharField("campo destino", max_length=100, blank=True)
    transformacion  = models.CharField(
        "transformación", max_length=20,
        choices=TRANSFORMACION_CHOICES, default="directo",
    )
    mapeo_valores   = models.JSONField(
        "mapeo de valores", default=dict, blank=True,
        help_text='Traduce valores de origen a choices del campo destino. Ej: {"Journal Article": "articulo_revista"}',
    )

    class Meta:
        verbose_name = "mapeo de columna"
        verbose_name_plural = "mapeos de columnas"
        unique_together = [("carga", "columna_origen")]
        ordering = ["columna_origen"]

    def __str__(self):
        destino = f"{self.modelo_destino}.{self.campo_destino}" if self.modelo_destino else "ignorar"
        return f"{self.columna_origen} → {destino}"
