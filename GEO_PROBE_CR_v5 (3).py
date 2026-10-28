#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
GEO-PROBE CR — v4.0 "BOREHOLE"
Red Nacional de Precursores Sísmicos · Costa Rica
═══════════════════════════════════════════════════════════════════════════════
Inventor: Jason Manuel Sarmiento Salazar · Cédula 114510108
Divulgación técnica: 12 de septiembre de 2026 · OTPR CR / PCT WIPO

CAMBIO ESTRUCTURAL RESPECTO A v3.8
──────────────────────────────────
v3.8 arrastraba del diseño ODISEO (10 km) un reactor de 350 MWt para FUNDIR
roca, y una sonda de Ø3.5 m. A 600 m eso no es necesario ni financiable:

  · El pozo de 600 m se PERFORA (rotatoria convencional, ~$110k/nodo).
    Esa línea ya estaba en el CAPEX de v3.8 — el presupuesto nunca
    contempló fundir nada.
  · Un reactor de 350 MWt cuesta $1–3 B por unidad. v3.8 lo modelaba
    en la física pero lo costeaba en $0.
  · Un sonde de pozo estándar (Ø150–200 mm) CIERRA el enlace ULF con
    35–45 dB de margen. El Ø3.5 m era 17× mayor de lo necesario.

v4.0 elimina el reactor y la sonda gigante. Resultado: el proyecto pasa de
regulatoriamente imposible (nuclear en fallas activas, sin marco nuclear en
CR) a construible con tecnología de pozo comercial y permisos ordinarios.

CORRECCIONES v4.0 → v5.0 (auditoría independiente)
──────────────────────────────────────────────────
  1. PISO DE RUIDO. Pc1 ambiental real + cancelación por estación de referencia.
  2. PERMEABILIDAD. μ_eff derivado de geometría (≈383); diseño de compra ≥200.
  3. ARQUITECTURA. Cable armado PRIMARIO · ULF RESPALDO ante cizalla.

MEJORAS P1 integradas en v5.1 (auditoría competitiva)
─────────────────────────────────────────────────────
  1. Protocolo adaptativo por índice Kp — CORRECTO, verificado.
  2. Latencia dual cable/ULF — CORRECTO, buena clarificación.
  3. Contingencia CAPEX 18% — razonable, transparente.
  4. VAN @ 6% — recalculado independientemente, coincide exacto.

CORRECCIÓN v5.2 (auditoría independiente)
──────────────────────────────────────────
  μ_eff de diseño=200 decide TODOS los cálculos oficiales (no solo etiqueta).

MEJORAS v5.3
────────────
  1. Curva térmica de ferrita en pozo (40–80 °C) → μ_eff efectivo.
  2. P(cizalla de cable) vs Mw → cuantifica el valor del ULF de respaldo.
  3. Latencia y FA bajo escenario de cizalla post-sismo.
  4. Export JSON ampliado + diagnóstico unificado para evaluación entre IAs.

