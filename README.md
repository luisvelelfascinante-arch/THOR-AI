# THOR IA v2.0

Bot de **señales** (no ejecuta órdenes) para opciones binarias/forex,
reestructurado en capas independientes. Ver `CHANGELOG.md` para el detalle
de qué cambió respecto a v1 y por qué, y `INFORME_FASE1_AUDITORIA.md` para
la auditoría completa del proyecto original.

## Arquitectura

```
THOR-AI-v2/
├── main.py                       # entrada
├── diagnostico.py                # modo diagnóstico (ciclo único)
├── test_telegram.py
├── CHANGELOG.md
├── INFORME_FASE1_AUDITORIA.md
├── PERFORMANCE.md                 # optimizaciones de rendimiento y benchmarks (v3.0)
├── FUENTES.md                     # fuentes de la investigación aplicada (v2.1+)
├── requirements.txt
├── .env.example
├── core/
│   ├── config.py                  # config por dominio (estrategia/operativa/riesgo/...)
│   ├── logging_setup.py
│   └── brain.py                   # loop principal
├── connectors/
│   └── mt5_connector.py           # SOLO conexión MT5
├── data/
│   └── data_provider.py           # SOLO adquisición de velas
├── indicators/
│   ├── indicator_bank.py          # cálculo PURO, versión escalar (vivo) y vectorizada (backtesting)
│   ├── signal_bank.py             # señales técnicas vectorizadas con NumPy (v3.0)
│   ├── cache.py                   # caché en disco de indicadores, invalidación automática (v3.0)
│   └── volatility_filter.py       # filtro ATR, inactivo por defecto (v2.1)
├── strategy/
│   ├── confluence.py              # motor v1, activo por defecto
│   ├── strategy_engine.py         # selecciona motor + cooldown
│   └── scanner.py                 # escanea todos los pares
├── scoring/
│   └── score_engine.py            # motor v2 (Fase 3, corregido en v2.1) — NO activo por defecto
├── risk/
│   └── risk_manager.py            # límites de señales, racha de pérdidas
├── backtesting/
│   ├── loader.py                  # carga CSV histórico REAL
│   ├── export_historico.py        # exporta histórico real desde tu MT5
│   ├── backtest_engine.py         # simulación en 2 etapas (indicadores cacheados + evaluación vectorizada)
│   ├── monte_carlo.py             # reshuffle de operaciones para bandas de drawdown (v2.2)
│   └── run_backtest.py            # CLI, con multiprocessing por par (v3.0)
├── optimization/
│   └── optimizer.py               # grid-search + walk-forward, indicadores reutilizados entre combinaciones
├── notifications/
│   └── telegram_service.py        # mensaje enriquecido (Fase 6)
├── storage/
│   ├── history.py                 # historial de señales en vivo
│   └── stats.py
├── tests/                         # pruebas automatizadas (v3.0) — no requieren MT5 conectado
│   ├── test_strategy_logic.py
│   ├── test_risk_manager.py
│   ├── test_backtest_stats.py
│   ├── test_monte_carlo.py
│   └── test_optimizer_folds.py
├── legacy/
│   ├── thor_score.py              # código muerto de v1, conservado
│   └── price_action.py            # placeholder, pendiente material del curso
├── data_files/
│   ├── historial.csv              # señales reales enviadas
│   ├── historicos/                # CSV que tú exportes para backtesting
│   ├── cache/                     # caché de indicadores (se genera sola, se puede borrar)
│   └── backtests/                 # resultados de backtesting/optimización
└── logs/thor.log
```

## Pruebas automatizadas

```bash
python -m unittest discover tests
```

27 pruebas, cubren la lógica de decisión (confluencia y score ponderado,
incluyendo el caso de redundancia de momentum corregido en v2.1), el
gestor de riesgo, las estadísticas de backtesting (winrate, significancia
estadística), Monte Carlo, y la división en folds del walk-forward. No
requieren MT5 conectado ni datos históricos — corren en cualquier momento
como chequeo rápido de que nada se rompió.

## Instalación

```bash
pip install -r requirements.txt
cp .env.example .env
# completa TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TWELVE_DATA_API_KEY
```

## Fuente de datos (v4.0)

THOR AI soporta 2 fuentes para el modo EN VIVO (el backtesting siempre
lee CSV, no depende de esto):

- **`twelve_data`** (default): API en la nube (twelvedata.com), NO
  requiere tener ningún terminal abierto. Necesitas una API key gratis —
  ver más abajo. **Límite del plan gratuito: 8 llamadas/minuto, 800/día,
  1 crédito por símbolo por llamada.** Con eso en mente,
  `core/config.py` calcula automáticamente un intervalo de escaneo que no
  agota el cupo diario según cuántos `SYMBOLS` configures (no lo bajes a
  mano sin hacer la cuenta).
- **`mt5`**: requiere Windows con terminal MetaTrader 5 abierto y sesión
  iniciada. Es el modo original (v1-v3).

