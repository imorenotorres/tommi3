import matplotlib
matplotlib.use('Agg')  # Backend no interactivo
import matplotlib.pyplot as plt
import numpy as np

# Configuración de estilo
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.figsize'] = (14, 10)
plt.rcParams['font.size'] = 11

# Parámetros de coste API Mistral Large 2
COST_INPUT_PER_M = 2.00  # $ por millón de tokens
COST_OUTPUT_PER_M = 6.00  # $ por millón de tokens

# Estimación de tokens por agente por año según nivel de uso
# (promedio ponderado entre tutores, toolshot y RAG)
USAGE_LEVELS = {
    'bajo': {
        'input_tokens_per_agent_year': 8_000_000,   # 8M tokens/agente/año
        'output_tokens_per_agent_year': 4_000_000,  # 4M tokens/agente/año
        'label': 'Uso Bajo (8M input + 4M output/agente/año)',
        'color': '#2ecc71',
        'linestyle': '-'
    },
    'medio': {
        'input_tokens_per_agent_year': 25_000_000,  # 25M tokens/agente/año
        'output_tokens_per_agent_year': 14_000_000, # 14M tokens/agente/año
        'label': 'Uso Medio (25M input + 14M output/agente/año)',
        'color': '#f39c12',
        'linestyle': '-'
    },
    'alto': {
        'input_tokens_per_agent_year': 50_000_000,  # 50M tokens/agente/año
        'output_tokens_per_agent_year': 28_000_000, # 28M tokens/agente/año
        'label': 'Uso Alto (50M input + 28M output/agente/año)',
        'color': '#e74c3c',
        'linestyle': '-'
    }
}

# Costes On-Premise (INCLUYE PERSONAL)
# Desglose: Hardware amortizado + Electricidad + Licencias + PERSONAL + Mantenimiento
ON_PREMISE_CONFIGS = {
    'basico': {
        'initial_cost': 80_000,       # 2x A100 80GB + servidor
        'yearly_operational': 130_000, # $25k infra + $100k personal (1.5 FTE básico)
        'max_agents': 400,             # Capacidad máxima de agentes simultáneos
        'label': 'On-Premise Básico (2x A100) + 1.5 FTE',
        'color': '#3498db',
        'linestyle': '--'
    },
    'medio': {
        'initial_cost': 150_000,      # 4x A100 80GB + servidor enterprise
        'yearly_operational': 200_000, # $50k infra + $150k personal (2 FTE)
        'max_agents': 800,
        'label': 'On-Premise Medio (4x A100) + 2 FTE',
        'color': '#9b59b6',
        'linestyle': '--'
    },
    'alto': {
        'initial_cost': 300_000,      # 8x H100 + infraestructura
        'yearly_operational': 320_000, # $70k infra + $250k personal (3-4 FTE 24/7)
        'max_agents': 2000,
        'label': 'On-Premise Alto (8x H100) + 3-4 FTE',
        'color': '#1abc9c',
        'linestyle': '--'
    }
}

def calculate_api_cost(num_agents, usage_level):
    """Calcula el coste anual de la API para un número de agentes"""
    config = USAGE_LEVELS[usage_level]
    input_cost = (num_agents * config['input_tokens_per_agent_year'] / 1_000_000) * COST_INPUT_PER_M
    output_cost = (num_agents * config['output_tokens_per_agent_year'] / 1_000_000) * COST_OUTPUT_PER_M
    return input_cost + output_cost

def calculate_onprem_cost_year(config, year):
    """Calcula el coste acumulado on-premise para un año específico"""
    return config['initial_cost'] + (config['yearly_operational'] * year)

def calculate_onprem_annual_equivalent(config, years=3):
    """Calcula el coste anual equivalente amortizando la inversión"""
    total_cost = config['initial_cost'] + (config['yearly_operational'] * years)
    return total_cost / years

# Rango de agentes
agents = np.arange(0, 2001, 50)
agents[0] = 1  # Empezar desde 1 agente

# Crear figura con subplots
fig, axes = plt.subplots(2, 2, figsize=(16, 14))

# ============================================
# GRÁFICO 1: Coste Anual API vs Número de Agentes
# ============================================
ax1 = axes[0, 0]

for level, config in USAGE_LEVELS.items():
    costs = [calculate_api_cost(n, level) for n in agents]
    ax1.plot(agents, np.array(costs)/1000,
             label=config['label'],
             color=config['color'],
             linewidth=2.5,
             linestyle=config['linestyle'])

