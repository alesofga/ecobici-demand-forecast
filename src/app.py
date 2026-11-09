import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
from datetime import date, timedelta

st.set_page_config(page_title="Ecobici Demand Forecast", layout="wide")

st.title("🚲 Sistema de Pronóstico de Demanda Ecobici CDMX")
st.caption("Herramienta de planificación de flota y redistribución de bicicletas por estación.")

@st.cache_resource
def get_connection():
    return duckdb.connect("data/ecobici.db", read_only=True)

conn = get_connection()

# 1. Obtener lista de estaciones
try:
    estaciones_df = conn.execute("SELECT estacion_id, nombre, latitud, longitud FROM dim_estacion ORDER BY estacion_id").df()
except Exception:
    estaciones_df = pd.DataFrame(columns=['estacion_id', 'nombre', 'latitud', 'longitud'])

if estaciones_df.empty:
    st.error("No se encontraron estaciones en la base de datos.")
    st.stop()

# 2. Sidebar con selección de estación
st.sidebar.header("⚙️ Configuración")
lista_estaciones = estaciones_df['estacion_id'].tolist()
estacion_sel = st.sidebar.selectbox("Selecciona una Estación:", options=lista_estaciones, index=0)

info_estacion = estaciones_df[estaciones_df['estacion_id'] == estacion_sel].iloc[0]
nombre_estacion = info_estacion['nombre'] if pd.notna(info_estacion['nombre']) else f"Estación {estacion_sel}"
st.sidebar.markdown(f"**Estación Seleccionada:** {nombre_estacion}")

# 3. Pestañas
tab1, tab2, tab3 = st.tabs([
    "📈 Backtest (Oct-Dic 2025)", 
    "🔮 Forecast (Oct-Dic 2026)", 
    "📊 Evaluación del Modelo"
])

# --- PESTAÑA 1: BACKTEST 2025 (CON FILTRO DE FECHAS Y ZOOM) ---
# --- PESTAÑA 1: BACKTEST 2025 ---
with tab1:
    st.header(f"Validación Histórica - Estación {estacion_sel}")

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        f_inicio_bt = st.date_input("Desde:", value=date(2025, 10, 1), min_value=date(2025, 10, 1), max_value=date(2025, 12, 31), key="bt_start")
    with col_d2:
        f_fin_bt = st.date_input("Hasta:", value=date(2025, 10, 14), min_value=date(2025, 10, 1), max_value=date(2025, 12, 31), key="bt_end")

    try:
        # Consulta limpia sin concatenación complicada en SQL
        query_bt = f"""
            SELECT 
                fecha::VARCHAR AS fecha_str,
                hora,
                salidas AS salidas_reales,
                salidas_pred AS salidas_pronostico
            FROM backtest_predictions
            WHERE estacion_id::INTEGER = {int(estacion_sel)}
              AND fecha BETWEEN '{f_inicio_bt}' AND '{f_fin_bt}'
            ORDER BY fecha, hora
        """
        df_bt = conn.execute(query_bt).df()

        if not df_bt.empty:
            # Construcción infalible de fecha_hora en Pandas
            df_bt['fecha_clean'] = df_bt['fecha_str'].str.slice(0, 10) # Tomar solo YYYY-MM-DD
            df_bt['fecha_hora'] = pd.to_datetime(
                df_bt['fecha_clean'] + ' ' + df_bt['hora'].astype(str).str.zfill(2) + ':00:00'
            )

            df_bt_melted = df_bt.melt(
                id_vars=['fecha_hora'], 
                value_vars=['salidas_reales', 'salidas_pronostico'],
                var_name='Tipo de Serie', 
                value_name='Número de Viajes'
            )

            fig_bt = px.line(
                df_bt_melted, 
                x='fecha_hora', 
                y='Número de Viajes',
                color='Tipo de Serie',
                title=f"Demanda Real vs Pronosticada ({f_inicio_bt} al {f_fin_bt})"
            )

            fig_bt.update_xaxes(
                hoverformat="%d/%m/%Y %H:%M hrs",
                rangeslider_visible=True,
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1D", step="day", stepmode="backward"),
                        dict(count=7, label="7D", step="day", stepmode="backward"),
                        dict(count=14, label="14D", step="day", stepmode="backward"),
                        dict(step="all", label="Todo el rango")
                    ])
                )
            )

            fig_bt.update_traces(
            hovertemplate="<b>%{fullData.name}</b>: %{y:.1f} viajes<extra></extra>"
            )

            fig_bt.update_layout(template="plotly_white", hovermode="x unified")
            st.plotly_chart(fig_bt, use_container_width=True)
        else:
            st.warning("No hay datos disponibles para el rango seleccionado.")
    except Exception as e:
        st.error(f"Error al consultar el backtest: {e}")

