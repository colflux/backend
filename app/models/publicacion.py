from django.db import models

from .base import TimestampedModel
from .sitio import Sitio


class Publicacion(TimestampedModel):
    bibliography_type = models.CharField("tipo de referencia", max_length=80, blank=True)
    isbn = models.CharField("ISBN", max_length=20, blank=True)
    doi = models.CharField("DOI", max_length=255, blank=True)
    identifier = models.CharField("identificador", max_length=120, blank=True)
    titulo = models.TextField("título")
    journal = models.CharField("revista / journal", max_length=255, blank=True)
    volumen = models.CharField("volumen", max_length=20, blank=True)
    numero = models.CharField("número", max_length=20, blank=True)
    paginas = models.CharField("páginas", max_length=40, blank=True)
    anio = models.PositiveIntegerField("año", null=True, blank=True)
    mes = models.CharField("mes", max_length=20, blank=True)
    email = models.EmailField("email de contacto", blank=True)
    url = models.URLField("URL", max_length=2048, blank=True)
    abstract = models.TextField("resumen", blank=True)
    keywords = models.TextField("palabras clave", blank=True)
    validacion_campo = models.BooleanField("validación en campo", default=False)
    datos_disponibles_repositorio = models.BooleanField("datos disponibles en repositorio", default=False)

    autores = models.ManyToManyField("Autor", through="PublicacionAutor", related_name="publicaciones", blank=True)
    sitios = models.ManyToManyField(Sitio, through="PublicacionSitio", related_name="publicaciones", blank=True)

    class Meta:
        verbose_name = "publicación"
        verbose_name_plural = "publicaciones"
        ordering = ["-anio", "titulo"]

    def __str__(self):
        return self.titulo[:80]


class Autor(TimestampedModel):
    nombre = models.CharField("nombre", max_length=255)

    class Meta:
        verbose_name = "autor"
        verbose_name_plural = "autores"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class PublicacionAutor(models.Model):
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE)
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "publicación-autor"
        verbose_name_plural = "publicaciones-autores"
        unique_together = [("publicacion", "autor")]

    def __str__(self):
        return f"{self.autor} — {self.publicacion}"


class PublicacionSitio(models.Model):
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE)
    sitio = models.ForeignKey(Sitio, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "publicación-sitio"
        verbose_name_plural = "publicaciones-sitios"
        unique_together = [("publicacion", "sitio")]

    def __str__(self):
        return f"{self.sitio} — {self.publicacion}"


class ResultadoPublicacion(TimestampedModel):
    VARIABLE_CHOICES = [
        ("Biomasa_Aerea_C", "Biomasa aérea (C)"),
        ("Biomasa_Subterranea_C", "Biomasa subterránea (C)"),
        ("Biomasa_Total_C", "Biomasa total (C)"),
        ("COS", "Carbono orgánico del suelo (COS)"),
        ("MOM", "MOM"),
        ("AMP_TM", "AMP TM"),
        ("DFM", "DFM"),
        ("DGM", "DGM"),
        ("Hojarasca", "Hojarasca"),
        ("CO2_Flux", "Flujo CO₂"),
        ("CH4_Flux", "Flujo CH₄"),
        ("N2O_Flux", "Flujo N₂O"),
    ]

    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE, related_name="resultados")
    variable = models.CharField("variable", max_length=30, choices=VARIABLE_CHOICES)
    valor = models.DecimalField("valor", max_digits=18, decimal_places=6, null=True, blank=True)
    unidad = models.CharField("unidad", max_length=80, blank=True)
    error = models.DecimalField("error", max_digits=12, decimal_places=6, null=True, blank=True)
    metodologia = models.TextField("metodología", blank=True)

    class Meta:
        verbose_name = "resultado de publicación"
        verbose_name_plural = "resultados de publicación"
        ordering = ["publicacion", "variable"]

    def __str__(self):
        return f"{self.get_variable_display()} — {self.publicacion}"
