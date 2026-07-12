from django.db import models

from .base import TimestampedModel


class RolUsuario(TimestampedModel):
    """Catálogo de roles que puede tener un usuario (coordinador, investigador, técnico, …)."""

    codigo = models.CharField("código", max_length=80, unique=True)
    nombre = models.CharField("nombre", max_length=120)

    class Meta:
        verbose_name = "rol de usuario"
        verbose_name_plural = "roles de usuario"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Usuario(TimestampedModel):
    """Persona vinculada a la red: datos de contacto, institución y roles que desempeña."""

    nombre = models.CharField("nombre", max_length=255)
    cargo = models.CharField("cargo", max_length=255, blank=True)
    correo_institucional = models.EmailField("correo institucional", blank=True)
    correo = models.EmailField("correo personal", blank=True)
    institucion = models.ForeignKey(
        "app.Institucion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios",
        verbose_name="institución",
    )
    roles = models.ManyToManyField(
        RolUsuario,
        through="UsuarioRol",
        related_name="usuarios",
        blank=True,
    )

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class UsuarioRol(models.Model):
    """Relación entre un usuario y uno de sus roles."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    rol = models.ForeignKey(RolUsuario, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "usuario rol"
        verbose_name_plural = "usuarios roles"
        unique_together = [("usuario", "rol")]

    def __str__(self):
        return f"{self.usuario} — {self.rol}"


class FuenteDatos(TimestampedModel):
    """Fuente de datos reportada a un proyecto (archivo Excel/CSV, shapefile, API, …) y su estado de procesamiento."""

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
        Usuario, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fuentes_datos", verbose_name="reportador",
    )

    nombre = models.CharField("nombre", max_length=255)
    descripcion = models.TextField("descripción", blank=True)
    tipo = models.CharField("tipo", max_length=20, choices=TIPO_CHOICES, default="excel")
    url = models.CharField("enlace o ruta al archivo", max_length=2048, blank=True)
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
    """Proceso ETL de carga de un archivo de una fuente de datos: inspección de columnas, mapeo, validación e importación."""

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
    """Mapeo de una columna del archivo cargado hacia un campo del modelo destino, con su transformación."""

    TRANSFORMACION_CHOICES = [
        ("directo", "Directo"),
        ("lookup", "Lookup / FK"),
        ("split", "Split"),
        ("fecha", "Parsear fecha"),
        ("constante", "Valor constante"),
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
    valor_constante = models.CharField(
        "valor constante", max_length=500, blank=True, default="",
        help_text="Valor fijo para todas las filas cuando la transformación es 'constante' (atributo sin columna en la fuente).",
    )

    class Meta:
        verbose_name = "mapeo de columna"
        verbose_name_plural = "mapeos de columnas"
        unique_together = [("carga", "columna_origen")]
        ordering = ["columna_origen"]

    def __str__(self):
        destino = f"{self.modelo_destino}.{self.campo_destino}" if self.modelo_destino else "ignorar"
        return f"{self.columna_origen} → {destino}"