# --- PESTAÑA 2: FORECAST 2026 (CON FILTRO DE FECHAS Y ZOOM) ---
# --- PESTAÑA 2: FORECAST 2026 ---
with tab2:
    st.header(f"Pronóstico de Demanda (Oct-Dic 2026) - Estación {estacion_sel}")

    col_fc1, col_fc2 = st.columns(2)
    with col_fc1:
        f_inicio_fc = st.date_input("Desde:", value=date(2026, 10, 1), min_value=date(2026, 10, 1), max_value=date(2026, 12, 31), key="fc_start")
    with col_fc2:
        f_fin_fc = st.date_input("Hasta:", value=date(2026, 10, 14), min_value=date(2026, 10, 1), max_value=date(2026, 12, 31), key="fc_end")

    try:
        query_fc = f"""
            SELECT 
                fecha::VARCHAR AS fecha_str,
                hora,
                salidas_pred,
                arribos_pred
            FROM predictions
            WHERE estacion_id::INTEGER = {int(estacion_sel)}
              AND fecha BETWEEN '{f_inicio_fc}' AND '{f_fin_fc}'
            ORDER BY fecha, hora
        """
        df_fc = conn.execute(query_fc).df()

        if not df_fc.empty:
            df_fc['fecha_clean'] = df_fc['fecha_str'].str.slice(0, 10)
            df_fc['fecha_hora'] = pd.to_datetime(
                df_fc['fecha_clean'] + ' ' + df_fc['hora'].astype(str).str.zfill(2) + ':00:00'
            )

            df_fc_melted = df_fc.melt(
                id_vars=['fecha_hora'], 
                value_vars=['salidas_pred', 'arribos_pred'],
                var_name='Tipo de Flujo', 
                value_name='Viajes Pronosticados'
            )

            fig_fc = px.line(
                df_fc_melted, 
                x='fecha_hora', 
                y='Viajes Pronosticados', 
                color='Tipo de Flujo',
                title=f"Pronóstico Horario ({f_inicio_fc} al {f_fin_fc})"
            )

            fig_fc.update_xaxes(
                hoverformat="%d/%m/%Y %H:%M hrs",
                rangeslider_visible=True,
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1D", step="day", stepmode="backward"),
                        dict(count=7, label="7D", step="day", stepmode="backward"),
                        dict(count=14, label="14D", step="day", stepmode="backward"),
                        dict(step="all", label="Todo el rango")
                    ])
                )
            )

            fig_fc.update_traces(
                hovertemplate="<b>%{x|%d/%m/%Y %H:%M hrs}</b><br>Viajes: <b>%{y:.1f}</b><extra>%{fullData.name}</extra>"
            )

            fig_fc.update_layout(template="plotly_white", hovermode="x unified")
            st.plotly_chart(fig_fc, use_container_width=True)
        else:
            st.warning("No hay predicciones disponibles para las fechas seleccionadas.")
    except Exception as e:
        st.error(f"Error al consultar el forecast: {e}")
# --- PESTAÑA 3: EVALUACIÓN DEL MODELO ---
with tab3:
    st.header("📊 Evaluación General del Modelo")
    st.markdown("Métricas globales de precisión del algoritmo LightGBM sobre el periodo de prueba (Backtest 2025).")

    try:
        # 1. Cargar y mostrar tarjetas de métricas (KPIs)
        df_metrics = conn.execute("SELECT metrica, valor FROM model_metrics").df()
        
        if not df_metrics.empty:
            metrics_dict = dict(zip(df_metrics['metrica'], df_metrics['valor']))
            
            mae_val = metrics_dict.get('MAE', 0.0)
            rmse_val = metrics_dict.get('RMSE', 0.0)
            wape_val = metrics_dict.get('WAPE', 0.0)
            
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric(label="MAE (Error Absoluto Medio)", value=f"{mae_val:.3f} viajes")
            with col_m2:
                st.metric(label="RMSE (Raíz del Error Cuadrático)", value=f"{rmse_val:.3f}")
            with col_m3:
                st.metric(label="WAPE / WMAE (%)", value=f"{wape_val:.2f}%")
        else:
            st.warning("No se encontraron registros en la tabla 'model_metrics'.")

        st.markdown("---")
        
        # 2. Cargar y mostrar gráfica de Importancia de Variables (Feature Importance)
        st.subheader("🎯 Importancia de Características (Feature Importance)")
        st.markdown("Ranking de las variables explicativas que más influyen en las predicciones del modelo:")

        df_feat_imp = conn.execute("SELECT feature, importance FROM feature_importance ORDER BY importance ASC").df()

        if not df_feat_imp.empty:
            fig_imp = px.bar(
                df_feat_imp,
                x='importance',
                y='feature',
                orientation='h',
                labels={'importance': 'Importancia Absoluta', 'feature': 'Variable'},
                title="Importancia Relativa de Variables en LightGBM",
                color='importance',
                color_continuous_scale='Blues'
            )
            fig_imp.update_layout(template="plotly_white", showlegend=False, height=450)
            st.plotly_chart(fig_imp, use_container_width=True)
        else:
            st.warning("No se encontraron datos en la tabla 'feature_importance'.")

    except Exception as e:
        st.error(f"Error al cargar la evaluación del modelo: {e}")
        st.info("Asegúrate de ejecutar 'python src/train.py' para popular las tablas de evaluación en DuckDB.")