import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DatasetMetadata",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=180, verbose_name="nombre")),
                ("source", models.CharField(blank=True, max_length=240, verbose_name="fuente")),
                ("version", models.CharField(blank=True, max_length=80)),
                ("publication_year", models.PositiveIntegerField(blank=True, null=True, verbose_name="ano de publicacion")),
                ("description", models.TextField(blank=True, verbose_name="descripcion")),
                ("license", models.CharField(blank=True, max_length=120, verbose_name="licencia")),
            ],
            options={"verbose_name": "metadato de dataset", "verbose_name_plural": "metadatos de datasets", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Gas",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120, verbose_name="nombre")),
                ("chemical_formula", models.CharField(max_length=24, unique=True, verbose_name="formula")),
                ("gwp_100", models.DecimalField(decimal_places=3, default=1, max_digits=12, verbose_name="PCG 100 anos")),
            ],
            options={"verbose_name": "gas", "verbose_name_plural": "gases", "ordering": ["chemical_formula"]},
        ),
        migrations.CreateModel(
            name="Sector",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=160, unique=True, verbose_name="nombre")),
                ("ipcc_code", models.CharField(blank=True, max_length=40, verbose_name="codigo IPCC")),
                ("description", models.TextField(blank=True, verbose_name="descripcion")),
            ],
            options={"verbose_name": "sector", "verbose_name_plural": "sectores", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Region",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=160, verbose_name="nombre")),
                ("code", models.CharField(blank=True, max_length=40, verbose_name="codigo")),
                ("region_type", models.CharField(choices=[("country", "Pais"), ("department", "Departamento"), ("municipality", "Municipio"), ("basin", "Cuenca")], default="department", max_length=24, verbose_name="tipo")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="children", to="app.region")),
            ],
            options={"verbose_name": "region", "verbose_name_plural": "regiones", "ordering": ["name"], "unique_together": {("name", "region_type", "parent")}},
        ),
        migrations.CreateModel(
            name="EmissionSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=180, verbose_name="nombre")),
                ("description", models.TextField(blank=True, verbose_name="descripcion")),
                ("sector", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sources", to="app.sector")),
            ],
            options={"verbose_name": "fuente emisora", "verbose_name_plural": "fuentes emisoras", "ordering": ["sector__name", "name"], "unique_together": {("name", "sector")}},
        ),
        migrations.CreateModel(
            name="EmissionRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("year", models.PositiveIntegerField(verbose_name="ano")),
                ("value_tonnes", models.DecimalField(decimal_places=3, max_digits=18, verbose_name="toneladas de gas")),
                ("co2e_tonnes", models.DecimalField(decimal_places=3, max_digits=18, verbose_name="toneladas CO2e")),
                ("unit", models.CharField(default="t", max_length=40, verbose_name="unidad original")),
                ("method", models.CharField(blank=True, max_length=160, verbose_name="metodo")),
                ("data_quality", models.CharField(choices=[("activity", "Dato de actividad"), ("measured", "Medido"), ("estimated", "Estimado")], default="estimated", max_length=24, verbose_name="calidad del dato")),
                ("notes", models.TextField(blank=True, verbose_name="notas")),
                ("dataset", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="records", to="app.datasetmetadata")),
                ("gas", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="records", to="app.gas")),
                ("region", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="records", to="app.region")),
                ("sector", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="records", to="app.sector")),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="records", to="app.emissionsource")),
            ],
            options={"verbose_name": "registro de emision", "verbose_name_plural": "registros de emisiones", "ordering": ["-year", "region__name", "sector__name"], "unique_together": {("dataset", "region", "sector", "source", "gas", "year")}},
        ),
        migrations.AddIndex(model_name="emissionrecord", index=models.Index(fields=["year"], name="emissions_e_year_e5e10c_idx")),
        migrations.AddIndex(model_name="emissionrecord", index=models.Index(fields=["region", "year"], name="emissions_e_region__b35ace_idx")),
        migrations.AddIndex(model_name="emissionrecord", index=models.Index(fields=["sector", "year"], name="emissions_e_sector__bc1b56_idx")),
        migrations.AddIndex(model_name="emissionrecord", index=models.Index(fields=["gas", "year"], name="emissions_e_gas_id_d1e897_idx")),
    ]
