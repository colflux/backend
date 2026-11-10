# Primer paso del rediseño de Disturbio: separa catálogo (tipo de disturbio)
# de instancia reportada (por unidad de muestreo). Se crea con el nombre
# temporal 'TipoDisturbio' porque el viejo modelo 'Disturbio' todavía existe
# -se necesitan ambos a la vez durante el backfill (0113)-; 0115 lo renombra
# a su nombre final 'Disturbio' una vez borrado el viejo (0114).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0111_cobertura_manual_endurecer'),
    ]

    operations = [
        migrations.CreateModel(
            name='TipoDisturbio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nombre', models.CharField(max_length=60, unique=True, verbose_name='nombre')),
            ],
            options={
                'verbose_name': 'tipo de disturbio',
                'verbose_name_plural': 'tipos de disturbio',
                'ordering': ['nombre'],
            },
        ),
        migrations.CreateModel(
            name='UnidadMuestreoDisturbio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('descripcion', models.TextField(blank=True, verbose_name='descripción')),
                ('fecha_inicio', models.DateField(blank=True, null=True, verbose_name='fecha de inicio')),
                ('fecha_fin', models.DateField(blank=True, null=True, verbose_name='fecha de fin')),
                ('incertidumbre_anios', models.PositiveIntegerField(blank=True, null=True, verbose_name='incertidumbre (años)')),
                ('fecha_reporte', models.DateField(blank=True, null=True, verbose_name='fecha de reporte')),
                ('anios_disturbio', models.PositiveIntegerField(blank=True, null=True, verbose_name='años de disturbio')),
                ('anios_desde_fin', models.PositiveIntegerField(blank=True, null=True, verbose_name='años desde fin del disturbio')),
                ('estado_actual', models.CharField(blank=True, choices=[
                    ('Intacto', 'Intacto'), ('Ligeramente_degradado', 'Ligeramente degradado'),
                    ('Moderadamente_degradado', 'Moderadamente degradado'), ('Severamente_degradado', 'Severamente degradado'),
                    ('En_recuperacion_natural', 'En recuperación natural'), ('En_restauracion_activa', 'En restauración activa'),
                    ('Estable', 'Estable'), ('En_transicion', 'En transición'),
                ], max_length=30, verbose_name='estado actual')),
                ('estado_conservacion', models.CharField(
                    blank=True, choices=[
                        ('Natural', 'Natural (sin manejo humano significativo)'),
                        ('Seminatural', 'Seminatural (manejo bajo, regeneración natural dominante)'),
                        ('Manejado', 'Manejado (aprovechamiento, ganadería, agroforestería)'),
                        ('Plantacion', 'Plantación (vegetación establecida y manejada)'),
                        ('Artificial_Urbano', 'Artificial / Urbano (superficie no natural)'),
                    ], help_text='Estado del ecosistema frente a la presencia de manejo humano (taxonomía del vocabulario IDEAM).',
                    max_length=20, verbose_name='estado de conservación',
                )),
                ('proteccion_legal', models.TextField(
                    blank=True, help_text='Si el sitio está bajo alguna figura de reserva, parque, santuario, etc.',
                    verbose_name='protección legal',
                )),
                ('es_dominante', models.BooleanField(default=False, verbose_name='es el disturbio dominante')),
                ('disturbio', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name='reportes',
                    to='app.tipodisturbio', verbose_name='tipo de disturbio',
                )),
                ('unidad_muestreo', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='disturbios',
                    to='app.unidadmuestreo', verbose_name='unidad de muestreo',
                )),
            ],
            options={
                'verbose_name': 'disturbio de unidad de muestreo',
                'verbose_name_plural': 'disturbios de unidad de muestreo',
                'ordering': ['unidad_muestreo', 'disturbio'],
            },
        ),
    ]
