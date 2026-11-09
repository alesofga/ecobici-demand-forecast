import hashlib
import os
from urllib.parse import urljoin
import duckdb
import pandas as pd
import requests
from bs4 import BeautifulSoup

DB_PATH = 'data/ecobici.db'
BASE_URL = 'https://ecobici.cdmx.gob.mx/datos-abiertos/'

STATIONS_URLS = [
    'https://raw.githubusercontent.com/GrupoGiganteDTI/ecobici-estado-estaciones/main/estaciones.csv',
    'https://raw.githubusercontent.com/GrupoGiganteDTI/ecobici-estado-estaciones/master/estaciones.csv',
]

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
        ' like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
}


def init_db(con):
  """Crea esquema, tablas de hechos y bitácora de archivos procesados."""
  con.execute("""
        CREATE TABLE IF NOT EXISTS processed_files (
            filename VARCHAR PRIMARY KEY,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS dim_estacion (
            estacion_id INTEGER PRIMARY KEY,
            nombre VARCHAR,
            latitud DOUBLE,
            longitud DOUBLE
        );

        CREATE TABLE IF NOT EXISTS raw_viajes (
            viaje_id VARCHAR PRIMARY KEY,
            bici_id VARCHAR,
            genero VARCHAR,
            edad INTEGER,
            estacion_retiro_id INTEGER,
            fecha_retiro DATE,
            hora_retiro TIME,
            estacion_arribo_id INTEGER,
            fecha_arribo DATE,
            hora_arribo TIME
        );

        CREATE TABLE IF NOT EXISTS fact_viajes_horarios (
            fecha DATE,
            hora INTEGER,
            estacion_id INTEGER,
            salidas INTEGER,
            arribos INTEGER,
            PRIMARY KEY (fecha, hora, estacion_id)
        );
    """)


def fetch_stations_catalog(con):
  """Ingesta la dimensión de estaciones si no ha sido poblada."""
  count = con.execute('SELECT COUNT(*) FROM dim_estacion').fetchone()[0]
  if count > 0:
    print(f'Catálogo de estaciones ya cargado ({count} estaciones). Omitiendo...')
    return

  print('Cargando catálogo de estaciones...')
  for url in STATIONS_URLS:
    try:
      df = pd.read_csv(url)
      col_map = {
          'id': 'estacion_id',
          'name': 'nombre',
          'latitude': 'latitud',
          'longitude': 'longitud',
      }
      df = df.rename(
          columns={k: v for k, v in col_map.items() if k in df.columns}
      )

      required_cols = ['estacion_id', 'nombre', 'latitud', 'longitud']
      available_cols = [c for c in required_cols if c in df.columns]
      df = df[available_cols]

      con.execute('INSERT OR REPLACE INTO dim_estacion SELECT * FROM df')
      print(f'Catálogo cargado desde {url}: {len(df)} estaciones.')
      break
    except Exception:
      continue


def get_monthly_zip_urls():
  """Extrae las URLs de descarga ordenándolas cronológicamente por etiqueta visual."""
  response = requests.get(BASE_URL, headers=HEADERS)
  soup = BeautifulSoup(response.text, 'html.parser')
  url_pairs = []

  for a in soup.find_all('a', href=True):
    href = a['href']
    text = a.get_text(strip=True)
    href_lower = href.lower()

    if '.csv' in href_lower or '.zip' in href_lower:
      full_url = urljoin(BASE_URL, href)
      url_pairs.append((text, full_url))

  unique_pairs = list(set(url_pairs))
  sorted_pairs = sorted(unique_pairs, key=lambda x: x[0])
  return [url for text, url in sorted_pairs]


def normalize_columns(df):
  """Estandariza variaciones de columnas históricas (2010 a 2026)."""
  column_mapping = {
      'Bici': 'bici_id',
      'Bici_Id': 'bici_id',
      'bici': 'bici_id',
      'Genero': 'genero',
      'Genero_Usuario': 'genero',
      'genero': 'genero',
      'Edad': 'edad',
      'Edad_Usuario': 'edad',
      'edad': 'edad',
      'Ciclo_Estacion_Retiro': 'estacion_retiro_id',
      'Estacion_Retiro': 'estacion_retiro_id',
      'estacion_retiro': 'estacion_retiro_id',
      'Fecha_Retiro': 'fecha_retiro',
      'FechaRetiro': 'fecha_retiro',
      'fecha_retiro': 'fecha_retiro',
      'Hora_Retiro': 'hora_retiro',
      'HoraRetiro': 'hora_retiro',
      'hora_retiro': 'hora_retiro',
      'Ciclo_Estacion_Arribo': 'estacion_arribo_id',
      'Estacion_Arribo': 'estacion_arribo_id',
      'estacion_arribo': 'estacion_arribo_id',
      'Fecha_Arribo': 'fecha_arribo',
      'FechaArribo': 'fecha_arribo',
      'fecha_arribo': 'fecha_arribo',
      'Hora_Arribo': 'hora_arribo',
      'HoraArribo': 'hora_arribo',
      'hora_arribo': 'hora_arribo',
  }

  df = df.rename(columns=column_mapping)
  target_cols = [
      'bici_id',
      'genero',
      'edad',
      'estacion_retiro_id',
      'fecha_retiro',
      'hora_retiro',
      'estacion_arribo_id',
      'fecha_arribo',
      'hora_arribo',
  ]
  for col in target_cols:
    if col not in df.columns:
      df[col] = None

  return df[target_cols]


