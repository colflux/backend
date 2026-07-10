# Modulos de la pagina Datos

Esta carpeta agrupa la logica especifica de `pages/data.html`.

Modulos actuales:

- `fuente-drawer.js`: crear fuentes de datos.
- `proyecto-drawer.js`: crear proyectos.
- `responsable-drawer.js`: crear y editar usuarios responsables.
- `etl-actions.js`: acciones ETL que se disparen desde la pagina Datos.
- `data-state.js`: estado compartido, fetch principal, filtros base y render general.
- `proyectos-section.js`: tabla, buscador y acciones de la seccion de proyectos.
- `fuentes-section.js`: tabla, filtros y acciones de la seccion de fuentes.
- `data-main.js`: inicializacion de drawers, eventos y carga inicial.

Los modulos deben colgar de `window.COLFLUX_DATA` para evitar globals sueltos.
