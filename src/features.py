import pandas as pd
import numpy as np

def generate_hourly_grid(df_raw, min_date, max_date):
    """Genera la cuadrícula completa de horas x estaciones optimizada en memoria."""
    future_dates = pd.date_range(start=min_date, end=max_date, freq='D')
    hours = np.arange(0, 24, dtype=np.int8)
    stations = df_raw['estacion_id'].unique().astype(np.int16)

    grid = pd.MultiIndex.from_product(
        [future_dates, hours, stations],
        names=['fecha', 'hora', 'estacion_id']
    ).to_frame().reset_index(drop=True)

    df_full = pd.merge(grid, df_raw, on=['fecha', 'hora', 'estacion_id'], how='left').fillna(0)
    
    # Reducir tipos de datos
    df_full['salidas'] = df_full['salidas'].astype(np.float32)
    df_full['arribos'] = df_full['arribos'].astype(np.float32)
    df_full['estacion_id'] = df_full['estacion_id'].astype(np.int16)
    df_full['hora'] = df_full['hora'].astype(np.int8)
    
    return df_full

def extract_time_features(df):
    """Extrae características temporales en formato de 32 bits."""
    df['fecha'] = pd.to_datetime(df['fecha'])
    df['dayofweek'] = df['fecha'].dt.dayofweek.astype(np.int8)
    df['is_weekend'] = df['dayofweek'].isin([5, 6]).astype(np.int8)
    df['month'] = df['fecha'].dt.month.astype(np.int8)

    # Senos y cosenos en float32
    df['sin_hora'] = np.sin(2 * np.pi * df['hora'] / 24.0).astype(np.float32)
    df['cos_hora'] = np.cos(2 * np.pi * df['hora'] / 24.0).astype(np.float32)
    df['sin_dow'] = np.sin(2 * np.pi * df['dayofweek'] / 7.0).astype(np.float32)
    df['cos_dow'] = np.cos(2 * np.pi * df['dayofweek'] / 7.0).astype(np.float32)

    return df

def add_advanced_features(df):
    """Agrega lags y perfiles históricos optimizando el uso de RAM."""
    df = df.sort_values(by=['estacion_id', 'fecha', 'hora']).reset_index(drop=True)

    # 1. Perfil histórico en float32
    profile_salidas = df.groupby(['estacion_id', 'dayofweek', 'hora'])['salidas'].agg(
        hist_mean_salidas='mean',
        hist_max_salidas='max',
        hist_std_salidas='std'
    ).astype(np.float32).reset_index()

    profile_arribos = df.groupby(['estacion_id', 'dayofweek', 'hora'])['arribos'].agg(
        hist_mean_arribos='mean',
        hist_max_arribos='max',
        hist_std_arribos='std'
    ).astype(np.float32).reset_index()

    df = pd.merge(df, profile_salidas, on=['estacion_id', 'dayofweek', 'hora'], how='left')
    df = pd.merge(df, profile_arribos, on=['estacion_id', 'dayofweek', 'hora'], how='left')

    df['hist_std_salidas'] = df['hist_std_salidas'].fillna(0).astype(np.float32)
    df['hist_std_arribos'] = df['hist_std_arribos'].fillna(0).astype(np.float32)

    # 2. Lags Temporales
    grouped_salidas = df.groupby('estacion_id')['salidas']
    grouped_arribos = df.groupby('estacion_id')['arribos']

    df['salidas_lag_24h'] = grouped_salidas.shift(24).fillna(df['hist_mean_salidas']).astype(np.float32)
    df['salidas_lag_168h'] = grouped_salidas.shift(168).fillna(df['hist_mean_salidas']).astype(np.float32)

    df['arribos_lag_24h'] = grouped_arribos.shift(24).fillna(df['hist_mean_arribos']).astype(np.float32)
    df['arribos_lag_168h'] = grouped_arribos.shift(168).fillna(df['hist_mean_arribos']).astype(np.float32)

    return df