def process_and_ingest(con, zip_urls):
    """Procesa e ingesta omitiendo descargas y lecturas de archivos ya completados."""
    os.makedirs("data/raw", exist_ok=True)

    processed_set = set(con.execute("SELECT filename FROM processed_files").df()['filename'].tolist())

    for url in zip_urls:
        filename = url.split('/')[-1]
        local_path = os.path.join("data/raw", filename)

        if filename in processed_set:
            print(f"{filename} ya fue ingestado en DuckDB. Saltando...")
            continue

        if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
            print(f"Descargando {filename}...")
            res = requests.get(url, headers=HEADERS, stream=True)
            with open(local_path, 'wb') as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
        else:
            print(f"Usando archivo en disco: {filename}")

        print(f"Procesando {filename}...")
        try:
            try:
                df = pd.read_csv(local_path, low_memory=False, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(local_path, low_memory=False, encoding='latin1')

            df = normalize_columns(df)

            # Extracción robusta de números de estación
            for col in ['estacion_retiro_id', 'estacion_arribo_id']:
                df[col] = df[col].astype(str).str.extract(r'(\d+)', expand=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.dropna(subset=['estacion_retiro_id', 'fecha_retiro', 'hora_retiro'])
            df['estacion_arribo_id'] = df['estacion_arribo_id'].fillna(df['estacion_retiro_id'])

            df['estacion_retiro_id'] = df['estacion_retiro_id'].astype(int)
            df['estacion_arribo_id'] = df['estacion_arribo_id'].astype(int)

            # Hash idempotente seguro ante nulos/floats
            df['viaje_id'] = (
                df['estacion_retiro_id'].astype(str) + '_' + 
                df['fecha_retiro'].astype(str) + '_' + 
                df['hora_retiro'].astype(str) + '_' + 
                df['bici_id'].fillna('').astype(str)
            ).apply(lambda x: hashlib.md5(str(x).encode()).hexdigest())

            df['fecha_retiro'] = pd.to_datetime(df['fecha_retiro'], format='mixed', dayfirst=True, errors='coerce').dt.date
            df['fecha_arribo'] = pd.to_datetime(df['fecha_arribo'], format='mixed', dayfirst=True, errors='coerce').dt.date
            df['hora_retiro'] = pd.to_datetime(df['hora_retiro'].astype(str), format='%H:%M:%S', errors='coerce').dt.time
            df['hora_arribo'] = pd.to_datetime(df['hora_arribo'].astype(str), format='%H:%M:%S', errors='coerce').dt.time

            con.execute("INSERT OR IGNORE INTO raw_viajes SELECT viaje_id, bici_id, genero, edad, estacion_retiro_id, fecha_retiro, hora_retiro, estacion_arribo_id, fecha_arribo, hora_arribo FROM df")

            con.execute("INSERT OR REPLACE INTO processed_files (filename) VALUES (?)", [filename])
            print(f"✓ {filename} ingestado exitosamente.")

        except Exception as e:
            print(f" Error al procesar {filename}: {e}")


def build_fact_hourly(con):
    """Agrega los datos por hora (05:00 a 23:59) y genera la tabla de hechos filtrando nulos."""
    print("Construyendo/Actualizando tabla agregada fact_viajes_horarios...")

    con.execute("""
        INSERT OR REPLACE INTO fact_viajes_horarios
        WITH salidas AS (
            SELECT 
                fecha_retiro AS fecha,
                EXTRACT(HOUR FROM hora_retiro)::INTEGER AS hora,
                estacion_retiro_id AS estacion_id,
                COUNT(*)::INTEGER AS salidas
            FROM raw_viajes
            WHERE fecha_retiro IS NOT NULL 
              AND hora_retiro IS NOT NULL 
              AND estacion_retiro_id IS NOT NULL
              AND EXTRACT(HOUR FROM hora_retiro) BETWEEN 5 AND 23
            GROUP BY 1, 2, 3
        ),
        arribos AS (
            SELECT 
                fecha_arribo AS fecha,
                EXTRACT(HOUR FROM hora_arribo)::INTEGER AS hora,
                estacion_arribo_id AS estacion_id,
                COUNT(*)::INTEGER AS arribos
            FROM raw_viajes
            WHERE fecha_arribo IS NOT NULL 
              AND hora_arribo IS NOT NULL 
              AND estacion_arribo_id IS NOT NULL
              AND EXTRACT(HOUR FROM hora_arribo) BETWEEN 5 AND 23
            GROUP BY 1, 2, 3
        )
        SELECT 
            COALESCE(s.fecha, a.fecha) AS fecha,
            COALESCE(s.hora, a.hora) AS hora,
            COALESCE(s.estacion_id, a.estacion_id) AS estacion_id,
            COALESCE(s.salidas, 0)::INTEGER AS salidas,
            COALESCE(a.arribos, 0)::INTEGER AS arribos
        FROM salidas s
        FULL OUTER JOIN arribos a
            ON s.fecha = a.fecha 
           AND s.hora = a.hora 
           AND s.estacion_id = a.estacion_id
        WHERE COALESCE(s.fecha, a.fecha) IS NOT NULL
          AND COALESCE(s.hora, a.hora) IS NOT NULL
          AND COALESCE(s.estacion_id, a.estacion_id) IS NOT NULL;
    """)

    con.execute("""
        INSERT OR IGNORE INTO dim_estacion (estacion_id, nombre, latitud, longitud)
        SELECT DISTINCT estacion_id, 'Estación ' || estacion_id::VARCHAR, NULL, NULL
        FROM fact_viajes_horarios;
    """)

    print("✓ Ingesta agregada completada exitosamente.")

if __name__ == '__main__':
  conn = duckdb.connect(DB_PATH)
  init_db(conn)
  fetch_stations_catalog(conn)
  urls = get_monthly_zip_urls()
  process_and_ingest(conn, urls)
  build_fact_hourly(conn)
  conn.close()