# Categoría produccion en resumen_geografico

## Contexto

`resumen_geografico` expone tres categorías: `flujos`, `biomasa` y `cos`. La de biomasa está
configurada sobre `prom_tonc_ha`, que es el **carbono almacenado** en la biomasa.

`MuestraBiomasa` guarda dos magnitudes que no son la misma cosa:

- `prom_tonc_ha` — carbono almacenado, en toneladas de carbono por hectárea. Es un stock: lo
  que hay acumulado en un momento dado.
- `prod_biomasa_g` — biomasa producida, en gramos. Es un flujo: lo que se genera en un
  periodo.

Para un inventario de carbono la primera responde cuánto hay; la segunda, a qué ritmo se
incorpora. Un promedio que mezclara ambas no significaría nada.

Al medir sobre los datos cargados aparece algo que conviene señalar: de los **646 registros**
de `MuestraBiomasa`, las columnas de carbono —`prom_tonc_ha`, `contenido_carbono`, y las de
desviación, mínimo y máximo— **están vacías en todas las filas**. La única con datos es
`prod_biomasa_g`, con 617 valores.

La consecuencia práctica es que **`categoria=biomasa` devuelve hoy una colección vacía**. El
endpoint funciona; simplemente no hay nada detrás. Así que esta propuesta no añade una
variable más: da acceso a los únicos datos de biomasa que la plataforma tiene.

## Cambios

Una entrada en `_CATEGORIA_CONFIG`, siguiendo el patrón de las existentes:

```python
"produccion": {
    "modelo": MuestraBiomasa,
    "prefijo_sitio": "unidad_muestreo__sitio",
    "prefijo_proyecto": "unidad_muestreo__unidad_experimental__proyecto",
    "campo_valor": "prod_biomasa_g",
    "campo_unidad": None,
    "unidad_fija": "g",
    "filtro_gas": None,
    "excluir_valor_nulo": True,
},
```

Se usa `unidad_fija` porque el modelo no tiene columna de unidad para ese campo: el nombre
del propio campo declara los gramos. Es el mismo criterio que ya se aplica en `cos`.

No se toca ninguna otra categoría, ni el cálculo, ni los filtros comunes: la agregación, el
filtrado geográfico y el conteo de excluidos son los que ya existen.

## Resultados medidos

Contra los datos actuales, agrupando por departamento:

```
categoria=biomasa      unidad tonc_ha    0 grupos, ninguna medición
categoria=produccion   unidad g          Cundinamarca  157 muestras   promedio    637,66 g
                                         Caldas        460 muestras   promedio  1.151,30 g
```

Los 617 registros con valor quedan repartidos entre los dos departamentos. Antes de este
cambio no eran alcanzables por la API.

## Verificación

```bash
curl -s "http://SERVIDOR/api/geo/resumen/?nivel=departamento&categoria=biomasa"
curl -s "http://SERVIDOR/api/geo/resumen/?nivel=departamento&categoria=produccion"
```

La primera devuelve `features: []`; la segunda, los dos departamentos con su promedio y la
unidad declarada en `g`.

Los filtros comunes siguen funcionando sobre la categoría nueva, porque no se tocó
`_aplicar_filtros_comunes`: acotar por `sitio`, `vereda`, `municipio`, `departamento` o
rango de fechas da el subconjunto correspondiente.

## Fuera de alcance

**Las columnas de carbono vacías.** Que `prom_tonc_ha` y sus columnas asociadas estén sin
valor en los 646 registros parece un hueco de la carga, no del endpoint. Este cambio no lo
corrige ni lo disimula: si esas columnas se llenan más adelante, `categoria=biomasa` empezará
a devolver datos sin tocar nada. Merece revisarse aparte, mirando el archivo de origen.

**La unidad fija.** Si en el futuro se cargaran producciones en otra unidad, haría falta una
columna de unidad en el modelo y pasar a `campo_unidad`, como en flujos. Con los datos
actuales no es necesario.

**El nombre de la categoría.** Se eligió `produccion` por simetría con las demás, que usan un
término corto. Si el equipo prefiere `produccion_biomasa` u otro, es un cambio de una línea.

