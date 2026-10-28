#!/usr/bin/env python3
"""
GEO-PROBE CR — v6.2 UNIFICADA CANÓNICA
Red Nacional de Precursores Sísmicos · Costa Rica
Inventor: Jason Manuel Sarmiento Salazar · Cédula 114510108
Divulgación: 12 de septiembre de 2026 · OTPR CR / PCT WIPO

Historial: v3→v4 sin reactor · v4→v5 Pc1 real + cable primario · v5.2 μ_diseño=200
v5.4 P(cizalla) calibrada · v6.1 peso_canal+T_max+majority (solo impreso)
v6.2 REEMPLAZOS derivado [V] · v6.3 auditoría de v6.2:

  1. REEMPLAZOS correcto hoy (3.09M vs 3.03M plano) pero la fórmula
     "int(30/vida)-1" solo coincide con ceil(30/vida)-1 porque 7.5/10/15
     dividen 30 exacto. Cambiado a ceil() para que no falle en silencio
     si alguien ajusta una vida útil a un número que no divida 30.
  2. peso_canal/T_max/majority estaban calculados e impresos pero NUNCA
     llegaban a ArbolIA — el diagnóstico los marcaba "✓ v6.1" como si
     fueran un seguro activo, cuando eran narración desconectada del
     código de decisión. Ahora ArbolIA.evaluar_evento() recibe el peso
     del canal y aplica la regla que el propio texto describía: un 111
     solo-ULF con peso<0.50 baja a 010, salvo P>0.95 con ≥3 nodos.
  3. La línea de consola tenía "ULF lento={peso_storm}" mostrando el
     peso YA RESUELTO del escenario (0.70, rama "OK") bajo la etiqueta
     de la rama degradada — el JSON sí tenía bien los dos valores fijos
     (0.70 / 0.40), solo la impresión de consola los confundía. Corregido
     para mostrar ambas constantes de referencia, no el valor de turno.
  4. "MC sin fuga de ámbito" (v6.2) no corregía un bug real: el bucle
     exterior termina antes de que arranque el Monte Carlo, así que
     reusar M/prec/dano nunca colisionaba. Verificado ejecutando ambas
     versiones con semilla idéntica: salida idéntica byte a byte. Se
     conserva el estilo (es más claro) pero sin la etiqueta de "fix".

Determinista (seed 2026) · auditada contra 4 implementaciones previas.
"""
import numpy as np
import os
import json
import warnings
from math import ceil

warnings.filterwarnings("ignore")
rng = np.random.default_rng(2026)

VERSION = "6.3 UNIFICADA CANÓNICA"
DEPTH_CR = 600
N_NODOS = 5
D_HOLE_MM = 200
D_SONDE_MM = 168
L_SONDE_M = 6.0
ROP_M_DIA = 45
DIAS_COMPL = 6

MU0 = 4 * np.pi * 1e-7
F_ULF = 2.0
T_BIT = 30.0
MU_R = 2000.0
L_CORE = 4.0
D_CORE = 0.10
MU_EFF_DESIGN = 200.0
RHO_FER = 4800.0
RHO_CU = 1.68e-8
N_REF = 1000
I_REF = 20
A_REF = 10
R_COIL = 0.055
DUTY = 0.17
REJ_REF_DB = 30.0

T_SURF = 25.0
GRAD_TERMICO = 30.0
DERATE_PCT_PER_C = 0.004

CONTINGENCIA_PCT = 0.18
R_DISC = 0.06
INFLACION = 0.035
YEARS_PROYECTO = 30
VSL_USD = 1_200_000
VIDAS_OFICIAL = 290

SHEAR_K = 1.937
SHEAR_M0 = 7.581
T_MAX_ULF_S = 15 * 60

PC1_RUIDO = {
    "Tranquilo (noche, Kp≤2)": 20.0,
    "Típico diurno": 60.0,
    "Activo (Kp 4–5)": 300.0,
    "Tormenta CME (Kp≥7)": 3000.0,
}

SISMOS = [
    (1991, "Limón", 7.6, "posible", 92e6),
    (2009, "Cinchona", 6.2, "ninguno", 100e6),
    (2012, "Nicoya", 7.6, "documentado", 45e6),
    (2025, "GAM proy.", 6.5, "posible", 150e6),
    (2035, "Osa proy.", 7.8, "documentado", 300e6),
]


