# Modulos de la pagina Datos

Esta carpeta agrupa la logica especifica de `pages/data.html`.

Modulos actuales:

- `fuente-drawer.js`: crear fuentes de datos.
- `proyecto-drawer.js`: crear proyectos.
- `responsable-drawer.js`: preparar la creacion de responsables.
- `etl-actions.js`: acciones ETL que se disparen desde la pagina Datos.

Los modulos deben colgar de `window.COLFLUX_DATA` para evitar globals sueltos.
