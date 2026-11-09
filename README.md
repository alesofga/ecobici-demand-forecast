1. Cómo correr el modelo: 
	- Requisitos: 
		- Python 3.10 o más nuevo 
		- Acceso a internet. 
	1. Primer paso: clonar el repositorio e instalar , el depósito está en la siguiente liga: https://github.com/alesofga/ecobici-demand-forecast
	2. Segundo paso: Se necesitan ejecutar los comandos en la terminal de la computadora o en vs code. 
		- pip install -r requirements.txt
		- python src/ingest.py
		- python src/train.py
		- python python -m streamlit run src/app.py 
		 si no se tiene streamlit, se tiene que hacer un pip install streamlit
		- en sí hay un archivo que se llama run.ps1 para que se haga de manera automática, pero creo que es más confiable así.
2. Decisiones de arquitectura: 
	1. Almacenamiento DuckDB en modo "solo lectura": 
		Esto con el fin de evitar bloqueos de archivos cuando Streamlit lee datos mientras los scripts de procesamiento generan la base de datos.
	2. Variables Cíclicas de Calendario: 
		Transformación del tiempo usando senos y cosenos (sin(2$\pi$ x hora/24 ), cos(2$\pi$ x hora/24)), esto con el fin de tener continuidad entre las 23:00 y las 00:00. 
	3. Perfiles Históricos: 
		Inclusión histórica del promedio, máximo y desviación estándar por hora y/o día de la semana, sumando a rezagos temporales a 24 horas y 168 horas. Esto nos sirve para atenuar picos de demanda en horas pico.
	4. Optimización de RAM: 
		Se convierten los registros de datos en tipo compactos. 
	5. Construcción de Marcas Temporales en Pandas: 
		La construcción del vector timestamp-fecha_hora se trasladó de SQL a Pandas mediante pd.to_datetime con ceros a la izquierda.
3. Modelos probados: 
	1. Baseline Histórico: 
		Asigna a cada hora del periodo de prueba el promedio histórico observado en el conjunto de entrenamiento, se probó porque es muy usado para establecer el benchmark. Sirve para validar si un modelo de ML aporta valor analítico. Presentó un MAE de 1.84 viajes y un WMAPE del 38.5%, el cuál es muy elevado, demostrando que no era capaz de adaptarse a los patrones estacionales o a dinámicas atípicas. 
	2. Light GBM Regressor: Se usó un Gradient Boosting entrenado solo con variables temporales básicas. Se probó porque ofrece una velocidad de entrenamiento superior a otros modelos y un bajo recurso de matrices. Superó el baseline, sin embargo, surgió una regresión a la media, que es un suavizado excesivo de los árboles de decisión. Como no tenía una visualización, se aplanaba la curva y subestimaba los picos de demanda en horas pico. 
	3. Light GBM Regessor con Feature Engineering Avanzado y Downcasting
		Se incluyeron características de perfil histórico y variables de rezago temporal a 24 horas y 168 horas, se optimizaron para mejor manejo de memoria, se probo para generar una ventana móvil, la cual pudiera ayudar a la precisión de la predicción de la demanda. Es el modelo final, debido a que logró la mejor precisión, se redujo el MAE a 1.10 viajes y se bajó el WMAPE a 23.12, logrando tener un modelo más apegado a la realidad sin saturar la RAM.
4. Limitaciones: 
	1. Estaciones con Arranque en Frío: Hay estaciones de creación reciente que no tienen historial en el periodo de entrenamiento. Se predicen con el promedio global del sistema por hora/día.
	2. No se contemplan factores externos: Depende exclusivamente de patrones temporales e históricos. 