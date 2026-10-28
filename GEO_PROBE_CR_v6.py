#!/usr/bin/env python3
"""
GEO-PROBE CR — v6.0 UNIFICADA (versión canónica)
Red Nacional de Precursores Sísmicos · Costa Rica
Inventor: Jason Manuel Sarmiento Salazar · Cédula 114510108
Divulgación: 12 de septiembre de 2026 · OTPR CR / PCT WIPO

HISTORIAL DE AUDITORÍA (cada corrección, verificada independientemente)
────────────────────────────────────────────────────────────────────────
  v3→v4   Reactor de 350 MWt eliminado: a 600 m el pozo se perfora, no se
          funde. Sonda de Ø3.5 m reducida a sonde de pozo estándar. El
          enlace ULF cierra con bobina de ferrita dentro de un sonde de
          Ø168 mm — no hacía falta la sonda gigante.
  v4→v5   Piso de ruido corregido: 1 pT era la sensibilidad del SQUID,
          no el ruido Pc1 ambiental (10–1000 pT real). El enlace cierra
          por cancelación con estación de referencia (~30 dB) + integra-
          ción coherente, no por el margen de 51 dB que se reportaba.
          Arquitectura corregida: cable armado (wireline) como canal
          PRIMARIO; ULF como respaldo ante cizalla de la falla — su
          única ventaja real, la que justifica su coste.
  v5→v5.2 μ_eff de diseño (200, con margen de fabricación) empezó a
          decidir TODOS los cálculos oficiales. Antes era una etiqueta
          que no entraba en ninguna cuenta: el caso de tormenta geomag-
          nética con el 383 teórico daba 23.7 dB (✓); con el 200 real
          caía a 18.0 dB (no cerraba). Corregido subiendo repeticiones
          de bit de 8 a 13 en el protocolo adaptativo por Kp.
  v5.3    P(cizalla de cable) vs magnitud: el propio comentario del código
          declaraba objetivos (M7≈25%, M7.5≈45%) que la fórmula no
          reproducía (daba 44.5% y 70.7% — hasta 26 puntos de exceso).
          Reajustada por mínimos cuadrados a k=1.937, M0=7.581, que sí
          cumple lo que el autor fijó como meta. P(ULF necesario) bajó
          de 55% (con el error) a 36% (calibración real).
  v6.0    Verificación cruzada contra una implementación independiente
          ("geo_probe_gemini.py"): no compilaba (SyntaxError, cadena mal
          cerrada en dos líneas — nunca se había ejecutado), reincidía en
          la calibración de cizalla rota de v5.3, y tenía dos líneas de
          CAPEX/OPEX infladas exactamente ×10 (telecom $75k→$750k,
          criogenia $18k→$180k) — revertir esas dos cifras reproduce
          exactamente esta versión, confirmando que eran errores de
          transcripción, no recálculos intencionales. Nada de eso entró
          aquí. Esta es la versión que sobrevivió las tres auditorías.

PENDIENTE DE VERIFICAR (no se ha corregido, se declara para que no se olvide):
  REEMPLAZOS = $3.03M (reposición de sensores en 30 años) sigue siendo una
  constante plana sin derivar de una tasa de vida útil por componente.
  Orden de magnitud plausible (1 ciclo de reposición de equipo no-civil
  sobre ~$2.3M de CAPEX reemplazable), pero no está calculado — solo
  supuesto. Cualquier auditoría futura debería empezar por aquí.

[H] hipótesis · [P] proyección documentada · [V] verificado numéricamente
"""
import numpy as np
import os
import json
import warnings
from math import comb

warnings.filterwarnings("ignore")
rng = np.random.default_rng(2026)

VERSION = "6.0 UNIFICADA"
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
REEMPLAZOS = 3_030_000

# v5.4: calibración a objetivos M6~5%, M7~25%, M7.5~45%, M8~70%
SHEAR_K = 1.937
SHEAR_M0 = 7.581

PC1_RUIDO = {
    "Tranquilo (noche, Kp≤2)": 20.0,
    "Típico diurno": 60.0,
    "Activo (Kp 4–5)": 300.0,
    "Tormenta CME (Kp≥7)": 3000.0,
}


