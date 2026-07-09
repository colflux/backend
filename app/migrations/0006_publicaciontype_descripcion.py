from django.db import migrations, models


DESCRIPCIONES = {
    "Article":        "Artículo publicado en una revista o journal académico.",
    "Book":           "Libro completo con uno o más autores.",
    "Booklet":        "Obra impresa sin editorial formal, como folletos o libretos.",
    "Inbook":         "Capítulo o sección específica dentro de un libro.",
    "Incollection":   "Contribución dentro de un libro de colección con editor.",
    "Inproceedings":  "Artículo publicado en las memorias de una conferencia.",
    "Manual":         "Documentación técnica o manual de usuario.",
    "Mastersthesis":  "Tesis de maestría.",
    "Misc":           "Referencia que no encaja en ninguna otra categoría.",
    "Other":          "Otro tipo de publicación no clasificado.",
    "Phdthesis":      "Tesis doctoral.",
    "Proceedings":    "Memorias completas de una conferencia o simposio.",
    "Techreport":     "Informe técnico publicado por una institución u organización.",
    "Unpublished":    "Trabajo que existe pero no ha sido publicado formalmente.",
}


def seed_descripciones(apps, schema_editor):
    PublicacionType = apps.get_model("app", "PublicacionType")
    for obj in PublicacionType.objects.all():
        obj.descripcion = DESCRIPCIONES.get(obj.nombre, "")
        obj.save(update_fields=["descripcion"])


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0005_publicaciontype_publicacion_bibliography_type_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicaciontype",
            name="descripcion",
            field=models.TextField(blank=True, verbose_name="descripción"),
        ),
        migrations.RunPython(seed_descripciones, migrations.RunPython.noop),
    ]
