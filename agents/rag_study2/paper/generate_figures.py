#!/usr/bin/env python3
"""Generate all figures for the paper."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

FIGDIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIGDIR, exist_ok=True)

# Consistent style
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 11,
    'axes.titlesize': 13,
    'axes.labelsize': 11,
    'figure.dpi': 200,
})

COLORS = {
    'production': '#9ca3af',
    'auto_rule': '#f59e0b',
    'llm': '#3b82f6',
}


# ═══════════════════════════════════════════════════════════════════════════
# Figure 1: Vanilla RAG vs Classified RAG architecture diagrams
# ═══════════════════════════════════════════════════════════════════════════

def _draw_classified_rag(ax, title, classification_label, classification_color,
                         classification_fc, classification_detail, highlight=False):
    """Draw a classified RAG diagram on an axis."""
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 11)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(title, fontweight='bold', fontsize=12)

    # Query
    ax.add_patch(mpatches.FancyBboxPatch((5, 9.2), 4, 1, boxstyle="round,pad=0.15",
        facecolor='#e0e7ff', edgecolor='#4f46e5', linewidth=2))
    ax.text(7, 9.7, 'User Query', ha='center', va='center', fontsize=10, fontweight='bold')

    # Classification — highlighted with thicker border if this is the differentiating element
    lw = 3.5 if highlight else 2
    ax.add_patch(mpatches.FancyBboxPatch((3.5, 7.3), 7, 1.2, boxstyle="round,pad=0.15",
        facecolor=classification_fc, edgecolor=classification_color, linewidth=lw))
    ax.text(7, 8.15, classification_label, ha='center', va='center', fontsize=10,
            fontweight='bold', color=classification_color)
    ax.text(7, 7.65, classification_detail, ha='center', va='center', fontsize=7.5,
            color='#374151', style='italic')
    ax.annotate('', xy=(7, 8.5), xytext=(7, 9.2),
        arrowprops=dict(arrowstyle='->', color='#374151', lw=2))

    # Left branch — Programmatic
    ax.add_patch(mpatches.FancyBboxPatch((0.3, 4.8), 5.4, 1.6, boxstyle="round,pad=0.15",
        facecolor='#d1fae5', edgecolor='#059669', linewidth=2))
    ax.text(3, 6.0, 'Programmatic Paths', ha='center', va='center', fontsize=9, fontweight='bold', color='#059669')
    ax.text(3, 5.3, 'meta, glossary, researcher,\nproject, off_topic, non_research',
             ha='center', va='center', fontsize=7, color='#065f46')

    # Right branch — BM25 + LLM
    ax.add_patch(mpatches.FancyBboxPatch((8.3, 5.6), 5.2, 0.8, boxstyle="round,pad=0.15",
        facecolor='#fef3c7', edgecolor='#d97706', linewidth=2))
    ax.text(10.9, 6.0, 'BM25 Retrieval', ha='center', va='center', fontsize=9, fontweight='bold', color='#d97706')

    ax.add_patch(mpatches.FancyBboxPatch((8.3, 4.2), 5.2, 0.8, boxstyle="round,pad=0.15",
        facecolor='#fee2e2', edgecolor='#dc2626', linewidth=2))
    ax.text(10.9, 4.6, 'LLM Generation', ha='center', va='center', fontsize=9, fontweight='bold', color='#dc2626')

    ax.annotate('', xy=(10.9, 5.0), xytext=(10.9, 5.6),
        arrowprops=dict(arrowstyle='->', color='#374151', lw=1.5))

    # Arrows from classification
    ax.annotate('', xy=(3, 6.4), xytext=(5, 7.3),
        arrowprops=dict(arrowstyle='->', color='#059669', lw=2))
    ax.annotate('', xy=(10.9, 6.4), xytext=(9, 7.3),
        arrowprops=dict(arrowstyle='->', color='#dc2626', lw=2))

    # Response
    ax.add_patch(mpatches.FancyBboxPatch((5, 1.8), 4, 1, boxstyle="round,pad=0.15",
        facecolor='#e0e7ff', edgecolor='#4f46e5', linewidth=2))
    ax.text(7, 2.3, 'Response', ha='center', va='center', fontsize=10, fontweight='bold')

    ax.annotate('', xy=(5.5, 2.8), xytext=(3, 4.8),
        arrowprops=dict(arrowstyle='->', color='#059669', lw=2))
    ax.annotate('', xy=(8.5, 2.8), xytext=(10.9, 4.2),
        arrowprops=dict(arrowstyle='->', color='#dc2626', lw=2))

    ax.text(10.9, 3.5, 'topic_search, gap,\ngeneral, followup',
             ha='center', va='center', fontsize=7, color='#991b1b')
    ax.text(1.5, 3.5, 'Deterministic\n(no LLM, no hallucination)',
             ha='center', va='center', fontsize=7, color='#059669', style='italic')


def fig1_architecture():
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 5.5))

    # --- (a) Vanilla RAG ---
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 11)
    ax1.set_aspect('equal')
    ax1.axis('off')
    ax1.set_title('(a) Vanilla RAG', fontweight='bold', fontsize=12)

    boxes = [
        (5, 9.0, 'User Query', '#e0e7ff', '#4f46e5'),
        (5, 7.0, 'BM25 Retrieval', '#fef3c7', '#d97706'),
        (5, 5.0, 'LLM Generation', '#fee2e2', '#dc2626'),
        (5, 3.0, 'Response', '#e0e7ff', '#4f46e5'),
    ]
    for x, y, label, fc, ec in boxes:
        ax1.add_patch(mpatches.FancyBboxPatch((x-2, y-0.6), 4, 1.2,
            boxstyle="round,pad=0.15", facecolor=fc, edgecolor=ec, linewidth=2))
        ax1.text(x, y, label, ha='center', va='center', fontsize=10, fontweight='bold')

    for i in range(3):
        ax1.annotate('', xy=(5, boxes[i+1][1]+0.6), xytext=(5, boxes[i][1]-0.6),
            arrowprops=dict(arrowstyle='->', color='#374151', lw=2))

    ax1.text(5, 1.5, 'Every query follows the\nsame path (no classification)',
             ha='center', va='center', fontsize=9, color='#6b7280', style='italic')

    # --- (b) Rule-based Classification ---
    _draw_classified_rag(ax2,
        title='(b) Rule-based Classification',
        classification_label='Rule-based Classification',
        classification_color='#d97706',
        classification_fc='#fef9c3',
        classification_detail='Regex patterns + synonym maps (deterministic)',
        highlight=True)

    # --- (c) LLM-based Classification ---
    _draw_classified_rag(ax3,
        title='(c) LLM-based Classification',
        classification_label='LLM Classification',
        classification_color='#2563eb',
        classification_fc='#dbeafe',
        classification_detail='Separate LLM call (non-deterministic)',
        highlight=True)

    # Comparison annotations between panels
    # Arrow (a)→(b): response paths
    fig.text(0.27, 0.03, '← adds response paths →',
             ha='center', va='center', fontsize=10, fontweight='bold', color='#059669',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#d1fae5', edgecolor='#059669', linewidth=1.5))

    # Arrow (b)→(c): classification mechanism
    fig.text(0.63, 0.03, '← swaps classification mechanism →',
             ha='center', va='center', fontsize=10, fontweight='bold', color='#2563eb',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#dbeafe', edgecolor='#2563eb', linewidth=1.5))

    plt.tight_layout(rect=[0, 0.07, 1, 1])
    plt.savefig(os.path.join(FIGDIR, 'fig1_architecture.png'), bbox_inches='tight')
    plt.close()
    print("fig1_architecture.png")


# ═══════════════════════════════════════════════════════════════════════════
# Figure 2: Rabanser aggregate scores (4 agents, 4 dimensions)
# ═══════════════════════════════════════════════════════════════════════════

def fig2_rabanser():
    dimensions = ['R_Con\n(Consistency)', 'R_Rob\n(Robustness)', 'R_Pred\n(Predictability)', 'R_Saf\n(Safety)']
    production = [0.823, 0.691, 0.506, 0.500]
    auto_rule = [0.983, 0.665, 0.676, 0.864]
    llm = [0.975, 0.922, 0.743, 0.936]
    llm_std = [0.003, 0.007, 0.002, 0.010]

    x = np.arange(len(dimensions))
    w = 0.22

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.bar(x - w, production, w, label='Production rule-based (months)', color=COLORS['production'], edgecolor='white')
    ax.bar(x, auto_rule, w, label='Auto-constructed rule-based (hours)', color=COLORS['auto_rule'], edgecolor='white')
    ax.bar(x + w, llm, w, label='Auto-constructed LLM-based (N=5)', color=COLORS['llm'], edgecolor='white',
           yerr=llm_std, capsize=3, error_kw={'linewidth': 1.5})

    ax.set_ylabel('Score')
    ax.set_title('Rabanser Reliability Dimensions (216 unseen queries)', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(dimensions)
    ax.set_ylim(0, 1.1)
    ax.axhline(y=1.0, color='#d1d5db', linestyle='--', linewidth=0.8)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=9, framealpha=0.9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.2)
    plt.savefig(os.path.join(FIGDIR, 'fig2_rabanser.png'), bbox_inches='tight')
    plt.close()
    print("fig2_rabanser.png")


# ═══════════════════════════════════════════════════════════════════════════
# Figure 3: Accuracy by tier (robustness degradation)
# ═══════════════════════════════════════════════════════════════════════════

def fig3_tiers():
    tiers = ['Tier 1\n(Standard)', 'Tier 2\n(Unusual)', 'Tier 3\n(Adversarial)']
    production = [45.8, 42.6, 40.0]
    auto_rule = [96.7, 45.9, 54.3]
    llm_mean = [91.3, 80.7, 88.0]
    llm_std = [0.7, 0.7, 1.3]

    x = np.arange(len(tiers))
    w = 0.22

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.bar(x - w, production, w, label='Production rule-based', color=COLORS['production'], edgecolor='white')
    ax.bar(x, auto_rule, w, label='Auto-constructed rule-based', color=COLORS['auto_rule'], edgecolor='white')
    ax.bar(x + w, llm_mean, w, label='Auto-constructed LLM-based (N=5)', color=COLORS['llm'], edgecolor='white',
           yerr=llm_std, capsize=3, error_kw={'linewidth': 1.5})

    ax.set_ylabel('Classification Accuracy (%)')
    ax.set_title('Robustness: Accuracy Degradation Across Difficulty Tiers', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(tiers)
    ax.set_ylim(0, 110)

    # Degradation annotations
    ax.annotate('', xy=(2.22, 88), xytext=(0.22, 91.3),
        arrowprops=dict(arrowstyle='->', color=COLORS['llm'], lw=1.5, linestyle='--'))
    ax.text(1.3, 93, '−3.3 pts', color=COLORS['llm'], fontsize=8, fontweight='bold')

    ax.annotate('', xy=(2.0, 54.3), xytext=(0.0, 96.7),
        arrowprops=dict(arrowstyle='->', color=COLORS['auto_rule'], lw=1.5, linestyle='--'))
    ax.text(0.7, 78, '−42.4 pts', color=COLORS['auto_rule'], fontsize=8, fontweight='bold')

    ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(os.path.join(FIGDIR, 'fig3_tiers.png'), bbox_inches='tight')
    plt.close()
    print("fig3_tiers.png")


# ═══════════════════════════════════════════════════════════════════════════
# Figure 4: Consistency paradox — C_traj vs C_out
# ═══════════════════════════════════════════════════════════════════════════

def fig4_consistency():
    agents = ['Production\nrule-based', 'Auto-constructed\nrule-based', 'Auto-constructed\nLLM-based']
    c_traj = [100.0, 100.0, 97.4]
    c_out = [50.0, 100.0, 100.0]
    accuracy = [44.0, 75.5, 87.8]

    x = np.arange(len(agents))
    w = 0.25

    fig, ax1 = plt.subplots(figsize=(9, 5.5))

    b1 = ax1.bar(x - w/2, c_traj, w, label='C_traj (classification)', color='#93c5fd', edgecolor='white')
    b2 = ax1.bar(x + w/2, c_out, w, label='C_out (response)', color='#3b82f6', edgecolor='white')

    ax1.set_ylabel('Consistency (%)')
    ax1.set_title('The Consistency Paradox: C_traj vs C_out', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(agents)
    ax1.set_ylim(0, 115)

    # Accuracy overlay as line
    ax2 = ax1.twinx()
    ax2.plot(x, accuracy, 'o-', color='#ef4444', linewidth=2, markersize=8, label='Accuracy (%)')
    ax2.set_ylabel('Classification Accuracy (%)', color='#ef4444')
    ax2.tick_params(axis='y', labelcolor='#ef4444')
    ax2.set_ylim(0, 115)

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='lower right', fontsize=9, framealpha=0.9)

    # Annotation
    ax1.annotate('100% C_traj\nbut 50% C_out\n(consistently wrong)',
                 xy=(0, 50), xytext=(0.8, 30),
                 arrowprops=dict(arrowstyle='->', color='#374151'),
                 fontsize=8, color='#374151', ha='center')

    ax1.spines['top'].set_visible(False)
    ax2.spines['top'].set_visible(False)

    plt.tight_layout()
    plt.savefig(os.path.join(FIGDIR, 'fig4_consistency.png'), bbox_inches='tight')
    plt.close()
    print("fig4_consistency.png")


# ═══════════════════════════════════════════════════════════════════════════
# Figure 5: Construction trajectory
# ═══════════════════════════════════════════════════════════════════════════

def fig5_construction():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

    # Dev set accuracy during construction
    rb_iters = [0, 1, 2, 3]
    rb_acc = [79.7, 91.3, 97.1, 100.0]
    llm_iters = [0, 1, 2, 3]
    llm_acc = [95.7, 95.7, 98.6, 100.0]

    ax1.plot(rb_iters, rb_acc, 'o-', color=COLORS['auto_rule'], linewidth=2, markersize=8, label='Auto rule-based')
    ax1.plot(llm_iters, llm_acc, 's-', color=COLORS['llm'], linewidth=2, markersize=8, label='Auto LLM-based')
    ax1.set_xlabel('Iteration')
    ax1.set_ylabel('Dev Set Accuracy (%)')
    ax1.set_title('(a) Construction Trajectory', fontweight='bold')
    ax1.set_ylim(70, 105)
    ax1.set_xticks([0, 1, 2, 3])
    ax1.legend(fontsize=9)
    ax1.axhline(y=100, color='#d1d5db', linestyle='--', linewidth=0.8)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # Generalisation gap
    agents = ['Production\nrule-based', 'Auto\nrule-based', 'Auto\nLLM-based']
    dev = [100, 95.8, 100]
    eval_acc = [44.0, 75.5, 87.8]

    x = np.arange(len(agents))
    w = 0.3
    ax2.bar(x - w/2, dev, w, label='Dev set', color='#93c5fd', edgecolor='white')
    ax2.bar(x + w/2, eval_acc, w, label='Eval set (unseen)', color='#3b82f6', edgecolor='white')

    # Gap annotations
    for i in range(3):
        gap = dev[i] - eval_acc[i]
        ax2.annotate(f'−{gap:.0f}', xy=(i, eval_acc[i] + 1),
                     ha='center', va='bottom', fontsize=8, color='#dc2626', fontweight='bold')

    ax2.set_ylabel('Accuracy (%)')
    ax2.set_title('(b) Generalisation Gap (Dev → Eval)', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(agents)
    ax2.set_ylim(0, 115)
    ax2.legend(fontsize=9)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(os.path.join(FIGDIR, 'fig5_construction.png'), bbox_inches='tight')
    plt.close()
    print("fig5_construction.png")


# ═══════════════════════════════════════════════════════════════════════════
# Figure 6: Per-category accuracy heatmap
# ═══════════════════════════════════════════════════════════════════════════

def fig6_categories():
    categories = ['project', 'topic_search', 'univ_papers', 'researcher',
                  'glossary', 'meta', 'non_research', 'figure', 'gap',
                  'general', 'off_topic', 'followup']
    production = [100, 35, 75, 50, 5, 0, 0, 14, 24, 59, 79, 17]
    auto_rule = [100, 80, 88, 72, 68, 61, 70, 79, 71, 82, 79, 50]
    llm = [100, 100, 100, 89, 95, 89, 85, 93, 82, 77, 75, 67]

    data = np.array([production, auto_rule, llm])
    agents_labels = ['Production rule-based', 'Auto-constructed rule-based', 'Auto-constructed LLM-based']

    fig, ax = plt.subplots(figsize=(12, 4))
    im = ax.imshow(data, cmap='RdYlGn', aspect='auto', vmin=0, vmax=100)

    ax.set_xticks(np.arange(len(categories)))
    ax.set_yticks(np.arange(len(agents_labels)))
    ax.set_xticklabels(categories, rotation=45, ha='right', fontsize=9)
    ax.set_yticklabels(agents_labels, fontsize=10)

    # Text annotations
    for i in range(len(agents_labels)):
        for j in range(len(categories)):
            val = data[i, j]
            color = 'white' if val < 40 or val > 85 else 'black'
            ax.text(j, i, f'{val:.0f}', ha='center', va='center', fontsize=8,
                    fontweight='bold', color=color)

    ax.set_title('Per-Category Classification Accuracy (%) on Evaluation Set', fontweight='bold')
    fig.colorbar(im, ax=ax, label='Accuracy (%)', shrink=0.8)

    plt.tight_layout()
    plt.savefig(os.path.join(FIGDIR, 'fig6_categories.png'), bbox_inches='tight')
    plt.close()
    print("fig6_categories.png")


# ═══════════════════════════════════════════════════════════════════════════
# Generate all
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Generating figures...")
    fig1_architecture()
    fig2_rabanser()
    fig3_tiers()
    fig4_consistency()
    fig5_construction()
    fig6_categories()
    print(f"\nAll figures saved to {FIGDIR}/")