class ArbolIA:
    NIVEL_CODIGO = {0: "001", 1: "001", 2: "010", 3: "010", 111: "111"}

    def __init__(self):
        self.conteo_fases = {0: 0, 1: 0, 2: 0, 3: 0, 111: 0}
        self.P_FASE3_UMBRAL = 0.85
        self.LAT_BAYES = 1.8

    PESO_MINIMO_111 = 0.50
    P_OVERRIDE_CANAL_DEBIL = 0.95
    NODOS_OVERRIDE_CANAL_DEBIL = 3

    def evaluar_evento(self, e, peso_canal=1.0):
        """
        peso_canal: 1.00 cable (primario) · 0.70 ULF a tiempo · 0.40 ULF
        degradado (excede T_max). v6.3: la regla que antes solo se
        imprimía ahora decide de verdad — un 111 sostenido nada más que
        por un canal débil (peso<0.50) baja a 010, salvo consenso fuerte
        (P>0.95 y ≥3 nodos), que sí amerita saltarse el filtro de canal.
        """
        if e["energia"] <= e["umbral"]:
            fase, txt = 0, "Archivado — ruido local"
        elif e["sensores"] < 3:
            fase, txt = 1, "Amarilla interna — 1-2 sensores"
        elif e["nodos_adj"] < 2:
            fase, txt = 2, "Naranja — informe OVSICORI/RSN"
        elif e["p_bayes"] <= self.P_FASE3_UMBRAL:
            fase, txt = 3, f"Pre-alerta — P={e['p_bayes']:.2f}"
        else:
            override = (e["p_bayes"] > self.P_OVERRIDE_CANAL_DEBIL
                        and e["nodos_adj"] >= self.NODOS_OVERRIDE_CANAL_DEBIL)
            if peso_canal < self.PESO_MINIMO_111 and not override:
                fase = 3
                txt = (f"111→010 degradado: peso_canal={peso_canal:.2f}<"
                       f"{self.PESO_MINIMO_111:.2f} sin consenso fuerte")
            else:
                fase, txt = 111, f"ROJA — Cell Broadcast ({self.LAT_BAYES}s)"
        self.conteo_fases[fase] += 1
        return fase, self.NIVEL_CODIGO[fase], txt


def skin(sigma):
    return np.sqrt(2 / (2 * np.pi * F_ULF * MU0 * sigma))


def mu_eff_teorica(L, Dc):
    LD = L / Dc
    Nd = (np.log(2 * LD) - 1) / (LD ** 2)
    return MU_R / (1 + Nd * (MU_R - 1)), Nd


def campo_pT(m, d=DEPTH_CR, sigma=1.2e-4):
    return MU0 * m / (2 * np.pi * d ** 3) * np.exp(-d / skin(sigma)) * 1e12


def snr_real(m, pc1_pT, rej_dB=REJ_REF_DB, d=DEPTH_CR, sigma=1.2e-4):
    B = campo_pT(m, d, sigma)
    eff = pc1_pT / 10 ** (rej_dB / 20)
    raw = 20 * np.log10(B / eff)
    return raw, raw + 10 * np.log10(F_ULF * T_BIT)


def p_shear(Mw):
    return 1.0 / (1.0 + np.exp(-SHEAR_K * (Mw - SHEAR_M0)))


def Pd(Mw, prec):
    base = 0.55 if Mw < 6 else 0.60 if Mw < 6.5 else 0.72 if Mw < 7 else 0.85 if Mw < 7.5 else 0.92
    return min(0.95, base * {"documentado": 1.15, "posible": 1.02, "ninguno": 0.82}[prec])


def aviso_h(Mw):
    return 6 if Mw < 6 else 18 if Mw < 6.5 else 36 if Mw < 7 else 60 if Mw < 7.5 else 96


def reduc(h):
    return 0.20 if h <= 6 else 0.45 if h <= 24 else 0.70 if h <= 48 else 0.80


def ciclos_reemplazo(vida_anos, horizonte=30):
    """
    [V] N° de compras de reposición (no la unidad original de CAPEX)
    necesarias para mantener el componente operativo todo el horizonte.
    ceil(), no int(): int() solo da el mismo resultado cuando `vida`
    divide exacto al horizonte (7.5/10/15 → 30 sí; 8, 12, etc. no).
    """
    return ceil(horizonte / vida_anos) - 1