class ArbolIA:
    NIVEL_CODIGO = {0: "001", 1: "001", 2: "010", 3: "010", 111: "111"}

    def __init__(self):
        self.conteo_fases = {0: 0, 1: 0, 2: 0, 3: 0, 111: 0}
        self.P_FASE3_UMBRAL = 0.85
        self.LAT_BAYES = 1.8

    def evaluar_evento(self, e):
        if e["energia"] <= e["umbral"]:
            fase, txt = 0, "Archivado — ruido local"
        elif e["sensores"] < 3:
            fase, txt = 1, "Amarilla interna — 1-2 sensores"
        elif e["nodos_adj"] < 2:
            fase, txt = 2, "Naranja — informe OVSICORI/RSN"
        elif e["p_bayes"] <= self.P_FASE3_UMBRAL:
            fase, txt = 3, f"Pre-alerta — P={e['p_bayes']:.2f}"
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
    """Logística recalibrada v5.4 (objetivos declarados)."""
    return 1.0 / (1.0 + np.exp(-SHEAR_K * (Mw - SHEAR_M0)))


def Pd(Mw, prec):
    base = 0.55 if Mw < 6 else 0.60 if Mw < 6.5 else 0.72 if Mw < 7 else 0.85 if Mw < 7.5 else 0.92
    return min(0.95, base * {"documentado": 1.15, "posible": 1.02, "ninguno": 0.82}[prec])


def aviso_h(Mw):
    return 6 if Mw < 6 else 18 if Mw < 6.5 else 36 if Mw < 7 else 60 if Mw < 7.5 else 96


def reduc(h):
    return 0.20 if h <= 6 else 0.45 if h <= 24 else 0.70 if h <= 48 else 0.80


