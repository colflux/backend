"""Migra a la RDS real los datos de contenido que quedaron atrapados en el
volumen de Docker Postgres local huérfano (`backend_postgres_data`), tras el
cambio del proyecto a conectar directo a RDS.

Requiere que ese volumen esté levantado en un contenedor aparte, accesible
desde el contenedor `web` en `host.docker.internal:55432` (ver
personal/tasks/inprogress/migrar-datos-docker-local-a-produccion.md, repo
`context`, para el procedimiento completo). Cada tabla se procesa en su
propio paso (verificación de que RDS esté vacía + carga por lotes +
verificación de conteo) — nunca se usa TRUNCATE CASCADE, porque varias
tablas tienen FKs entrantes desde tablas nuevas que no existían en el
snapshot local. Si a mitad de camino se cae la conexión, solo se pierde el
lote/tabla en curso, nunca lo que ya quedó cargado.

Uso:

    python manage.py migrar_datos_locales --dry-run          # solo reporta
    python manage.py migrar_datos_locales                    # todo, en orden
    python manage.py migrar_datos_locales --tabla sitio       # solo esa tabla
    python manage.py migrar_datos_locales --desde sitio       # reanuda desde ahí

Este comando es de un solo uso — se puede borrar del repo una vez migrados
los datos y verificados en RDS.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from app.models import (
    AplicacionRegla, CargaArchivo, CaracterizacionMuestreoSuelo, Cobertura, ConfiguracionSensorGas,
    Disturbio, Equipo, FuenteDatos, IndividuoArboreo, MapeoColumna, MonitoreoParcela,
    MonitoreoSuelo, Municipio, MuestraAmbiental, MuestraBiomasa, MuestraGEI, MuestraMOM, Parcela,
    Proyecto, ProyectoInstitucion, ReglaAutollenado, Sitio, SubmuestraGEI, SubmuestraSuelo,
    TorreEc, TorreFuenteEnergia, Transecto, UnidadExperimental, UnidadMedida, UnidadMuestreo,
    UnidadMuestreoTipo, Vegetacion, Vereda,
)

ORIGEN = "origen"
LOTE = 1000

# Catálogos que ya coinciden entre local y RDS (mismos seeds de migración):
# Region, Departamento, Municipio, TipoCobertura, TipoMuestra, PublicacionType,
# RolUsuario — no se tocan.

# Catálogos con seed base igual + filas extra en local que sí hay que agregar
# (nuevo PK en RDS, no se preserva el PK local).
CATALOGOS_A_COMPLETAR = [
    (Equipo, "modelo"),
    (UnidadMedida, "codigo"),
    (UnidadMuestreoTipo, "nombre"),
]

# Institucion NO se migra: RDS ya tiene su propia fila real (creada después
# de que este volumen local quedara huérfano) y local no tiene ninguna fila
# que aportar. Además Usuario.institucion_id referencia esta tabla, así que
# un TRUNCATE...CASCADE sobre ella borraría a los usuarios reales de RDS.

# Tablas de "datos reales": cada una se carga por lotes preservando el PK
# original del local. Se verifica que la tabla en RDS esté vacía antes de
# cargar (nunca se usa TRUNCATE CASCADE: varias de estas tablas tienen FKs
# entrantes desde tablas que no existían en el snapshot local — p. ej.
# Sitio <- DocumentoConocimiento/MedicionRapidaChat — y un TRUNCATE CASCADE
# las arrastraría sin que este comando sepa que existen). Orden = dependencia
# (padres antes que hijos). "fk_a_nulear" fuerza esos campos a NULL al cargar
# (no se migran datos de usuarios: FuenteDatos.reportador es el único caso).
# "fk_diferida" son FKs que apuntan a una tabla que se carga DESPUÉS
# (dependencia circular) — se cargan en NULL y se parchan al final leyendo
# de nuevo el origen (no hace falta guardar estado entre pasos).
TABLAS_CONTENIDO = [
    dict(modelo=Proyecto, fk_diferida=["sitio_principal_id"]),
    dict(modelo=Vereda, remap_municipio=True),
    dict(modelo=Disturbio),
    dict(modelo=Vegetacion),
    dict(modelo=Sitio),
    dict(modelo=Cobertura),
    dict(modelo=ProyectoInstitucion),
    dict(modelo=UnidadExperimental),
    dict(modelo=FuenteDatos, fk_a_nulear=["reportador_id"]),
    dict(modelo=UnidadMuestreo),
    dict(modelo=Parcela),
    dict(modelo=Transecto),
    dict(modelo=MonitoreoParcela),
    dict(modelo=CaracterizacionMuestreoSuelo),
    dict(modelo=MonitoreoSuelo),
    dict(modelo=SubmuestraSuelo),
    dict(modelo=MuestraBiomasa),
    dict(modelo=IndividuoArboreo),
    dict(modelo=MuestraMOM),
    dict(modelo=MuestraAmbiental),
    dict(modelo=MuestraGEI),
    dict(modelo=SubmuestraGEI),
    dict(modelo=TorreEc, fk_diferida=["configuracion_principal_id"]),
    dict(modelo=ConfiguracionSensorGas),
    dict(modelo=TorreFuenteEnergia),
    dict(modelo=CargaArchivo),
    dict(modelo=MapeoColumna),
    dict(modelo=ReglaAutollenado),
    dict(modelo=AplicacionRegla),
]

NOMBRE_A_PASO = {paso["modelo"].__name__.lower(): paso for paso in TABLAS_CONTENIDO}

# Parches de FK diferida: (modelo, campo) -> se resuelve releyendo el origen
# una vez que la tabla referenciada ya está cargada. No depende de que los
# pasos hayan corrido en el mismo proceso.
PARCHES_FK_DIFERIDA = [
    (Proyecto, "sitio_principal_id"),
    (TorreEc, "configuracion_principal_id"),
]


class Command(BaseCommand):
    help = "Migra datos de contenido del Postgres local huérfano hacia la RDS real, tabla por tabla."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo reporta, no escribe nada.")
        parser.add_argument("--tabla", help="Migra solo esta tabla (nombre del modelo, minúsculas).")
        parser.add_argument("--desde", help="Migra desde esta tabla en adelante (para reanudar).")
        parser.add_argument("--sin-parches", action="store_true", help="No corre el parche de FKs diferidas al final.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        self._registrar_conexion_origen()

        pasos = self._seleccionar_pasos(options)

        self.stdout.write(self.style.WARNING(f"{'[DRY-RUN] ' if dry_run else ''}Pasos a correr: {', '.join(p['modelo'].__name__ for p in pasos)}"))

        if not options["tabla"] and not options["desde"]:
            self._migrar_catalogos(dry_run)

        for paso in pasos:
            self._migrar_tabla(paso, dry_run)

        if not dry_run and not options["sin_parches"] and not options["tabla"]:
            self._aplicar_parches_fk_diferida()

        self.stdout.write(self.style.SUCCESS("Listo."))

    def _seleccionar_pasos(self, options):
        if options["tabla"] and options["desde"]:
            raise CommandError("Usa --tabla o --desde, no ambos.")
        if options["tabla"]:
            paso = NOMBRE_A_PASO.get(options["tabla"].lower())
            if not paso:
                raise CommandError(f"Tabla desconocida: {options['tabla']}. Opciones: {', '.join(NOMBRE_A_PASO)}")
            return [paso]
        if options["desde"]:
            nombres = list(NOMBRE_A_PASO)
            if options["desde"].lower() not in NOMBRE_A_PASO:
                raise CommandError(f"Tabla desconocida: {options['desde']}. Opciones: {', '.join(nombres)}")
            idx = nombres.index(options["desde"].lower())
            return TABLAS_CONTENIDO[idx:]
        return TABLAS_CONTENIDO

    def _registrar_conexion_origen(self):
        settings.DATABASES[ORIGEN] = {
            **settings.DATABASES["default"],
            "HOST": "host.docker.internal",
            "PORT": "55432",
            "NAME": "ghg",
            "USER": "ghg",
            "PASSWORD": "ghg",
            "CONN_MAX_AGE": 0,
        }

    # ---- catálogos con filas extra (Equipo, UnidadMedida, UnidadMuestreoTipo) ----

    def _migrar_catalogos(self, dry_run):
        for modelo, campo_natural in CATALOGOS_A_COMPLETAR:
            existentes = set(modelo.objects.using("default").values_list(campo_natural, flat=True))
            faltantes = list(
                modelo.objects.using(ORIGEN).exclude(**{f"{campo_natural}__in": existentes})
            )
            self.stdout.write(f"{modelo.__name__}: {len(faltantes)} fila(s) nueva(s) por agregar")
            if not dry_run:
                for obj in faltantes:
                    obj.pk = None
                    obj._state.adding = True
                    obj.save(using="default")

    # ---- una tabla: TRUNCATE propio + carga por lotes + verificación ----

    def _migrar_tabla(self, paso, dry_run):
        modelo = paso["modelo"]
        total_origen = modelo.objects.using(ORIGEN).count()
        total_rds_antes = modelo.objects.using("default").count()
        self.stdout.write(f"\n== {modelo.__name__}: {total_origen} en local, {total_rds_antes} en RDS ==")
        if dry_run:
            return

        if total_rds_antes != 0:
            raise CommandError(
                f"{modelo.__name__} ya tiene {total_rds_antes} fila(s) en RDS — no se trunca "
                "automáticamente (riesgo de TRUNCATE CASCADE sobre tablas no previstas). "
                "Revisa manualmente antes de continuar."
            )

        if paso.get("remap_municipio"):
            creadas, saltadas = self._cargar_vereda_por_lotes()
            self.stdout.write(self.style.SUCCESS(f"  {modelo.__name__}: {creadas} creadas, {saltadas} sin municipio equivalente"))
        else:
            creadas = self._cargar_generico_por_lotes(paso)
            self.stdout.write(self.style.SUCCESS(f"  {modelo.__name__}: {creadas} filas cargadas"))

        self._resincronizar_secuencia(modelo)

        total_rds_despues = modelo.objects.using("default").count()
        if total_rds_despues != total_origen:
            self.stdout.write(self.style.ERROR(
                f"  ATENCIÓN: {modelo.__name__} quedó con {total_rds_despues}, se esperaban {total_origen}"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"  Verificado: {total_rds_despues}/{total_origen}"))

    def _resincronizar_secuencia(self, modelo):
        """Tras insertar PKs explícitos, la secuencia autoincremental de RDS
        se queda atrás — el siguiente INSERT sin PK explícito chocaría con un
        id ya usado. La reancla al máximo id real de la tabla."""
        tabla = modelo._meta.db_table
        with connections["default"].cursor() as cur:
            cur.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {tabla}), 1), "
                f"(SELECT MAX(id) FROM {tabla}) IS NOT NULL)",
                [tabla],
            )

    def _cargar_generico_por_lotes(self, paso):
        modelo = paso["modelo"]
        fk_a_nulear = paso.get("fk_a_nulear", [])
        fk_diferida = paso.get("fk_diferida", [])
        total_cargadas = 0
        lote_actual = []
        qs = modelo.objects.using(ORIGEN).order_by("pk").iterator(chunk_size=LOTE)
        for obj in qs:
            for campo in fk_a_nulear + fk_diferida:
                setattr(obj, campo, None)
            obj._state.db = "default"
            obj._state.adding = True
            lote_actual.append(obj)
            if len(lote_actual) >= LOTE:
                with transaction.atomic(using="default"):
                    modelo.objects.using("default").bulk_create(lote_actual)
                total_cargadas += len(lote_actual)
                self.stdout.write(f"  {modelo.__name__}: {total_cargadas} cargadas...")
                lote_actual = []
        if lote_actual:
            with transaction.atomic(using="default"):
                modelo.objects.using("default").bulk_create(lote_actual)
            total_cargadas += len(lote_actual)
        return total_cargadas

    def _cargar_vereda_por_lotes(self):
        municipio_por_dane = dict(Municipio.objects.using("default").values_list("codigo_dane", "id"))
        municipio_local_a_dane = dict(Municipio.objects.using(ORIGEN).values_list("id", "codigo_dane"))

        total = Vereda.objects.using(ORIGEN).count()
        creadas, saltadas = 0, 0
        lote_actual = []
        qs = Vereda.objects.using(ORIGEN).order_by("id").iterator(chunk_size=LOTE)
        for v in qs:
            dane_municipio = municipio_local_a_dane.get(v.municipio_id)
            municipio_rds_id = municipio_por_dane.get(dane_municipio)
            if municipio_rds_id is None:
                saltadas += 1
                continue
            lote_actual.append(Vereda(
                id=v.id, nombre=v.nombre, codigo_dane=v.codigo_dane, tipo=v.tipo,
                municipio_id=municipio_rds_id, geom=v.geom,
                created_at=v.created_at, updated_at=v.updated_at,
            ))
            if len(lote_actual) >= LOTE:
                with transaction.atomic(using="default"):
                    Vereda.objects.using("default").bulk_create(lote_actual)
                creadas += len(lote_actual)
                self.stdout.write(f"  Vereda: {creadas}/{total} cargadas...")
                lote_actual = []
        if lote_actual:
            with transaction.atomic(using="default"):
                Vereda.objects.using("default").bulk_create(lote_actual)
            creadas += len(lote_actual)
        return creadas, saltadas

    # ---- parches de FK diferida (dependencias circulares) ----

    def _aplicar_parches_fk_diferida(self):
        self.stdout.write("\n== Aplicando parches de FK diferida ==")
        for modelo, campo in PARCHES_FK_DIFERIDA:
            campo_fk = campo.removesuffix("_id")
            pendientes = list(
                modelo.objects.using(ORIGEN).exclude(**{campo: None}).values_list("id", campo)
            )
            with transaction.atomic(using="default"):
                for obj_id, valor in pendientes:
                    modelo.objects.using("default").filter(id=obj_id).update(**{campo: valor})
            self.stdout.write(f"  {modelo.__name__}.{campo_fk}: {len(pendientes)} parchados")
