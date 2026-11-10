# El viejo 'Disturbio' ya se borró (0114) -queda libre el nombre final-:
# renombra el catálogo nuevo 'TipoDisturbio' a 'Disturbio', como queda
# definido en app/models/cobertura.py.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0114_borrar_disturbio_viejo'),
    ]

    operations = [
        migrations.RenameModel(old_name='TipoDisturbio', new_name='Disturbio'),
    ]