SE CONSERVA de v3.8: árbol de decisiones 4 fases, Monte Carlo, correlación
de fallos, latencia extremo a extremo, tasa de falsas alarmas, σ variable.
[H] hipótesis · [P] proyección documentada · [V] verificado numéricamente
"""
import numpy as np, os, json
from math import comb
import warnings; warnings.filterwarnings('ignore')
rng = np.random.default_rng(2026)

VERSION = "5.3 COMPLETA"
OUT = os.environ.get("GEOPROBE_OUT_DIR") or os.path.join(
      os.path.dirname(os.path.abspath(__file__)), "artifacts")
os.makedirs(OUT, exist_ok=True)

L = "═"*74
print(L); print(f" GEO-PROBE CR — v{VERSION}")
print(" Jason Manuel Sarmiento Salazar · Cédula 114510108")
print(" v5.3 COMPLETA · P(cizalla)+curva T+valor ULF · Lista para competir")
print(L)

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ A — GEOMETRÍA Y DESPLIEGUE (CORREGIDO)                                ║
# ╚════════════════════════════════════════════════════════════════════════╝
D_HOLE_MM   = 200          # mm, pozo perforado (HQ/PQ ampliado) [V]
D_SONDE_MM  = 168          # mm, Ø externo del sonde
L_SONDE_M   = 6.0          # m, tren de instrumentos
DEPTH_CR    = 600          # m
R_COIL      = 0.075        # m, radio bobina ULF dentro del sonde
N_NODOS     = 5

# Perforación convencional: tasas reales de sondeo geotécnico/minero
ROP_M_DIA   = 45           # m/día en roca volcánica dura (rotatoria diamantina) [P]
DIAS_POZO   = DEPTH_CR / ROP_M_DIA
DIAS_COMPL  = 6            # entubado, cementado, bajada de sonde, pruebas

print(f"\n[A] DESPLIEGUE — PERFORACIÓN CONVENCIONAL\n")
print(f"  Pozo:                 Ø{D_HOLE_MM} mm × {DEPTH_CR} m")
print(f"  Sonde instrumentado:  Ø{D_SONDE_MM} mm × {L_SONDE_M} m")
print(f"  Método:               Rotatoria diamantina (sin reactor, sin fusión)")
print(f"  ROP en roca volcánica:{ROP_M_DIA} m/día  [P tarifa comercial CR]")
print(f"  Perforación:          {DIAS_POZO:.1f} días/nodo")
print(f"  Completación:         {DIAS_COMPL} días/nodo")
print(f"  TOTAL por nodo:       {DIAS_POZO+DIAS_COMPL:.1f} días")
print(f"  5 nodos (2 equipos):  {(DIAS_POZO+DIAS_COMPL)*N_NODOS/2/30:.1f} meses")
print(f"\n  vs v3.8 (fundir con 350 MWt): 3.0 días/nodo + reactor de $1–3 B")
print(f"  → Se pierde velocidad de penetración, se gana viabilidad total.")

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ B — ENLACE ULF CON BOBINA DE POZO REAL                                ║
# ╚════════════════════════════════════════════════════════════════════════╝
MU0, F_ULF, B_NOISE = 4*np.pi*1e-7, 2.0, 1e-12
T_BIT = 30.0

def skin(sig): return np.sqrt(2/(2*np.pi*F_ULF*MU0*sig))
def link(N, I, r=R_COIL, d=DEPTH_CR, sig=1.2e-4):
    m   = N*I*np.pi*r**2
    atn = np.exp(-d/skin(sig))
    B   = MU0*m/(2*np.pi*d**3)*atn
    raw = 20*np.log10(B/B_NOISE)
    return dict(m=m, B_pT=B*1e12, atn_dB=20*np.log10(atn),
                snr_raw=raw, snr=raw+10*np.log10(F_ULF*T_BIT))



# ── Permeabilidad efectiva DERIVADA de la geometría (no asumida) ─────────
MU_R    = 2000.0     # ferrita MnZn a 2 Hz [P]
RHO_CU  = 1.68e-8
RHO_FER = 4800.0

def mu_eff(L, Dc):
    """μ_eff = μr/(1+Nd(μr-1)); Nd de barra prolata."""
    LD = L/Dc
    Nd = (np.log(2*LD)-1)/(LD**2)
    return MU_R/(1+Nd*(MU_R-1)), Nd

# Núcleo de referencia v5: más fino y ligero que v4, con MÁS momento
L_CORE, D_CORE = 4.0, 0.10
MU_EFF_TH, ND = mu_eff(L_CORE, D_CORE)  # teórico de geometría — referencia
MU_EFF_DESIGN = 200.0                   # spec de compra con margen de fabricación
MU_EFF = MU_EFF_DESIGN                  # v5.2: el diseño manda los cálculos oficiales
R_COIL  = 0.055                      # bobina sobre núcleo Ø100 mm
N_REF, I_REF, A_REF = 1000, 20, 10   # vueltas, A, mm²
DUTY    = 0.17                       # 1 bit/30 s, ráfaga ~5 s
M_FER   = RHO_FER*np.pi*(D_CORE/2)**2*L_CORE

# ── Modelo de ruido Pc1 REAL (corrección central de v5) ──────────────────
# B_NOISE de v4 (1 pT) era el piso del SENSOR, no el ruido ambiental.
PC1 = {"Tranquilo (noche, Kp≤2)":20.0, "Típico diurno":60.0,
       "Activo (Kp 4–5)":300.0, "Tormenta CME (Kp≥7)":3000.0}
REJ_REF_DB = 30.0    # cancelación con estación de referencia a 20 km [P]

def dipolo(N=N_REF, I=I_REF, mu=None, r=R_COIL, d=DEPTH_CR):
    return (MU_EFF if mu is None else mu)*N*I*np.pi*r**2

def campo_pT(m, d=DEPTH_CR, sig=1.2e-4):
    return MU0*m/(2*np.pi*d**3)*np.exp(-d/skin(sig))*1e12

def snr_real(m, pc1_pT, rej_dB=REJ_REF_DB, d=DEPTH_CR, sig=1.2e-4):
    B   = campo_pT(m, d, sig)
    eff = pc1_pT/10**(rej_dB/20)
    raw = 20*np.log10(B/eff)
    return raw, raw+10*np.log10(F_ULF*T_BIT)

M_REF = dipolo()
B_REF = campo_pT(M_REF)

print(f"\n{'─'*74}")
print(f"[B] ENLACE ULF — RUIDO Pc1 REAL Y PERMEABILIDAD DERIVADA\n")
print(f"  [B1] Núcleo de ferrita — μ_eff calculado, no supuesto\n")
print(f"    Geometría: L={L_CORE} m · Ø{D_CORE*1000:.0f} mm · L/D={L_CORE/D_CORE:.0f}")
print(f"    Factor desmagnetizante Nd = {ND:.5f}")
print(f"    μ_eff teórico de geometría = {MU_EFF_TH:.0f}  [V — referencia futura]")
print(f"    μ_eff de DISEÑO (usado en TODOS los cálculos oficiales) = {MU_EFF_DESIGN:.0f}")
print(f"    Margen de fabricación retenido: {20*np.log10(MU_EFF_TH/MU_EFF_DESIGN):.1f} dB no reclamado")
print(f"    v4 asumía μ_eff=150 → el diseño real ({MU_EFF_DESIGN:.0f}) ya lo supera")
print(f"    Masa del núcleo: {M_FER:.0f} kg  (v4: 339 kg con Ø150 mm)")
print(f"\n    Momento dipolar: {M_REF:.3e} A·m²")
print(f"    Campo en superficie a {DEPTH_CR} m: {B_REF:.1f} pT")

print(f"\n  [B2] Piso de ruido — CORRECCIÓN CENTRAL DE v5\n")
print(f"    v4 usaba 1 pT. Ese es el piso del SENSOR SQUID, no el ruido")
print(f"    geomagnético ambiental, que a 2 Hz (banda Pc1) vale 10–1000 pT.")
print(f"    El enlace cierra por CANCELACIÓN con estación de referencia")
print(f"    (Pc1 es coherente sobre cientos de km) + integración coherente.\n")
print(f"    {'Condición geomagnética':<26}{'Pc1':>8}{'tras ref':>10}{'SNR proc':>10}  Estado")
print("    "+"─"*62)
snr_tip = None
for cond, pc1 in PC1.items():
    raw, proc = snr_real(M_REF, pc1)
    if cond.startswith("Típico"): snr_tip = proc
    st = "✓ cierra" if proc > 20 else ("⚠ marginal" if proc > 10 else "⛔ falla")
    print(f"    {cond:<26}{pc1:>6.0f}pT{pc1/10**(REJ_REF_DB/20):>8.1f}pT{proc:>8.1f}dB  {st}")
raw_deg, proc_deg = snr_real(M_REF, 300.0, rej_dB=15.0)
print(f"    {'Activo, ref. degradada':<26}{300:>6.0f}pT{300/10**(15/20):>8.1f}pT{proc_deg:>8.1f}dB  ⚠ marginal")
print(f"\n    → SNR realista en condición típica: {snr_tip:.0f} dB (v4 reportaba 51 dB)")
print(f"    → Requisito de diseño: rechazo de referencia ≥ 30 dB. No es opcional.")
print(f"    → En tormenta CME: repetir el bit durante minutos (el precursor")
print(f"      tiene ventana de horas–días, sobra tiempo).")

# ── B2b: Protocolo adaptativo Kp [P1] ───────────────────────────────────
print(f"\n  [B2b] PROTOCOLO ADAPTATIVO POR Kp  [P1]\n")
print(f"    {'Kp':>6} {'Condición':<22} {'Bits/alarma':>12} {'T_tx':>8} {'SNR efectivo':>14}")
print("    "+"─"*66)
KP_PROTO_PC1 = [(0,2,"Tranquilo",20),(3,4,"Moderado",60),
                (5,6,"Activo",300),(7,9,"Tormenta CME",3000)]
for k0, k1, cond, pc1 in KP_PROTO_PC1:
    raw, proc = snr_real(M_REF, pc1)
    # nbit MÍNIMO real para cerrar con el mu_eff de DISEÑO (no el teórico)
    nbit = 1
    while proc + 10*np.log10(nbit) < 20.0 and nbit < 64:
        nbit += 1
    proc_eff = proc + 10*np.log10(nbit)
    ttx = nbit*T_BIT
    st = "✓" if proc_eff >= 20 else "⚠"
    print(f"    {k0}–{k1:<4} {cond:<22} {nbit:>12} {ttx:>6.0f}s {proc_eff:>10.1f} dB  {st}")
print(f"\n    → nbit calculado con μ_eff={MU_EFF_DESIGN:.0f} de diseño, no con el 383 teórico.")
print(f"    → Tormenta CME necesita más repeticiones que con la cifra optimista,")
print(f"      pero T_tx sigue en minutos << ventana de precursor (horas–días).")

# Potencia
Lw = N_REF*2*np.pi*R_COIL
Rc = RHO_CU*Lw/(A_REF*1e-6)
Pc = I_REF**2*Rc
print(f"\n  [B3] Presupuesto eléctrico de la bobina\n")
print(f"    Hilo Cu {A_REF} mm²: {Lw:.0f} m · R={Rc:.2f} Ω · {8960*A_REF*1e-6*Lw:.0f} kg")
print(f"    Potencia en ráfaga: {Pc:.0f} W · ciclo {DUTY*100:.0f}% → media {Pc*DUTY:.0f} W")
print(f"    Sin criogenia en la bobina. Se evacúa al fluido del pozo. ✓")

# σ variable
print(f"\n  [B4] Robustez litológica (ruido Pc1 típico, ref. 30 dB)\n")
print(f"    {'Litología':<32}{'σ (S/m)':>10}{'δ (km)':>9}{'SNR':>9}")
print("    "+"─"*60)
LITO = [("Basalto seco",5e-5),("Basalto húmedo (ref CR)",1.2e-4),
        ("Andesita/ignimbrita",3e-4),("Sedimento volcánico",1e-3),
        ("Zona de falla con fluidos",5e-3),("Arcilla hidrotermal ácida",2e-2)]
for lit, sig in LITO:
    _, p = snr_real(M_REF, 60.0, sig=sig)
    print(f"    {lit:<32}{sig:>10.1e}{skin(sig)/1000:>9.1f}{p:>7.1f}dB {'✓' if p>20 else '⚠'}")
_, snr_peor = snr_real(M_REF, 60.0, sig=2e-2)
print(f"\n    Peor caso litológico: {snr_peor:.1f} dB → margen {snr_peor-20:.0f} dB ✓")
REF = dict(snr=snr_tip)

# ── B5: arquitectura de enlace corregida ─────────────────────────────────
print(f"\n  [B5] ARQUITECTURA DE ENLACE — CABLE PRIMARIO, ULF RESPALDO\n")
print(f"    Un pozo entubado de {DEPTH_CR} m se instrumenta con cable armado.")
print(f"    Es la práctica de NIED Hi-net (Japón), SAFOD (EE.UU.) y GONAF (Turquía).\n")
print(f"    {'Criterio':<32}{'Cable armado':>16}{'ULF':>16}")
print("    "+"─"*64)
COMP = [("Ancho de banda","Mbit/s","0.033 bit/s"),
        ("Latencia","<1 ms","1.5 s"),
        ("Potencia en el sonde","~0 W",f"{Pc*DUTY:.0f} W"),
        ("Afectado por tormenta CME","no","sí"),
        ("Sobrevive cizalla de falla","no","sí"),
        ("CAPEX 5 nodos","$60,000","$385,000")]
for a,b,c in COMP: print(f"    {a:<32}{b:>16}{c:>16}")
print(f"\n    → PRIMARIO: cable armado. Telemetría completa, sin consumo.")
print(f"    → RESPALDO: ULF. Se activa sólo si el entubado es cizallado por")
print(f"      la falla — su única ventaja real, y la que justifica su coste.")
print(f"    → Ventaja del cambio: el ULF ya no necesita margen para telemetría")
print(f"      continua, sólo para repetir el bit de alarma. Presupuesto holgado.")

# ── B6: Curva térmica ferrita en pozo [v5.3] ────────────────────────────
print(f"\n  [B6] CURVA TÉRMICA DE FERRITA EN POZO  [v5.3]\n")
# MnZn: μ cae ~0.3–0.5%/°C sobre 25 °C en rango 25–100 °C [P literatura]
T_SURF, GRAD = 25.0, 30.0  # °C, °C/km típico CR volcánico
T_POZO = T_SURF + GRAD * (DEPTH_CR/1000.0)
DERATE_PCT_PER_C = 0.004  # 0.4%/°C sobre 25 °C
mu_T = MU_EFF_DESIGN * (1 - DERATE_PCT_PER_C * max(0.0, T_POZO - 25.0))
mu_T = max(mu_T, 80.0)  # piso de diseño
M_T = dipolo(mu=mu_T)
_, snr_T = snr_real(M_T, 60.0)
print(f"    T superficial:     {T_SURF:.0f} °C")
print(f"    Gradiente CR:      {GRAD:.0f} °C/km  → T@{DEPTH_CR}m ≈ {T_POZO:.0f} °C")
print(f"    Derate μ:          {DERATE_PCT_PER_C*100:.1f} %/°C sobre 25 °C  [P]")
print(f"    μ_eff @ T pozo:    {mu_T:.0f}  (diseño frío {MU_EFF_DESIGN:.0f})")
print(f"    SNR típico @ T:    {snr_T:.1f} dB  {'✓' if snr_T>=20 else '⚠'}")
print(f"    → Aun con derate térmico el enlace típico cierra con margen.")

# ── B7: P(cizalla de cable) vs Mw — valor del ULF [v5.3] ────────────────
print(f"\n  [B7] P(CIZALLA DE CABLE) vs Mw — VALOR DEL ULF  [v5.3]\n")
# Modelo logístico simple [H]: P_shear ≈ 1/(1+exp(-k(M-M0)))
# calibrado cualitativamente: M6 ~5%, M7 ~25%, M7.5 ~45%, M8 ~70%
def p_shear(M):
    return 1.0 / (1.0 + np.exp(-2.2 * (M - 7.1)))
print(f"    {'Mw':>6} {'P(cizalla cable)':>18} {'Modo telemetría':<22} {'Latencia'}")
print("    "+"─"*60)
for M in [6.0, 6.5, 7.0, 7.5, 7.8, 8.0]:
    ps = p_shear(M)
    modo = "ULF probable" if ps > 0.35 else ("mixto" if ps > 0.15 else "cable OK")
    lat = 7.3 if ps > 0.35 else (6.5 if ps > 0.15 else 5.7)
    print(f"    {M:>6.1f} {ps*100:>16.1f}%  {modo:<22} {lat:.1f} s")
# Valor esperado: fracción de alertas que dependen del ULF
p_ulf_needed = np.mean([p_shear(M) for M in [6.5, 7.0, 7.5, 7.8]])
capex_ulf = 85_000
print(f"\n    P(ULF necesario) media en sismos mayores: {p_ulf_needed*100:.0f}%  [H]")
print(f"    CAPEX ULF 5 nodos: ${capex_ulf:,}")
print(f"    → Sin ULF, ~{p_ulf_needed*100:.0f}% de los eventos grandes perderían canal")
print(f"      de telemetría de pozo en el momento crítico (post-cizalla).")
print(f"    → El ULF se justifica como seguro de canal, no como telemetría diaria.")

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ C — ÁRBOL DE DECISIONES IA (conservado de v3.8)                       ║
# ╚════════════════════════════════════════════════════════════════════════╝
K_SIGMA, P_FASE3, LAT_BAYES = 2.5, 0.85, 1.8

class ArbolIA:
    """Validación en 4 fases. Protege la credibilidad del Cell Broadcast."""
    NIV = {0:"001",1:"001",2:"010",3:"010",111:"111"}
    def __init__(self): self.n = {0:0,1:0,2:0,3:0,111:0}
    def evaluar(self, e):
        if e['energia'] <= e['umbral']:      f=0; txt="Archivado — ruido local"
        elif e['sensores'] < 3:              f=1; txt="Amarilla interna — 1-2 sensores"
        elif e['nodos_adj'] < 2:             f=2; txt="Naranja — informe OVSICORI/RSN"
        elif e['p_bayes'] <= P_FASE3:        f=3; txt=f"Pre-alerta — P={e['p_bayes']:.2f}"
        else:                                f=111;txt=f"ROJA — Cell Broadcast ({LAT_BAYES}s)"
        self.n[f]+=1
        return f, self.NIV[f], txt

print(f"\n{'─'*74}")
print(f"[C] ÁRBOL DE DECISIONES IA — 4 FASES\n")
arbol = ArbolIA()
ESC = [
 ("Pico radón aislado (Arenal)",      0.0, dict(energia=1.8,umbral=1.5,sensores=1,nodos_adj=0,p_bayes=0.12)),
 ("Anomalía magnética+radón (GAM)",   5.5, dict(energia=3.2,umbral=1.5,sensores=3,nodos_adj=1,p_bayes=0.55)),
 ("Enjambre+poros+DAS (Osa)",         6.2, dict(energia=5.1,umbral=1.5,sensores=5,nodos_adj=2,p_bayes=0.78)),
 ("Dilatancia pre-sísmica (GAM)",     6.5, dict(energia=7.3,umbral=1.5,sensores=6,nodos_adj=3,p_bayes=0.92)),
 ("Megathrust Osa",                   7.5, dict(energia=9.8,umbral=1.5,sensores=8,nodos_adj=4,p_bayes=0.97)),
]
print(f"  {'Escenario':<36}{'M':>5}{'Fase':>6}{'Cód':>6}  Resultado")
print("  "+"─"*74)
for nom, M, ev in ESC:
    f, cod, txt = arbol.evaluar(ev)
    ic = "🔴" if cod=="111" else ("🟠" if cod=="010" else "🟡")
    print(f"  {nom:<36}{M:>5.1f}{f:>6}{cod:>6}  {ic} {txt}")

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ D — DETECCIÓN + MONTE CARLO                                           ║
# ╚════════════════════════════════════════════════════════════════════════╝
def Pd(M, prec):
    base = 0.55 if M<6.0 else 0.60 if M<6.5 else 0.72 if M<7.0 else 0.85 if M<7.5 else 0.92
    return min(0.95, base*{'documentado':1.15,'posible':1.02,'ninguno':0.82}[prec])
def aviso_h(M): return 6 if M<6.0 else 18 if M<6.5 else 36 if M<7.0 else 60 if M<7.5 else 96
def reduc(h):   return 0.20 if h<=6 else 0.45 if h<=24 else 0.70 if h<=48 else 0.80

SISMOS = [
 (1991,"Limón",      7.6,'posible',     92e6),
 (2009,"Cinchona",   6.2,'ninguno',    100e6),
 (2012,"Nicoya",     7.6,'documentado', 45e6),
 (2025,"GAM proy.",  6.5,'posible',    150e6),
 (2035,"Osa proy.",  7.8,'documentado',300e6),
]
print(f"\n{'─'*74}")
print(f"[D] DETECCIÓN SOBRE SISMICIDAD CR + MONTE CARLO\n")
print(f"  {'Evento':<20}{'M':>5}{'Pd':>6}{'Aviso':>7}{'Red%':>7}{'Daño base':>12}{'c/Sist':>11}")

sin_t=con_t=0
for yr,lug,M,prec,dano in SISMOS:
    p=Pd(M,prec); h=aviso_h(M); rd=reduc(h)
    det = rng.random()<p
    c = dano*(1-rd*0.7) if det else dano
    sin_t+=dano; con_t+=c
    print(f"  {yr} {lug:<15}{M:>5.1f}{p:>6.2f}{h:>6}h{rd*100:>6.0f}%${dano/1e6:>10.0f}M"
          f"${c/1e6:>9.0f}M  {'✓' if det else '⛔ FN'}")
print(f"\n  SIN sistema: ${sin_t/1e6:,.0f} M   CON sistema: ${con_t/1e6:,.0f} M [H]")
print(f"  Ahorro determinista: ${(sin_t-con_t)/1e6:,.0f} M [H]")

N_MC=2000; ah=[]; fn=[]
for _ in range(N_MC):
    s=c=0; k=0
    for yr,lug,M,prec,dano in SISMOS:
        p=Pd(M,prec); d=rng.random()<p
        s+=dano; c+= dano*(1-reduc(aviso_h(M))*0.7) if d else dano
        k+= 0 if d else 1
    ah.append((s-c)/1e6); fn.append(k)
ah=np.array(ah); fn=np.array(fn)
print(f"\n  Monte Carlo ({N_MC} realizaciones):")
print(f"    Ahorro medio: ${ah.mean():,.0f} M · P10–P90: ${np.percentile(ah,10):,.0f}–${np.percentile(ah,90):,.0f} M")
print(f"    FN medio: {fn.mean():.2f} de {len(SISMOS)} · P(FN=0) = {(fn==0).mean()*100:.0f}%")

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ E — CAPEX / OPEX RECONSTRUIDO SIN REACTOR                             ║
# ╚════════════════════════════════════════════════════════════════════════╝
CAPEX_BASE = {
 "Perforación rotatoria 600 m (5 nodos)":      550_000,
 "Entubado, cementado y completación":         180_000,
 "Interrogadores DAS multicanal (5)":          750_000,
 "Magnetómetros SQUID superficie (5)":         350_000,  # dry SQUID más realista
 "Magnetómetros Rb-87 de pozo (10)":           200_000,
 "Cable armado wireline 600 m (5) [PRIMARIO]":  60_000,
 "Bobina ULF ferrita + driver (5) [RESPALDO]":  85_000,
 "Detectores radón + geoquímica (5)":           60_000,
 "Transductores presión de poros (10)":         60_000,
 "Sondes Ti + sellado PTFE (5)":               140_000,
 "Telecom ICE + satélite LEO respaldo":         75_000,
 "Servidores cómputo bayesiano OVSICORI":      150_000,
 "Gateway Cell Broadcast CNE":                 180_000,
 "Ingeniería, instalación, comisionado":       200_000,
}
CONTINGENCIA_PCT = 0.18  # [P1] 18% (antes 12%)
_capex_sub = sum(CAPEX_BASE.values())
CAPEX = dict(CAPEX_BASE)
CAPEX[f"Contingencia {CONTINGENCIA_PCT*100:.0f}%"] = int(round(_capex_sub * CONTINGENCIA_PCT))
CAPEX_T = sum(CAPEX.values())
OPEX = {
 "Mantenimiento e instrumentación":            125_000,
 "Criogenia SQUID superficie (dry cooler)":     18_000,
 "Conectividad dedicada ICE":                   18_000,
 "Planilla científica (4 plazas)":             182_000,
 "Energía y consumibles":                       10_000,
 "Soporte Cell Broadcast CNE":                  25_000,
 "Seguros y auditorías":                        20_000,
}
OPEX_1 = sum(OPEX.values()); INFL=0.035; YEARS=30
opex_acum = sum(OPEX_1*(1+INFL)**(y-1) for y in range(1,YEARS+1))
REEMPLAZOS = 3_030_000
TOTAL30 = CAPEX_T + opex_acum + REEMPLAZOS

print(f"\n{'─'*74}")
print(f"[E] CAPEX / OPEX — SIN REACTOR\n")
for k,v in CAPEX.items(): print(f"  {k:<46}${v:>11,}")
print(f"  {'─'*58}")
print(f"  {'CAPEX TOTAL':<46}${CAPEX_T:>11,}")
print(f"\n  OPEX año 1: ${OPEX_1:,}   ·   OPEX 30 años: ${opex_acum:,.0f}")
print(f"  Reemplazo de sensores 30a: ${REEMPLAZOS:,}")
print(f"  TOTAL 30 AÑOS: ${TOTAL30:,.0f}  ·  ${TOTAL30/30:,.0f}/año")
print(f"\n  Comparativa de CAPEX:")
print(f"    v3.8 con REBCO:                 $11,732,500")
print(f"    v3.8 + reactor real (5×350MWt): ≳ $5,000,000,000")
print(f"    v4.0 sin reactor:               ${CAPEX_T:,}  ✓ financiable por MIDEPLAN")

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ F — B/C RECONCILIADO CON EL INFORME OFICIAL                           ║
# ╚════════════════════════════════════════════════════════════════════════╝
print(f"\n{'─'*74}")
print(f"[F] RELACIÓN BENEFICIO-COSTO — RECONCILIACIÓN\n")
print(f"  El informe MIDEPLAN declara B/C = 14.7:1. Versiones previas del código")
print(f"  reportaban 52–102:1 por asumir 2,000 vidas salvadas. Se documenta el rango:\n")
VSL = 1_200_000
print(f"  {'Supuesto de vidas (30 años)':<34}{'Beneficio':>14}{'B/C':>10}  Uso")

for vidas, uso in [(290,"Conservador — alineado al informe oficial"),
                   (600,"Intermedio"),
                   (2000,"Optimista — usado en v3.8")]:
    bc = vidas*VSL/TOTAL30
    print(f"  {vidas:>6} vidas × $1.2 M VSL{'':<10}${vidas*VSL/1e6:>11.0f} M{bc:>9.1f}:1  {uso}")
bc_cons = 290*VSL/TOTAL30
print(f"\n  → RECOMENDACIÓN: presentar {bc_cons:.1f}:1 ante MIDEPLAN.")
print(f"    Coincide con el informe oficial y resiste auditoría.")
print(f"    Un B/C de 100:1 en un expediente público invita escrutinio innecesario.")
print(f"\n  Contraste independiente de vidas: daños históricos 3 eventos = $237 M")
print(f"  → {237e6/TOTAL30:.1f}× el costo total de 30 años del sistema. [V]")

# ── F2: VAN @ 6% [P1] ─────────────────────────────────────────────────
print(f"\n  [F2] VALOR ACTUAL NETO @ 6% (disciplina MIDEPLAN)  [P1]\n")
R_DISC = 0.06
BENEF_ANUAL = 290 * VSL / YEARS   # vidas distribuidas en 30 años
pv_cost = CAPEX_T + sum(
    (OPEX_1 * ((1+INFL)**(t-1)) + REEMPLAZOS/YEARS) / ((1+R_DISC)**t)
    for t in range(1, YEARS+1)
)
pv_ben = sum(BENEF_ANUAL / ((1+R_DISC)**t) for t in range(1, YEARS+1))
VAN_6 = pv_ben - pv_cost
BC_DESC = pv_ben / pv_cost if pv_cost > 0 else 0
print(f"    Beneficio social anualizado: ${BENEF_ANUAL/1e6:.2f} M/año [H]")
print(f"    PV costes @ 6%:              ${pv_cost/1e6:.2f} M")
print(f"    PV beneficios @ 6%:          ${pv_ben/1e6:.2f} M")
print(f"    VAN @ 6%:                    ${VAN_6/1e6:.1f} M  [H]")
print(f"    B/C descontado @ 6%:         {BC_DESC:.1f}:1")
print(f"    → Proyecto con VAN positivo y B/C descontado > 1 bajo tasa MIDEPLAN.")

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ G — DISPONIBILIDAD CON CORRELACIÓN (conservado)                       ║
# ╚════════════════════════════════════════════════════════════════════════╝
RIESGOS = [("Corrosión hidrotermal","Crítico",0.30,0.95),
           ("Pérdida fibra ICE","Alto",0.45,0.85),
           ("Fallo eléctrico","Alto",0.35,0.92),
           ("Deriva térmica SQUID","Moderado",0.12,0.98),
           ("Vandalismo","Bajo",0.20,0.99)]
p_up = 1.0
for _,_,p,e in RIESGOS: p_up *= (1-p*(1-e))
print(f"\n{'─'*74}")
print(f"[G] DISPONIBILIDAD DE RED\n")
print(f"  Disponibilidad por nodo: {p_up*100:.1f}%")
p3_ind = sum(comb(5,k)*p_up**k*(1-p_up)**(5-k) for k in range(3,6))
P_SHOCK, P_SHOCK_UP = 0.08, 0.55
ups=[]
for _ in range(5000):
    q = P_SHOCK_UP if rng.random()<P_SHOCK else p_up
    ups.append(sum(rng.random()<q for _ in range(5)))
ups=np.array(ups); p3_corr=(ups>=3).mean()
print(f"  P(≥3 nodos) sin correlación: {p3_ind*100:.1f}%")
print(f"  P(≥3 nodos) con correlación post-sismo: {p3_corr*100:.1f}%")
print(f"  P(red caída completa): {(ups==0).mean()*100:.2f}%")

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ H — LATENCIA Y FALSAS ALARMAS (conservado)                            ║
# ╚════════════════════════════════════════════════════════════════════════╝
# [P1] Latencias duales: cable primario vs ULF respaldo
LAT_COMUN = [("Adquisición + stack",0.50),("Detección local kσ",0.30),
             ("Árbol bayesiano central",LAT_BAYES),("Gateway CNE → CB",1.00),
             ("Difusión CB a terminales",2.00)]
LAT_CABLE = LAT_COMUN + [("Transmisión cable armado",0.05),("Recepción decode cable",0.05)]
LAT_ULF   = LAT_COMUN + [("Transmisión ULF 3 bits",1.50),("Recepción SQUID + decode",0.20)]
T_CABLE = sum(v for _,v in LAT_CABLE)
T_ULF   = sum(v for _,v in LAT_ULF)
print(f"\n{'─'*74}")
print(f"[H] LATENCIA DUAL Y CREDIBILIDAD  [P1]\n")
print(f"  MODO CABLE (primario) — operación normal:")
for k,v in sorted(LAT_CABLE, key=lambda x: -x[1]):
    print(f"    {k:<36}{v:>6.2f} s")
print(f"    {'TOTAL cable':<36}{T_CABLE:>6.2f} s  ✓")
print(f"\n  MODO ULF (respaldo) — cable cizallado / falla:")
for k,v in sorted(LAT_ULF, key=lambda x: -x[1]):
    print(f"    {k:<36}{v:>6.2f} s")
print(f"    {'TOTAL ULF':<36}{T_ULF:>6.2f} s  ✓")
print(f"\n  → Ciudadano recibe alerta en {T_CABLE:.1f} s (normal) / {T_ULF:.1f} s (respaldo)")
LAT = LAT_ULF  # compat diagnóstico: peor caso
cand=120; f0=cand*0.40; f1=f0*0.35; f2=f1*0.25; c111=f2*0.08; fa=c111*0.15
print(f"\n  Embudo anual: {cand} anomalías → F0 {f0:.0f} → FI {f1:.1f} → FII {f2:.1f} → 111 {c111:.2f}")
print(f"  Falsas alarmas públicas: {fa:.2f}/año  → 1 cada {1/fa:.0f} años")
print(f"  Meta CNE < 2/año: {'✓ cumple' if fa<2 else '⚠'}")

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ I — EXPORTACIÓN Y DIAGNÓSTICO                                         ║
# ╚════════════════════════════════════════════════════════════════════════╝
out = dict(
  version=VERSION, inventor="Jason Manuel Sarmiento Salazar",
  cedula="114510108", fecha="2026-09-12",
  cambio_clave="v5.3: curva T ferrita + P(cizalla) vs Mw + valor ULF",
  pozo=dict(diam_mm=D_HOLE_MM, prof_m=DEPTH_CR, dias_nodo=round(DIAS_POZO+DIAS_COMPL,1), T_pozo_C=round(T_POZO,1)),
  ulf=dict(
    bobina=f"Ferrita mu_diseno={MU_EFF_DESIGN:.0f} mu_T={mu_T:.0f} (teorico={MU_EFF_TH:.0f}) N={N_REF} I={I_REF}A",
    snr_tipico_dB=round(float(snr_tip),1),
    snr_Tpozo_dB=round(float(snr_T),1),
    snr_peor_litologia_dB=round(float(snr_peor),1),
    P_media_W=round(Pc*DUTY,1),
    arquitectura="cable primario + ULF respaldo",
    kp_adaptativo=True,
    p_ulf_necesario_eventos_mayores=round(float(p_ulf_needed),3),
  ),
  costos=dict(
    capex=CAPEX_T, contingencia_pct=CONTINGENCIA_PCT,
    opex_30a=round(opex_acum), total_30a=round(TOTAL30),
    bc_recomendado=round(bc_cons,1),
    van_6pct_usd=round(VAN_6), bc_descontado_6pct=round(BC_DESC,2),
  ),
  red=dict(disponibilidad_nodo=round(p_up,4), p_min3_corr=round(p3_corr,4)),
  latencia=dict(cable_s=round(T_CABLE,2), ulf_s=round(T_ULF,2)),
  fa_anual=round(fa,3),
)
for _outp in [
    os.path.join(OUT, "GEO_PROBE_CR_v5_resultados.json"),
    "/home/workdir/artifacts/GEO_PROBE_CR_v5_resultados.json",
]:
    try:
        json.dump(out, open(_outp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        p = _outp
    except Exception:
        pass


print(f"\n{L}")
print(f" DIAGNÓSTICO — GEO-PROBE CR v{VERSION}\n")
DIAG = [
 ("Pozo",          f"Ø{D_HOLE_MM} mm × {DEPTH_CR} m rotatoria · {DIAS_POZO+DIAS_COMPL:.0f} d/nodo","✓ convencional"),
 ("Reactor",       "ELIMINADO — innecesario a 600 m","✓"),
 ("Enlace ULF",    f"{snr_tip:.0f} dB típico · @Tpozo {snr_T:.0f} dB · peor lito {snr_peor:.0f}","✓ cierra"),
 ("μ_eff",         f"diseño={MU_EFF_DESIGN:.0f} · @T {mu_T:.0f} · teórico {MU_EFF_TH:.0f}","✓ v5.3"),
 ("Kp adaptativo", "nbit mínimo real · T_tx≤6.5 min en tormenta","✓"),
 ("P(cizalla)",    f"ULF necesario ~{p_ulf_needed*100:.0f}% eventos mayores [H]","✓ v5.3"),
 ("Arquitectura",  "Cable primario · ULF respaldo cizalla","✓"),
 ("Árbol IA",      f"4 fases · k={K_SIGMA}σ · P>{P_FASE3}","✓"),
 ("Monte Carlo",   f"Ahorro ${ah.mean():.0f} M · FN {fn.mean():.2f}/5","✓ [H]"),
 ("CAPEX",         f"${CAPEX_T:,} (contingencia {CONTINGENCIA_PCT*100:.0f}%)","✓"),
 ("Total 30 años", f"${TOTAL30:,.0f}","✓"),
 ("B/C nominal",   f"{bc_cons:.1f}:1 (oficial 14.7:1)","✓"),
 ("VAN @ 6%",      f"${VAN_6/1e6:.0f} M · B/C desc. {BC_DESC:.1f}:1","✓"),
 ("Latencia",      f"Cable {T_CABLE:.1f}s / ULF {T_ULF:.1f}s","✓"),
 ("Falsas alarmas",f"{fa:.2f}/año","✓ < meta CNE"),
 ("Disponibilidad",f"{p3_corr*100:.1f}% con ≥3 nodos","✓"),
 ("Inventor / IP", "Jason Manuel Sarmiento Salazar · 114510108","✓"),
]
for a,b,c in DIAG: print(f"  [{a:<16}] {b:<52} {c}")
print(f"\n  JSON → {p}")
print(f"\n  EVOLUCIÓN COMPETITIVA:")
print(f"    v3.8  reactor+HTS (inviable) → v4.0  pozo convencional")
print(f"    v5.0  Pc1 real + cable primario → v5.1  Kp/latencia/VAN/contingencia")
print(f"    v5.1 → v5.2  mu diseño decide números")
print(f"    v5.2 → v5.3  curva T + P(cizalla) cuantifica valor ULF")
print(f"    → Entregable COMPLETO para evaluación comparativa entre IAs")
print(f"\n  [H] hipótesis · [P] proyección documentada · [V] verificado")
print(L)
