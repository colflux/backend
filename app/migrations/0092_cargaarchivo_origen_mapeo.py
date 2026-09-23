import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0091_passwordresettoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='cargaarchivo',
            name='origen_mapeo',
            field=models.CharField(
                choices=[('manual', 'Mapeo manual (Gestión de Datos)'), ('ia_chat', 'Mapeo propuesto por IA (formulario web)')],
                default='manual', help_text='Quién propuso el mapeo de columnas: una persona (Gestión de Datos) o la IA (formulario web).',
                max_length=20, verbose_name='origen del mapeo',
            ),
        ),
        migrations.AddField(
            model_name='cargaarchivo',
            name='validado_por',
            field=models.ForeignKey(
                blank=True, help_text='Persona del equipo que revisó y confirmó una carga con origen_mapeo=ia_chat.',
                null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='cargas_validadas', to='app.usuario', verbose_name='validado por',
            ),
        ),
        migrations.AddField(
            model_name='cargaarchivo',
            name='fecha_validacion',
            field=models.DateTimeField(blank=True, null=True, verbose_name='fecha de validación'),
        ),
    ]
