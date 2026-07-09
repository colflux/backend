from django.db import migrations, models
import django.db.models.deletion


BIBLIOGRAPHY_TYPES = [
    "Article",
    "Book",
    "Booklet",
    "Inbook",
    "Incollection",
    "Inproceedings",
    "Manual",
    "Mastersthesis",
    "Misc",
    "Other",
    "Phdthesis",
    "Proceedings",
    "Techreport",
    "Unpublished",
]


def seed_types(apps, schema_editor):
    PublicacionType = apps.get_model("app", "PublicacionType")
    for nombre in BIBLIOGRAPHY_TYPES:
        PublicacionType.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0004_mapeocolumna"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicacionType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=80, unique=True, verbose_name="nombre")),
            ],
            options={
                "verbose_name": "tipo de publicación",
                "verbose_name_plural": "tipos de publicación",
                "ordering": ["nombre"],
            },
        ),
        migrations.RunPython(seed_types, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="publicacion",
            name="bibliography_type",
        ),
        migrations.AddField(
            model_name="publicacion",
            name="bibliography_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="publicaciones",
                to="app.publicaciontype",
                verbose_name="tipo de referencia",
            ),
        ),
    ]
