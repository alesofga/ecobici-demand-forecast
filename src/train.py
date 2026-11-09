import duckdb
import pandas as pd
import numpy as np
import lightgbm as lgb
import gc
from sklearn.metrics import mean_absolute_error
from features import generate_hourly_grid, extract_time_features, add_advanced_features

DB_PATH = "data/ecobici.db"

def calculate_wmape(y_true, y_pred):
    sum_true = np.sum(np.abs(y_true))
    if sum_true == 0:
        return 0.0
    return np.sum(np.abs(y_true - y_pred)) / sum_true

def run_backtest_2025(df_full):
    print("--- INICIANDO BACKTEST 2025 (OPTIMIZADO EN MEMORIA) ---")
    
    train_mask = (df_full['fecha'] <= '2025-09-30')
    test_mask = (df_full['fecha'] >= '2025-10-01') & (df_full['fecha'] <= '2025-12-31')

    # Filtrar sin duplicar memoria excesiva
    features_salidas = [
        'estacion_id', 'hora', 'dayofweek', 'is_weekend', 'month', 
        'sin_hora', 'cos_hora', 'sin_dow', 'cos_dow',
        'hist_mean_salidas', 'hist_max_salidas', 'hist_std_salidas',
        'salidas_lag_24h', 'salidas_lag_168h'
    ]

    features_arribos = [
        'estacion_id', 'hora', 'dayofweek', 'is_weekend', 'month', 
        'sin_hora', 'cos_hora', 'sin_dow', 'cos_dow',
        'hist_mean_arribos', 'hist_max_arribos', 'hist_std_arribos',
        'arribos_lag_24h', 'arribos_lag_168h'
    ]

    X_train_s = df_full.loc[train_mask, features_salidas]
    y_train_s = df_full.loc[train_mask, 'salidas']
    
    X_test_s = df_full.loc[test_mask, features_salidas]
    y_test_s = df_full.loc[test_mask, 'salidas']

    # Entrenar Salidas
    print("Entrenando modelo de Salidas...")
    model_salidas = lgb.LGBMRegressor(
        n_estimators=300, 
        learning_rate=0.05, 
        num_leaves=31,
        random_state=42,
        n_jobs=-1,
        verbose=-1
    )
    model_salidas.fit(X_train_s, y_train_s)
    
    test_df = df_full.loc[test_mask, ['fecha', 'hora', 'estacion_id', 'salidas']].copy()
    test_df['salidas_pred'] = np.maximum(0, model_salidas.predict(X_test_s))

    del X_train_s, y_train_s, X_test_s, y_test_s
    gc.collect()

    # Entrenar Arribos
    print("Entrenando modelo de Arribos...")
    X_train_a = df_full.loc[train_mask, features_arribos]
    y_train_a = df_full.loc[train_mask, 'arribos']
    X_test_a = df_full.loc[test_mask, features_arribos]

    model_arribos = lgb.LGBMRegressor(
        n_estimators=300, 
        learning_rate=0.05, 
        num_leaves=31,
        random_state=42,
        n_jobs=-1,
        verbose=-1
    )
    model_arribos.fit(X_train_a, y_train_a)
    test_df['arribos_pred'] = np.maximum(0, model_arribos.predict(X_test_a))

    del X_train_a, y_train_a, X_test_a
    gc.collect()

    mae_lgb = mean_absolute_error(test_df['salidas'], test_df['salidas_pred'])
    wmape_lgb = calculate_wmape(test_df['salidas'].values, test_df['salidas_pred'].values) * 100
    print(f"[MODELO OPTIMIZADO] Backtest Salidas MAE: {mae_lgb:.4f} | WMAPE: {wmape_lgb:.2f}%")

    return test_df, model_salidas, model_arribos, features_salidas

