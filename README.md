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
│   └── indicator_bank.py          # cálculo PURO (reutilizable en backtesting)
├── strategy/
│   ├── confluence.py              # motor v1, activo por defecto
│   ├── strategy_engine.py         # selecciona motor + cooldown
│   └── scanner.py                 # escanea todos los pares
├── scoring/
│   └── score_engine.py            # motor v2 (Fase 3) — NO activo por defecto
├── risk/
│   └── risk_manager.py            # límites de señales, racha de pérdidas
├── backtesting/
│   ├── loader.py                  # carga CSV histórico REAL
│   ├── export_historico.py        # exporta histórico real desde tu MT5
│   ├── backtest_engine.py         # simulación vela por vela
│   └── run_backtest.py            # CLI
├── optimization/
│   └── optimizer.py               # grid-search sobre backtesting
├── notifications/
│   └── telegram_service.py        # mensaje enriquecido (Fase 6)
├── storage/
│   ├── history.py                 # historial de señales en vivo
│   └── stats.py
├── legacy/
│   ├── thor_score.py              # código muerto de v1, conservado
│   └── price_action.py            # placeholder, pendiente material del curso
├── data_files/
│   ├── historial.csv              # señales reales enviadas
│   ├── historicos/                # CSV que tú exportes para backtesting
│   └── backtests/                 # resultados de backtesting/optimización
└── logs/thor.log
```

## Instalación

```bash
pip install -r requirements.txt
cp .env.example .env
# completa TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, y revisa PAYOUT_PCT
```

## Ejecutar en vivo

```bash
python main.py            # loop en vivo (requiere MT5 abierto)
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

