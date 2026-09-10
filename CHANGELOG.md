# CHANGELOG — THOR IA

## v3.0 — Optimización profesional de rendimiento (ver PERFORMANCE.md)

Cambio de arquitectura enfocado en eliminar cuellos de botella, no solo
en el backtesting sino en todo el pipeline de cálculo. Ver
`PERFORMANCE.md` para benchmarks reales y el detalle de cada punto.

- **NUEVO `indicators/signal_bank.py`**: las 6 confirmaciones técnicas
  (tendencia, RSI(2), MACD, Stochastic, Bollinger, PSAR) ahora se
  calculan para TODA la serie con NumPy vectorizado, no fila por fila en
  un bucle de Python. Verificado matemáticamente idéntico a la versión
  escalar (0 discrepancias en 2,400 filas comparadas una por una).
- **NUEVO `indicators/cache.py`**: caché en disco de la serie de
  indicadores, con invalidación automática si cambia cualquier parámetro
  de configuración (no hay que limpiarla a mano, y nunca sirve un
  resultado calculado con parámetros distintos a los actuales).
- **`backtesting/backtest_engine.py` reestructurado en 2 etapas**:
  `preparar_serie_y_senales()` (cara, una vez por par/segmento, cacheada)
  y `generar_operaciones()` (barata, recibe indicadores ya calculados —
  así el optimizador prueba 10+ combinaciones de motor×umbral sin
  recalcular indicadores cada vez).
- **`optimization/optimizer.py` reescrito**: reutiliza indicadores ya
  calculados entre todas las combinaciones del grid search y entre folds
  del walk-forward. De paso, se corrigió un bug real heredado de una
  sesión anterior: la función `_correr_config()` había quedado sin
  definir (código muerto huérfano) — ver PERFORMANCE.md para el detalle.
- **Multiprocessing por par** en `run_backtest.py` y `optimizer.py`
  (`ProcessPoolExecutor`) — los pares son independientes entre sí, caso
  ideal para paralelismo. Flag `--sin-paralelo` para desactivarlo si hace
  falta depurar.
- **Corregido bug de mutación global**: el optimizador anterior hacía
  `config.operativa.PROBABILIDAD_MINIMA = umbral` para probar distintos
  umbrales — no sobrevive a multiprocessing (cada proceso hijo relee su
  `.env` desde cero) y es frágil en general. Ahora el umbral se pasa
  siempre como parámetro explícito.
- **`core.config.estrategia.PARES` ahora se puede sobreescribir** con la
  variable de entorno `PARES` (lista separada por comas), para escalar a
  decenas de pares sin tocar código.
- **Corregido caso límite**: `backtesting/monte_carlo.py` fallaba con
  `KeyError` cuando el backtest no generaba ninguna señal.
- **NUEVO verificador estático** (namespace aplanado por archivo,
  documentado en PERFORMANCE.md) que detecta nombres usados pero nunca
  definidos dentro del mismo archivo — el tipo de bug que el verificador
  anterior (solo imports entre archivos) no detectaba.
- **Documentado y sin cambios**: el loop en vivo (`core/brain.py`) NO se
  paralelizó — la conexión MT5 es una sesión única con estado, no segura
  para llamadas concurrentes. No es el cuello de botella real en vivo de
  todas formas (ver PERFORMANCE.md, sección "Lo que NO se paralelizó").

## v2.2 — Pendientes de v2.1 resueltos: Monte Carlo y walk-forward rolling

- **NUEVO `backtesting/monte_carlo.py`**: reshuffle de operaciones (bootstrap
  IID) para estimar bandas de drawdown realistas, no solo el drawdown del
  orden histórico real. Activable con `run_backtest.py --monte-carlo`.
  Probado con datos sintéticos: detecta correctamente que una racha de
  pérdidas agrupada da un drawdown peor que la mediana de reordenamientos
  al azar.
- **`optimization/optimizer.py`**: agregado `walk_forward_rolling()`
  (walk-forward "anchored" con N folds), activable con `--rolling
  --folds N`. Reemplaza el split único 70/30 de v2.1 por múltiples
  validaciones secuenciales, y reporta si la configuración ganadora es
  consistente entre folds (inestabilidad = señal adicional de
  overfitting). El split único sigue disponible sin `--rolling`, para
  una comprobación rápida.
- Ver `FUENTES.md` puntos 5 y 6 para las fuentes exactas.
- Límite honesto documentado: el reshuffle es IID simple, no
  block-bootstrap — no modela rachas por régimen de mercado. Documentado
  en el docstring del módulo, no oculto.

## v2.1 — Correcciones basadas en investigación de buenas prácticas

Ver `FUENTES.md` para la fuente exacta de cada punto.

- **`scoring/score_engine.py` corregido**: RSI(2)/MACD/Stochastic ya no
  suman 25 puntos cada uno como si fueran independientes — son la misma
  familia de momentum (correlacionados) y ahora cuentan como UN consenso
  (mayoría 2 de 3). Bollinger (60) y Parabolic SAR (40) quedan como los
  factores ponderados, por ser las dimensiones menos redundantes con el
  filtro obligatorio de tendencia.
- **NUEVO `indicators/volatility_filter.py`**: filtro de volatilidad ATR,
  apagado por defecto (`ATR_FILTRO_ACTIVO=false`). Evita operar en
  mercado de baja volatilidad/"choppy", donde la literatura reporta 30-40%
  más señales falsas.
- **`indicators/indicator_bank.py`**: ahora también calcula ATR (periodo
  14, estándar de Wilder) y su promedio móvil de 50 velas.
