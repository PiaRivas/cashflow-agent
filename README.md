# cashflow-agent

Un agente de línea de comandos que convierte mensajes (texto o **notas de voz**) en transacciones estructuradas, calcula tu flujo de caja y responde **"¿Cuánto puedo pagar de cuota al mes?"** en soles, mostrando el cálculo.

## Qué hace

1. **Escucha o lee mensajes.** Acepta texto directo o archivos de audio (`.ogg`, `.mp3`, `.wav`) que transcribe localmente.
2. **Convierte a transacciones estructuradas.** Cada mensaje se vuelve un registro JSON: tipo (ingreso/gasto), monto, moneda, categoría, descripción y fecha.
3. **Repregunta cuando falta un dato.** Si no puede determinar el monto o si es ingreso o gasto, pregunta en lugar de inventar el dato.
4. **Calcula tu flujo de caja.** Totales, flujo neto y desglose mes a mes.
5. **Responde la cuota mensual.** Promedia tu excedente mensual (ingresos - gastos) y aplica un margen de seguridad del 70%: `cuota = excedente_promedio x 0.70`.

## Requisitos

- Python 3.8+ (el núcleo usa solo la stdlib, **sin APIs de pago**).
- Opcional, para notas de voz: `pip install openai-whisper` (Whisper corre local y gratis; requiere `ffmpeg`).

## Uso

```bash
# Agregar transacciones en texto
python cashflow_agent.py agregar "gasté 50 soles en taxi"
python cashflow_agent.py agregar "me pagaron el sueldo de 3000 soles"

# Agregar desde una nota de voz
python cashflow_agent.py agregar --voz nota.ogg

# Ver el flujo de caja
python cashflow_agent.py flujo

# ¿Cuánto puedo pagar de cuota al mes?
python cashflow_agent.py cuota

# Listar transacciones
python cashflow_agent.py lista
```

Si falta un dato, el agente no inventa:

```
$ python cashflow_agent.py agregar "gasté en comida"
Me falta información, no la voy a inventar:
  - ¿Cuánto fue el monto en soles?
```

## Cómo funciona la cuota

1. Agrupa tus transacciones por mes y saca el excedente de cada mes (ingresos - gastos).
2. Promedia los excedentes.
3. Multiplica por el margen de seguridad (70%, configurable en `MARGEN_SEGURIDAD`) para no comprometer todo tu excedente.

## Configuración

- `CASHFLOW_DATOS`: ruta del archivo de datos (default `transacciones.json`).
- `WHISPER_MODELO`: modelo de Whisper para voz (default `base`).
- `MARGEN_SEGURIDAD`: en el código, fracción del excedente comprometible (default `0.70`).

## Notas

- Los montos se asumen en soles (PEN).
- El parser es por reglas en español: no necesita internet ni claves de API.
- `transacciones.json` y los audios están en `.gitignore`: tus datos no se suben al repo.
