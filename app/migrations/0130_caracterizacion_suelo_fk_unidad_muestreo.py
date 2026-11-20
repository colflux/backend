from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0129_alter_filabronce_hoja'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='caracterizacionmuestreosuelo',
            name='sitio',
        ),
        migrations.RemoveField(
            model_name='caracterizacionmuestreosuelo',
            name='muestreo_id',
        ),
        migrations.RemoveField(
            model_name='caracterizacionmuestreosuelo',
            name='tipo_de_suelo',
        ),
        migrations.AddField(
            model_name='caracterizacionmuestreosuelo',
            name='unidad_muestreo',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='caracterizaciones_suelo',
                to='app.unidadmuestreo',
                verbose_name='unidad de muestreo',
                default=None,
            ),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='caracterizacionmuestreosuelo',
            options={'ordering': ['unidad_muestreo'], 'verbose_name': 'caracterización muestreo suelo', 'verbose_name_plural': 'caracterizaciones muestreo suelo'},
        ),
    ]