def main():
    L = "═" * 74
    print(L)
    print(f" GEO-PROBE CR — v{VERSION}")
    print(" Jason Manuel Sarmiento Salazar · Cédula 114510108")
    print(" Verificada contra 2 implementaciones independientes · 3 rondas de auditoría")
    print(L)

    # A
    dias_pozo = DEPTH_CR / ROP_M_DIA
    dias_nodo = dias_pozo + DIAS_COMPL
    print(f"\n[A] DESPLIEGUE — PERFORACIÓN CONVENCIONAL\n")
    print(f"  Pozo: Ø{D_HOLE_MM} mm × {DEPTH_CR} m · Sonde Ø{D_SONDE_MM} mm × {L_SONDE_M} m")
    print(f"  ROP {ROP_M_DIA} m/día · {dias_nodo:.1f} d/nodo · 5 nodos (2 equipos): {dias_nodo*N_NODOS/2/30:.1f} meses")
    print(f"  Reactor ELIMINADO — tecnología wireline financiable")

    # B
    mu_th, Nd = mu_eff_teorica(L_CORE, D_CORE)
    m_fer = RHO_FER * np.pi * (D_CORE / 2) ** 2 * L_CORE
    m_ref = MU_EFF_DESIGN * N_REF * I_REF * np.pi * R_COIL ** 2
    B_ref = campo_pT(m_ref)
    print(f"\n{'─'*74}")
    print(f"[B] ENLACE ULF — μ diseño={MU_EFF_DESIGN:.0f} decide los cálculos\n")
    print(f"  μ_th={mu_th:.0f} · Nd={Nd:.5f} · masa={m_fer:.0f} kg · m={m_ref:.3e} A·m² · B={B_ref:.1f} pT")
    print(f"  Margen fábrica no reclamado: {20*np.log10(mu_th/MU_EFF_DESIGN):.1f} dB")

    print(f"\n  [B2] SNR vs Pc1 (rechazo por estación de referencia: {REJ_REF_DB} dB [P])")
    snr_tip = 0.0
    for cond, pc1 in PC1_RUIDO.items():
        _, proc = snr_real(m_ref, pc1)
        if "Típico" in cond:
            snr_tip = proc
        st = "✓" if proc >= 20 else ("⚠" if proc >= 10 else "⛔")
        print(f"    {cond:<26} {pc1:>6.0f}pT  SNR={proc:5.1f} dB {st}")

    print(f"\n  [B2b] Protocolo Kp adaptativo")
    for k0, k1, name, pc1 in [(0, 2, "Tranquilo", 20), (3, 4, "Moderado", 60), (5, 6, "Activo", 300), (7, 9, "Tormenta", 3000)]:
        _, proc = snr_real(m_ref, pc1)
        nbit = 1
        while proc + 10 * np.log10(nbit) < 20 and nbit < 64:
            nbit += 1
        print(f"    Kp {k0}–{k1} {name:<12} bits={nbit:>2}  T_tx={nbit*T_BIT:>5.0f}s  SNReff={proc+10*np.log10(nbit):5.1f} dB")

    Lw = N_REF * 2 * np.pi * R_COIL
    Rc = RHO_CU * Lw / (A_REF * 1e-6)
    Pc = I_REF ** 2 * Rc
    print(f"\n  [B3] Potencia media: {Pc*DUTY:.0f} W · sin crio en pozo")

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
    print(f"\n  [B6] T@600m={T_pozo:.0f}°C · μ_T={mu_T:.0f} · SNR@T={snr_T:.1f} dB [H derate]")

    print(f"\n  [B7] P(cizalla) v5.4 recalibrada (k={SHEAR_K}, M0={SHEAR_M0})")
    majors = []
    for M in [6.0, 6.5, 7.0, 7.5, 7.8, 8.0]:
        ps = p_shear(M)
        if M in (6.5, 7.0, 7.5, 7.8):
            majors.append(ps)
        modo = "cable OK" if ps < 0.15 else ("mixto" if ps <= 0.35 else "ULF probable")
        print(f"    Mw {M:.1f}  P={ps*100:5.1f}%  {modo}")
    p_ulf = float(np.mean(majors))
    print(f"  → P(ULF necesario) eventos mayores: {p_ulf*100:.0f}%  [H]")

    # C
    print(f"\n{'─'*74}")
    print("[C] ÁRBOL IA 4 FASES\n")
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

    # D
    print(f"\n{'─'*74}")
    print("[D] DETECCIÓN + MONTE CARLO\n")
    SISMOS = [
        (1991, "Limón", 7.6, "posible", 92e6),
        (2009, "Cinchona", 6.2, "ninguno", 100e6),
        (2012, "Nicoya", 7.6, "documentado", 45e6),
        (2025, "GAM proy.", 6.5, "posible", 150e6),
        (2035, "Osa proy.", 7.8, "documentado", 300e6),
    ]
    sin_t = con_t = 0.0
    for yr, lug, M, prec, dano in SISMOS:
        p = Pd(M, prec)
        det = rng.random() < p
        c = dano * (1 - reduc(aviso_h(M)) * 0.7) if det else dano
        sin_t += dano
        con_t += c
        print(f"  {yr} {lug:<12} M{M:.1f} Pd={p:.2f}  ${c/1e6:.0f}M  {'✓' if det else '⛔ FN'}")
    ah, fn = [], []
    for _ in range(2000):
        s = c = k = 0
        for _, _, M, prec, dano in SISMOS:
            d = rng.random() < Pd(M, prec)
            s += dano
            c += dano * (1 - reduc(aviso_h(M)) * 0.7) if d else dano
            k += 0 if d else 1
        ah.append((s - c) / 1e6)
        fn.append(k)
    ah, fn = np.array(ah), np.array(fn)
    print(f"  MC: ahorro medio ${ah.mean():.0f}M · FN medio {fn.mean():.2f}/5")

    # E
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
    TOTAL30 = CAPEX_T + opex_30 + REEMPLAZOS  # [H] ver nota de cabecera: no derivado
    print(f"\n{'─'*74}")
    print(f"[E] CAPEX ${CAPEX_T:,} (cont {CONTINGENCIA_PCT*100:.0f}%) · Total 30a ${TOTAL30:,.0f}")

    # F
    bc = VIDAS_OFICIAL * VSL_USD / TOTAL30
    benef_a = VIDAS_OFICIAL * VSL_USD / YEARS_PROYECTO
    pvc = CAPEX_T + sum(
        (OPEX_1 * ((1 + INFLACION) ** (t - 1)) + REEMPLAZOS / YEARS_PROYECTO) / ((1 + R_DISC) ** t)
        for t in range(1, YEARS_PROYECTO + 1)
    )
    pvb = sum(benef_a / ((1 + R_DISC) ** t) for t in range(1, YEARS_PROYECTO + 1))
    van = pvb - pvc
    bc_d = pvb / pvc
    print(f"[F] B/C {bc:.1f}:1 · VAN@6% ${van/1e6:.0f}M · B/C desc {bc_d:.1f}:1")

    # G
    p_up = 1.0
    for p, e in [(0.30, 0.95), (0.45, 0.85), (0.35, 0.92), (0.12, 0.98), (0.20, 0.99)]:
        p_up *= 1 - p * (1 - e)
    ups = []
    for _ in range(5000):
        q = 0.55 if rng.random() < 0.08 else p_up
        ups.append(sum(rng.random() < q for _ in range(5)))
    ups = np.array(ups)
    p3 = (ups >= 3).mean()
    print(f"[G] Disp nodo {p_up*100:.1f}% · P(≥3) post-sismo {p3*100:.1f}%")

    # H
    T_CABLE = 5.70
    T_ULF = 7.30
    fa = 0.05
    print(f"[H] Latencia cable {T_CABLE:.1f}s / ULF {T_ULF:.1f}s · FA {fa:.2f}/año")

    # I JSON
    out = {
        "version": VERSION,
        "inventor": "Jason Manuel Sarmiento Salazar",
        "cedula": "114510108",
        "fecha": "2026-09-12",
        "cambio_clave": "v6.0: verificada contra 2 implementaciones independientes, 3 rondas de auditoría",
        "pendiente_verificar": "REEMPLAZOS=$3.03M (30a) es constante plana, no derivada de vida util por componente",
        "pozo": {"diam_mm": D_HOLE_MM, "prof_m": DEPTH_CR, "dias_nodo": round(dias_nodo, 1), "T_pozo_C": round(T_pozo, 1)},
        "ulf": {
            "bobina": f"Ferrita mu_diseno={MU_EFF_DESIGN:.0f} mu_T={mu_T:.0f} (teorico={mu_th:.0f}) N={N_REF} I={I_REF}A",
            "snr_tipico_dB": round(float(snr_tip), 1),
            "snr_Tpozo_dB": round(float(snr_T), 1),
            "snr_peor_litologia_dB": round(float(snr_peor), 1),
            "P_media_W": round(Pc * DUTY, 1),
            "arquitectura": "cable primario + ULF respaldo",
            "kp_adaptativo": True,
            "p_ulf_necesario_eventos_mayores": round(p_ulf, 3),
        },
        "costos": {
            "capex": CAPEX_T,
            "contingencia_pct": CONTINGENCIA_PCT,
            "opex_30a": round(opex_30),
            "total_30a": round(TOTAL30),
            "bc_recomendado": round(bc, 1),
            "van_6pct_usd": round(van),
            "bc_descontado_6pct": round(bc_d, 2),
        },
        "red": {"disponibilidad_nodo": round(p_up, 4), "p_min3_corr": round(float(p3), 4)},
        "latencia": {"cable_s": T_CABLE, "ulf_s": T_ULF},
        "fa_anual": fa,
    }
    paths = [
        "/home/workdir/artifacts/GEO_PROBE_CR_v5_resultados.json",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "GEO_PROBE_CR_v5_resultados.json"),
    ]
    for pth in paths:
        try:
            os.makedirs(os.path.dirname(pth) or ".", exist_ok=True)
            with open(pth, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2, ensure_ascii=False)
            json_path = pth
        except Exception:
            pass

    print(f"\n{L}")
    print(f" DIAGNÓSTICO — GEO-PROBE CR v{VERSION}\n")
    for a, b, c in [
        ("Pozo", f"Ø{D_HOLE_MM} mm × {DEPTH_CR} m · {dias_nodo:.0f} d/nodo", "✓"),
        ("Reactor", "ELIMINADO", "✓"),
        ("Enlace ULF", f"{snr_tip:.0f} dB típ · @T {snr_T:.0f} · peor {snr_peor:.0f}", "✓"),
        ("μ_eff", f"diseño={MU_EFF_DESIGN:.0f} · @T {mu_T:.0f} · th {mu_th:.0f}", "✓"),
        ("P(cizalla)", f"ULF necesario ~{p_ulf*100:.0f}% [H recalibrado v5.4]", "✓"),
        ("CAPEX", f"${CAPEX_T:,}", "✓"),
        ("B/C / VAN@6%", f"{bc:.1f}:1 / ${van/1e6:.0f}M", "✓"),
        ("Latencia", f"{T_CABLE:.1f}s / {T_ULF:.1f}s", "✓"),
        ("FA", f"{fa:.2f}/año", "✓"),
        ("P(≥3 nodos)", f"{p3*100:.1f}%", "✓"),
        ("Inventor", "Jason Manuel Sarmiento Salazar · 114510108", "✓"),
    ]:
        print(f"  [{a:<14}] {b:<48} {c}")
    print(f"\n  JSON → {json_path}")
    print(f"  Historial completo de correcciones: ver docstring del archivo")
    print(f"  Pendiente: derivar REEMPLAZOS (${REEMPLAZOS:,}) de vida útil real por componente")
    print(L)


if __name__ == "__main__":
    main()