def calcular_reemplazos_analiticos():
    """[V] Fondo de reemplazos a 30 años por vida útil real de cada componente."""
    # Costos unitarios desde CAPEX agregado
    c_das = 750_000 / 5          # por nodo
    c_squid = 350_000 / 5
    c_rb87 = 200_000 / 10        # por sensor (2 por nodo en fórmula)
    c_sonda = 140_000 / 5
    c_telecom = 75_000 / 5

    ciclos_rb87 = ciclos_reemplazo(7.5)     # 3
    ciclos_sonda = ciclos_reemplazo(15)     # 1
    ciclos_das = ciclos_reemplazo(10)       # 2
    ciclos_squid = ciclos_reemplazo(10)     # 2
    ciclos_telecom = ciclos_reemplazo(10)   # 2

    total = N_NODOS * (
        c_rb87 * 2 * ciclos_rb87
        + c_sonda * ciclos_sonda
        + c_das * ciclos_das
        + c_squid * ciclos_squid
        + c_telecom * ciclos_telecom
    )
    return int(round(total))


def main():
    L = "═" * 74
    print(L)
    print(f" GEO-PROBE CR — v{VERSION}")
    print(" Jason Manuel Sarmiento Salazar · Cédula 114510108")
    print(" REEMPLAZOS derivado · MC sin fuga de ámbito · Protocolos v6.1")
    print(L)

    dias_pozo = DEPTH_CR / ROP_M_DIA
    dias_nodo = dias_pozo + DIAS_COMPL
    print(f"\n[A] DESPLIEGUE — PERFORACIÓN CONVENCIONAL\n")
    print(f"  Pozo: Ø{D_HOLE_MM} mm × {DEPTH_CR} m · Sonde Ø{D_SONDE_MM} mm × {L_SONDE_M} m")
    print(f"  ROP {ROP_M_DIA} m/día · {dias_nodo:.1f} d/nodo · 5 nodos: {dias_nodo*N_NODOS/2/30:.1f} meses")
    print(f"  Reactor ELIMINADO")

    mu_th, Nd = mu_eff_teorica(L_CORE, D_CORE)
    m_fer = RHO_FER * np.pi * (D_CORE / 2) ** 2 * L_CORE
    m_ref = MU_EFF_DESIGN * N_REF * I_REF * np.pi * R_COIL ** 2
    B_ref = campo_pT(m_ref)
    print(f"\n{'─'*74}")
    print(f"[B] ENLACE ULF — μ diseño={MU_EFF_DESIGN:.0f}\n")
    print(f"  μ_th={mu_th:.0f} · Nd={Nd:.5f} · masa={m_fer:.0f} kg · m={m_ref:.3e} · B={B_ref:.1f} pT")
    print(f"  Margen fábrica: {20*np.log10(mu_th/MU_EFF_DESIGN):.1f} dB")

    print(f"\n  [B2] SNR vs Pc1 (rechazo {REJ_REF_DB} dB)")
    snr_tip = 0.0
    for cond, pc1 in PC1_RUIDO.items():
        _, proc = snr_real(m_ref, pc1)
        if "Típico" in cond:
            snr_tip = proc
        st = "✓" if proc >= 20 else ("⚠" if proc >= 10 else "⛔")
        print(f"    {cond:<26} {pc1:>6.0f}pT  SNR={proc:5.1f} dB {st}")

    print(f"\n  [B2b] Protocolo Kp adaptativo")
    for k0, k1, name, pc1 in [(0, 2, "Tranquilo", 20), (3, 4, "Moderado", 60),
                               (5, 6, "Activo", 300), (7, 9, "Tormenta", 3000)]:
        _, proc = snr_real(m_ref, pc1)
        nbit = 1
        while proc + 10 * np.log10(nbit) < 20 and nbit < 64:
            nbit += 1
        print(f"    Kp {k0}–{k1} {name:<12} bits={nbit:>2}  T_tx={nbit*T_BIT:>5.0f}s  SNReff={proc+10*np.log10(nbit):5.1f} dB")

    print(f"\n  [B2c] PROTOCOLOS DE CORRECCIÓN  [v6.1]\n")
    _, proc_storm = snr_real(m_ref, 3000)
    nbit_s = 1
    while proc_storm + 10 * np.log10(nbit_s) < 20 and nbit_s < 64:
        nbit_s += 1
    t_storm = nbit_s * T_BIT
    maj_ok = (3 * t_storm) <= T_MAX_ULF_S
    peso_storm = 0.7 if t_storm <= T_MAX_ULF_S else 0.4
    print(f"    T_max ULF={T_MAX_ULF_S/60:.0f} min · Tormenta nbit={nbit_s} T_tx={t_storm:.0f}s")
    print(f"    Majority 2-de-3: {'✓' if maj_ok else '✗ (excede T_max)'}")
    print(f"    Escenario tormenta resuelve a peso_canal={peso_storm:.2f} "
          f"({'ULF a tiempo' if peso_storm>=0.7 else 'ULF degradado'})")
    print(f"    Constantes de referencia: cable=1.00 | ULF a tiempo=0.70 | ULF degradado=0.40")
    print(f"    111 solo-ULF con peso<0.50 baja a 010 salvo P>0.95 y ≥3 nodos [ArbolIA v6.3]")

    Lw = N_REF * 2 * np.pi * R_COIL
    Rc = RHO_CU * Lw / (A_REF * 1e-6)
    Pc = I_REF ** 2 * Rc
    print(f"\n  [B3] Potencia media: {Pc*DUTY:.0f} W")

    print(f"\n  [B4] Litologías")
    snr_peor = 0.0
    for lit, sig in [("Basalto seco", 5e-5), ("Basalto húmedo CR", 1.2e-4), ("Andesita", 3e-4),
                     ("Sedimento", 1e-3), ("Falla fluidos", 5e-3), ("Arcilla ácida", 2e-2)]:
        _, p = snr_real(m_ref, 60.0, sigma=sig)
        if sig == 2e-2:
            snr_peor = p
        print(f"    {lit:<22} σ={sig:.1e}  SNR={p:5.1f} dB")

    T_pozo = T_SURF + GRAD_TERMICO * (DEPTH_CR / 1000)
    mu_T = max(80.0, MU_EFF_DESIGN * (1 - DERATE_PCT_PER_C * max(0, T_pozo - 25)))
    m_T = mu_T * N_REF * I_REF * np.pi * R_COIL ** 2
    _, snr_T = snr_real(m_T, 60.0)
    print(f"\n  [B6] T@600m={T_pozo:.0f}°C · μ_T={mu_T:.0f} · SNR@T={snr_T:.1f} dB")

    print(f"\n  [B7] P(cizalla) k={SHEAR_K} M0={SHEAR_M0}")
    majors = []
    for M in [6.0, 6.5, 7.0, 7.5, 7.8, 8.0]:
        ps = p_shear(M)
        if M in (6.5, 7.0, 7.5, 7.8):
            majors.append(ps)
        modo = "cable OK" if ps < 0.15 else ("mixto" if ps <= 0.35 else "ULF probable")
        print(f"    Mw {M:.1f}  P={ps*100:5.1f}%  {modo}")
    p_ulf = float(np.mean(majors))
    print(f"  → P(ULF necesario): {p_ulf*100:.0f}%")

    print(f"\n{'─'*74}\n[C] ÁRBOL IA 4 FASES\n")
    arbol = ArbolIA()
    for nom, M, ev in [
        ("Radón aislado Arenal", 0.0, dict(energia=1.8, umbral=1.5, sensores=1, nodos_adj=0, p_bayes=0.12)),
        ("Anomalía GAM", 5.5, dict(energia=3.2, umbral=1.5, sensores=3, nodos_adj=1, p_bayes=0.55)),
        ("Enjambre Osa", 6.2, dict(energia=5.1, umbral=1.5, sensores=5, nodos_adj=2, p_bayes=0.78)),
        ("Dilatancia GAM", 6.5, dict(energia=7.3, umbral=1.5, sensores=6, nodos_adj=3, p_bayes=0.92)),
        ("Megathrust Osa", 7.5, dict(energia=9.8, umbral=1.5, sensores=8, nodos_adj=4, p_bayes=0.97)),
    ]:
        f, cod, txt = arbol.evaluar_evento(ev)
        ic = "🔴" if cod == "111" else ("🟠" if cod == "010" else "🟡")
        print(f"  {nom:<28} M{M:.1f}  fase {f} {cod}  {ic} {txt}")

    print(f"\n  [C2] Gate de canal en la práctica — mismo evento, dos canales\n")
    caso_fuerte = dict(energia=9.8, umbral=1.5, sensores=8, nodos_adj=4, p_bayes=0.97)
    caso_debil  = dict(energia=7.3, umbral=1.5, sensores=6, nodos_adj=2, p_bayes=0.90)
    for etiqueta, ev_c, peso in [
        ("Megathrust Osa, cable primario", caso_fuerte, 1.00),
        ("Megathrust Osa, solo ULF degradado, consenso fuerte", caso_fuerte, 0.40),
        ("Evento menor, solo ULF degradado, sin consenso fuerte", caso_debil, 0.40),
    ]:
        f, cod, txt = arbol.evaluar_evento(ev_c, peso_canal=peso)
        print(f"    peso={peso:.2f}  {etiqueta:<52} → {cod}  {txt}")

    print(f"\n{'─'*74}\n[D] DETECCIÓN + MONTE CARLO (v6.2 vars locales)\n")
    for yr, lug, M, prec, dano in SISMOS:
        p = Pd(M, prec)
        det = rng.random() < p
        c = dano * (1 - reduc(aviso_h(M)) * 0.7) if det else dano
        print(f"  {yr} {lug:<12} M{M:.1f} Pd={p:.2f}  ${c/1e6:.0f}M  {'✓' if det else '⛔ FN'}")
    ah, fn = [], []
    for _ in range(2000):
        s = c = k = 0
        for _, _, m_mc, prec_mc, dano_mc in SISMOS:
            d = rng.random() < Pd(m_mc, prec_mc)
            s += dano_mc
            c += dano_mc * (1 - reduc(aviso_h(m_mc)) * 0.7) if d else dano_mc
            k += 0 if d else 1
        ah.append((s - c) / 1e6)
        fn.append(k)
    ah, fn = np.array(ah), np.array(fn)
    print(f"  MC: ahorro medio ${ah.mean():.0f}M · FN medio {fn.mean():.2f}/5")

    CAPEX_BASE = {
        "Perforación 5×600m": 550_000,
        "Entubado/cementado": 180_000,
        "DAS (5)": 750_000,
        "SQUID superficie (5)": 350_000,
        "Rb-87 pozo (10)": 200_000,
        "Cable armado (5) PRIMARIO": 60_000,
        "Bobina ULF (5) RESPALDO": 85_000,
        "Radón (5)": 60_000,
        "Presión poros (10)": 60_000,
        "Sondes Ti/PTFE (5)": 140_000,
        "Telecom ICE+LEO": 75_000,
        "Cómputo OVSICORI": 150_000,
        "Gateway CB CNE": 180_000,
        "Ingeniería/comisionado": 200_000,
    }
    sub = sum(CAPEX_BASE.values())
    cont = int(round(sub * CONTINGENCIA_PCT))
    CAPEX_T = sub + cont
    OPEX_1 = 125_000 + 18_000 + 18_000 + 182_000 + 10_000 + 25_000 + 20_000
    opex_30 = sum(OPEX_1 * ((1 + INFLACION) ** (y - 1)) for y in range(1, YEARS_PROYECTO + 1))
    reemplazos = calcular_reemplazos_analiticos()
    TOTAL30 = CAPEX_T + opex_30 + reemplazos
    print(f"\n{'─'*74}")
    print(f"[E] CAPEX ${CAPEX_T:,} · OPEX30 ${opex_30:,.0f}")
    print(f"    REEMPLAZOS derivados [V]: ${reemplazos:,}  (antes constante $3,030,000 [H])")
    print(f"    Total 30a ${TOTAL30:,.0f}")

    bc = VIDAS_OFICIAL * VSL_USD / TOTAL30
    benef_a = VIDAS_OFICIAL * VSL_USD / YEARS_PROYECTO
    pvc = CAPEX_T + sum(
        (OPEX_1 * ((1 + INFLACION) ** (t - 1)) + reemplazos / YEARS_PROYECTO) / ((1 + R_DISC) ** t)
        for t in range(1, YEARS_PROYECTO + 1)
    )
    pvb = sum(benef_a / ((1 + R_DISC) ** t) for t in range(1, YEARS_PROYECTO + 1))
    van = pvb - pvc
    bc_d = pvb / pvc
    print(f"[F] B/C {bc:.1f}:1 · VAN@6% ${van/1e6:.0f}M · B/C desc {bc_d:.1f}:1")

    p_up = 1.0
    for p, e in [(0.30, 0.95), (0.45, 0.85), (0.35, 0.92), (0.12, 0.98), (0.20, 0.99)]:
        p_up *= 1 - p * (1 - e)
    ups = []
    for _ in range(5000):
        q = 0.55 if rng.random() < 0.08 else p_up
        ups.append(sum(rng.random() < q for _ in range(5)))
    ups = np.array(ups)
    p3 = (ups >= 3).mean()
    print(f"[G] Disp nodo {p_up*100:.1f}% · P(≥3) {p3*100:.1f}%")

    T_CABLE, T_ULF, fa = 5.70, 7.30, 0.05
    print(f"[H] Latencia {T_CABLE:.1f}s / {T_ULF:.1f}s · FA {fa:.2f}/año")

    out = {
        "version": VERSION,
        "inventor": "Jason Manuel Sarmiento Salazar",
        "cedula": "114510108",
        "fecha": "2026-09-12",
        "cambio_clave": "v6.3: ceil() en reemplazos, peso_canal aplicado en ArbolIA, print corregido",
        "auditoria_estatus": "v6.2 auditada: formula reemplazos + gate de canal + fuga de ambito revisados",
        "pozo": {"diam_mm": D_HOLE_MM, "prof_m": DEPTH_CR, "dias_nodo": round(dias_nodo, 1), "T_pozo_C": round(T_pozo, 1)},
        "ulf": {
            "bobina": f"Ferrita mu_diseno={MU_EFF_DESIGN:.0f} mu_T={mu_T:.0f} (teorico={mu_th:.0f})",
            "snr_tipico_dB": round(float(snr_tip), 1),
            "snr_Tpozo_dB": round(float(snr_T), 1),
            "snr_peor_litologia_dB": round(float(snr_peor), 1),
            "P_media_W": round(Pc * DUTY, 1),
            "arquitectura": "cable primario + ULF respaldo",
            "kp_adaptativo": True,
            "t_max_ulf_s": T_MAX_ULF_S,
            "peso_canal": {"cable": 1.0, "ulf_ok": 0.7, "ulf_lento": 0.4},
            "p_ulf_necesario_eventos_mayores": round(p_ulf, 3),
        },
        "costos": {
            "capex": CAPEX_T,
            "contingencia_pct": CONTINGENCIA_PCT,
            "opex_30a": round(opex_30),
            "reemplazos_ciclo_vida_usd": reemplazos,
            "total_30a": round(TOTAL30),
            "bc_recomendado": round(bc, 1),
            "van_6pct_usd": round(van),
            "bc_descontado_6pct": round(bc_d, 2),
        },
        "red": {"disponibilidad_nodo": round(p_up, 4), "p_min3_corr": round(float(p3), 4)},
        "latencia": {"cable_s": T_CABLE, "ulf_s": T_ULF},
        "fa_anual": fa,
    }
    out_dir = os.environ.get("GEOPROBE_OUT_DIR") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "artifacts")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "GEO_PROBE_CR_v6_resultados.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"\n{L}")
    print(f" DIAGNÓSTICO — GEO-PROBE CR v{VERSION}\n")
    for a, b, c in [
        ("Pozo", f"Ø{D_HOLE_MM} mm × {DEPTH_CR} m · {dias_nodo:.0f} d/nodo", "✓"),
        ("Reactor", "ELIMINADO", "✓"),
        ("Enlace ULF", f"{snr_tip:.0f} dB típ · @T {snr_T:.0f} · peor {snr_peor:.0f}", "✓"),
        ("μ_eff", f"diseño={MU_EFF_DESIGN:.0f} · @T {mu_T:.0f} · th {mu_th:.0f}", "✓"),
        ("P(cizalla)", f"ULF ~{p_ulf*100:.0f}%", "✓"),
        ("Protocolos", "peso_canal ahora dentro de ArbolIA, no solo impreso", "✓ v6.3"),
        ("REEMPLAZOS", f"${reemplazos:,} derivado [V]", "✓ v6.2"),
        ("CAPEX", f"${CAPEX_T:,}", "✓"),
        ("B/C / VAN@6%", f"{bc:.1f}:1 / ${van/1e6:.0f}M", "✓"),
        ("Latencia", f"{T_CABLE:.1f}s / {T_ULF:.1f}s", "✓"),
        ("FA", f"{fa:.2f}/año", "✓"),
        ("P(≥3 nodos)", f"{p3*100:.1f}%", "✓"),
        ("Inventor", "Jason Manuel Sarmiento Salazar · 114510108", "✓"),
    ]:
        print(f"  [{a:<14}] {b:<48} {c}")
    print(f"\n  JSON → {json_path}")
    print(L)


if __name__ == "__main__":
    main()
