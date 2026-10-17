#!/usr/bin/env python3
"""
cashflow-agent: convierte mensajes (texto o notas de voz) en transacciones
estructuradas, calcula tu flujo de caja y responde:
"¿Cuánto puedo pagar de cuota al mes?"

Uso:
  python cashflow_agent.py agregar "gasté 50 soles en taxi"
  python cashflow_agent.py agregar --voz nota.ogg
  python cashflow_agent.py flujo
  python cashflow_agent.py cuota
  python cashflow_agent.py lista
"""
import json, os, re, sys, uuid
from datetime import date, datetime

DATOS = os.environ.get("CASHFLOW_DATOS", "transacciones.json")
MARGEN_SEGURIDAD = 0.70  # solo comprometes 70% de tu excedente mensual

# ---------------- almacenamiento ----------------

def cargar():
    if not os.path.exists(DATOS):
        return []
    with open(DATOS, encoding="utf-8") as f:
        return json.load(f)

def guardar(txs):
    with open(DATOS, "w", encoding="utf-8") as f:
        json.dump(txs, f, ensure_ascii=False, indent=2)

# ---------------- transcripción (pluggeable) ----------------

def transcribir(ruta_audio):
    """Transcribe una nota de voz con Whisper local (openai-whisper).
    No usa APIs de pago: corre 100% en tu máquina.
    Si no está instalado, explica cómo instalarlo y sale."""
    try:
        import whisper  # openai-whisper
    except ImportError:
        sys.exit(
            "Para notas de voz necesitas Whisper local:\n"
            "  pip install openai-whisper\n"
            "o pasa el mensaje como texto:\n"
            f'  python cashflow_agent.py agregar "tu mensaje"'
        )
    modelo = os.environ.get("WHISPER_MODELO", "base")
    print(f"Transcribiendo con whisper ({modelo})...")
    return whisper.load_model(modelo).transcribe(ruta_audio, language="es")["text"]

# ---------------- extracción estructurada ----------------

PALABRAS_GASTO = ["gasté", "gaste", "gasto", "pagué", "pague", "pago", "compré",
                  "compre", "salida", "egreso", "me costó", "me costo"]
PALABRAS_INGRESO = ["ingreso", "recibí", "recibi", "cobré", "cobre", "cobro",
                    "gané", "gane", "vendí", "vendi", "me pagaron", "entrada", "sueldo"]
CATEGORIAS = {
    "transporte": ["taxi", "uber", "bus", "gasolina", "combustible", "pasaje"],
    "comida": ["almuerzo", "comida", "restaurante", "cena", "desayuno", "café", "cafe", "mercado"],
    "casa": ["alquiler", "renta", "luz", "agua", "internet", "servicios"],
    "salud": ["farmacia", "doctor", "médico", "medico", "clínica", "clinica"],
    "ocio": ["cine", "fiesta", "bar", "netflix", "spotify", "juego"],
    "sueldo": ["sueldo", "salario", "nómina", "nomina"],
}

RE_MONTO = re.compile(
    r"(?:s/?\.?\s*)?(\d+(?:[.,]\d{1,2})?)\s*(?:soles|sol|pen|pavos)?\b", re.I)

def extraer(texto):
    """Convierte un mensaje en una transacción estructurada.
    REGLA DE ORO: si falta un dato, devuelve pregunta; nunca lo inventa."""
    t = texto.lower()
    tipo = None
    if any(p in t for p in PALABRAS_GASTO):
        tipo = "gasto"
    if any(p in t for p in PALABRAS_INGRESO):
        tipo = "ingreso" if tipo is None else tipo  # empate -> pregunta abajo
        if any(p in t for p in PALABRAS_GASTO):
            tipo = None  # señales contradictorias: preguntar

    monto = None
    # prioriza montos con moneda explícita
    m = re.search(r"s/?\.?\s*(\d+(?:[.,]\d{1,2})?)", t) or \
        re.search(r"(\d+(?:[.,]\d{1,2})?)\s*(?:soles|sol|pen|pavos)\b", t) or \
        RE_MONTO.search(t)
    if m:
        monto = float(m.group(1).replace(",", "."))
        if monto <= 0:
            monto = None

    categoria = next((c for c, kws in CATEGORIAS.items() if any(k in t for k in kws)), None)

    faltantes = []
    if tipo is None:
        faltantes.append("¿Es un ingreso o un gasto?")
    if monto is None:
        faltantes.append("¿Cuánto fue el monto en soles?")
    if faltantes:
        return {"ok": False, "preguntas": faltantes, "parcial": {"tipo": tipo, "monto": monto}}

    return {"ok": True, "tx": {
        "id": uuid.uuid4().hex[:8],
        "tipo": tipo,
        "monto": round(monto, 2),
        "moneda": "PEN",
        "categoria": categoria or ("otros-ingresos" if tipo == "ingreso" else "otros-gastos"),
        "descripcion": texto.strip(),
        "fecha": str(date.today()),
    }}

