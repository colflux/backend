# Datos para las gráficas del dashboard

## Introducción

Ajustes de la API geográfica que necesita el rediseño de las gráficas del dashboard
(PR del frontend `feat/graficas-dashboard`): muestras por unidad experimental, promedios
de flujo dentro de una sola unidad y estado de conservación de cada sitio.

## Contexto

El equipo revisó las gráficas del dashboard (documento «cambios gráficos plataforma»):

- Pidió ver las muestras y los sitios por **unidad experimental**, en vez de por proyecto
  y por uso del sitio.
- Pidió que el flujo por condición de luz diga que es un **promedio**. Además, ese
  promedio mezclaba unidades distintas (µmol/m²/s, nmol/m²/s y g/m²/h).
- Pidió un gráfico de torta del **estado de conservación**. Salía vacío porque se contaba
  sobre las mediciones de gases, y los sitios con mediciones no tienen estado registrado.

## Qué hace

`app/api/geo/views.py`:

- **`/api/geo/resumen-categorico/?dimension=unidad_experimental`**: dimensión nueva.
  Agrupa las mediciones de flujo por unidad experimental, con su nombre.
- **Filtro `unidad`** (código de `UnidadMedida`, p. ej. `umol_m2_s`) en los filtros
  comunes de flujos. Aplica a `/resumen/` y `/resumen-categorico/`: el dashboard pide el
  promedio por condición de luz de a una unidad a la vez.
- **`/api/geo/sitios/`**: cada sitio trae `estado_conservacion` (el de su disturbio, con
  la etiqueta corta: «Natural», «Seminatural», «Manejado»…) o `null`.

No cambia el modelo ni hay migraciones.

## Plan por fases

1. API (este cambio) y frontend (`feat/graficas-dashboard`).
2. Futuro: que `/resumen/` devuelva un promedio por unidad en lugar de uno mezclado
   (ver la revisión de datos del 25/09/2026).

## Verificación

- `resumen-categorico?dimension=unidad_experimental&gas=CO2`: una fila por unidad
  experimental; la suma de `total_muestras` coincide con el total de CO2.
- `resumen-categorico?dimension=condicion_luz&gas=CO2&unidad=umol_m2_s`: promedios
  calculados solo con mediciones en µmol/m²/s.
- `/sitios/`: `estado_conservacion` presente en los sitios con disturbio.
