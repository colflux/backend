# Plan de desarrollo — Rendimiento de la API geografica

## Contexto

`ROADMAP.md`, en "Ideas mencionadas, no decididas", ya registra el diagnostico:

> `sitios_geojson` y `resumen_geografico` traen **todas** las `SubmuestraCO2`
> filtradas a Python y agregan a mano (conteos, min/max, ultima medicion) en vez
> de usar `.values(...).annotate(Count/Avg/Min/Max)` y `DISTINCT ON` de Postgres.

> `series_co2` no tiene paginacion ni limite — devuelve el dataset filtrado
> completo en un solo response.

Lo que faltaba era la medida del impacto. Con el dataset actual (113 sitios,
7.048 `SubmuestraGEI`, 2 proyectos), medido sobre el servidor de produccion:

```
/api/geo/series/                        14,2 s   (2 MB)
/api/geo/resumen/?nivel=departamento     9,4 s   (105 KB)
/api/geo/sitios/                         4,6 s   (126 KB)
```

Y la misma consulta agregada, ejecutada de las dos formas contra la misma base:

```
recorriendo en Python :  15,20 s | 7.048 filas materializadas
agregando en SQL      :   0,01 s |     2 filas
```

El contenedor `backend-web-1` paso de **191 MB** sin datos a **864 MB** con estos
7.048 registros. El costo crece linealmente: a ~70.000 mediciones excede la
memoria de la instancia y el contenedor entra en ciclo de reinicio.

Este plan tambien corrige una desviacion entre la API documentada y la
implementada: `CLAUDE.md` describe `/api/geo/resumen/` con "mismos filtros que
`series`", pero `sitio` no estaba implementado en la vista.

### Relacion con `ResumenGeoMensual`

`ROADMAP.md` registra como decision tomada una tabla materializada de resumen
geografico, aun sin implementar. Este plan **no la reemplaza ni la bloquea**; la
vuelve opcional:

- La tabla materializada reduce el dataset a iterar, pero mantiene la agregacion
  en memoria ("mismo agrupado en memoria, pero sobre un dataset mucho mas
  chico"). Agregar en SQL la elimina por completo.
- La tabla materializada cubre `resumen_geografico`. Este plan cubre ademas
  `sitios_geojson` y `series_co2`.
- Agregar en SQL no introduce modelo nuevo, migracion, comando de refresco ni
  riesgo de desactualizacion.

Si el volumen futuro la justifica, puede construirse sobre estas vistas ya
corregidas.

## Cambios

Todas las fases estan implementadas y verificadas en la rama `fix/rendimiento-geo`.

| # | Vista | Cambio |
|---|---|---|
| 1 | `resumen_geografico` | Filtro por `sitio` |
| 2 | `resumen_geografico` | Agregacion en la base |
| 3 | `resumen_geografico` | Campo `excluidos` en el response |
| 4 | `series_co2` | `.values()` en vez de instancias de modelo |
| 5 | `sitios_geojson` | Agregacion en la base |

---

### 1 — Filtro por `sitio` en `resumen_geografico`

**Problema.** `CLAUDE.md` documenta el endpoint con "mismos filtros que `series`",
lista que incluye `sitio`. La vista leia `proyecto`, `vereda`, `municipio`,
`departamento` y `region`, pero no `sitio`.

Consecuencia: `?nivel=sitio&sitio=105` devolvia los 94 sitios agrupados en vez de
uno. Cualquier cliente que confiara en la documentacion — incluido el servidor
MCP de `ia-functions` — recibia el promedio de un sitio distinto al solicitado,
sin ningun error.

**Cambio.**

```python
sitio_id = request.GET.get("sitio")
if sitio_id:
    qs = qs.filter(muestra__unidad_muestreo__sitio_id=sitio_id)
```

**Verificacion.** `?nivel=sitio&gas=CO2&sitio=105` devuelve un unico feature,
con `id=105` y `promedio=2,3549` sobre 27 muestras. Sin el filtro, 94 features.

---

### 2 — `resumen_geografico` agrega en la base

**Problema.** La vista materializaba todas las `SubmuestraGEI` filtradas,
acumulaba los valores en listas de Python y calculaba `sum/len`, `min` y `max`
al final.

**Cambio.** Una consulta con `GROUP BY` por nivel, mas una segunda con
`DISTINCT ON` para la ultima medicion de cada grupo. Los nombres y geometrias se
resuelven con una consulta por nivel sobre el modelo geografico correspondiente.

Se usa la columna explicita (`..._id`) en lugar de la relacion: al ordenar por
una relacion, Django aplica el `Meta.ordering` del modelo relacionado, lo que
rompe el `DISTINCT ON` y ademas anade un JOIN innecesario.

**Sobre `ultima_medicion`.** El codigo anterior resolvia los empates de fecha con
`>=` sobre un queryset sin `ORDER BY`: ganaba la fila que la base devolviera de
ultimo, un resultado no determinista. Es frecuente: en el sitio 105, la fecha mas
reciente tiene 4 lecturas de 2 gases distintos. Ahora se resuelve por el id mayor
y se documenta en el docstring.

---

### 3 — Campo `excluidos`

**Problema.** Para cualquier nivel distinto de `sitio`, la vista descarta en
silencio las mediciones cuyo sitio no tiene vereda asignada.

**Cambio.** El response expone cuantas quedaron fuera:

```json
{ "type": "FeatureCollection", "features": [ ... ], "excluidos": 1 }
```

Con el dataset actual es una sola medicion. El valor del cambio no es el volumen
sino la visibilidad: hoy es una, y en cargas futuras podrian ser cientos sin que
nadie lo note.

---

### 4 — `series_co2` sin instancias de modelo

**Problema.** La vista solo lee campos planos, pero construia una instancia de
`SubmuestraGEI` por fila con toda su cadena de relaciones — unas diez instancias
por medicion, cerca de 70.000 objetos para el dataset actual.

**Cambio.** `.values(...)` con la lista explicita de campos. La respuesta es
identica byte a byte: 1.996.044 bytes antes y despues.

---

### 5 — `sitios_geojson` agrega en la base

**Problema.** Recorria **todas** las `SubmuestraGEI` del sistema para construir
el resumen embebido de cada sitio.

**Cambio.** Cuatro consultas agregadas: conteo y rango de fechas por sitio y por
sitio+gas, mas `DISTINCT ON` para la ultima medicion de cada uno. Aplica el mismo
criterio de desempate documentado en el punto 2.

---

## Pendiente, opcional

**Paginacion de `series_co2`.** El endpoint sigue devolviendo el dataset filtrado
completo, sin limite. Con `.values()` el tiempo dejo de ser un problema (0,13 s),
pero sigue siendo posible pedir la tabla entera en una sola peticion. Se propone
aparte porque cambia el contrato de la respuesta.

---

## Resultados medidos

Sobre la copia de produccion (113 sitios, 7.048 mediciones), en caliente:

```
                                        antes     despues
/api/geo/series/                       14,07 s     0,13 s
/api/geo/resumen/?nivel=departamento   12,63 s     0,12 s
/api/geo/resumen/?nivel=sitio          13,05 s     0,44 s
/api/geo/sitios/                        1,23 s     0,89 s
```

La pagina de Mapas hace cuatro llamadas a la API. En produccion suman unos 37
segundos; con estos cambios, menos de 2.

La mejora en `sitios_geojson` es la mas modesta en tiempo absoluto, pero es la
misma en naturaleza: la vista deja de recorrer la tabla completa, asi que su
costo ya no crece con el volumen.

---

## Verificacion

El guion `scripts/medir_resumen_geo.py` compara ambas implementaciones de la
misma consulta sobre la misma base. Solo lectura:

```bash
docker compose exec web python manage.py shell \\
    -c "exec(open('scripts/medir_resumen_geo.py').read())"
```

La equivalencia de la salida se comprobo capturando el response de cada endpoint
con la implementacion anterior y con la nueva, y comparandolos campo por campo:

- `resumen_geografico`, los cinco niveles: **cero diferencias** en `nombre`,
  `total_muestras`, `promedio`, `minimo`, `maximo` y `rango_fechas`. Mismos
  identificadores, mismo numero de features.
- `sitios_geojson`, los 113 sitios: **cero diferencias** en `nombre`,
  `municipio`, `departamento`, `altitud`, `uso_actual`, `proyectos`,
  `unidades_muestreo`, `total_muestras_co2` y `rango_fechas`.
- `series_co2`: respuesta identica byte a byte.

La unica diferencia es `ultima_medicion` en los empates de fecha, explicada en el
punto 2: el comportamiento anterior no estaba definido.

---

## Fuera de alcance

- **`ResumenGeoMensual`**. Ver la seccion de contexto sobre por que queda
  opcional despues de estos cambios.
- **`cache_page`**. Con los tiempos resultantes deja de ser necesario.
- **Nombres faltantes en `Sitio`**. 76 de 113 sitios no tienen `nombre`. Coincide
  en numero con los 76 sitios del dataset de seed mencionado en `ROADMAP.md`, lo
  que sugiere que el origen es la carga inicial y no el ETL. Es un problema de
  datos, no de estas vistas.

