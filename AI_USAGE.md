
DECLARACIÓN DE USO DE INTELIGENCIA ARTIFICIAL (AI_USAGE)

Sistema de Pronóstico de Demanda Ecobici CDMX

Este documento describe con precisión el rol de la Inteligencia Artificial (IA) como herramienta de apoyo técnico durante el desarrollo del proyecto.

1. SOPORTE Y ASISTENCIA DE LA IA


La IA fue utilizada de forma puntual en las siguientes tareas de apoyo:

- Depuración y corrección de errores de código:
  * Resolución de excepciones de memoria (ArrayMemoryError) mediante técnicas 
    de downcasting (float32/int16) y recolección de basura.

  * Solución a bloqueos de archivo de base de datos en DuckDB (IOException) 
    implementando conexiones en modo solo lectura (read_only=True).

  * Corrección en el formateo y concatenación de marcas temporales (fecha y hora) en Pandas para evitar truncamientos a la medianoche.



- Formato visual y experiencia de usuario en el Dashboard:
  * Estilización de gráficos dinámicos con Plotly Express (configuración de 
    tooltips limpios sin etiquetas redundantes, inclusión de sliders de tiempo 
    y selectores de rango de fecha).



- Explicación de conceptos teóricos y analíticos:
  * Explicación e interpretación analítica de las métricas de evaluación de 
    series de tiempo.

  * Justificación del comportamiento visual de las predicciones frente a los 
    datos reales (desfases en horas pico y regresión a la media).

  * Creación de formato AI_USAGE




2. VERIFICACIÓN, CONTROL Y EJECUCIÓN POR PARTE DEL AUTOR

En el proyecto, fui responsable de:
- Concepción y arquitectura del sistema: Diseño del pipeline modular end-to-end 
(Ingesta -> Feature Engineering -> Entrenamiento -> Persistencia -> Dashboard).

- Selección de modelos y experimentos: Decisión de comparar el Baseline Histórico frente a LightGBM e inclusión de características avanzadas (lags de 24h/168h y perfiles históricos).

- Aplicación y validación de cambios: Implementación directa de las soluciones 
en el entorno local, ejecución de los scripts de entrenamiento y verificación 
de la integridad de los datos en DuckDB.

- Aprobación de interfaz y resultados: Prueba funcional del dashboard en Streamlit, confirmación del correcto despliegue visual por horas y validación final del rendimiento del modelo.