def forecast_2026(df_full, model_salidas, model_arribos, features_salidas, con):
    print("--- GENERANDO FORECAST 2026 ---")
    
    future_dates = pd.date_range(start='2026-10-01', end='2026-12-31', freq='D')
    hours = np.arange(0, 24, dtype=np.int8)
    stations = df_full['estacion_id'].unique().astype(np.int16)

    grid_2026 = pd.MultiIndex.from_product(
        [future_dates, hours, stations], 
        names=['fecha', 'hora', 'estacion_id']
    ).to_frame().reset_index(drop=True)

    grid_2026['salidas'] = 0.0
    grid_2026['arribos'] = 0.0
    
    grid_2026 = extract_time_features(grid_2026)
    
    profile_salidas = df_full.groupby(['estacion_id', 'dayofweek', 'hora'])['salidas'].agg(
        hist_mean_salidas='mean', hist_max_salidas='max', hist_std_salidas='std'
    ).astype(np.float32).reset_index()

    profile_arribos = df_full.groupby(['estacion_id', 'dayofweek', 'hora'])['arribos'].agg(
        hist_mean_arribos='mean', hist_max_arribos='max', hist_std_arribos='std'
    ).astype(np.float32).reset_index()

    grid_2026 = pd.merge(grid_2026, profile_salidas, on=['estacion_id', 'dayofweek', 'hora'], how='left')
    grid_2026 = pd.merge(grid_2026, profile_arribos, on=['estacion_id', 'dayofweek', 'hora'], how='left')
    
    grid_2026['salidas_lag_24h'] = grid_2026['hist_mean_salidas']
    grid_2026['salidas_lag_168h'] = grid_2026['hist_mean_salidas']
    grid_2026['arribos_lag_24h'] = grid_2026['hist_mean_arribos']
    grid_2026['arribos_lag_168h'] = grid_2026['hist_mean_arribos']

    features_arribos = [f.replace('salidas', 'arribos') for f in features_salidas]

    grid_2026['salidas_pred'] = np.maximum(0, model_salidas.predict(grid_2026[features_salidas]))
    grid_2026['arribos_pred'] = np.maximum(0, model_arribos.predict(grid_2026[features_arribos]))

    df_db = grid_2026[['fecha', 'hora', 'estacion_id', 'salidas_pred', 'arribos_pred']].copy()
    df_db['tipo'] = 'FORECAST_2026'

    con.execute("DROP TABLE IF EXISTS fact_predictions;")
    con.execute("""
        CREATE TABLE fact_predictions (
            fecha DATE,
            hora INTEGER,
            estacion_id INTEGER,
            salidas_pred DOUBLE,
            arribos_pred DOUBLE,
            tipo VARCHAR
        )
    """)
    con.execute("INSERT INTO fact_predictions SELECT * FROM df_db")

if __name__ == "__main__":
    conn = duckdb.connect(DB_PATH)
    
    df_raw = conn.execute("SELECT * FROM fact_viajes_horarios").df()
    min_date = df_raw['fecha'].min()
    max_date = df_raw['fecha'].max()
    
    df_full = generate_hourly_grid(df_raw, min_date, max_date)
    df_full = extract_time_features(df_full)
    df_full = add_advanced_features(df_full)
    
    test_backtest, model_s, model_a, feat_list = run_backtest_2025(df_full)
    
    # Guardar Backtest
    test_backtest['estacion_id'] = test_backtest['estacion_id'].astype(int)
    conn.execute("DROP TABLE IF EXISTS backtest_predictions;")
    conn.execute("CREATE TABLE backtest_predictions AS SELECT * FROM test_backtest")

    # Guardar Forecast 2026
    forecast_2026(df_full, model_s, model_a, feat_list, conn)
    conn.execute("DROP TABLE IF EXISTS predictions;")
    conn.execute("CREATE TABLE predictions AS SELECT * FROM fact_predictions")

    # Guardar Métricas
    mae_val = float(mean_absolute_error(test_backtest['salidas'], test_backtest['salidas_pred']))
    wmape_val = float(calculate_wmape(test_backtest['salidas'].values, test_backtest['salidas_pred'].values))
    rmse_val = float(np.sqrt(np.mean((test_backtest['salidas'] - test_backtest['salidas_pred']) ** 2)))
    
    df_metrics = pd.DataFrame([
        {'metrica': 'MAE', 'valor': mae_val},
        {'metrica': 'RMSE', 'valor': rmse_val},
        {'metrica': 'WAPE', 'valor': wmape_val}
    ])
    conn.execute("DROP TABLE IF EXISTS model_metrics;")
    conn.execute("CREATE TABLE model_metrics AS SELECT * FROM df_metrics")

    # Feature Importance
    df_feat_imp = pd.DataFrame({
        'feature': feat_list,
        'importance': model_s.feature_importances_
    }).sort_values(by='importance', ascending=False)
    
    conn.execute("DROP TABLE IF EXISTS feature_importance;")
    conn.execute("CREATE TABLE feature_importance AS SELECT * FROM df_feat_imp")

    conn.close()
    print("🚀 Entrenamiento completado exitosamente sin sobrecargar la memoria RAM.")