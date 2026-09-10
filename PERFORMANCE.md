# THOR IA — Optimización de rendimiento (v3.0)

Este documento se llena a medida que se hacen los cambios, con números
reales de antes/después, no estimaciones. Todas las pruebas de esta
sesión corrieron sin red (sin `ta` ni MT5 reales) usando un stub
matemáticamente simplificado pero funcional de la librería `ta` — sirve
para medir la FORMA de la mejora (O(n·ventana) → O(n), N llamadas → 1
llamada), no el tiempo exacto en tu máquina con indicadores reales. La
magnitud real la vas a ver tú al correrlo.

## Cuellos de botella encontrados, en orden de impacto

### 1. Indicadores recalculados desde cero por vela (ya corregido antes)
`calcular_confluencia()` recibía una ventana de ~600 velas y reconstruía
cada indicador desde cero, por cada una de las ~30,000 velas del
histórico. Corregido con `calcular_confluencia_serie()` (vectorizado,
una sola vez por serie completa). Medido: 30,541 velas, ~2.6s con el
stub simplificado (antes, con el bucle por ventana, del orden de minutos
a horas dependiendo del tamaño del histórico).

### 2. El optimizador recalculaba los MISMOS indicadores una vez POR CADA
   combinación de umbral × motor que probaba
Con 5 umbrales × 2 motores = 10 combinaciones, y 5 pares, esto eran 50
veces el mismo cálculo de indicadores (que no depende del umbral ni del
motor — los indicadores son los mismos, solo cambia qué umbral/regla se
les aplica encima). Con `--rolling` (walk-forward, 5 folds) esto se
multiplicaba otra vez por hasta 4-5.

**Corrección**: separar "calcular indicadores" (una vez por par/segmento)
de "evaluar motor+umbral sobre esos indicadores ya calculados" (barato,
se puede repetir cientos de veces sin problema). Ver sección "Arquitectura
nueva" abajo.

### 3. La decisión de señal (confluencia/score) se evaluaba con un bucle
   de Python fila por fila, incluso después de vectorizar indicadores
`evaluar_confluencia()`/`calcular_score()` llamaban 6 funciones por cada
fila, en un `for` de Python — para 30,000 filas eso es 180,000+ llamadas
a función solo para la lógica de decisión, antes de llegar siquiera al
cooldown.

**Corrección**: `indicators/signal_bank.py` calcula las 6 confirmaciones
para TODA la serie de una vez con NumPy (comparaciones vectorizadas), y
`strategy/confluence.py` / `scoring/score_engine.py` tienen ahora una
versión vectorizada que evalúa las 30,000 filas en un solo paso. El
bucle de Python que queda solo recorre las señales que YA pasaron el
umbral (normalmente un puñado, no 30,000) para aplicarles el cooldown.

### 4. Sin caché — cada corrida repetía cálculo aunque los datos no
   hubieran cambiado
Si corrías `run_backtest.py` dos veces seguidas sobre el mismo CSV (por
ejemplo, comparando motores), o el optimizador repetía sobre el mismo
segmento en cada fold, los indicadores se recalculaban igual.

**Corrección**: `indicators/cache.py` — cachea en disco
(`data_files/cache/`) la serie de indicadores ya calculada, con una
clave que incluye el par, el rango de fechas, el tamaño de los datos, Y
un hash de los parámetros de configuración (BB, RSI, MACD, etc.) — si
cambias un parámetro en `.env` o `config.py`, la caché se invalida sola,
no sirve un resultado viejo por error.

### 5. Backtesting por pares corría secuencial (uno tras otro) pudiendo
   ser paralelo
Los pares son independientes entre sí — el cálculo de EURUSD no depende
de GBPUSD. Es un caso ideal para multiprocessing.

**Corrección**: `run_backtest.py` y `optimizer.py` ahora procesan los
pares en paralelo con `ProcessPoolExecutor` (un proceso por núcleo de tu
CPU, hasta el número de pares). Con 5 pares en una máquina de 4+ núcleos,
esto es hasta ~4-5x más rápido que secuencial, y escala mejor con más
pares (ver punto 7).

### 6. Bug de corrección (no de velocidad): mutación de config global para
   probar umbrales
El optimizador anterior hacía `O.PROBABILIDAD_MINIMA = umbral` para
"inyectar" el umbral a probar — esto es fràgil (afecta estado global
compartido) y ROMPE con multiprocessing (cada proceso nuevo relee su
propio `.env`, no hereda la mutación del proceso padre; el umbral
"inyectado" se perdía silenciosamente en los procesos hijos).

