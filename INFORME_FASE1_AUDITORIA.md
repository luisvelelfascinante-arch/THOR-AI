# THOR IA — Informe de auditoría (Fase 1)

Basado en revisión directa del código de `THOR-AI-v1.0.zip`, línea por línea.
Ningún punto aquí es especulación: cada uno referencia el archivo/línea real.

## Fortalezas

- **Conexión MT5 aislada y persistente** (`engines/indicators.py:conectar_mt5`):
  corrige el problema real del proyecto original (reconexión en cada par/ciclo).
- **Cooldown por tiempo** en vez de bloqueo permanente (`engines/strategy.py`).
- **Manejo explícito de datos insuficientes**: `obtener_indicadores_confluencia`
  devuelve `None` en vez de confundir "sin datos" con "0" — evita señales falsas
  por NaN.
- **Separación básica ya existente**: Telegram, historial y stats están en
  módulos propios (`services/`), no mezclados con la lógica de señales.
- **Parámetros de indicadores documentados y trazables**: los valores de
  Bollinger/RSI/Stochastic/MACD/PSAR están anotados como tomados de capturas
  reales de la plataforma, no inventados.

## Debilidades y errores de arquitectura

1. **`engines/indicators.py` mezcla 3 responsabilidades**: conexión MT5,
   adquisición de velas, y cálculo de indicadores. Un cambio en cómo se pide
   la conexión obliga a tocar el mismo archivo que calcula RSI. Se separa en
   Fase 2 en `connectors/`, `data/`, `indicators/`.
2. **`engines/scanner.py` tiene una comparación muerta**:
   `candidato["score"] > mejor["score"]` nunca es verdadera porque solo entran
   candidatos con score=100 (los demás se descartan antes). En la práctica,
   si dos pares dan señal en el mismo ciclo, gana el primero en `config.PARES`
   por orden de lista, no por ningún criterio de calidad.
3. **Decisión binaria sin gradiente**: `evaluar_confluencia` solo devuelve
   señal en 6/6. No existe un concepto de "score parcial válido" — para
   cambiar la sensibilidad hay que tocar código, no configuración.
4. **Sin backtesting**: ningún cambio de estrategia se puede validar contra
   datos históricos antes de arriesgarlo en producción. Esto es la brecha más
   grave del proyecto actual.
5. **Sin gestor de riesgo**: no hay módulo que límite operaciones simultáneas,
   pérdidas diarias, ni valide una señal contra reglas de exposición. Hoy no
   es crítico porque el bot no ejecuta órdenes, pero si en algún momento se
   activa ejecución automática, no hay ninguna barrera.
6. **`core/config.py` mezcla dominios**: config de estrategia (`PARES`,
   `EMA_PERIODO` — que además ya no se usa en el motor real de confluencia),
   config operativa (`INTERVALO_ESCANEO_SEGUNDOS`, `COOLDOWN_MINUTOS`) y
   secretos, todo en un archivo plano.
7. **Sin CHANGELOG ni versión de estrategia**: si cambian umbrales, no queda
   registro de qué cambió, cuándo, ni por qué.
8. **Sin tests automatizados** de ningún tipo.
9. **Carpeta `dashboard/` nunca llegó con contenido en ningún envío** — todo
   indica que nunca se implementó, es una carpeta vacía en la estructura.

## Código duplicado

- `obtener_indicadores()` (método legado EMA50/RSI14) y
  `obtener_indicadores_confluencia()` repiten casi la misma estructura
  ("conectar → pedir velas → calcular → manejar NaN") para dos conjuntos de
  indicadores distintos. Se unifica en Fase 2 en un solo pipeline
  `data_provider → indicator_bank`.

## Módulos innecesarios (en su forma actual)

- `engines/thor_score.py` y `engines/price_action.py`: **código muerto**.
  `core/brain.py` nunca los importa. No los borro sin tu permiso — se mueven
  a `legacy/` para que sigan disponibles pero dejen de aparentar ser lógica
  activa.

## Mejoras aplicadas en Fase 2–7

- Arquitectura en capas independientes (ver estructura abajo).
- Motor de score ponderado en vez de todo-o-nada (Fase 3 — **requiere tu
  decisión**, ver más abajo).
- Backtesting real sobre datos históricos exportados de MT5 (Fase 4).
- Optimización por grid-search validada solo contra backtesting, nunca en
  vivo (Fase 5).
- Telegram con motivo de entrada e indicadores que confirmaron/rechazaron
  (Fase 6).
- `CHANGELOG.md` (Fase 7).
