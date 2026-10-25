#!/usr/bin/env python3
"""Descarga precios, estados financieros, dividendos y consenso de Yahoo Finance
y escribe docs/data/live.json con el MISMO formato compacto que usa la app.

- Si una emisora falla, conserva los datos de la corrida anterior y lo registra en `status`.
- Estados financieros: se refrescan los lunes (o con FORCE_FUND=1, o si faltan).
"""
import json, os, sys, time, datetime as dt
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "docs" / "data" / "live.json"

EMISORAS = {  # clave: (nombre, símbolo Yahoo)
 "AC":("Arca Continental","AC.MX"),"ALSEA":("Alsea","ALSEA.MX"),"AMXB":("América Móvil B","AMXB.MX"),
 "ASURB":("Grupo Aeroportuario del Sureste B","ASURB.MX"),"BBAJIOO":("Banco del Bajío O","BBAJIOO.MX"),
 "BIMBOA":("Grupo Bimbo A","BIMBOA.MX"),"BOLSAA":("Grupo BMV A","BOLSAA.MX"),"CEMEXCPO":("Cemex CPO","CEMEXCPO.MX"),
 "CHDRAUIB":("Chedraui B","CHDRAUIB.MX"),"CUERVO":("Becle (Cuervo)","CUERVO.MX"),"FEMSAUBD":("FEMSA UBD","FEMSAUBD.MX"),
 "GAPB":("Grupo Aeroportuario del Pacífico B","GAPB.MX"),"GCARSOA1":("Grupo Carso A1","GCARSOA1.MX"),"GCC":("GCC","GCC.MX"),
 "GFINBURO":("Grupo Financiero Inbursa O","GFINBURO.MX"),"GFNORTEO":("Grupo Financiero Banorte O","GFNORTEO.MX"),
 "GMEXICOB":("Grupo México B","GMEXICOB.MX"),"GRUMAB":("Gruma B","GRUMAB.MX"),"KIMBERA":("Kimberly-Clark de México A","KIMBERA.MX"),
 "KOFUBL":("Coca-Cola FEMSA UBL","KOFUBL.MX"),"LABB":("Genomma Lab B","LABB.MX"),"LIVEPOL1":("Liverpool 1","LIVEPOL1.MX"),
 "MEGACPO":("Megacable CPO","MEGACPO.MX"),"OMAB":("Grupo Aeroportuario Centro Norte B","OMAB.MX"),"ORBIA":("Orbia","ORBIA.MX"),
 "PE&OLES":("Industrias Peñoles","PE&OLES.MX"),"PINFRA":("Promotora y Operadora de Infraestructura","PINFRA.MX"),
 "Q":("Quálitas","Q.MX"),"TLEVISACPO":("Grupo Televisa CPO","TLEVISACPO.MX"),"VESTA":("Vesta","VESTA.MX"),
 "VOLARA":("Volaris A","VOLARA.MX"),"WALMEX":("Wal-Mart de México","WALMEX.MX"),
}
BENCH = ("__BENCH__", "^MXX")
MAPA = {
 "ingresos":["Total Revenue","Operating Revenue"], "utilidad_bruta":["Gross Profit"],
 "utilidad_operativa":["Operating Income","Total Operating Income As Reported"], "ebitda":["EBITDA","Normalized EBITDA"],
 "utilidad_neta":["Net Income","Net Income Common Stockholders"], "upa":["Diluted EPS","Basic EPS"],
 "gastos_por_intereses":["Interest Expense","Interest Expense Non Operating"],
 "depreciacion_amortizacion":["Reconciled Depreciation","Depreciation And Amortization In Income Statement"],
 "activos_totales":["Total Assets"], "activos_circulantes":["Current Assets"],
 "efectivo":["Cash And Cash Equivalents","Cash Cash Equivalents And Short Term Investments"],
 "inventarios":["Inventory"], "pasivos_totales":["Total Liabilities Net Minority Interest"],
 "pasivos_circulantes":["Current Liabilities"],
 "deuda_corto_plazo":["Current Debt And Capital Lease Obligation","Current Debt"],
 "deuda_largo_plazo":["Long Term Debt And Capital Lease Obligation","Long Term Debt"],
 "capital_contable":["Stockholders Equity","Common Stock Equity","Total Equity Gross Minority Interest"],
 "flujo_operativo":["Operating Cash Flow","Cash Flow From Continuing Operating Activities"],
 "flujo_inversion":["Investing Cash Flow","Cash Flow From Continuing Investing Activities"],
 "flujo_financiamiento":["Financing Cash Flow","Cash Flow From Continuing Financing Activities"],
 "capex":["Capital Expenditure"]}
REC = {"strong_buy":"compra fuerte","buy":"compra","hold":"mantener","underperform":"bajo desempeño","sell":"venta","strong_sell":"venta fuerte","none":""}
EPOCH = dt.date(2000, 1, 1)


