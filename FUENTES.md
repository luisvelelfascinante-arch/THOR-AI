# Fuentes — investigación aplicada en v2.1

Cada cambio de esta revisión está atado a una fuente concreta, no a
opinión. Así puedes verificarlas tú mismo.

## 1. Redundancia de indicadores de momentum (scoring/score_engine.py)

RSI, MACD y Stochastic son osciladores de la misma familia (momentum),
calculados sobre el mismo precio de cierre — tratarlos como confirmaciones
independientes infla el score artificialmente.

- Pomegra — "Indicator Overload" (pomegra.io/learn/library — capítulo de
  análisis técnico): ejemplo explícito de por qué RSI+Stochastic no son
  evidencia independiente.
- Tradeciety — "How To Combine The Best Indicators And Avoid Wrong
  Signals" (tradeciety.com): muestra 3 indicadores de momentum
  (MACD/RSI/Stochastic) moviéndose juntos en el mismo gráfico.
- Yellow.com — "Why Most Crypto Traders Use Indicators Wrong": misma
  conclusión, con el principio de "un indicador por categoría".

**Cambio aplicado**: RSI(2)/MACD/Stochastic pasan de sumar 25 puntos cada
uno a contar como UN consenso (mayoría 2 de 3), no tres independientes.

## 2. Filtro de volatilidad ATR (indicators/volatility_filter.py)

- AlfaTactix — "ATR Filter (MT5): Volatility Gate for Better Trade
  Quality": cita que operar en ATR bajo aumenta señales falsas 30-40%.
- TradingFinder — guía de indicadores para opciones binarias: recomienda
  ATR específicamente para decidir cuándo operar en binarias.
- Wilder, J. Welles Jr. (1978) — "New Concepts in Technical Trading
  Systems": origen del ATR y su uso como filtro de volatilidad.

**Cambio aplicado**: nuevo filtro opcional (apagado por defecto) que
descarta señales cuando el ATR actual está muy por debajo de su propio
promedio reciente.

## 3. Walk-forward en vez de optimizar y medir en el mismo período
   (optimization/optimizer.py)

- QuantInsti — "Walk-Forward Optimization: How It Works, Its
  Limitations, and Backtesting Implementation".
- AlgoTrading101 — "What is a Walk-Forward Optimization and How to Run
  It?".
- Bailey, D. et al. (2014) — trabajo citado en varias fuentes sobre
  "Minimum Backtest Length" y el riesgo de sobreajuste al elegir la mejor
  estrategia entre muchas configuraciones probadas sobre el mismo dato.

**Cambio aplicado**: el optimizador ahora divide el histórico en
train/test cronológico; el umbral se elige en train y se valida en test
sin volver a tocarlo, reportando si el winrate cae fuerte de uno a otro
(señal de overfitting).

## 4. Tamaño mínimo de muestra para confiar en un backtest
   (optimization/optimizer.py, backtesting/backtest_engine.py)

- Medium — "How Many Trades Are Enough? A Guide to Statistical
  Significance in Backtesting": mínimo 30 para empezar a inferir algo,
  100+ para métricas confiables.
- TestMax — "How to Backtest a Trading Strategy (2026 Guide)": 50 como
  piso, 100+ como estándar.
- arXiv 2602.00080 — "The GT-Score: A Robust Objective Function for
  Reducing Overfitting in Data-Driven Trading Strategies": usa n_min=50
  como penalización de configuraciones con pocas operaciones.

**Cambio aplicado**: el umbral mínimo de operaciones del optimizador subió
de 30 a 50. Se agregó también un test de significancia estadística
(z-test contra el winrate de equilibrio dado el payout) en
`calcular_estadisticas()`, con advertencia explícita si la muestra es
menor a 50.

## Lo que NO se aplicó todavía (honesto, no se ocultó)

- Filtro de sesión/horario de baja liquidez (fin de semana, apertura de
  mercados) — el backtesting ya calcula winrate por hora
  (`winrate_por_hora_pct`), así que con datos reales tuyos se puede saber
  si aplica antes de construir el filtro, en vez de asumirlo.
- Block-bootstrap (en vez de reshuffle IID simple) para Monte Carlo — el
  reshuffle actual asume operaciones independientes; si hay rachas por
  régimen de mercado, un block-bootstrap sería más preciso. Se puede
  agregar si el resultado del reshuffle IID muestra algo que valga la
  pena refinar.
- Walk-forward "no-anchored" (ventanas de tamaño fijo que se deslizan, en
  vez de expandirse) — se implementó la variante "anchored" (Carta et al.
  2021), que es una de las dos formas estándar, no ambas.

## 5. Monte Carlo por reshuffle de operaciones (backtesting/monte_carlo.py)

- BuildAlpha — "Monte Carlo Simulation: Complete Guide and Simulator":
  método de reshuffle para estimar bandas de drawdown realistas.
- DEV Community — "Monte Carlo Simulation for Trading Systems (Code
  Example)": implementación de referencia del reshuffle en Python.

**Cambio aplicado**: nuevo `backtesting/monte_carlo.py` — reordena
aleatoriamente las operaciones ya observadas miles de veces para mostrar
el rango de drawdowns plausible, no solo el que salió en el orden
histórico real. Activable con `--monte-carlo` en `run_backtest.py`.

## 6. Walk-forward "anchored" con múltiples folds (optimization/optimizer.py)

- Carta et al. (2021), citado en arXiv 2406.18206 ("LSTM-ARIMA as a
  Hybrid Approach in Algorithmic Investment Strategies"): define walk-
  forward anchored vs. non-anchored como las dos variantes estándar.

**Cambio aplicado**: `optimizer.py --rolling` divide el histórico en N
folds cronológicos y re-optimiza en cada paso solo con el train acumulado
hasta ese punto, validando en el fold siguiente — en vez de un único
split train/test. Reporta si la configuración ganadora es consistente
entre folds (si cambia mucho, es una señal de inestabilidad adicional a
la caída de winrate train→test).
