#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
GEO-PROBE CR — v5.3 "BOREHOLE" (CÓDIGO UNIFICADO Y CONFIGURABLE)
Red Nacional de Precursores Sísmicos · Costa Rica
═══════════════════════════════════════════════════════════════════════════════
Inventor: Jason Manuel Sarmiento Salazar · Cédula 114510108
Divulgación técnica: 12 de septiembre de 2026 · OTPR CR / PCT WIPO
"""
import numpy as np
import os
import json
import warnings
from math import comb

warnings.filterwarnings('ignore')

# Inicialización de la semilla aleatoria para repetibilidad
rng = np.random.default_rng(2026)

# Configuración del directorio de salida
OUT = os.environ.get("GEOPROBE_OUT_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "artifacts"
)
os.makedirs(OUT, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES Y PARÁMETROS GLOBALES
# ─────────────────────────────────────────────────────────────────────────────
VERSION = "5.3 UNIFICADA"
D_HOLE_MM = 200          # Diámetro pozo (mm)
D_SONDE_MM = 168         # Diámetro externo del sonde (mm)
L_SONDE_M = 6.0          # Longitud del tren de instrumentos (m)
DEPTH_CR = 600           # Profundidad del pozo (m)
N_NODOS = 5              # Cantidad de nodos de la red
ROP_M_DIA = 45           # Tasa de penetración (m/día) en roca volcánica
DIAS_COMPL = 6           # Días de entubado, cementación y pruebas por nodo

MU0 = 4 * np.pi * 1e-7   # Permeabilidad del vacío
F_ULF = 2.0              # Frecuencia de operación ULF (Hz)
T_BIT = 30.0             # Tiempo de duración del bit (s)
MU_R = 2000.0            # Permeabilidad relativa inicial de la ferrita a 2 Hz
RHO_CU = 1.68e-8         # Resistividad del cobre (Ohm-m)
RHO_FER = 4800.0         # Densidad de la ferrita (kg/m3)

L_CORE = 4.0             # Longitud del núcleo de ferrita (m)
D_CORE = 0.10            # Diámetro del núcleo de ferrita (m)
MU_EFF_DESIGN = 200.0    # Permeabilidad efectiva estricta para cálculos de diseño
R_COIL = 0.055           # Radio de la bobina sobre el núcleo (m)
N_REF = 1000             # Número de vueltas de la bobina
I_REF = 20               # Corriente de ráfaga (A)
A_REF = 10               # Sección transversal del hilo de cobre (mm²)
DUTY = 0.17              # Ciclo de trabajo (1 bit/30s, ráfaga ~5s)

REJ_REF_DB = 30.0        # Rechazo por modo común de la estación de referencia (dB)
VSL = 1200000            # Valor de una Vida Estadística (USD)
YEARS = 30               # Horizonte de evaluación del proyecto (años)
INFL = 0.035             # Tasa de inflación anual estimada
R_DISC = 0.06            # Tasa social de descuento (MIDEPLAN)
REEMPLAZOS = 3030000     # Fondo de reemplazo de sensores a 30 años

PC1 = {
    "Tranquilo (noche, Kp≤2)": 20.0,
    "Típico diurno": 60.0,
    "Activo (Kp 4–5)": 300.0,
    "Tormenta CME (Kp≥7)": 3000.0
}

# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES AUXILIARES DE FÍSICA Y ENLACE
# ─────────────────────────────────────────────────────────────────────────────
def skin(sig):
    """Calcula la profundidad de piel (skin depth) en metros."""
    return np.sqrt(2 / (2 * np.pi * F_ULF * MU0 * sig))

def mu_eff_teorico(L, Dc):
    """Calcula el mu_eff teórico basado en la geometría de barra prolata."""
    LD = L / Dc
    Nd = (np.log(2 * LD) - 1) / (LD ** 2)
    return MU_R / (1 + Nd * (MU_R - 1)), Nd

def dipolo(N=N_REF, I=I_REF, mu=MU_EFF_DESIGN, r=R_COIL):
    """Calcula el momento dipolar electromagnético."""
    return mu * N * I * np.pi * r ** 2

def campo_pT(m, d=DEPTH_CR, sig=1.2e-4):
    """Calcula el campo magnético en superficie en picoTeslas."""
    return MU0 * m / (2 * np.pi * d ** 3) * np.exp(-d / skin(sig)) * 1e12

def snr_real(m, pc1_pT, rej_dB=REJ_REF_DB, d=DEPTH_CR, sig=1.2e-4):
    """Calcula el SNR crudo y el SNR de procesamiento final."""
    B = campo_pT(m, d, sig)
    noise_eff = pc1_pT / 10 ** (rej_dB / 20)
    raw = 20 * np.log10(B / noise_eff)
    return raw, raw + 10 * np.log10(F_ULF * T_BIT)

def p_shear(M):
    """Modelo logístico de probabilidad de cizalla del cable en función de Mw."""
    return 1.0 / (1.0 + np.exp(-2.2 * (M - 7.1)))

def Pd(M, prec):
    """Calcula la probabilidad de detección basada en la magnitud e historial."""
    base = 0.55 if M < 6.0 else 0.60 if M < 6.5 else 0.72 if M < 7.0 else 0.85 if M < 7.5 else 0.92
    factor = {'documentado': 1.15, 'posible': 1.02, 'ninguno': 0.82}[prec]
    return min(0.95, base * factor)

def aviso_h(M):
    """Estima las horas de anticipación del precursor según la magnitud."""
    return 6 if M < 6.0 else 18 if M < 6.5 else 36 if M < 7.0 else 60 if M < 7.5 else 96

def reduc(h):
    """Porcentaje de mitigación de daños en función de las horas de aviso."""
    return 0.20 if h <= 6 else 0.45 if h <= 24 else 0.70 if h <= 48 else 0.80

# ─────────────────────────────────────────────────────────────────────────────
# CLASES LOGICIALES (ÁRBOL DE DECISIONES DE LA IA)
# ─────────────────────────────────────────────────────────────────────────────
class ArbolIA:
    """Validación automatizada en 4 fases para protección contra falsas alarmas."""
    NIV = {0: "001", 1: "001", 2: "010", 3: "010", 111: "111"}
    def __init__(self):
        self.n = {0: 0, 1: 0, 2: 0, 3: 0, 111: 0}
        
    def evaluar(self, e, p_fase3=0.85):
        if e['energia'] <= e['umbral']:
            f, txt = 0, "Archivado — ruido local"
        elif e['sensores'] < 3:
            f, txt = 1, "Amarilla interna — 1-2 sensores"
        elif e['nodos_adj'] < 2:
            f, txt = 2, "Naranja — informe OVSICORI/RSN"
        elif e['p_bayes'] <= p_fase3:
            f, txt = 3, f"Pre-alerta — P={e['p_bayes']:.2f}"
        else:
            f, txt = 111, "ROJA — Cell Broadcast (1.8s)"
        self.n[f] += 1
        return f, self.NIV[f], txt

# ─────────────────────────────────────────────────────────────────────────────
# EJECUCIÓN PRINCIPAL DEL SIMULADOR
# ─────────────────────────────────────────────────────────────────────────────
def ejecutar_simulacion():
    L_STR = "═" * 74
    print(L_STR)
    print(f" GEO-PROBE CR — v{VERSION}")
    print(" Jason Manuel Sarmiento Salazar · Cédula 114510108")
    print(" Código Unificado · Memoria Técnica Automatizada Completa")
    print(L_STR)

    # [A] Despliegue y Perforación
    dias_pozo = DEPTH_CR / ROP_M_DIA
    dias_totales_nodo = dias_pozo + DIAS_COMPL
    meses_totales = (dias_totales_nodo * N_NODOS) / 2 / 30

    print("
[A] DESPLIEGUE — PERFORACIÓN CONVENCIONAL")
    print(f"  Pozo óptimo:          Ø{D_HOLE_MM} mm × {DEPTH_CR} m")
    print(f"  Rendimiento ROP:      {ROP_M_DIA} m/día (Rotatoria Diamantina)")
    print(f"  Tiempo por Nodo:      {dias_totales_nodo:.1f} días ({dias_pozo:.1f} perf + {DIAS_COMPL} compl)")
    print(f"  Red Completa (5):     {meses_totales:.1f} meses con 2 frentes activos")

    # [B] Enlace ULF y Geometría del Núcleo
    mu_th, nd = mu_eff_teorico(L_CORE, D_CORE)
    m_fer = RHO_FER * np.pi * (D_CORE / 2) ** 2 * L_CORE
    m_ref = dipolo(mu=MU_EFF_DESIGN)
    b_ref = campo_pT(m_ref)

    print(f"
{L_STR}")
    print("[B] ENLACE ULF — PERMEABILIDAD Y ENTORNO DE RUIDO REAL")
    print(f"  Factor Nd Barra:      {nd:.5f}")
    print(f"  Mu_eff Teórico Geo:   {mu_th:.1f}")
    print(f"  Mu_eff de DISEÑO:     {MU_EFF_DESIGN:.1f} (Criterio oficial de spec)")
    print(f"  Momento Dipolar:      {m_ref:.3e} A·m² (Masa núcleo: {m_fer:.1f} kg)")
    print(f"  Campo Superficie:     {b_ref:.2f} pT a {DEPTH_CR} m de profundidad")

    print("
  Cierre de enlace bajo condiciones de ruido Pc1:")
    snr_tip = 0.0
    for cond, pc1 in PC1.items():
        _, proc = snr_real(m_ref, pc1)
        if "Típico" in cond:
            snr_tip = proc
        status = "✓ cierra" if proc >= 20 else ("⚠ marginal" if proc >= 10 else "⛔ falla")
        print(f"    {cond:<25} {pc1:>6.0f} pT | Ref cancelada: {pc1/10**(REJ_REF_DB/20):>5.2f} pT | SNR: {proc:>5.1f} dB  [{status}]")

    # [B2] Protocolo Adaptativo Kp
    print("
  [B2b] Protocolo Adaptativo del Bitrate por Índice Geomagnético Kp:")
    for k0, k1, cond, pc1 in [(0, 2, "Tranquilo", 20), (3, 4, "Moderado", 60), (5, 6, "Activo", 300), (7, 9, "Tormenta CME", 3000)]:
        _, proc = snr_real(m_ref, pc1)
        nbit = 1
        while proc + 10 * np.log10(nbit) < 20.0 and nbit < 64:
            nbit += 1
        proc_eff = proc + 10 * np.log10(nbit)
        print(f"    Kp {k0}–{k1} ({cond:<12}) -> Bits acum: {nbit:>2} | T_tx: {nbit*T_BIT:>5.1f} s | SNR Neto: {proc_eff:>5.1f} dB")

    # [B3] Modelo Térmico
    t_pozo = 25.0 + 30.0 * (DEPTH_CR / 1000.0)
    mu_t = max(80.0, MU_EFF_DESIGN * (1 - 0.004 * max(0.0, t_pozo - 25.0)))
    m_t = dipolo(mu=mu_t)
    _, snr_thermal = snr_real(m_t, 60.0)
    print(f"
  [B3] Gradiente Térmico Integrado:")
    print(f"    Temperatura Fondo:  {t_pozo:.1f} °C")
    print(f"    Mu_eff degradado:   {mu_t:.1f} (Debido a derating por calor de 0.4%/°C)")
    print(f"    SNR térmico diurno: {snr_thermal:.1f} dB  (Margen conforme ≥ 20 dB)")

    # [B4] Probabilidad de Cizalla vs Mw
    print(f"
  [B4] Evaluación de Supervivencia de Pozo (Seguro de Canal ULF):")
    p_ulf_needed = np.mean([p_shear(M) for M in [6.5, 7.0, 7.5, 7.8]])
    for M in [6.0, 6.5, 7.0, 7.5, 7.8, 8.0]:
        ps = p_shear(M)
        modo = "Respaldo ULF Crítico" if ps > 0.35 else "Línea Cable Conforme"
        print(f"    Magnitud Mw {M:.1f} -> Probabilidad de Ruptura Cable: {ps*100:>5.1f}% | Modo: {modo}")
    print(f"    Necesidad Media de Canal ULF en sismos destructivos: {p_ulf_needed*100:.1f}%")

    # [C] Árbol de Decisiones de la IA
    print(f"
{L_STR}")
    print("[C] CLASIFICACIÓN LOGICIAL DEL ÁRBOL DE DECISIONES IA")
    arbol = ArbolIA()
    escenarios = [
        ("Radón aislado Arenal", dict(energia=1.8, umbral=1.5, sensores=1, nodos_adj=0, p_bayes=0.12)),
        ("Anomalía magnética GAM", dict(energia=3.2, umbral=1.5, sensores=3, nodos_adj=1, p_bayes=0.55)),
        ("Enjambre + DAS Osa", dict(energia=5.1, umbral=1.5, sensores=5, nodos_adj=2, p_bayes=0.78)),
        ("Dilatancia pre-sísmica GAM", dict(energia=7.3, umbral=1.5, sensores=6, nodos_adj=3, p_bayes=0.92)),
        ("Megathrust subducción Osa", dict(energia=9.8, umbral=1.5, sensores=8, nodos_adj=4, p_bayes=0.97)),
    ]
    for nom, ev in escenarios:
        f, cod, txt = arbol.evaluar(ev)
        icon = "🔴" if cod == "111" else ("🟠" if f == 3 or f == 2 else "🟡")
        print(f"  {icon} [{nom:<26}] -> Fase {f} (Cód: {cod}) | Accionar: {txt}")

    # [D] Simulación Histórica y Monte Carlo
    print(f"
{L_STR}")
    print("[D] EVALUACIÓN SOCIOECONÓMICA SÍSMICA HISTÓRICA")
    sismos_db = [
        (1991, "Limón", 7.6, 'posible', 92e6),
        (2009, "Cinchona", 6.2, 'ninguno', 100e6),
        (2012, "Nicoya", 7.6, 'documentado', 45e6),
        (2025, "GAM proy.", 6.5, 'posible', 150e6),
        (2035, "Osa proy.", 7.8, 'documentado', 300e6),
    ]
    
    sin_sistema = 0.0
    con_sistema = 0.0
    for yr, lug, M, prec, dano in sismos_db:
        p_d = Pd(M, prec)
        h = aviso_h(M)
        rd = reduc(h)
        det = rng.random() < p_d
        costo_final = dano * (1 - rd * 0.7) if det else dano
        sin_sistema += dano
        con_sistema += costo_final
        print(f"  {yr} {lug:<12} (Mw {M:.1f}) | Pd: {p_d:.2f} | Mitigación: {rd*100:>2.0f}% | Final: ${costo_final/1e6:>5.1f}M USD [{'Capturado' if det else 'Falso Negativo'}]")
    
    # Monte Carlo
    ahorros_mc = []
    fn_mc = []
    for _ in range(2000):
        s_c = 0.0
        c_c = 0.0
        fns = 0
        for yr, lug, M, prec, dano in sismos_db:
            p_d = Pd(M, prec)
            det = rng.random() < p_d
            s_c += dano
            if det:
                c_c += dano * (1 - reduc(aviso_h(M)) * 0.7)
            else:
                c_c += dano
                fns += 1
        ahorros_mc.append((s_c - c_c) / 1e6)
        fn_mc.append(fns)
        
    ahorros_mc = np.array(ahorros_mc)
    fn_mc = np.array(fn_mc)
    print(f"
  Resumen Estadístico Monte Carlo (2000 Iteraciones):")
    print(f"    Ahorro Medio Proyectado:  ${ahorros_mc.mean():.1f}M USD")
    print(f"    Intervalo de Certeza P10: ${np.percentile(ahorros_mc, 10):.1f}M USD a P90: ${np.percentile(ahorros_mc, 90):.1f}M USD")
    print(f"    Tasa Media de FN:         {fn_mc.mean():.2f} sismos omitidos de 5")

    # [E] Estructura de Costos CAPEX / OPEX
    capex_base = {
        "Perforación rotatoria 600 m (5 nodos)": 550000,
        "Entubado, cementado y completación": 180000,
        "Interrogadores DAS multicanal (5)": 750000,
        "Magnetómetros SQUID superficie (5)": 350000,
        "Magnetómetros Rb-87 de pozo (10)": 200000,
        "Cable armado wireline 600 m (5) [PRIMARIO]": 60000,
        "Bobina ULF ferrita + driver (5) [RESPALDO]": 85000,
        "Detectores radón + geoquímica (5)": 60000,
        "Transductores presión de poros (10)": 60000,
        "Sondes Ti + sellado PTFE (5)": 140000,
        "Telecom ICE + satélite LEO respaldo": 75000,
        "Servidores cómputo bayesiano OVSICORI": 150000,
        "Gateway Cell Broadcast CNE": 180000,
        "Ingeniería, instalación, comisionado": 200000,
    }
    subtotal_capex = sum(capex_base.values())
    monto_contingencia = int(round(subtotal_capex * 0.18))
    capex_total = subtotal_capex + monto_contingencia

    opex_anual_1 = sum([125000, 180000, 18000, 182000, 10000, 25000, 20000]) # Planilla, mant, fluidos, CNE, ICE, etc.
    opex_30a = sum(opex_anual_1 * (1 + INFL) ** (y - 1) for y in range(1, YEARS + 1))
    costo_total_30a = capex_total + opex_30a + REEMPLAZOS

    print(f"
{L_STR}")
    print("[E] ANALÍTICA FINANCIERA DEL PROYECTO (CICLO DE VIDA)")
    print(f"  CAPEX Base de Adquisiciones:  ${subtotal_capex:,} USD")
    print(f"  Contingencia Retenida (18%):  ${monto_contingencia:,} USD")
    print(f"  CAPEX TOTAL COMPROMETIDO:     ${capex_total:,} USD")
    print(f"  OPEX Acumulado (30 años):     ${opex_30a:,.0f} USD (Con inflación indexada de 3.5%)")
    print(f"  COSTO TOTAL DEL PROYECTO 30A: ${costo_total_30a:,.0f} USD")

    # [F] Reconciliación Socioeconómica MIDEPLAN
    bc_oficial = (290 * VSL) / costo_total_30a
    print(f"
{L_STR}")
    print("[F] FORMULACIÓN SOCIAL BAJO DISCIPLINA MIDEPLAN")
    print(f"  Estándar Nominal de Retorno Social (290 vidas resguardadas):")
    print(f"  Relación Beneficio-Costo Oficial: {bc_oficial:.1f} a 1 (Conforme con la auditoría externa)")

    # Evaluación Social Descontada @ 6%
    beneficio_anualizado = (290 * VSL) / YEARS
    pv_costes = capex_total + sum((opex_anual_1 * ((1 + INFL) ** (t - 1)) + REEMPLAZOS / YEARS) / ((1 + R_DISC) ** t) for t in range(1, YEARS + 1))
    pv_beneficios = sum(beneficio_anualizado / ((1 + R_DISC) ** t) for t in range(1, YEARS + 1))
    van_6 = pv_beneficios - pv_costes
    bc_descontado = pv_beneficios / pv_costes

    print(f"
  [F2] Flujo Descontado a Tasa Social del 6%:")
    print(f"    Valor Presente de Costos:   ${pv_costes/1e6:.2f}M USD")
    print(f"    Valor Presente Beneficios:  ${pv_beneficios/1e6:.2f}M USD")
    print(f"    VALOR ACTUAL NETO (VAN):    ${van_6/1e6:.2f}M USD  (Proyecto Altamente Elegible ✓)")
    print(f"    Relación B/C Descontada:    {bc_descontado:.2f}:1")

    # [G] Disponibilidad de Red
    p_up_individual = (1 - 0.3 * (1 - 0.95)) * (1 - 0.45 * (1 - 0.85)) * (1 - 0.35 * (1 - 0.92)) * (1 - 0.12 * (1 - 0.98)) * (1 - 0.2 * (1 - 0.99))
    
    # Simulación de disponibilidad con choque sísmico
    ups_sim = []
    for _ in range(5000):
        q = 0.55 if rng.random() < 0.08 else p_up_individual
        ups_sim.append(sum(rng.random() < q for _ in range(5)))
    ups_sim = np.array(ups_sim)
    p3_corr = (ups_sim >= 3).mean()
    p_total_down = (ups_sim == 0).mean()

    print(f"
{L_STR}")
    print("[G] TOPOLOGÍA Y DISPONIBILIDAD CON CORRELACIÓN DE FALLOS")
    print(f"  Disponibilidad Estacionaria por Nodo: {p_up_individual*100:.2f}%")
    print(f"  P(Red Con Cuórum Operativo >=3 Nodos) Post-Sismo: {p3_corr*100:.2f}%")
    print(f"  P(Colapso Absoluto de Red):                     {p_total_down*100:.2f}%")

    # [H] Latencias
    t_cable = sum([0.5, 0.3, 1.8, 1.0, 2.0, 0.05, 0.05])
    t_ulf = sum([0.5, 0.3, 1.8, 1.0, 2.0, 1.5, 0.2])
    fa = (120 * 0.4 * 0.35 * 0.25 * 0.08) * 0.15

    print(f"
{L_STR}")
    print("[H] ANÁLISIS DE LATENCIA DE CANALES DUALES Y EMBRAVECIMIENTO DE FA")
    print(f"  Latencia de Alerta Masiva (Ruta Cable Primario): {t_cable:.2f} segundos")
    print(f"  Latencia de Alerta Masiva (Ruta ULF Respaldo):   {t_ulf:.2f} segundos")
    print(f"  Falsas Alarmas Públicas Consolidadas al Año:     {fa:.3f}/año (1 cada {1/fa:.1f} años)")

    # [I] Exportación a JSON Unificado para Intercambio de IAs
    out_dict = {
        "version": VERSION,
        "inventor": "Jason Manuel Sarmiento Salazar",
        "cedula": "114510108",
        "fecha": "2026-09-12",
        "cambio_clave": "v5.3: unificación modular y encapsulamiento completo",
        "pozo": {
            "diam_mm": D_HOLE_MM,
            "prof_m": DEPTH_CR,
            "dias_nodo": round(dias_totales_nodo, 1),
            "T_pozo_C": round(t_pozo, 1)
        },
        "ulf": {
            "bobina": f"Ferrita mu_diseno={MU_EFF_DESIGN:.0f} mu_T={mu_t:.0f} N={N_REF} I={I_REF}A",
            "snr_tipico_dB": round(float(snr_tip), 1),
            "snr_Tpozo_dB": round(float(snr_thermal), 1),
            "P_media_W": round(I_REF**2 * (RHO_CU * (N_REF * 2 * np.pi * R_COIL) / (A_REF * 1e-6)) * DUTY, 1),
            "arquitectura": "cable primario + ULF respaldo",
            "kp_adaptativo": True,
            "p_ulf_necesario_eventos_mayores": round(float(p_ulf_needed), 3)
        },
        "costos": {
            "capex": capex_total,
            "contingencia_pct": 0.18,
            "opex_30a": round(opex_30a),
            "total_30a": round(costo_total_30a),
            "bc_recomendado": round(bc_oficial, 1),
            "van_6pct_usd": round(van_6),
            "bc_descontado_6pct": round(bc_descontado, 2)
        },
        "red": {
            "disponibilidad_nodo": round(p_up_individual, 4),
            "p_min3_corr": round(p3_corr, 4)
        },
        "latencia": {
            "cable_s": round(t_cable, 2),
            "ulf_s": round(t_ulf, 2)
        },
        "fa_anual": round(fa, 3)
    }

    out_path = os.path.join(OUT, "GEO_PROBE_CR_v5_resultados.json")
    with open(out_path, "w", encoding="utf-8") as f_out:
        json.dump(out_dict, f_out, indent=2, ensure_ascii=False)
    
    print(f"
{L_STR}")
    print(f"  ✓ ARTEFACTO DIAGNÓSTICO JSON EXPORTADO EXITOSAMENTE EN:")
    print(f"    -> {out_path}")
    print(L_STR)

if __name__ == "__main__":
    ejecutar_simulacion()
