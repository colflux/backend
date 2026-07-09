# Plan de desarrollo — Pipeline ETL de carga de datos

## Contexto

El data-portal ya tiene `data.html`: una página que lista fuentes de datos (`FuenteDatos`) por proyecto
y permite registrar nuevas con estado `pendiente`. El backend Django expone esas fuentes en
`/api/fuentes-datos/`.

El archivo de ejemplo es `data/Base_de_Datos_2025.xlsx`:
- Hoja principal `Documentos2025_1`: 53 registros, ~110 columnas
- Cubre datos bibliográficos, ubicación geográfica, coberturas, contenidos de carbono y flujos de gases
- El modelo de dominio en Django (modelos en `app/models/`) tiene: `Publicacion`, `Sitio`,
  `Parcela`, `Cobertura`, `MonitoreoSuelo`, `ResultadoPublicacion`, entre otros

---

## Flujo completo

```
data.html
  └─ [card de fuente en estado "pendiente"]
       └─ botón "Iniciar carga" ──→ etl-upload.html?fuente=<id>
                                         │
                                    [Paso 1] Subir archivo
                                         │
                                    [Paso 2] Mapeo de columnas
                                         │
                                    [Paso 3] Reporte de calidad
                                         │
                                    [Paso 4] Corrección (opcional)
                                         │
                                    [Paso 5] Importar a BD
                                         └─ actualiza FuenteDatos.estado → "completo"
```

---

## Fases de desarrollo

### Fase 1 — Trigger desde data.html
**Qué**: Agregar un botón "Iniciar carga →" en cada card de `data.html` que lleve a `etl-upload.html?fuente=<id>`.

**Criterio de done**:
- Solo aparece en fuentes con `tipo: excel` o `tipo: csv`
- Abre `etl-upload.html` con el `id` de la fuente como query param
- La página nueva muestra el nombre de la fuente en el encabezado (fetch al API)

**Archivos a tocar**:
- `data-portal/pages/data.html` — agregar botón en `renderCards()`
- `data-portal/pages/etl-upload.html` — crear

---

### Fase 2 — Backend: upload e inspección del archivo
**Qué**: Endpoint Django que recibe un archivo (Excel/CSV) y devuelve sus hojas, columnas y
muestra de datos.

**Endpoints nuevos**:
```
POST /api/fuentes-datos/<id>/upload/
  Body: multipart — campo `archivo`
  Response:
    {
      "sheets": ["Documentos2025_1", "Hoja1"],
      "columns": [
        { "name": "Author", "dtype": "string", "nulls": 3, "sample": ["García et al.", "López 2022"] }
      ],
      "row_count": 53
    }
```

**Modelo nuevo** — `CargaArchivo`:
```python
class CargaArchivo(TimestampedModel):
    fuente       = ForeignKey(FuenteDatos, ...)
    archivo      = FileField(upload_to="cargas/")
    hoja_activa  = CharField(...)     # sheet seleccionada
    estado       = CharField(choices=[("subido","Subido"),("mapeado","Mapeado"),
                                      ("validado","Validado"),("importado","Importado")])
    columnas_raw = JSONField()        # resultado del inspect
```

**Archivos a tocar**:
- `app/models/datos.py` — agregar `CargaArchivo`
- `app/views/` — nuevo `EtlUploadView`, `EtlInspectView`
- `app/urls.py`
- nueva migración

---

### Fase 3 — UI de mapeo de columnas (página ETL)
**Qué**: Interfaz dividida en dos paneles donde el usuario conecta columnas del archivo con campos del modelo Django.

**Layout**:
```
┌─────────────────────────────┬──────────────────────────────────┐
│  COLUMNAS DEL ARCHIVO        │  CAMPOS DE LA BASE DE DATOS       │
│                             │                                    │
│  Author ──────────────────→ │  [Publicacion.autores ▼]          │
│    sample: García, López    │                                    │
│                             │                                    │
│  Latitud ─────────────────→ │  [Sitio.latitud ▼]                │
│    sample: 1.234, -74.2     │                                    │
│                             │                                    │
│  Ecosistema / Cobertura ──→ │  [Cobertura.nombre ▼]             │
│    sample: Turbera, Bosque  │                                    │
│                             │                                    │
│  ISBN ─────────────────────→│  [— ignorar —]                    │
└─────────────────────────────┴──────────────────────────────────┘
                          [Guardar mapeo →]
```

**Endpoint nuevo**:
```
GET  /api/etl/campos-destino/
  Response: árbol de modelos y campos disponibles
  {
    "Publicacion": ["titulo", "doi", "anio", "url"],
    "Sitio":       ["nombre", "latitud", "longitud", "altitud", "departamento"],
    "Cobertura":   ["nombre", "cobertura_ipcc", "cobertura_clc"],
    ...
  }

POST /api/fuentes-datos/<id>/carga/<carga_id>/mapeo/
  Body: { "mapeo": [{"columna_origen": "Author", "modelo": "Publicacion", "campo": "autores"}, ...] }
```