**Corrección**: el umbral ahora se pasa como parámetro explícito a cada
función (`generar_operaciones(..., umbral_minimo=X)`), nunca por mutación
global. Esto también lo vuelve seguro de usar en paralelo.

### 7. Sin plan para "decenas de pares" sin degradar
Con la arquitectura anterior, el tiempo crecía linealmente con: (núm.
pares) × (núm. velas) × (ventana de recálculo) × (núm. combinaciones del
optimizador) — un crecimiento fuera de control.

Con las correcciones 1-6, el tiempo ahora crece aproximadamente como:
(núm. pares / núm. núcleos de CPU) × (núm. velas) × 1 — lineal en velas,
dividido entre núcleos en pares, sin el factor de "ventana" ni de
"combinaciones repetidas". Además, `core.config.estrategia.PARES` ahora
se puede sobreescribir con la variable de entorno `PARES` (lista separada
por comas) sin tocar código, para escalar a más pares sin editar
`config.py`.

## Lo que NO se paralelizó, y por qué (honesto)

- **El loop en vivo (`core/brain.py`) sigue siendo secuencial**, pár por
  par, cada 15 segundos. NO lo paralelicé porque la conexión de MT5
  (`connectors/mt5_connector.py`) es una sesión única con estado — no es
  segura para llamadas concurrentes desde varios hilos/procesos (el
  API de MetaTrader5 no está documentada como thread-safe). Escanear 5-50
  pares secuencialmente, cada uno pidiendo ~600 velas por HTTP/socket
  local a MT5, toma del orden de décimas de segundo por par — con
  decenas de pares, sigue siendo mucho menor a los 15 segundos del ciclo,
  así que no es el cuello de botella real ahí. Si en el futuro esto
  cambia (cientos de pares, ciclo más corto), la solución correcta sería
  un pool de conexiones MT5 (varias sesiones), no hilos sobre una sola
  conexión — lo dejo anotado, no implementado, porque hoy no hace falta.

## Benchmarks (con el stub, ver nota arriba)

Todas las pruebas corrieron en este entorno (sandbox Linux, sin red, con
un stub matemáticamente funcional pero simplificado de `ta` — más liviano
que la librería real, así que los tiempos con `ta` real en tu máquina
serán mayores en términos absolutos, pero la MEJORA relativa entre
antes/después es la misma forma de mejora):

| Prueba | Resultado |
|---|---|
| `backtest_par()`, 1 par, 30,541 velas, caché fría | 0.058s |
| `backtest_par()`, mismo par/datos/config, caché caliente | 0.006s (~10x) |
| 10 combinaciones motor×umbral reutilizando indicadores ya calculados | 0.021s total (2.1 ms/combinación) |
| `optimizar()` completo, 5 pares, split train/test, 10 combinaciones | 0.79s |
| `walk_forward_rolling()`, 5 pares, 5 folds anchored (~4x el trabajo de un split único) | 1.24s |
| `optimizar()` con 20 pares (15,000 velas c/u), preparación en paralelo | 1.04s (preparación: 0.52s) |

**Verificación de correctitud** (no solo velocidad): se comparó la salida
de la versión vectorizada contra la versión escalar original, fila por
fila, sobre 2,400 filas de datos sintéticos — 0 discrepancias en
`confluencia_total` y 0 en `score_ponderado`. La vectorización no cambió
ninguna regla de decisión, solo la velocidad de cálculo.

**Bug real encontrado y corregido durante esta ronda**: al reescribir
`optimization/optimizer.py` para la arquitectura de dos etapas, una
edición anterior (de una sesión previa) había dejado la función
`_correr_config()` completamente sin definir — el código de su cuerpo
quedó huérfano como código muerto dentro de otra función. Esto habría
producido un `NameError` en cuanto se llamara. Se agregó además un
verificador estático nuevo (namespace aplanado por archivo) que detecta
este tipo de error — nombres usados pero nunca definidos en el mismo
archivo — que el verificador anterior (solo cruzaba imports entre
archivos) no detectaba. Ver la sección de pruebas en el chat para el
detalle exacto.

**Caso límite corregido**: `backtesting/monte_carlo.py` fallaba con
`KeyError: 'resultado'` cuando el backtest no generaba ninguna señal (
DataFrame vacío sin columnas). Corregido para devolver un resultado
informativo (`"aplica": false`) en vez de reventar.

