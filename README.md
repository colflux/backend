# Inventario GEI

Prototipo Django para modelar, administrar y visualizar datos de gases de efecto invernadero.

## Que incluye

- Modelo relacional para datasets, regiones, sectores IPCC, gases, fuentes emisoras y registros de emisiones.
- CRUD web para registros de emisiones.
- Admin de Django para mantener catalogos.
- Visualizador preliminar con agregaciones por ano, sector y gas.
- Docker Compose con PostgreSQL.
- Landing page estatica en `docs/` lista para publicar con GitHub Pages.
- Plantilla de mapeo para columnas de Excel en `data/excel_mapping_template.csv`.

## Ejecutar con Docker

```bash
docker compose up --build
```

Luego abre:

- App: http://localhost:8000
- CRUD: http://localhost:8000/emisiones/
- Visualizador: http://localhost:8000/visualizador/
- Admin: http://localhost:8000/admin/

Para crear un usuario administrador:

```bash
docker compose exec web python manage.py createsuperuser
```

## Ejecutar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_ghg_data
python manage.py runserver
```

## Desplegar en Render

Para produccion crea una base PostgreSQL en Render y conecta el Web Service con
estas variables de entorno:

```env
DATABASE_URL=<Internal Database URL de PostgreSQL en Render>
DJANGO_ALLOWED_HOSTS=backend-143s.onrender.com
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<clave larga y aleatoria>
```

Usa la **Internal Database URL** que entrega Render para la base PostgreSQL.
No uses la URL local de Docker Compose (`postgres://ghg:ghg@db:5432/ghg`),
porque el host `db` solo existe dentro de `docker-compose.yml` y Render no lo
puede resolver.

## Publicar landing en GitHub Pages

En GitHub, ve a Settings > Pages y selecciona la carpeta `docs/` de la rama principal.
