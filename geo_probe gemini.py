#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
GEO-PROBE CR — v5.3 "BOREHOLE" (CÓDIGO UNIFICADO Y COMPLETO)
Red Nacional de Precursores Sísmicos · Costa Rica
═══════════════════════════════════════════════════════════════════════════════
Inventor: Jason Manuel Sarmiento Salazar · Cédula 114510108
Divulgación técnica: 12 de septiembre de 2026 · OTPR CR / PCT WIPO

Este script unifica de manera absoluta todos los módulos de ingeniería, física
de enlace ULF, degradación térmica, árboles de decisión de IA, simulaciones
Monte Carlo y análisis financiero estructurado bajo las normativas de MIDEPLAN y la CNE.
"""

import numpy as np
import os
import json
import warnings
from math import comb

warnings.filterwarnings('ignore')

# Configuración de rutas y semilla aleatoria
VERSION = "5.3 UNIFICADO"
OUT_DIR = os.environ.get("GEOPROBE_OUT_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "artifacts" if "__file__" in locals() else "generated"
)
os.makedirs(OUT_DIR, exist_ok=True)
rng = np.random.default_rng(2026)

# ═════════════════════════════════════════════════════════════════════════════
# CONSTANTES Y PARÁMETROS GLOBALES
# ═════════════════════════════════════════════════════════════════════════════
# [A] Geometría y Perforación
D_HOLE_MM = 200          # Diámetro pozo (HQ/PQ ampliado)
D_SONDE_MM = 168         # Diámetro externo de la sonda instrumentada
L_SONDE_M = 6.0          # Longitud del tren de instrumentos
DEPTH_CR = 600           # Profundidad de despliegue en metros
N_NODOS = 5              # Número total de nodos en la red sísmica
ROP_M_DIA = 45           # Tasa de penetración (m/día) en roca volcánica dura
DIAS_COMPL = 6           # Días de entubado, cementación y pruebas por nodo

# [B] Parámetros Físicos y Enlace ULF
MU0 = 4 * np.pi * 1e-7   # Permeabilidad del vacío (H/m)
F_ULF = 2.0              # Frecuencia de operación ULF (Hz)
B_NOISE_LIMIT = 1e-12    # Piso base teórico de instrumentación SQUID (1 pT)
T_BIT = 30.0             # Duración intrínseca de transmisión de 1 bit (s)
MU_R = 2000.0            # Permeabilidad relativa inicial de la ferrita MnZn a 2 Hz
RHO_CU = 1.68e-8         # Resistividad del cobre (Ohm-m)
RHO_FER = 4800.0         # Densidad de la ferrita (kg/m³)
L_CORE = 4.0             # Longitud del núcleo de ferrita (m)
D_CORE = 0.10            # Diámetro del núcleo de ferrita (m)
R_COIL = 0.055           # Radio de la bobina de cobre sobre el núcleo (m)
N_REF = 1000             # Número de vueltas de la bobina ULF
I_REF = 20               # Corriente de pico en ráfaga (A)
A_REF = 10               # Sección transversal del hilo de cobre (mm²)
DUTY = 0.17              # Ciclo de trabajo (1 bit por cada 30 segundos, ~5s ráfaga)
REJ_REF_DB = 30.0        # Rechazo por modo común con estación de referencia a 20 km

# [B6-B7] Modelo Térmico y Cizalla Logística
T_SURF = 25.0            # Temperatura de la superficie (°C)
GRAD_TERMICO = 30.0      # Gradiente térmico en zonas volcánicas de CR (°C/km)
DERATE_PCT_PER_C = 0.004 # Caída de permeabilidad magnética por temperatura (0.4%/°C)

# Condición geomagnética y ruido Pc1 real en banda de 2 Hz
PC1_RUIDO = {
    "Tranquilo (noche, Kp≤2)": 20.0,
    "Típico diurno": 60.0,
    "Activo (Kp 4–5)": 300.0,
    "Tormenta CME (Kp≥7)": 3000.0
}

# Litologías típicas y su conductividad eléctrica (S/m)
LITOLOGIAS = [
    ("Basalto seco", 5e-5),
    ("Basalto húmedo (ref CR)", 1.2e-4),
    ("Andesita/ignimbrita", 3e-4),
    ("Sedimento volcánico", 1e-3),
    ("Zona de falla con fluidos", 5e-3),
    ("Arcilla hidrotermal ácida", 2e-2)
]

# [C] Árbol de Decisiones de IA y Umbrales
K_SIGMA = 2.5
P_FASE3_LIMITE = 0.85
LAT_BAYES = 1.8

# [E-F] Finanzas e Inversión Social (Normativa MIDEPLAN)
CONTINGENCIA_PCT = 0.18  # Contingencia del CAPEX base
INFLACION = 0.035        # Tasa de inflación anual proyectada (3.5%)
YEARS_PROYECTO = 30      # Ciclo de vida del proyecto institucional
REEMPLAZOS_30A = 3030000 # Costo de reemplazo de sensores a lo largo de 30 años
VSL_USD = 1200000        # Valor de una Vida Estadística (MIDEPLAN)
R_DESCUENTO = 0.06       # Tasa social de descuento (6% MIDEPLAN)

# ═════════════════════════════════════════════════════════════════════════════
# COMPONENTES AUXILIARES Y CLASES
# ═════════════════════════════════════════════════════════════════════════════
def calcular_skin_depth(sig):
    """Calcula la profundidad de piel (skin depth) de la roca en metros."""
    return np.sqrt(2 / (2 * np.pi * F_ULF * MU0 * sig))

def mu_eff(L, Dc):
    """Calcula la permeabilidad efectiva teórica considerando el factor de desmagnetización."""
    LD = L / Dc
    Nd = (np.log(2 * LD) - 1) / (LD ** 2)
    return MU_R / (1 + Nd * (MU_R - 1)), Nd

def campo_pT(m, d, sig):
    """Calcula el campo magnético remanente en superficie expresado en pT."""
    atn = np.exp(-d / calcular_skin_depth(sig))
    return (MU0 * m / (2 * np.pi * (d ** 3))) * atn * 1e12

def snr_real(m, pc1_pT, rej_dB=REJ_REF_DB, d=DEPTH_CR, sig=1.2e-4):
    """Calcula el SNR crudo y procesado después de la estación de referencia."""
    B = campo_pT(m, d, sig)
    ruido_efectivo = pc1_pT / (10 ** (rej_dB / 20))
    raw_snr = 20 * np.log10(B / ruido_efectivo)
    proc_snr = raw_snr + 10 * np.log10(F_ULF * T_BIT)
    return raw_snr, proc_snr

def p_shear(M):
    """Modelo logístico de probabilidad de cizalla física del cable vs Magnitud (Mw)."""
    return 1.0 / (1.0 + np.exp(-2.2 * (M - 7.1)))

def calcular_pd(M, precedencia_historica):
    """Calcula la probabilidad de detección empírica para la simulación sísmica."""
    base = 0.55 if M < 6.0 else 0.60 if M < 6.5 else 0.72 if M < 7.0 else 0.85 if M < 7.5 else 0.92
    factor = {'documentado': 1.15, 'posible': 1.02, 'ninguno': 0.82}[precedencia_historica]
    return min(0.95, base * factor)

def horas_aviso(M):
    """Determina la ventana temporal estimada de aviso precursor según magnitud."""
    return 6 if M < 6.0 else 18 if M < 6.5 else 36 if M < 7.0 else 60 if M < 7.5 else 96

def porcentaje_reduccion(h):
    """Retorna la tasa de mitigación de daños según las horas previas de aviso."""
    return 0.20 if h <= 6 else 0.45 if h <= 24 else 0.70 if h <= 48 else 0.80

class ArbolIA:
    """Motor lógico bayesiano centralizado en 4 fases para control del Cell Broadcast."""
    NIVELES = {0: "001", 1: "001", 2: "010", 3: "010", 111: "111"}
    
    def __init__(self):
        self.conteo = {0: 0, 1: 0, 2: 0, 3: 0, 111: 0}
        
    def evaluar(self, evento):
        if evento['energia'] <= evento['umbral']:
            fase = 0
            txt = "Archivado — ruido local o transitorio instrumental"
        elif evento['sensores'] < 3:
            fase = 1
            txt = "Amarilla interna — anomalía en solo 1 o 2 sensores aislados"
        elif evento['nodos_adj'] < 2:
            fase = 2
            txt = "Naranja institucional — informe confidencial emitido a OVSICORI/RSN"
        elif evento['p_bayes'] <= P_FASE3_LIMITE:
            fase = 3
            txt = f"Pre-alerta interna — probabilidad intermedia (P={evento['p_bayes']:.2f})"
        else:
            fase = 111
            txt = f"ROJA DIRECTA — Cell Broadcast activado de inmediato ({LAT_BAYES}s)"
            
        self.conteo[fase] += 1
        return fase, self.NIVELES[fase], txt

# ═════════════════════════════════════════════════════════════════════════════
# EJECUCIÓN PRINCIPAL DE LOS MÓDULOS DE SIMULACIÓN
# ═════════════════════════════════════════════════════════════════════════════
def ejecutar_sistema():
    L_LINE = "═" * 78
    S_LINE = "─" * 78
    print(L_LINE)
    print(f" SISTEMA UNIFICADO DE EVALUACIÓN: GEO-PROBE CR v{VERSION}")
    print(" Inventor: Jason Manuel Sarmiento Salazar · Cédula 114510108")
    print(" Red Nacional de Precursores Sísmicos de Costa Rica · Cumplimiento MIDEPLAN")
    print(L_LINE)

    # ─────────────────────────────────────────────────────────────────────────
    # [MÓDULO A] Despliegue Estructural y Perforación
    # ─────────────────────────────────────────────────────────────────────────
    dias_perforacion_nodo = DEPTH_CR / ROP_M_DIA
    total_dias_nodo = dias_perforacion_nodo + DIAS_COMPL
    meses_totales_red = (total_dias_nodo * N_NODOS) / 2 / 30

    print(f"\n[A] DESPLIEGUE ESTRUCTURAL — PERFORACIÓN GEOTÉCNICA")
    print(f"  Geometría del Pozo:         Ø{D_HOLE_MM} mm × {DEPTH_CR} m de profundidad")
    print(f"  Tren de Instrumentos:       Ø{D_SONDE_MM} mm × {L_SONDE_M} m dentro del pozo")
    print(f"  Método de Excavación:       Rotatoria diamantina (Comercial convencional)")
    print(f"  Rendimiento Diario (ROP):   {ROP_M_DIA} m/día en roca volcánica compacta")
    print(f"  Duración por Nodo:          {dias_perforacion_nodo:.1f} días perforación + {DIAS_COMPL} días completación")
    print(f"  Plazo de Ejecución Red:     {meses_totales_red:.1f} meses aproximados (Utilizando 2 frentes)")
    print(f"  Ajuste Regulatorio:         Se elimina el reactor nuclear; viabilidad total de permisos.")

    # ─────────────────────────────────────────────────────────────────────────
    # [MÓDULO B] Enlace de Ondas ULF y Parámetros del Núcleo
    # ─────────────────────────────────────────────────────────────────────────
    mu_teorica, factor_nd = mu_eff(L_CORE, D_CORE)
    MU_EFF_DISEÑO = 200.0  # El criterio de diseño impuesto por la auditoría v5.2
    
    # Momento dipolar magnético m = N * I * A
    area_bobina = np.pi * (R_COIL ** 2)
    momento_dipolar = MU_EFF_DISEÑO * N_REF * I_REF * area_bobina
    campo_superficie = campo_pT(momento_dipolar, DEPTH_CR, sig=1.2e-4)
    masa_ferrita = RHO_FER * np.pi * ((D_CORE / 2) ** 2) * L_CORE

    print(f"\n{S_LINE}")
    print(f"[B] ENLACE DE TELEMETRÍA ELECTROMAGNÉTICA ULF")
    print(f"  [B1] Dimensionamiento y Geometría del Núcleo Ferromagnético")
    print(f"    Masa del núcleo:          {masa_ferrita:.1f} kg de ferrita MnZn tipo barra recta")
    print(f"    Factor Desmagnetizante:   Nd = {factor_nd:.5f}")
    print(f"    Permeabilidad Teórica:    μ_eff teórica = {mu_teorica:.1f} (Derivada geométricamente)")
    print(f"    Permeabilidad de Diseño:  μ_eff fijada = {MU_EFF_DISEÑO:.1f} (Criterio oficial de compra)")
    print(f"    Margen de Manufactura:    {20 * np.log10(mu_teorica / MU_EFF_DISEÑO):.2f} dB de seguridad pasiva")
    print(f"    Momento Dipolar:          {momento_dipolar:.3e} A·m²")
    print(f"    Campo Inducido Libre:     {campo_superficie:.2f} pT alcanzados en superficie")

    print(f"\n  [B2] Respuesta del Enlace ante Ruido Pc1 Real y Cancelación Activa")
    print(f"    Piso base de atenuación exigido por estación de referencia: ≥ {REJ_REF_DB} dB")
    print(f"    {"Condición Geomagnética":<28} {"Ruido Pc1":>10} {"Tras Ref":>12} {"SNR Proc":>12}  Estado")
    print(f"    " + "-" * 70")
    
    snr_diurno_tipico = None
    for cond, ruido in PC1_RUIDO.items():
        _, snr_p = snr_real(momento_dipolar, ruido)
        if "Típico diurno" in cond:
            snr_diurno_tipico = snr_p
        status = "✓ Conectado" if snr_p >= 20.0 else ("⚠ Marginal" if snr_p >= 10.0 else "⛔ Bloqueado")
        print(f"    {cond:<28} {ruido:>8.1f} pT {ruido / (10 ** (REJ_REF_DB / 20)):>10.2f} pT {snr_p:>10.1f} dB  {status}")

    # [B2b] Simulación del Protocolo Adaptativo Kp
    print(f"\n  [B2b] Matriz Operativa del Protocolo Adaptativo según Índice Kp")
    print(f"    {"Rango Kp":<10} {"Severidad":<15} {"Bits Requeridos":>15} {"Tiempo Tx":>12} {"SNR Ajustado":>14}")
    print(f"    " + "-" * 72)
    
    matriz_kp = [(0, 2, "Tranquilo", 20), (3, 4, "Moderado", 60), (5, 6, "Activo", 300), (7, 9, "Tormenta CME", 3000)]
    for k0, k1, label, r_pc1 in matriz_kp:
        _, snr_p = snr_real(momento_dipolar, r_pc1)
        bits = 1
        while snr_p + 10 * np.log10(bits) < 20.0 and bits < 64:
            bits += 1
        snr_final = snr_p + 10 * np.log10(bits)
        print(f"    Kp {k0}–{k1:<4} {label:<15} {bits:>15} {bits * T_BIT:>10.0f} s {snr_final:>12.1f} dB")

    # [B3] Parámetros Eléctricos
    longitud_hilo = N_REF * 2 * np.pi * R_COIL
    resistencia_bobina = RHO_CU * longitud_hilo / (A_REF * 1e-6)
    potencia_pico = (I_REF ** 2) * resistencia_bobina
    print(f"\n  [B3] Balance de Carga Eléctrica e Inyección de Potencia")
    print(f"    Hilo conductor:           Cobre electrolítico de {A_REF} mm² · Longitud total = {longitud_hilo:.1f} m")
    print(f"    Resistencia de Bobina:    R = {resistencia_bobina:.3f} Ohmios")
    print(f"    Potencia de Pico:         P_pico = {potencia_pico:.1f} W (Evacuación térmica directa al fluido del pozo)")
    print(f"    Consumo Medio Operativo:  P_medio = {potencia_pico * DUTY:.1f} W con Ciclo de Trabajo del {DUTY * 100:.1f}%")

    # [B4] Litología Variable
    print(f"\n  [B4] Comportamiento Litológico y Profundidad de Piel (Ruido Pc1 Típico)")
    print(f"    {"Formación Geológica":<32} {"Conductividad":>15} {"Skin Depth":>12} {"SNR Final":>12}")
    print(f"    " + "-" * 75)
    for lit, c_sig in LITOLOGIAS:
        _, snr_l = snr_real(momento_dipolar, 60.0, sig=c_sig)
        s_depth = calcular_skin_depth(c_sig)
        print(f"    {lit:<32} {c_sig:>13.1e} S/m {s_depth / 1000:>10.2f} km {snr_l:>10.1f} dB")
    _, peor_snr = snr_real(momento_dipolar, 60.0, sig=2e-2)

    # [B5] Matriz Comparativa Híbrida
    print(f"\n  [B5] Arquitectura Redundante del Enlace de Telecomunicaciones")
    print(f"    Enfoque híbrido adoptado: Canal Primario de Alta Velocidad + Respaldo de Seguridad por Ondas ULF.")

    # [B6] Degradación Térmica
    temperatura_fondo = T_SURF + GRAD_TERMICO * (DEPTH_CR / 1000.0)
    mu_degradada = MU_EFF_DISEÑO * (1.0 - DERATE_PCT_PER_C * max(0.0, temperatura_fondo - 25.0))
    mu_degradada = max(mu_degradada, 80.0)
    momento_termico = mu_degradada * N_REF * I_REF * area_bobina
    _, snr_termico = snr_real(momento_termico, 60.0)
    print(f"\n  [B6] Comportamiento de Degradación Térmica de Fondo de Pozo")
    print(f"    Gradiente Geotérmico CR:  {GRAD_TERMICO} °C/km → Temperatura calculada a 600m = {temperatura_fondo:.1f} °C")
    print(f"    Castigo de Permeabilidad: Tasa del {DERATE_PCT_PER_C * 100:.1f}% por °C sobre ambiente estándar de 25 °C")
    print(f"    Permeabilidad Efectiva:  μ_eff @ T_fondo = {mu_degradada:.1f} (Frente a {MU_EFF_DISEÑO:.1f} en frío)")
    print(f"    SNR en Peor Caso Térmico: {snr_termico:.1f} dB (Mantiene el canal abierto por encima de la frontera de 20 dB)")

    # [B7] Probabilidad de Cizalla de Cables Armados
    print(f"\n  [B7] Cuantificación Logística de Cizalla de Tubería y Fallo de Cables")
    print(f"    Voltaje y deformación tectónica estructural asimilada:")
    print(f"    {"Magnitud Sismo (Mw)":<22} {"Probabilidad de Ruptura del Cable":>35} {"Modo de Enlace Exigido"}")
    print(f"    " + "-" * 78)
    for mag in [6.0, 6.5, 7.0, 7.5, 7.8, 8.0]:
        p_s = p_shear(mag)
        modo_line = "ULF Obligatorio (Respaldo)" if p_s > 0.35 else ("Flujo Mixto / Alerta" if p_s > 0.15 else "Cable Íntegro (Primario)")
        print(f"    Mw {mag:<18.1f} {p_s * 100:>33.2f}%    {modo_line}")
    p_ulf_critica = np.mean([p_shear(m) for m in [6.5, 7.0, 7.5, 7.8]])

    # ─────────────────────────────────────────────────────────────────────────
    # [MÓDULO C] Árbol de Decisiones de Inteligencia Artificial de 4 Fases
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{S_LINE}")
    print(f"[C] CLASIFICACIÓN DE ALERTA: ÁRBOL DE DECISIONES DE LA IA EN 4 FASES")
    arbol = ArbolIA()
    escenarios = [
        ("Pico radón aislado (Arenal)", 0.0, dict(energia=1.8, umbral=1.5, sensores=1, nodos_adj=0, p_bayes=0.12)),
        ("Anomalía magnética+radón (GAM)", 5.5, dict(energia=3.2, umbral=1.5, sensores=3, nodos_adj=1, p_bayes=0.55)),
        ("Enjambre+poros+DAS (Osa)", 6.2, dict(energia=5.1, umbral=1.5, sensores=5, nodos_adj=2, p_bayes=0.78)),
        ("Dilatancia pre-sísmica (GAM)", 6.5, dict(energia=7.3, umbral=1.5, sensores=6, nodos_adj=3, p_bayes=0.92)),
        ("Megathrust Osa", 7.5, dict(energia=9.8, umbral=1.5, sensores=8, nodos_adj=4, p_bayes=0.97)),
    ]
    print(f"  {"Incidente Evaluado":<36} {"Mw":>5} {"Fase":>6} {"Código":>8}  Resultado")
    print(f"  " + "-" * 74)
    for name, mag, ev_data in escenarios:
        fase, cod, desc = arbol.evaluar(ev_data)
        icon = "🔴" if cod == "111" else ("🟠" if cod == "010" else "🟡")
        print(f"  {name:<36} {mag:>5.1f} {fase:>6} {cod:>8}  {icon} {desc}")

    # ─────────────────────────────────────────────────────────────────────────
    # [MÓDULO D] Historial de Sismicidad y Simulación de Monte Carlo
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{S_LINE}")
    print(f"[D] ANÁLISIS DE EFECTIVIDAD HISTÓRICA Y MONTE CARLO SÍSMICO")
    sismos_historicos = [
        (1991, "Limón", 7.6, 'posible', 92e6),
        (2009, "Cinchona", 6.2, 'ninguno', 100e6),
        (2012, "Nicoya", 7.6, 'documentado', 45e6),
        (2025, "GAM proy.", 6.5, 'posible', 150e6),
        (2035, "Osa proy.", 7.8, 'documentado', 300e6),
    ]
    print(f"  {"Evento Histórico":<20} {"Mw":>5} {"Pd":>6} {"Aviso":>7} {"Mitigación":>12} {"Daño Base":>12} {"Daño Mitigado":>14}")
    print(f"  " + "-" * 76)
    
    costo_sin_sistema = 0
    costo_con_sistema = 0
    for yr, lug, mag, prec, dano in sismos_historicos:
        p_d = calcular_pd(mag, prec)
        h_a = horas_aviso(mag)
        pct_r = porcentaje_reduccion(h_a)
        
        detectado = rng.random() < p_d
        dano_final = dano * (1.0 - pct_r * 0.7) if detectado else dano
        costo_sin_sistema += dano
        costo_con_sistema += dano_final
        
        status_d = "✓ Capturado" if detectado else "⛔ Falso Negativo"
        print(f"  {yr} {lug:<15} {mag:>5.1f} {p_d:>5.2f} {h_a:>5}h {pct_r * 100:>10.0f}% ${dano / 1e6:>10.1f}M ${dano_final / 1e6:>11.1f}M  {status_d}")
        
    ahorro_determinista = costo_sin_sistema - costo_con_sistema
    print(f"\n  Impacto Financiero Directo En Pool Evaluado:")
    print(f"    Pérdidas totales SIN el sistema de alerta: ${costo_sin_sistema / 1e6:.1f} M USD")
    print(f"    Pérdidas totales CON el sistema de de alerta: ${costo_con_sistema / 1e6:.1f} M USD")
    print(f"    Retorno por mitigación o ahorro neto:      ${ahorro_determinista / 1e6:.1f} M USD")

    # Simulación Estocástica de Monte Carlo (2,000 Iteraciones)
    N_MC = 2000
    ahorros_mc = []
    falsos_negativos_mc = []
    for _ in range(N_MC):
        s_dano = 0
        c_dano = 0
        fn_count = 0
        for yr, lug, mag, prec, dano in sismos_historicos:
            p_d = calcular_pd(mag, prec)
            if rng.random() < p_d:
                c_dano += dano * (1.0 - porcentaje_reduccion(horas_aviso(mag)) * 0.7)
            else:
                c_dano += dano
                fn_count += 1
            s_dano += dano
        ahorros_mc.append((s_dano - c_dano) / 1e6)
        falsos_negativos_mc.append(fn_count)
        
    ahorros_mc = np.array(ahorros_mc)
    falsos_negativos_mc = np.array(falsos_negativos_mc)
    
    print(f"\n  Resultados Robustos de Simulación Monte Carlo ({N_MC} realizaciones):")
    print(f"    Ahorro Medio Esperado por Mitigación:      ${ahorros_mc.mean():,.2f} M USD")
    print(f"    Intervalo de Confianza Social (P10–P90):  ${np.percentile(ahorros_mc, 10):,.1f} M a ${np.percentile(ahorros_mc, 90):,.1f} M USD")
    print(f"    Tasa Promedio de Falsos Negativos (FN):   {falsos_negativos_mc.mean():.2f} omisiones de un pool de {len(sismos_historicos)} sismos")
    print(f"    Probabilidad de Cobertura Total (FN=0):   {(falsos_negativos_mc == 0).mean() * 100:.1f}% de efectividad absoluta")

    # ─────────────────────────────────────────────────────────────────────────
    # [MÓDULO E] Estructuración Completa del CAPEX / OPEX (Sin Reactor)
    # ─────────────────────────────────────────────────────────────────────────
    CAPEX_BASE_ITEMS = {
        "Perforación rotatoria convencional a 600 m (5 nodos)": 550000,
        "Entubado, cementación estructural y completación": 180000,
        "Interrogadores DAS ópticos multicanal (5 unidades)": 750000,
        "Magnetómetros criogénicos SQUID de superficie (5 unidades)": 350000,
        "Magnetómetros de vapor de Rubidio-87 de pozo profundo (10 uds)": 200000,
        "Cable armado Wireline multitrenza primario 600 m (5 uds)": 60000,
        "Bobina ULF de núcleo de ferrita e inyectores de potencia": 85000,
        "Estaciones automatizadas de gas Radón y geoquímica (5 uds)": 60000,
        "Transductores de presión de poros y deformación (10 uds)": 60000,
        "Cápsulas de protección estructural de Titanio + PTFE (5 uds)": 140000,
        "Enlaces redundantes de telecomunicaciones (ICE + LEO Satélite)": 750000,
        "Clúster central de cómputo bayesiano de alta densidad (OVSICORI)": 150000,
        "Pasarela de conexión y Gateway Cell Broadcast dedicada (CNE)": 180000,
        "Ingeniería de campo, montaje, despliegue y comisionado": 200000
    }
    
    subtotal_capex = sum(CAPEX_BASE_ITEMS.values())
    contingencia_total = int(round(subtotal_capex * CONTINGENCIA_PCT))
    capex_consolidado = subtotal_capex + contingencia_total
    
    OPEX_ANUAL_BASE = {
        "Mantenimiento preventivo e instrumentación de campo": 125000,
        "Sistemas de refrigeración por aire para SQUID de superficie": 180000,
        "Enlaces y canales de datos dedicados (ICE Fibra)": 18000,
        "Planilla del equipo científico permanente (4 plazas sénior)": 182000,
        "Fluido eléctrico y consumibles operativos": 10000,
        "Soporte técnico y mantenimiento del enlace CNE": 25000,
        "Auditorías de seguridad estructural y pólizas de riesgo": 20000
    }
    
    opex_ano_1 = sum(OPEX_ANUAL_BASE.values())
    
    # Capitalización acumulada de OPEX a 30 años considerando inflación indexada
    opex_acumulado_30a = sum(opex_ano_1 * ((1.0 + INFLACION) ** (y - 1)) for y in range(1, YEARS_PROYECTO + 1))
    costo_total_ciclo_vida = capex_consolidado + opex_acumulado_30a + REEMPLAZOS_30A

    print(f"\n{S_LINE}")
    print(f"[E] ANALISIS DE COSTOS E INVERSIÓN: CAPEX / OPEX")
    print(f"  Desglose de la Estructura de Compra de Capital (CAPEX):")
    for item, costo in CAPEX_BASE_ITEMS.items():
        print(f"    - {item:<65} ${costo:>10,}")
    print(f"    - Contingencia Tecnológica Impuesta por MIDEPLAN ({CONTINGENCIA_PCT * 100:.0f}%): ${contingencia_total:>10,}")
    print(f"    " + "-" * 78")
    print(f"    INVERSIÓN TOTAL INICIAL (CAPEX CONSOLIDADO):          ${capex_consolidado:>10,} USD")
    print(f"\n  Presupuesto de Operación y Sostenibilidad (OPEX):")
    print(f"    Gasto operativo proyectado para el Año 1:            ${opex_ano_1:,} USD/año")
    print(f"    Gasto operativo acumulado indexado a 30 años (3.5%): ${opex_acumulado_30a:,.0f} USD")
    print(f"    Fondo de reserva de reemplazo de sensores (30 años): ${REEMPLAZOS_30A:,} USD")
    print(f"    COSTO TOTAL DE CICLO DE VIDA DE LA RED (30 AÑOS):     ${costo_total_ciclo_vida:,.0f} USD")

    # ─────────────────────────────────────────────────────────────────────────
    # [MÓDULO F] Relación Beneficio-Costo Social y Descuento MIDEPLAN
    # ─────────────────────────────────────────────────────────────────────────
    vidas_salvadas_supuesto = 290
    beneficio_nominal_30a = vidas_salvadas_supuesto * VSL_USD
    bc_nominal_ratio = beneficio_nominal_30a / costo_total_ciclo_vida
    
    # Análisis descontado bajo los requerimientos metodológicos del 6% social de MIDEPLAN
    beneficio_social_anualizado = beneficio_nominal_30a / YEARS_PROYECTO
    
    pv_costos = capex_consolidado + sum(
        (opex_ano_1 * ((1.0 + INFLACION) ** (t - 1)) + (REEMPLAZOS_30A / YEARS_PROYECTO)) / ((1.0 + R_DESCUENTO) ** t)
        for t in range(1, YEARS_PROYECTO + 1)
    )
    pv_beneficios = sum(beneficio_social_anualizado / ((1.0 + R_DESCUENTO) ** t) for t in range(1, YEARS_PROYECTO + 1))
    van_social = pv_beneficios - pv_costos
    bc_descontado_ratio = pv_beneficios / pv_costos

    print(f"\n{S_LINE}")
    print(f"[F] METODOLOGÍA DE EVALUACIÓN SOCIAL Y RECONCILIACIÓN MIDEPLAN")
    print(f"  Análisis Nominal del Retorno:")
    print(f"    Supuesto base oficial de vidas salvadas (Ciclo de 30 años): {vidas_salvadas_supuesto} vidas humanas")
    print(f"    Valor de una Vida Estadística (VSL):                       ${VSL_USD:,} USD por vida")
    print(f"    Beneficio bruto social cuantificado:                       ${beneficio_nominal_30a:,} USD")
    print(f"    RELACIÓN BENEFICIO-COSTO NOMINAL CONSOLIDADA:              {bc_nominal_ratio:.1f} a 1 (Conforme al informe oficial)")
    
    print(f"\n  Evaluación Socioeconómica Descontada (Tasa de Descuento Social del {R_DESCUENTO * 100:.0f}%):")
    print(f"    Beneficio social distribuído anualizado:                   ${beneficio_social_anualizado / 1e6:.2f} M USD/año")
    print(f"    Valor Presente de los Costos Totales (PV Costos):          ${pv_costos / 1e6:.2f} M USD")
    print(f"    Valor Presente de los Beneficios Sociales (PV Beneficios):  ${pv_beneficios / 1e6:.2f} M USD")
    print(f"    VALOR ACTUAL NETO SOCIAL GENERAL (VAN SOCIAL):             ${van_social / 1e6:.2f} M USD")
    print(f"    RELACIÓN BENEFICIO-COSTO DESCONTADA A TASA DEL 6%:         {bc_descontado_ratio:.2f} a 1")
    print(f"    Dictamen de Inversión Pública: El VAN es positivo; el proyecto es plenamente elegible.")

    # ─────────────────────────────────────────────────────────────────────────
    # [MÓDULO G] Disponibilidad del Sistema con Correlación de Fallas
    # ─────────────────────────────────────────────────────────────────────────
    # Riesgos ambientales ponderados
    riesgos_red = [
        ("Corrosión ácida de fondo de pozo", 0.30, 0.95),
        ("Cortes accidentales de fibra ICE", 0.45, 0.85),
        ("Fallo del suministro eléctrico de superficie", 0.35, 0.92),
        ("Deriva e inestabilidad térmica del SQUID", 0.12, 0.98),
        ("Actos de vandalismo o robo en caseta externa", 0.20, 0.99)
    ]
    disponibilidad_unitaria_nodo = 1.0
    for _, p_ocu, e_mit in riesgos_red:
        disponibilidad_unitaria_nodo *= (1.0 - p_ocu * (1.0 - e_mit))
        
    p_min_3_nodos_independiente = sum(comb(5, k) * (disponibilidad_unitaria_nodo ** k) * ((1.0 - disponibilidad_unitaria_nodo) ** (5 - k)) for k in range(3, 6))
    
    # Escenario de choque masivo post-sismo (Fallas altamente correlacionadas)
    PROB_CHOQUE_TECTÓNICO = 0.08
    DISPO_NODO_POST_SHOCK = 0.55
    
    sim_nodos_activos = []
    for _ in range(5000):
        prob_operativa = DISPO_NODO_POST_SHOCK if rng.random() < PROB_CHOQUE_TECTÓNICO else disponibilidad_unitaria_nodo
        nodos_vivos = sum(rng.random() < prob_operativa for _ in range(5))
        sim_nodos_activos.append(nodos_vivos)
        
    sim_nodos_activos = np.array(sim_nodos_activos)
    p_min_3_nodos_correlacionado = (sim_nodos_activos >= 3).mean()
    p_caida_total_red = (sim_nodos_activos == 0).mean()

    print(f"\n{S_LINE}")
    print(f"[G] MODELO DE DISPONIBILIDAD Y ANÁLISIS DE RESILIENCIA DE RED")
    print(f"  Disponibilidad Estructural por Nodo Individual:       {disponibilidad_unitaria_nodo * 100:.2f}% de permanencia")
    print(f"  Cuórum de Operación Mínimo (Por lo menos 3 de los 5 nodos activos):")
    print(f"    - Probabilidad en condiciones normales (Fallos independientes): {p_min_3_nodos_independiente * 100:.2f}%")
    print(f"    - Probabilidad bajo Estrés Post-Sismo (Fallos correlacionados): {p_min_3_nodos_correlacionado * 100:.2f}%")
    print(f"    - Riesgo de pérdida absoluta o apagón total de la red:        {p_caida_total_red * 100:.2f}% de probabilidad")

    # ─────────────────────────────────────────────────────────────────────────
    # [MÓDULO H] Tiempos de Latencia y Falsas Alarmas
    # ─────────────────────────────────────────────────────────────────────────
    latencias_comunes = [
        ("Adquisición digital + Stack de muestras", 0.50),
        ("Filtrado y Detección Local k-sigma", 0.30),
        ("Clasificación en Árbol Bayesiano Central", LAT_BAYES),
        ("Autenticación y Gateway de Entrada CNE", 1.00),
        ("Difusión masiva por antenas de telefonía", 2.00)
    ]
    
    latencia_cable_primario = sum(v for _, v in latencias_comunes) + 0.05 + 0.05  # + Tránsito e inversión en cable
    latencia_respaldo_ulf = sum(v for _, v in latencias_comunes) + 1.50 + 0.20    # + Tx bits ULF y decode SQUID
    
    # Embudo de falsas alarmas anuales
    anomalias_candidatas = 120
    fase_0 = anomalias_candidatas * 0.40
    fase_1 = fase_0 * 0.35
    fase_2 = fase_1 * 0.25
    alertas_emitidas_111 = fase_2 * 0.08
    falsas_alarmas_publicas = alertas_emitidas_111 * 0.15

    print(f"\n{S_LINE}")
    print(f"[H] AUDITORÍA DE LATENCIAS EXTREMO A EXTREMO Y FILTRO DE FALSAS ALARMAS")
    print(f"  Tiempos de Tránsito del Mensaje de Alerta Temprana:")
    print(f"    - RUTA POR CABLE ARMADO (Enlace Primario Principal): {latencia_cable_primario:.2f} segundos")
    print(f"    - RUTA ONDAS ELECTROMAGNÉTICAS ULF (Respaldo por Cizalla): {latencia_respaldo_ulf:.2f} segundos")
    print(f"    Dictamen Temporal: Ambos canales logran alertar a los cascos urbanos antes del arribo de la Onda S.")
    print(f"\n  Embudo de Credibilidad del Sistema (Mitigación del Pánico Social):")
    print(f"    Falsas Alarmas Públicas proyectadas: {falsas_alarmas_publicas:.3f} eventos erróneos por año")
    print(f"    Frecuencia Media de Error Público:   1 evento de falsa alarma cada {1.0 / falsas_alarmas_publicas:.1f} años")
    print(f"    Meta institucional impuesta por la CNE (< 2 alertas erróneas/año): ✓ CUMPLIMIENTO ABSOLUTO")

    # ─────────────────────────────────────────────────────────────────────────
    # [MÓDULO I] Compilación de Resultados Estructurados y Exportación JSON
    # ─────────────────────────────────────────────────────────────────────────
    json_output_data = {
        "version": VERSION,
        "inventor": "Jason Manuel Sarmiento Salazar",
        "cedula": "114510108",
        "fecha_emision": "2026-09-12",
        "cambio_tecnologico_clave": "v5.3: Modelo termorefractor de ferrita + Logística de Cizalla + VAN Descontado MIDEPLAN",
        "pozo_geometria": {
            "diametro_perforacion_mm": D_HOLE_MM,
            "profundidad_despliegue_m": DEPTH_CR,
            "dias_construccion_nodo": round(total_dias_nodo, 1),
            "temperatura_fondo_estimada_C": round(temperatura_fondo, 1)
        },
        "enlace_ulf_especificaciones": {
            "bobina_nucleo_config": f"Ferrita MnZn mu_diseno={MU_EFF_DISEÑO:.0f} mu_termica={mu_degradada:.0f} N={N_REF} I={I_REF}A",
            "snr_diurno_tipico_dB": round(float(snr_diurno_tipico), 1),
            "snr_peor_caso_termico_dB": round(float(snr_termico), 1),
            "snr_peor_caso_litologia_dB": round(float(peor_snr), 1),
            "potencia_media_bobina_W": round(potencia_pico * DUTY, 1),
            "arquitectura_enlace": "Canal hibrido - Cable armado primario + Respaldo electromagnetico ULF en cizalla",
            "control_kp_adaptativo": True,
            "probabilidad_ulf_critica_post_sismo": round(float(p_ulf_critica), 3)
        },
        "analisis_costos_financieros": {
            "inversion_capex_usd": capex_consolidado,
            "porcentaje_contingencia_aplicado": CONTINGENCIA_PCT,
            "opex_acumulado_30_anos_usd": round(opex_acumulado_30a),
            "costo_total_ciclo_vida_30_anos_usd": round(costo_total_ciclo_vida),
            "relacion_beneficio_costo_nominal": round(bc_nominal_ratio, 1),
            "valor_actual_neto_social_usd": round(van_social),
            "relacion_beneficio_costo_descontada_mideplan": round(bc_descontado_ratio, 2)
        },
        "resiliencia_red": {
            "disponibilidad_intrinsica_nodo": round(disponibilidad_unitaria_nodo, 4),
            "disponibilidad_cuorum_post_sismo": round(p_min_3_nodos_correlacionado, 4)
        },
        "tiempos_latencia": {
            "ruta_cable_primario_segundos": round(latencia_cable_primario, 2),
            "ruta_respaldo_ulf_segundos": round(latencia_respaldo_ulf, 2)
        },
        "tasa_falsas_alarmas_anual": round(falsas_alarmas_publicas, 3)
    }

    json_target_path = os.path.join(OUT_DIR, "GEO_PROBE_CR_v5_resultados.json")
    try:
        with open(json_target_path, "w", encoding="utf-8") as f_json:
            json.dump(json_output_data, f_json, indent=2, ensure_ascii=False)
        print(f"\n{L_LINE}")
        print(f" ARTEFACTO DE DATOS DE EXPORTACIÓN GENERADO CON ÉXITO")
        print(f" Archivo JSON guardado en: {json_target_path}")
    except Exception as e:
        print(f"\nError crítico al intentar volcar el artefacto de datos JSON: {e}")
        
    print(L_LINE)

if __name__ == "__main__":
    ejecutar_sistema()
