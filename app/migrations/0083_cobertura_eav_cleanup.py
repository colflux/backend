# Cierra el refactor de Cobertura: quita las 6 columnas viejas y el FK
# Sitio.cobertura (ya migrados a filas Cobertura por 0082) y endurece
# sitio/nombre a NOT NULL -ya no pueden quedar filas viejas sin migrar en
# este punto-.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0082_backfill_cobertura_eav'),
    ]

    operations = [
        migrations.RemoveField(model_name='cobertura', name='clima_koeppen'),
        migrations.RemoveField(model_name='cobertura', name='cobertura_clc'),
        migrations.RemoveField(model_name='cobertura', name='cobertura_igbp'),
        migrations.RemoveField(model_name='cobertura', name='cobertura_ipcc'),
        migrations.RemoveField(model_name='cobertura', name='cobertura_nombre_comun'),
        migrations.RemoveField(model_name='cobertura', name='suelo_ipcc'),
        migrations.RemoveField(model_name='sitio', name='cobertura'),
        migrations.AlterField(
            model_name='cobertura',
            name='sitio',
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE, related_name='coberturas',
                to='app.sitio', verbose_name='sitio',
            ),
        ),
        migrations.AlterField(
            model_name='cobertura',
            name='nombre',
            field=models.CharField(max_length=160, verbose_name='nombre reportado'),
        ),
        migrations.AlterModelOptions(
            name='cobertura',
            options={'ordering': ['sitio', 'tipo'], 'verbose_name': 'cobertura', 'verbose_name_plural': 'coberturas'},
        ),
        migrations.AddConstraint(
            model_name='cobertura',
            constraint=models.UniqueConstraint(fields=('sitio', 'tipo', 'nombre'), name='cobertura_unica_por_sitio_tipo_nombre'),
        ),
    ]