ax1.set_xlabel('Número de Agentes', fontsize=12)
ax1.set_ylabel('Coste Anual (miles $)', fontsize=12)
ax1.set_title('Coste Anual API Mistral Large 2 según Uso', fontsize=14, fontweight='bold')
ax1.legend(loc='upper left', fontsize=10)
ax1.set_xlim(0, 2000)
ax1.set_ylim(0, 800)
ax1.grid(True, alpha=0.3)

# ============================================
# GRÁFICO 2: Comparación API vs On-Premise (Uso Medio, 3 años)
# ============================================
ax2 = axes[0, 1]

# Coste API uso medio
api_costs_medio = [calculate_api_cost(n, 'medio') for n in agents]
ax2.plot(agents, np.array(api_costs_medio)/1000,
         label='API Mistral (Uso Medio) - Anual',
         color='#e74c3c', linewidth=3)

# Costes On-Premise (amortizado a 3 años)
for config_name, config in ON_PREMISE_CONFIGS.items():
    annual_equiv = calculate_onprem_annual_equivalent(config, years=3)
    # Línea horizontal hasta capacidad máxima
    valid_agents = agents[agents <= config['max_agents']]
    ax2.hlines(y=annual_equiv/1000, xmin=0, xmax=config['max_agents'],
               colors=config['color'], linestyles=config['linestyle'],
               linewidth=2.5, label=f"{config['label']} (amort. 3 años)")
    # Línea vertical indicando límite de capacidad
    ax2.vlines(x=config['max_agents'], ymin=0, ymax=annual_equiv/1000,
               colors=config['color'], linestyles=':', alpha=0.5)

ax2.set_xlabel('Número de Agentes', fontsize=12)
ax2.set_ylabel('Coste Anual Equivalente (miles $)', fontsize=12)
ax2.set_title('API vs On-Premise + Personal (Amortización 3 años)', fontsize=14, fontweight='bold')
ax2.legend(loc='upper left', fontsize=9)
ax2.set_xlim(0, 2000)
ax2.set_ylim(0, 600)
ax2.grid(True, alpha=0.3)

# ============================================
# GRÁFICO 3: Punto de Equilibrio según Uso
# ============================================
ax3 = axes[1, 0]

# Configuración on-premise media como referencia
onprem_config = ON_PREMISE_CONFIGS['medio']
onprem_annual = calculate_onprem_annual_equivalent(onprem_config, years=3)

breakeven_points = {}

for level, config in USAGE_LEVELS.items():
    costs = [calculate_api_cost(n, level) for n in agents]
    ax3.plot(agents, np.array(costs)/1000,
             label=f'API - {config["label"].split("(")[0].strip()}',
             color=config['color'], linewidth=2.5)

    # Encontrar punto de equilibrio
    for i, (n, cost) in enumerate(zip(agents, costs)):
        if cost >= onprem_annual and n <= onprem_config['max_agents']:
            breakeven_points[level] = n
            break

# Línea on-premise
ax3.hlines(y=onprem_annual/1000, xmin=0, xmax=onprem_config['max_agents'],
           colors='#9b59b6', linestyles='--', linewidth=3,
           label=f'On-Premise Medio ({onprem_annual/1000:.0f}k$/año)')

# Marcar puntos de equilibrio
for level, breakeven in breakeven_points.items():
    ax3.axvline(x=breakeven, color=USAGE_LEVELS[level]['color'],
                linestyle=':', alpha=0.7)
    # Ajustar posición del texto según el nivel
    offset_y = {'bajo': 40, 'medio': 25, 'alto': 10}.get(level, 20)
    ax3.annotate(f'{breakeven} agentes',
                 xy=(breakeven, onprem_annual/1000),
                 xytext=(breakeven+80, onprem_annual/1000 + offset_y),
                 fontsize=9, color=USAGE_LEVELS[level]['color'],
                 fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color=USAGE_LEVELS[level]['color'], alpha=0.7))

ax3.set_xlabel('Número de Agentes', fontsize=12)
ax3.set_ylabel('Coste Anual (miles $)', fontsize=12)
ax3.set_title('Punto de Equilibrio: API vs On-Premise Medio + Personal', fontsize=14, fontweight='bold')
ax3.legend(loc='upper left', fontsize=9)
ax3.set_xlim(0, 2000)
ax3.set_ylim(0, 500)
ax3.grid(True, alpha=0.3)

# ============================================
# GRÁFICO 4: Análisis ROI a 5 años
# ============================================
ax4 = axes[1, 1]

years = np.arange(1, 6)
num_agents_scenario = 500  # Escenario: 500 agentes

# Coste acumulado API
api_cumulative = {level: [] for level in USAGE_LEVELS}
for level in USAGE_LEVELS:
    annual_cost = calculate_api_cost(num_agents_scenario, level)
    for y in years:
        api_cumulative[level].append(annual_cost * y)

