# Bia Assignment Engine

Motor de asignacion comercial para distribuir registros entre vendedores con reglas deterministicas, AI asistida, aprobacion humana y trazabilidad en Snowflake.

## Arquitectura

```text
Streamlit -> FastAPI / dominio -> Snowflake
                         |
                         +-> Groq opcional
```

- `app/assignment.py`: metodos de asignacion y reglas de capacidad.
- `app/reassignment.py`: previsualizacion de redistribuciones.
- `app/snowflake_repository.py`: lectura y persistencia en Snowflake.
- `app/groq_provider.py`: analisis estructurado de notas comerciales.
- `app/streamlit_app.py`: consola operativa.
- `app/api.py`: API y documentacion OpenAPI.
- `sql/`: esquema y migraciones de auditoria.

## Instalacion

Usar Python 3.11+ en un entorno virtual o Conda:

```bash
python -m pip install -e ".[dev,snowflake,groq]"
```

Copia `.env.example` como `.env` y completa las variables localmente. No subas `.env`.

```text
SNOWFLAKE_ACCOUNT=FQ24217.us-east-2.aws
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_WAREHOUSE=
SNOWFLAKE_DATABASE=
SNOWFLAKE_SCHEMA=
SNOWFLAKE_ROLE=
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
```

## Ejecucion

Consola:

```bash
streamlit run app/streamlit_app.py
```

API:

```bash
uvicorn app.api:app --reload
```

Documentacion API: `http://127.0.0.1:8000/docs`.

## Despliegue en Streamlit Community Cloud

1. Conecta el repositorio de GitHub.
2. Selecciona `app/streamlit_app.py` como archivo principal.
3. Configura los secretos del archivo `.env.example` en la sección Secrets.
4. Comparte la URL generada.

El repositorio no incluye datos originales ni credenciales. Streamlit ejecuta la consola y conecta directamente con Snowflake y Groq usando secretos.

## Metodos

- `weighted_score`: zona, segmento, capacidad y balance con pesos configurables.
- `balanced`: prioriza menor ocupacion relativa.
- `round_robin`: reparte turnos respetando capacidad y ausencias.
- `ai_assisted`: Groq interpreta notas, prioriza registros y refuerza coincidencias de segmento. Las reglas duras siempre prevalecen.

## Flujo operativo

1. Seleccionar fuente, registros y metodo.
2. Previsualizar.
3. Preparar borrador.
4. Revisar razones y candidatos.
5. Aprobar.
6. Ejecutar.
7. Consultar trazabilidad.

Los borradores expiran despues de 24 horas. Una corrida `previewed`, `cancelled` o `expired` no cuenta como carga. Solo las corridas `executed` afectan la carga.

## Reasignaciones

La vista de reasignaciones solo propone movimientos de vendedores sobrecargados. Protege registros con actividad reciente y no ejecuta cambios automaticamente.

## Pruebas

```bash
python -m pytest -q
```

Las pruebas cubren normalizacion, capacidad, ausencias, metodos, AI, conciliacion historica y reglas de reasignacion.

## Datos privados

Los archivos originales del reto (`data/`, `requerimiento.txt` y `up.sql`) estan excluidos del repositorio mediante `.gitignore`.