Se elige con `DATA_SOURCE=twelve_data` o `DATA_SOURCE=mt5` en tu `.env`.

### Conseguir tu API key de Twelve Data

1. Ve a https://twelvedata.com/pricing y elige el plan **Basic** (gratis,
   no pide tarjeta).
2. Crea la cuenta (email o Google).
3. La API key aparece directo en tu dashboard al terminar el registro.
4. Pégala en `TWELVE_DATA_API_KEY=` en tu `.env`.

### Probar la conexión

```bash
python test_twelve_data.py   # pide unas pocas velas de un par, sin generar señales
```

## Ejecutar en vivo

```bash
python main.py            # loop en vivo (Twelve Data por defecto, no requiere MT5 abierto; con DATA_SOURCE=mt5 sí)
python main.py --stats    # estadísticas del historial en vivo
python diagnostico.py     # diagnóstico de un solo ciclo, motivo exacto de rechazo
python test_telegram.py   # prueba Telegram sin tocar MT5
```

## Backtesting (Fase 4) — antes de cambiar cualquier cosa en vivo

```bash
# 1. En tu máquina con MT5, exporta histórico real:
python backtesting/export_historico.py --desde 2024-01-01 --hasta 2024-06-01

# 2. Corre el backtest con el motor actual (v1, activo):
python backtesting/run_backtest.py --carpeta data_files/historicos --motor confluencia_total

# 3. Compáralo contra el motor nuevo (Fase 3, propuesta):
python backtesting/run_backtest.py --carpeta data_files/historicos --motor score_ponderado

# 4. Con bandas de drawdown realistas (Monte Carlo por reshuffle):
python backtesting/run_backtest.py --carpeta data_files/historicos --monte-carlo

# 5. Con el filtro de volatilidad ATR activado, para comparar:
python backtesting/run_backtest.py --carpeta data_files/historicos --atr-filtro
```

Genera `data_files/backtests/trades_<motor>.csv` (cada operación simulada)
y `stats_<motor>.json` (winrate, profit factor, drawdown, mejores
horas/pares). Los supuestos de la simulación están documentados en el
docstring de `backtesting/backtest_engine.py` — revísalos antes de confiar
en el número.

## Optimización (Fase 5)

```bash
python optimization/optimizer.py --carpeta data_files/historicos
# o, más riguroso (walk-forward anchored con varios folds):
python optimization/optimizer.py --carpeta data_files/historicos --rolling --folds 5
```

Compara `confluencia_total` vs `score_ponderado` en varios umbrales,
descarta configuraciones con menos de 30 operaciones (evita rankear
ruido), y advierte explícitamente sobre sobreajuste — el resultado es
"qué hubiera funcionado mejor en el pasado", no una garantía futura.

## Decisión pendiente — motor de score (Fase 3)

`STRATEGY_MODE=confluencia_total` es el default y es lo único que corre
en vivo. `score_ponderado` existe, es funcional, y se puede correr contra
backtesting — pero su clasificación de factores obligatorios/ponderados
es una propuesta técnica, no una transcripción verificada del curso de
Juan Fernández. Antes de poner `STRATEGY_MODE=score_ponderado` en tu
`.env` para producción: corre el backtesting de ambos motores sobre el
mismo período histórico y compara resultados.

## Otras decisiones pendientes (heredadas de v1, sin resolver)

1. **Price action real del curso** — `legacy/price_action.py` sigue
   siendo un placeholder de 3 patrones estándar, no la metodología del
   profesor (material nunca llegó).
2. **Resultado WIN/LOSS por señal** — el bot no ejecuta órdenes, así que
   no conoce el resultado real. Sin esto, `storage/stats.py` solo reporta
   actividad, no rentabilidad, y `risk_manager.evaluar_racha_perdidas()`
   no tiene datos para operar.
3. **Ejecución automática de operaciones** — sigue sin implementarse. Es
   una decisión de mucho más riesgo (dinero real sin confirmación humana)
   que no se agrega sin pedirlo explícitamente.

## Rendimiento (v3.0)

Ver `PERFORMANCE.md` para el detalle completo de cada optimización y sus
benchmarks. Resumen: indicadores vectorizados con NumPy (no bucles fila
por fila), caché en disco con invalidación automática, backtesting en 2
etapas (indicadores calculados una vez, reutilizados en todas las
combinaciones de umbral/motor), y multiprocessing por par en backtesting
y optimización.

```bash
python backtesting/run_backtest.py --carpeta data_files/historicos --sin-paralelo   # desactiva multiprocessing
python backtesting/run_backtest.py --carpeta data_files/historicos --limpiar-cache  # fuerza recálculo total
```

Para escalar a más pares sin tocar código, define en tu `.env`:
```
PARES=EURUSD,GBPUSD,USDJPY,EURJPY,GBPJPY,AUDUSD,USDCAD,NZDUSD
```