- **`optimization/optimizer.py` reescrito con walk-forward real**: antes
  optimizaba y medía sobre el mismo período histórico completo (riesgo
  alto de overfitting). Ahora divide 70/30 train/test cronológico, elige
  el umbral solo en train, y valida en test sin volver a tocarlo —
  reportando alerta si el winrate cae >10 puntos de train a test.
- **Umbral mínimo de operaciones subido de 30 a 50** en el optimizador,
  siguiendo la literatura de tamaño de muestra en backtesting.
- **NUEVO test de significancia estadística** en
  `backtesting/backtest_engine.calcular_estadisticas()`: z-test de una
  cola contra el winrate de equilibrio (dado el payout), con advertencia
  explícita si la muestra es menor a 50 operaciones.
- **`backtesting/run_backtest.py`**: flag `--atr-filtro` para comparar
  resultados con y sin el filtro de volatilidad.

## v2.0 — Reestructuración arquitectónica (Fases 1-7)

### Fase 1 — Auditoría
- Ver `INFORME_FASE1_AUDITORIA.md` para el detalle completo.

### Fase 2 — Arquitectura
- **Separado** `engines/indicators.py` (v1, mezclaba 3 responsabilidades) en:
  `connectors/mt5_connector.py` (conexión), `data/data_provider.py`
  (adquisición de velas), `indicators/indicator_bank.py` (cálculo puro,
  sin dependencia de MT5 — permite reutilizarlo en backtesting).
- **Corregido** bug de comparación muerta en el scanner
  (`candidato["score"] > mejor["score"]` nunca se activaba en v1 porque
  solo entraban candidatos con score=100). Ahora es efectiva porque
  `score_ponderado` sí produce valores intermedios reales.
- **Movidos** `engines/thor_score.py` y `engines/price_action.py` a
  `legacy/` — código muerto en v1 (no los importaba ningún módulo activo).
  No se borraron.
- **Separado** `core/config.py` en dominios: `EstrategiaConfig`,
  `OperativaConfig`, `RiesgoConfig`, `ConexionConfig`, `TelegramConfig`,
  `RutasConfig`.
- `core/brain.py` sigue corriendo en modo `confluencia_total` por defecto
  — ningún comportamiento en vivo cambió con esta fase.

### Fase 3 — Motor de score ponderado (`scoring/score_engine.py`)
- **NUEVO módulo, NO activo en producción** (`STRATEGY_MODE` sigue en
  `confluencia_total` por defecto en `.env.example`).
- Reemplaza la regla todo-o-nada por: 2 factores obligatorios (tendencia +
  RSI(2), deben coincidir entre sí) que actúan como filtro, y 4 factores
  ponderados (MACD, Stochastic, Bollinger, PSAR, 25 puntos c/u) que suman
  o restan sobre esa base.
- **Pendiente de decisión del usuario**: la clasificación
  obligatorio/ponderado y los pesos son una propuesta técnica, no una
  transcripción verificada del curso de Juan Fernández (material no
  disponible). Ver docstring completo en el archivo.
- Debe validarse contra `backtesting/run_backtest.py` comparando contra
  `confluencia_total` antes de activarse en vivo.

### Fase 4 — Backtesting (NUEVO, no existía en v1)
- `backtesting/loader.py`: carga CSV histórico real (no genera datos).
- `backtesting/export_historico.py`: exporta histórico real desde MT5
  (correr en máquina con MT5, a cargo del usuario).
- `backtesting/backtest_engine.py`: simula señal por señal sobre datos
  históricos usando la misma lógica que producción. Supuestos de
  simulación documentados explícitamente en el docstring (resultado por
  comparación de cierre a N minutos, empates excluidos del winrate,
  profit factor con payout configurable).
- `backtesting/run_backtest.py`: CLI, genera CSV de operaciones + JSON de
  estadísticas (winrate, profit factor, drawdown, mejores horas, mejores
  pares).

### Fase 5 — Optimización (NUEVO, no existía en v1)
- `optimization/optimizer.py`: grid-search de umbral × motor, SOLO contra
  backtesting histórico. Filtra configuraciones con muestra insuficiente
  (< 30 operaciones) para no rankear ruido como si fuera señal.
- Advertencia explícita de sobreajuste incluida en el reporte de salida.
- Pendiente natural: separar período de optimización y período de
  validación (walk-forward) — no implementado todavía, se ofrece como
  siguiente paso.

### Fase 6 — Telegram enriquecido
- `notifications/telegram_service.py`: el mensaje ahora incluye hora,
  nivel de confianza (Alto/Medio/Bajo según score), lista explícita de
  indicadores que confirmaron vs. rechazaron, y motivo de entrada en
  texto. Estructura de datos y umbrales sin cambios.

### Fase 7 — Documentación
- Este CHANGELOG.
- `INFORME_FASE1_AUDITORIA.md`.
- `README.md` actualizado con la arquitectura completa.

### Riesgo (NUEVO, no existía en v1)
- `risk/risk_manager.py`: límite de señales por hora y por par/día
  (evita saturar Telegram), y detección de racha de pérdidas consecutivas
  (solo útil si se carga `resultado` real en el historial — sigue siendo
  una decisión pendiente del proyecto original, ver README).
- No calcula tamaño de posición porque el bot no ejecuta órdenes.

### Sin cambios de comportamiento en vivo
- Con `STRATEGY_MODE=confluencia_total` (el default), los valores de
  todos los indicadores, umbrales y la regla 6/6 son idénticos a v1.
  Esta reestructuración es arquitectónica; el único cambio de
  comportamiento posible (`score_ponderado`) está apagado hasta que el
  backtesting lo respalde y el usuario lo confirme.
