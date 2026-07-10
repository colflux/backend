# Inventario GEI

Prototipo Django para modelar, administrar y visualizar datos de gases de efecto invernadero.

## Que incluye

- Modelo relacional para datasets, regiones, sectores IPCC, gases, fuentes emisoras y registros de emisiones.
- CRUD web para registros de emisiones.
- Admin de Django para mantener catalogos.
- Visualizador preliminar con agregaciones por ano, sector y gas.
- Docker Compose con PostgreSQL.
- Portal estatico de prototipos en `docs/`, conectado a la API Django.
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
DJANGO_SUPERUSER_USERNAME=<usuario admin>
DJANGO_SUPERUSER_EMAIL=<correo admin>
DJANGO_SUPERUSER_PASSWORD=<clave admin temporal>
LOAD_SEED_DATA=1
```

Usa la **Internal Database URL** que entrega Render para la base PostgreSQL.
No uses la URL local de Docker Compose (`postgres://ghg:ghg@db:5432/ghg`),
porque el host `db` solo existe dentro de `docker-compose.yml` y Render no lo
puede resolver.

Si no tienes Shell en Render, las variables `DJANGO_SUPERUSER_*` crean el usuario
admin automaticamente durante el deploy. Despues de entrar al admin por primera
vez, elimina `DJANGO_SUPERUSER_PASSWORD` de Render o cambiala por una nueva.

La variable `LOAD_SEED_DATA=1` ejecuta `python manage.py seed_ghg_data` durante
el deploy para cargar datos iniciales de demostracion. El comando evita duplicar
los registros existentes. Si ya no quieres cargar datos demo en cada deploy,
elimina esa variable o cambiala a `0`.

## Ejecutar el portal de datos

Con Django ejecutandose en el puerto 8000, inicia otro servidor desde la raiz
del repositorio:

```bash
python -m http.server 8080 --directory docs
```

Abre http://localhost:8080. La configuracion publica de servicios se encuentra
en `docs/config/services.js`; no guardes credenciales en esa carpeta.

## Actualizar catálogo y modelo entidad-relación

Las páginas estáticas `docs/pages/db.html` y
`docs/pages/catalogo-tecnico.html` no consultan una API para dibujar el
modelo. Ambas leen los assets generados en `docs/assets/data/`.

Cada vez que cambies modelos Django en `app/models/`, actualiza esos assets con:

```bash
python manage.py generate_catalogo
```

Ese comando regenera:

- `docs/assets/data/catalogo.json`
- `docs/assets/data/catalogo.js`

Después de correrlo, revisa y versiona esos archivos junto con el cambio del
modelo para que el portal estático quede sincronizado con el repositorio.