**Modelo nuevo** — `MapeoColumna`:
```python
class MapeoColumna(TimestampedModel):
    carga         = ForeignKey(CargaArchivo, ...)
    columna_origen = CharField(...)   # nombre en el Excel
    modelo_destino = CharField(...)   # "Publicacion", "Sitio", etc.
    campo_destino  = CharField(...)   # campo del modelo
    transformacion = CharField(...)   # "directo", "lookup", "split", etc.
```

---

### Fase 4 — Reporte de calidad del dato
**Qué**: Con el mapeo definido, correr validaciones y mostrar un reporte antes de importar.

**Endpoint**:
```
POST /api/fuentes-datos/<id>/carga/<carga_id>/validar/
  Response:
  {
    "resumen": { "total_filas": 53, "filas_ok": 40, "filas_con_errores": 13 },
    "columnas": [
      {
        "columna": "Latitud",
        "destino": "Sitio.latitud",
        "errores": [
          { "fila": 5,  "valor": "N/A",   "tipo": "tipo_invalido" },
          { "fila": 12, "valor": null,     "tipo": "nulo_obligatorio" }
        ],
        "ok": 51
      }
    ]
  }
```

**Tipos de validación a implementar**:
| Tipo | Descripción |
|------|-------------|
| `nulo_obligatorio` | Campo requerido en el modelo tiene valor vacío |
| `tipo_invalido` | Valor no se puede convertir al tipo del campo (ej: texto en FloatField) |
| `fuera_de_vocabulario` | Valor no está en los choices del campo |
| `duplicado` | Registro idéntico ya existe en la BD |
| `longitud_excedida` | Texto más largo que max_length del campo |

**UI del reporte**:
```
┌─ Resumen ───────────────────────────────────────────────────────┐
│  53 filas   ·   40 OK (75%)   ·   13 con errores (25%)         │
└─────────────────────────────────────────────────────────────────┘

┌─ Columna: Latitud → Sitio.latitud ──────────────────────────────┐
│  ✅ 51 valores válidos                                           │
│  ❌ Fila 5:  "N/A" — no es un número decimal                    │
│  ⚠️  Fila 12: vacío — campo obligatorio                          │
└─────────────────────────────────────────────────────────────────┘

[ Corregir errores ]      [ Importar igualando errores ]
```

---

### Fase 5 — Corrección inline (opcional / v2)
**Qué**: Tabla editable con las filas que tienen errores para que el usuario las corrija antes
de importar.

**Decisión de diseño**: Solo mostrar las filas con errores, con las celdas problemáticas
resaltadas en rojo. El usuario puede editar el valor directamente en la celda.

**Endpoint**:
```
PATCH /api/fuentes-datos/<id>/carga/<carga_id>/corregir/
  Body: { "correcciones": [{ "fila": 5, "columna": "Latitud", "valor_nuevo": "1.234" }] }
```

---

### Fase 6 — Importación final
**Qué**: Ejecutar el ETL con el mapeo aprobado y escribir los registros en la BD.

**Endpoint**:
```
POST /api/fuentes-datos/<id>/carga/<carga_id>/importar/
  Response:
  {
    "importados": 40,
    "omitidos":   13,
    "errores":    [],
    "estado_fuente": "completo"
  }
```

**Lógica**:
- Iterar filas del archivo usando el mapeo
- Por cada fila: crear/actualizar los modelos destino en orden de dependencia
  (primero `Region` → `Sitio` → `Parcela` → `ResultadoPublicacion`)
- Actualizar `FuenteDatos.estado` → `"completo"` o `"con_errores"`
- Guardar log de lo importado en `CargaArchivo`

---

## Orden de ejecución

| # | Fase | Dependencias | Esfuerzo estimado |
|---|------|--------------|-------------------|
| 1 | Trigger en data.html + esqueleto etl-upload.html | ninguna | pequeño |
| 2 | Backend upload + inspect | ninguna | mediano |
| 3 | UI mapeo de columnas | Fase 2 | grande |
| 4 | Backend validaciones + UI reporte | Fase 3 | grande |
| 5 | Corrección inline | Fase 4 | mediano |
| 6 | Importación final | Fases 3, 4 | mediano |

---

## Archivo de ejemplo

`data/Base_de_Datos_2025.xlsx` — hoja `Documentos2025_1`

Mapeo inicial sugerido (columnas del Excel → modelo Django):

| Columna Excel | Modelo.campo Django |
|---|---|
| Author | `Publicacion.autores` (texto libre por ahora) |
| Title | `Publicacion.titulo` |
| DOI | `Publicacion.doi` |
| Year | `Publicacion.anio` |
| Region Natural | `Region.nombre` |
| Departamento | `Sitio.departamento` (FK lookup) |
| Municipio | `Sitio.municipio` (FK lookup) |
| Latitud | `Sitio.latitud` |
| Longitud | `Sitio.longitud` |
| Altitud | `Sitio.altitud` |
| Ecosistema / Cobertura | `Cobertura.nombre` |
| Cobertura IPCC | `Cobertura.cobertura_ipcc` |
| Contenido de Carbono en biomasa aérea (tC/ha)2 | `ResultadoPublicacion.carbono_ba_tc_ha` |
| CO2 Flux | `ResultadoPublicacion.co2_flux` |
| CH4 Flux | `ResultadoPublicacion.ch4_flux` |
| N2O Flux | `ResultadoPublicacion.n2o_flux` |
