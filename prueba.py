import duckdb

conn = duckdb.connect("data/ecobici.db", read_only=True)

# Ver el promedio de viajes por hora para la estación seleccionada (ej. estacion_id = 1)
print(conn.execute("""
    SELECT hora, AVG(salidas) AS promedio_salidas
    FROM backtest_predictions
    WHERE estacion_id = 1
    GROUP BY hora
    ORDER BY hora
""").df())

conn.close()