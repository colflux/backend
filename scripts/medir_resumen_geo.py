"""Compara agregar en la base contra recorrer las filas en Python.

Uso:
    docker compose exec web python manage.py shell \\
        -c "exec(open('scripts/medir_resumen_geo.py').read())"

Solo lee datos: no modifica nada.
"""

import time

from django.db.models import Avg, Count, Max, Min

from app.models import SubmuestraGEI

DEP = "muestra__unidad_muestreo__sitio__vereda__municipio__departamento"

inicio = time.time()
qs = SubmuestraGEI.objects.exclude(fecha=None).select_related(
    "muestra__unidad_medida",
    "muestra__unidad_muestreo__sitio__vereda__municipio__departamento__region",
    "muestra__unidad_muestreo__unidad_experimental__proyecto",
)
grupos, filas = {}, 0
for sub in qs:
    filas += 1
    um = sub.muestra.unidad_muestreo
    sitio = um.sitio if um else None
    if sitio is None or sitio.vereda_id is None:
        continue
    muni = sitio.vereda.municipio if sitio.vereda.municipio_id else None
    dep = muni.departamento if muni and muni.departamento_id else None
    if dep is None:
        continue
    if sub.valor is not None:
        grupos.setdefault(dep.pk, []).append(float(sub.valor))
print("recorriendo en Python : %6.2f s | %3d grupos | %6d filas a memoria" % (time.time() - inicio, len(grupos), filas))

inicio = time.time()
res = list(
    SubmuestraGEI.objects.exclude(fecha=None)
    .exclude(**{DEP + "_id": None})
    .values(DEP + "_id")
    .annotate(n=Count("id"), prom=Avg("valor"), mn=Min("valor"), mx=Max("valor"))
)
print("agregando en SQL      : %6.2f s | %3d grupos | %6d filas a memoria" % (time.time() - inicio, len(res), len(res)))