# ---------------- flujo de caja ----------------

def flujo(txs):
    ing = sum(t["monto"] for t in txs if t["tipo"] == "ingreso")
    gas = sum(t["monto"] for t in txs if t["tipo"] == "gasto")
    por_mes = {}
    for t in txs:
        mes = t["fecha"][:7]
        d = por_mes.setdefault(mes, {"ingresos": 0.0, "gastos": 0.0})
        d["ingresos" if t["tipo"] == "ingreso" else "gastos"] += t["monto"]
    return ing, gas, ing - gas, por_mes

def cmd_flujo():
    txs = cargar()
    if not txs:
        print("No hay transacciones todavía. Agrega una con: agregar \"...\"")
        return
    ing, gas, neto, por_mes = flujo(txs)
    print(f"Ingresos totales:  S/ {ing:,.2f}")
    print(f"Gastos totales:    S/ {gas:,.2f}")
    print(f"Flujo neto:        S/ {neto:,.2f}\n")
    for mes in sorted(por_mes):
        d = por_mes[mes]
        print(f"  {mes}: +S/ {d['ingresos']:,.2f} / -S/ {d['gastos']:,.2f} "
              f"= S/ {d['ingresos']-d['gastos']:,.2f}")

def cmd_cuota():
    txs = cargar()
    if not txs:
        print("Sin transacciones no puedo calcular tu cuota. Agrega ingresos y gastos primero.")
        return
    _, _, _, por_mes = flujo(txs)
    excedentes = [d["ingresos"] - d["gastos"] for d in por_mes.values()]
    promedio = sum(excedentes) / len(excedentes)
    print("Cálculo de cuota mensual:")
    for mes in sorted(por_mes):
        d = por_mes[mes]
        print(f"  {mes}: ingresos S/ {d['ingresos']:,.2f} - gastos S/ {d['gastos']:,.2f} "
              f"= excedente S/ {d['ingresos']-d['gastos']:,.2f}")
    print(f"  Excedente promedio mensual: S/ {promedio:,.2f}")
    print(f"  Margen de seguridad: {int(MARGEN_SEGURIDAD*100)}%")
    if promedio <= 0:
        print("\nTu flujo mensual es cero o negativo: no puedes comprometer una cuota "
              "sin recortar gastos o aumentar ingresos.")
    else:
        print(f"\nPuedes pagar una cuota de hasta S/ {promedio*MARGEN_SEGURIDAD:,.2f} al mes "
              f"(= {promedio:,.2f} x {MARGEN_SEGURIDAD}).")

# ---------------- comandos ----------------

def cmd_agregar(texto=None, voz=None):
    if voz:
        texto = transcribir(voz)
        print(f'Transcripción: "{texto}"')
    if not texto:
        sys.exit("Falta el mensaje. Usa: agregar \"texto\" o agregar --voz archivo.ogg")
    r = extraer(texto)
    if not r["ok"]:
        print("Me falta información, no la voy a inventar:")
        for p in r["preguntas"]:
            print(f"  - {p}")
        print("Vuelve a mandarlo con ese dato, ej: agregar \"gasté 45 soles en comida\"")
        return
    txs = cargar()
    txs.append(r["tx"])
    guardar(txs)
    print("Transacción registrada:")
    print(json.dumps(r["tx"], ensure_ascii=False, indent=2))

def cmd_lista():
    for t in cargar():
        signo = "+" if t["tipo"] == "ingreso" else "-"
        print(f'{t["fecha"]}  {signo}S/ {t["monto"]:>9,.2f}  {t["categoria"]:<15} {t["descripcion"]}')

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
    elif args[0] == "agregar":
        if "--voz" in args:
            i = args.index("--voz")
            cmd_agregar(voz=args[i + 1])
        else:
            cmd_agregar(texto=" ".join(args[1:]))
    elif args[0] == "flujo":
        cmd_flujo()
    elif args[0] == "cuota":
        cmd_cuota()
    elif args[0] == "lista":
        cmd_lista()
    else:
        print(__doc__)
