# El backfill (0110) crea filas nuevas de CoberturaManual sin sitio/nombre
# (ya usan unidad_muestreo/valor) — aflojar estos dos campos a nullable antes,
# o esas inserciones violan el NOT NULL heredado del esquema viejo.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0108_cobertura_manual_rename'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coberturamanual',
            name='sitio',
            field=models.ForeignKey(
                null=True, blank=True, on_delete=models.deletion.CASCADE,
                related_name='coberturas_viejas', to='app.sitio', verbose_name='sitio',
            ),
        ),
        migrations.AlterField(
            model_name='coberturamanual',
            name='nombre',
            field=models.CharField(max_length=160, blank=True, verbose_name='nombre reportado'),
        ),
    ]