# Coste acumulado On-Premise
onprem_cumulative = {config_name: [] for config_name in ON_PREMISE_CONFIGS}
for config_name, config in ON_PREMISE_CONFIGS.items():
    for y in years:
        onprem_cumulative[config_name].append(calculate_onprem_cost_year(config, y))

# Graficar API
for level, costs in api_cumulative.items():
    ax4.plot(years, np.array(costs)/1000,
             label=f'API - Uso {level.capitalize()}',
             color=USAGE_LEVELS[level]['color'],
             linewidth=2.5, marker='o')

# Graficar On-Premise (solo medio para claridad)
config = ON_PREMISE_CONFIGS['medio']
costs = onprem_cumulative['medio']
ax4.plot(years, np.array(costs)/1000,
         label=config['label'],
         color=config['color'],
         linewidth=3, marker='s', linestyle='--')

ax4.set_xlabel('Años', fontsize=12)
ax4.set_ylabel('Coste Acumulado (miles $)', fontsize=12)
ax4.set_title(f'Coste Acumulado a 5 Años ({num_agents_scenario} agentes)', fontsize=14, fontweight='bold')
ax4.legend(loc='upper left', fontsize=9)
ax4.set_xlim(0.5, 5.5)
ax4.set_xticks(years)
ax4.grid(True, alpha=0.3)

# Ajustar layout
plt.tight_layout()

# Guardar figura
output_path = '/Users/ignaciomoreno-torres/Library/CloudStorage/OneDrive-UniversidaddeMálaga/agentes/tommi2/apps/cost_analysis_mistral.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
print(f"Gráfica guardada en: {output_path}")

# Mostrar resumen de puntos de equilibrio
print("\n" + "="*70)
print("RESUMEN: PUNTOS DE EQUILIBRIO (On-Premise + PERSONAL vs API)")
print("="*70)

print("\n📊 CONFIGURACIONES ON-PREMISE (incluye personal técnico):")
for config_name, config in ON_PREMISE_CONFIGS.items():
    annual_equiv = calculate_onprem_annual_equivalent(config, years=3)
    print(f"\n  {config['label']}:")
    print(f"    - Inversión inicial (hardware): ${config['initial_cost']:,}")
    print(f"    - Coste operativo anual (infra + personal): ${config['yearly_operational']:,}")
    print(f"    - Capacidad máxima: {config['max_agents']} agentes")
    print(f"    - Coste anual equivalente (amort. 3 años): ${annual_equiv:,.0f}")

print("\n" + "-"*70)
print("📈 PUNTOS DE EQUILIBRIO vs On-Premise Medio + 2 FTE:")
print("-"*70)
if breakeven_points:
    for level, breakeven in breakeven_points.items():
        print(f"  - Uso {level.capitalize()}: {breakeven} agentes")
else:
    print("  - Con los costes de personal, On-Premise requiere más agentes para ser rentable")

print("\n" + "="*70)
print("🎯 ESCENARIO USUARIO: 1300 agentes totales")
print("="*70)
user_agents = 1300
print("\nCoste API Mistral Large 2:")
for level in ['bajo', 'medio', 'alto']:
    cost = calculate_api_cost(user_agents, level)
    print(f"  - Uso {level.capitalize()}: ${cost:,.0f}/año")

print("\nCoste On-Premise + Personal:")
for config_name, config in ON_PREMISE_CONFIGS.items():
    if user_agents <= config['max_agents']:
        annual = calculate_onprem_annual_equivalent(config, 3)
        print(f"  - {config['label']}: ${annual:,.0f}/año")

# Análisis final
print("\n" + "="*70)
print("💡 ANÁLISIS Y RECOMENDACIÓN")
print("="*70)
api_medio = calculate_api_cost(user_agents, 'medio')
api_alto = calculate_api_cost(user_agents, 'alto')
onprem_alto_annual = calculate_onprem_annual_equivalent(ON_PREMISE_CONFIGS['alto'], 3)

print(f"\nPara 1300 agentes:")
print(f"  - API (uso medio): ${api_medio:,.0f}/año")
print(f"  - API (uso alto): ${api_alto:,.0f}/año")
print(f"  - On-Premise Alto + Personal: ${onprem_alto_annual:,.0f}/año")

if api_alto > onprem_alto_annual:
    ahorro = api_alto - onprem_alto_annual
    print(f"\n✅ Con USO ALTO: On-Premise ahorra ${ahorro:,.0f}/año")
if api_medio < onprem_alto_annual:
    extra = onprem_alto_annual - api_medio
    print(f"⚠️  Con USO MEDIO: API es ${extra:,.0f}/año más barato")
