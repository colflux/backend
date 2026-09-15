from django.conf import settings
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
    """Persona vinculada a la red: datos de contacto, institución y nivel de acceso a la plataforma."""

    # Jerarquía en cascada: cada nivel incluye todo lo que puede hacer el
    # anterior. ciudadano = igual que un visitante sin cuenta (solo lectura
    # pública); investigador = además puede descargar datos; reportador =
    # además puede subir datos; admin = acceso total.
    NIVELES_ACCESO = ("ciudadano", "investigador", "reportador", "admin")
    NIVEL_CHOICES = [
        ("ciudadano", "Ciudadano"),
        ("investigador", "Investigador"),
        ("reportador", "Reportador"),
        ("admin", "Administrador"),
    ]

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
    nivel = models.CharField(
        "nivel de acceso", max_length=20, choices=NIVEL_CHOICES, default="ciudadano",
    )
    auth_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuario",
        verbose_name="cuenta de acceso",
    )

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def tiene_nivel(self, minimo):
        """True si este usuario tiene al menos el nivel `minimo` en la cascada."""
        return self.NIVELES_ACCESO.index(self.nivel) >= self.NIVELES_ACCESO.index(minimo)


class SolicitudNivel(TimestampedModel):
    """Pedido de un usuario para subir su nivel de acceso, que un admin aprueba o rechaza.

    Aprobarla actualiza `Usuario.nivel` al nivel solicitado; rechazarla solo
    cambia el estado. Un usuario solo puede tener una solicitud `pendiente`
    a la vez (se valida en la vista, no acá).
    """

    NIVELES_SOLICITABLES = [n for n in Usuario.NIVELES_ACCESO if n != "ciudadano"]
    NIVEL_CHOICES = [c for c in Usuario.NIVEL_CHOICES if c[0] != "ciudadano"]
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("aprobada", "Aprobada"),
        ("rechazada", "Rechazada"),
    ]

    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name="solicitudes_nivel", verbose_name="usuario",
    )
    nivel_solicitado = models.CharField("nivel solicitado", max_length=20, choices=NIVEL_CHOICES)
    motivo = models.TextField("motivo", blank=True)
    estado = models.CharField("estado", max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    resuelta_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_resueltas",
        verbose_name="resuelta por",
    )

    class Meta:
        verbose_name = "solicitud de nivel"
        verbose_name_plural = "solicitudes de nivel"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.usuario.nombre} → {self.nivel_solicitado} ({self.estado})"


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
    pks_importados = models.JSONField(
        "pks creados/vinculados por esta carga", default=dict, blank=True,
        help_text='Acumula, por modelo, los pk que esta carga creó o reutilizó al importar. '
                   'Ej: {"SubmuestraGEI": [10, 11, 12]}. Permite mostrar solo los datos de esta carga en el panel de visualización.',
    )

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
        ("regex", "Expresión regular"),
        ("escala", "Conversión de unidades (factor de escala)"),
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
    regex_patron = models.CharField(
        "patrón regex", max_length=255, blank=True, default="",
        help_text="Expresión regular aplicada al valor de origen cuando la transformación es 'regex'. Si tiene un "
                   "grupo de captura se usa ese grupo; si no, se usa la coincidencia completa. Sin coincidencia, "
                   "el valor queda vacío. Ej: '^SWAMP_CO2_(.+?)_\\d+$' sobre 'SWAMP_CO2_S1_old_3' da 'S1_old'.",
    )
    factor_escala = models.DecimalField(
        "factor de escala", max_digits=20, decimal_places=10, null=True, blank=True,
        help_text="Multiplica el valor de origen por este factor cuando la transformación es 'escala', para "
                   "convertir unidades sin depender de que el archivo fuente ya venga en la unidad del campo "
                   "destino (p. ej. 0.01 para pasar centímetros a metros). Solo aplica a campos numéricos.",
    )

    ESTRATEGIA_NULOS_CHOICES = [
        ("dejar_null", "Dejar vacío"),
        ("rellenar", "Rellenar hacia abajo"),
        ("manual", "Ingresar valor manual"),
        ("ignorar_fila", "Ignorar registros sin este valor"),
    ]
    estrategia_nulos = models.CharField(
        "estrategia para datos faltantes", max_length=20,
        choices=ESTRATEGIA_NULOS_CHOICES, default="dejar_null",
        help_text="Qué hacer con las filas donde esta columna viene vacía: dejarlas vacías, repetir hacia abajo el "
                   "último valor visto, usar un valor fijo, o no crear el registro para esas filas.",
    )
    valor_relleno_manual = models.CharField(
        "valor manual para nulos", max_length=500, blank=True, default="",
        help_text="Valor usado para las filas vacías de esta columna cuando estrategia_nulos es 'manual'.",
    )
    tipo_cobertura = models.ForeignKey(
        "app.TipoCobertura", on_delete=models.PROTECT, null=True, blank=True,
        related_name="mapeos_columna", verbose_name="tipo de cobertura",
        help_text="Solo aplica cuando modelo_destino es 'Cobertura': etiqueta con qué sistema de "
                   "clasificación (CLC, IPCC, IGBP, …) se guarda el valor de esta columna, ya que un "
                   "sitio puede tener varias filas de Cobertura (una por columna/sistema de origen).",
    )

    class Meta:
        verbose_name = "mapeo de columna"
        verbose_name_plural = "mapeos de columnas"
        # Antes era único por (carga, columna_origen): una columna origen solo
        # podía alimentar un destino. Se amplía a la tupla completa para poder
        # mapear la misma columna a más de un modelo/campo (p. ej. una columna
        # "ID" que sirve como nombre de UnidadExperimental -vía regex- y,
        # completa, como nombre de UnidadMuestreo).
        unique_together = [("carga", "columna_origen", "modelo_destino", "campo_destino")]
        ordering = ["columna_origen"]

    def __str__(self):
        destino = f"{self.modelo_destino}.{self.campo_destino}" if self.modelo_destino else "ignorar"
        return f"{self.columna_origen} → {destino}"
