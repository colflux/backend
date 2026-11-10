"""Pre-procesamiento de archivos crudos de Eddypro para torre EC.

El motor ETL genérico (ver `views.py`) asume 1 fila origen = 1 registro
destino y no agrega filas. Eddypro entrega 1 fila cada 30 minutos con una
columna por variable (formato ancho); antes de que el archivo entre al
wizard genérico hay que:

1. Agregar a 1 valor por día (promedio), descartando semihorarios con
   flag de calidad "descartar" (qc_*=2) para la variable correspondiente.
2. Aplanar de ancho a largo: de 1 fila/día con N columnas de variable, a
   N filas/día con columnas (tipo_variable, fecha, valor, ...) — una fila
   por variable, alineado 1:1 con `MuestraTorre`/`SubMuestraTorre`.
"""

import pandas as pd

# Eddypro usa -9999 como sentinela de dato faltante en vez de NaN/vacío.
VALOR_FALTANTE_EDDYPRO = -9999

# Variables con control de calidad (qc_<col> en 0=bueno/1=aceptable/2=descartar).
# Mapea nombre de columna Eddypro -> tipo_variable de MuestraTorre.
_VARIABLES_CON_QC = {
    "Tau": "tau",
    "H": "h_flux",
    "LE": "le_flux",
    "co2_flux": "co2_flux",
    "h2o_flux": "h2o_flux",
    "ch4_flux": "ch4_flux",
}

# Variables sin flag de calidad propio: se promedian tal cual, sin filtrar.
_VARIABLES_SIN_QC = {
    "u*": "ustar",
    "TKE": "tke",
    "L": "monin_obukhov_length",
    "bowen_ratio": "bowen_ratio",
    "x_peak": "footprint_x_peak",
    "x_70%": "footprint_x_70",
    "x_90%": "footprint_x_90",
    "air_temperature": "air_temperature",
    "air_pressure": "air_pressure",
    "RH": "relative_humidity",
    "VPD": "vpd",
    "air_density": "air_density",
    "wind_speed": "wind_speed",
    "wind_dir": "wind_dir",
}


def leer_crudo_eddypro(archivo_o_ruta) -> pd.DataFrame:
    """Lee un CSV de salida de Eddypro (formato `full_output`/`adv`).

    El archivo trae 2 filas de encabezado extra antes de la fila de datos:
    la fila 1 agrupa columnas por categoría y la fila 3 trae las unidades.
    La fila 2 (índice 1) es el nombre real de cada columna.
    """
    return pd.read_csv(archivo_o_ruta, skiprows=[0, 2])


def agregar_y_aplanar_eddypro(df_crudo: pd.DataFrame, torre_id: int) -> pd.DataFrame:
    """Convierte un DataFrame crudo de Eddypro (semihorario, ancho) en uno
    diario y en formato largo, listo para el mapeo 1:1 del wizard ETL
    genérico (una fila por torre + variable + fecha).
    """
    df = df_crudo.replace(VALOR_FALTANTE_EDDYPRO, pd.NA).copy()
    df["fecha"] = pd.to_datetime(df["date"]).dt.date

    filas_largas = []

    for columna, tipo_variable in _VARIABLES_CON_QC.items():
        qc = df[f"qc_{columna}"]
        valores = df[columna].where(qc != 2)
        filas_largas.append(_resumir_por_dia(df["fecha"], valores, tipo_variable, qc=qc))

    for columna, tipo_variable in _VARIABLES_SIN_QC.items():
        if columna not in df.columns:
            continue
        filas_largas.append(_resumir_por_dia(df["fecha"], df[columna], tipo_variable))

    df_largo = pd.concat(filas_largas, ignore_index=True)
    df_largo["torre_id"] = torre_id
    return df_largo[["torre_id", "tipo_variable", "fecha", "valor", "pct_calidad_buena", "n_registros_validos"]]


def _resumir_por_dia(fechas: pd.Series, valores: pd.Series, tipo_variable: str, qc: pd.Series = None) -> pd.DataFrame:
    agrupado = valores.groupby(fechas)
    resumen = agrupado.agg(valor="mean", n_registros_validos="count")
    resumen = resumen.reset_index(names="fecha")

    if qc is not None:
        pct_buena = (qc == 0).groupby(fechas).mean().mul(100).round(2).reset_index(name="pct_calidad_buena")
        resumen = resumen.merge(pct_buena, on="fecha", how="left")
    else:
        resumen["pct_calidad_buena"] = None

    resumen["tipo_variable"] = tipo_variable
    return resumen