def codificar_precios(df):
    """df con índice de fechas y columnas Open, High, Low, Close, Volume -> {'start': días, 'd': 'dd,o,h,l,c,v;...'} (precios en centavos)."""
    import pandas as pd
    df = df.sort_index().dropna(subset=["Close"])
    df = df[(df[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
    desde = (dt.date.today() - dt.timedelta(days=3660))
    df = df[[i.date() >= desde for i in df.index]]
    if df.empty: return None
    o, h, l, c = [(df[x] * 100).round().astype(int) for x in ["Open", "High", "Low", "Close"]]
    hh = pd.concat([h, o, c], axis=1).max(axis=1); ll = pd.concat([l, o, c], axis=1).min(axis=1)
    v = df["Volume"].fillna(0).astype(int)
    dias = [(i.date() - EPOCH).days for i in df.index]; prev = dias[0]; filas = []
    for i in range(len(df)):
        filas.append(f"{dias[i]-prev},{o.iloc[i]},{hh.iloc[i]},{ll.iloc[i]},{c.iloc[i]},{v.iloc[i]}"); prev = dias[i]
    return {"start": dias[0], "d": ";".join(filas), "last": str(df.index[-1].date())}


def tomar(tabla, nombres):
    if tabla is None or getattr(tabla, "empty", True): return None
    for n in nombres:
        if n in tabla.index: return tabla.loc[n]
    return None


def codificar_estados(moneda, pares):
    """pares: [(tipo, income, balance, cashflow)] como DataFrames de yfinance -> {'cur', 'p': [[fin, tipo, {partida: valor}]]}"""
    import pandas as pd
    per = {}
    for tipo, inc, bal, cf in pares:
        tablas = [inc, bal, cf]
        periodos = sorted({c for t in tablas if t is not None and not t.empty for c in t.columns})
        for p in periodos:
            for partida, nombres in MAPA.items():
                for t in tablas:
                    s = tomar(t, nombres)
                    if s is not None and p in s.index and pd.notna(s[p]):
                        v = float(s[p]) if partida == "upa" else float(s[p]) / 1e6
                        per.setdefault((str(pd.Timestamp(p).date()), tipo), {})[partida] = round(v, 4 if partida == "upa" else 3); break
    if not per: return None
    return {"cur": moneda, "p": [[a, b, vals] for (a, b), vals in sorted(per.items())]}


class Yahoo:
    def __init__(self):
        import yfinance as yf
        self.yf = yf
    def precios(self, sym):
        for _ in range(3):
            try:
                df = self.yf.download(sym, period="max", interval="1d", auto_adjust=False, progress=False)
                if df is not None and not df.empty:
                    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                    return df
            except Exception as e:
                print("   reintento", sym, str(e)[:80])
            time.sleep(3)
        return None
    def ticker(self, sym): return self.yf.Ticker(sym)
    def info(self, t):
        try: return t.get_info() or {}
        except Exception: return {}
    def estados(self, t):
        return [("anual", t.income_stmt, t.balance_sheet, t.cashflow), ("trimestral", t.quarterly_income_stmt, t.quarterly_balance_sheet, t.quarterly_cashflow)]
    def dividendos(self, t):
        d = t.dividends
        return [] if d is None else [[str(f.date()), round(float(v), 6)] for f, v in d.items()]


def main(fuente=None, salida=SALIDA, hoy=None):
    fuente = fuente or Yahoo()
    hoy = hoy or dt.datetime.utcnow()
    previo = {}
    if salida.exists():
        try: previo = json.loads(salida.read_text(encoding="utf-8"))
        except Exception: previo = {}
    refrescar_fund = os.environ.get("FORCE_FUND") == "1" or hoy.weekday() == 0 or not previo.get("fund")
    live = {"asof": hoy.strftime("%Y-%m-%d %H:%M UTC"), "meta": {k: {"name": n, "sym": s} for k, (n, s) in EMISORAS.items()},
            "prices": dict(previo.get("prices", {})), "fund": dict(previo.get("fund", {})), "div": dict(previo.get("div", {})),
            "cons": dict(previo.get("cons", {})), "status": {}}
    objetivos = list(EMISORAS.items()) + [(BENCH[0], ("IPC", BENCH[1]))]
    for clave, (nombre, sym) in objetivos:
        st = {"sym": sym}
        try:
            df = fuente.precios(sym)
            enc = codificar_precios(df) if df is not None else None
            if enc:
                live["prices"][clave] = {"start": enc["start"], "d": enc["d"]}; st.update(ok=True, last=enc["last"])
            else:
                st.update(ok=False, error="sin precios; se conservan los anteriores")
        except Exception as e:
            st.update(ok=False, error=str(e)[:120])
        if clave != BENCH[0] and refrescar_fund:
            try:
                t = fuente.ticker(sym); info = fuente.info(t)
                est = codificar_estados(info.get("financialCurrency") or info.get("currency") or "MXN", fuente.estados(t))
                if est: live["fund"][clave] = est
                dv = fuente.dividendos(t)
                if dv: live["div"][clave] = dv
                live["cons"][clave] = {"rec": REC.get(str(info.get("recommendationKey")), str(info.get("recommendationKey") or "")),
                    "obj": info.get("targetMeanPrice"), "alto": info.get("targetHighPrice"), "bajo": info.get("targetLowPrice"), "n": info.get("numberOfAnalystOpinions")}
                st["fund_ok"] = bool(est)
            except Exception as e:
                st["fund_error"] = str(e)[:120]
            time.sleep(1)
        live["status"][clave] = st
        print(("ok  " if st.get("ok") else "FALLO"), clave, st.get("last", st.get("error", "")))
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(live, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    fallos = [k for k, v in live["status"].items() if not v.get("ok")]
    print(f"\nListo: {len(live['status'])-len(fallos)} ok, {len(fallos)} con fallo: {fallos}")
    # Si fallaron TODAS, que la corrida falle para que lo notes en GitHub.
    if len(fallos) == len(live["status"]): sys.exit(1)


if __name__ == "__main__":
    main()
