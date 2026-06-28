#!/usr/bin/env python3
"""Generate the architecture figure for the web page — two panels + classification variants."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os

FIGDIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIGDIR, exist_ok=True)

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 11,
    'figure.dpi': 200,
})


def draw_box(ax, x, y, w, h, label, fc, ec, lw=2, fontsize=10, sublabel=None):
    ax.add_patch(mpatches.FancyBboxPatch((x - w/2, y - h/2), w, h,
        boxstyle="round,pad=0.15", facecolor=fc, edgecolor=ec, linewidth=lw))
    ax.text(x, y + (0.15 if sublabel else 0), label,
            ha='center', va='center', fontsize=fontsize, fontweight='bold')
    if sublabel:
        ax.text(x, y - 0.3, sublabel, ha='center', va='center',
                fontsize=7.5, color='#374151', style='italic')


def arrow(ax, x1, y1, x2, y2, color='#374151', lw=2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle='->', color=color, lw=lw))


fig = plt.figure(figsize=(16, 8))

# Layout: two architecture panels on top, classification variants below
ax1 = fig.add_axes([0.02, 0.35, 0.30, 0.60])   # Vanilla RAG
ax2 = fig.add_axes([0.36, 0.35, 0.62, 0.60])    # Classified RAG
ax3 = fig.add_axes([0.05, 0.02, 0.90, 0.28])     # Classification variants

# ── (a) Vanilla RAG ──
ax1.set_xlim(0, 10)
ax1.set_ylim(0, 10)
ax1.set_aspect('equal')
ax1.axis('off')
ax1.set_title('(a) Vanilla RAG', fontweight='bold', fontsize=13, pad=10)

draw_box(ax1, 5, 8.5, 4.5, 1.2, 'User Query', '#e0e7ff', '#4f46e5')
draw_box(ax1, 5, 6.3, 4.5, 1.2, 'BM25 Retrieval', '#fef3c7', '#d97706')
draw_box(ax1, 5, 4.1, 4.5, 1.2, 'LLM Generation', '#fee2e2', '#dc2626')
draw_box(ax1, 5, 1.9, 4.5, 1.2, 'Response', '#e0e7ff', '#4f46e5')

arrow(ax1, 5, 7.9, 5, 6.9)
arrow(ax1, 5, 5.7, 5, 4.7)
arrow(ax1, 5, 3.5, 5, 2.5)

ax1.text(5, 0.6, 'Every query follows the\nsame path (no classification)',
         ha='center', va='center', fontsize=9, color='#6b7280', style='italic')

# ── (b) Classified RAG ──
ax2.set_xlim(0, 16)
ax2.set_ylim(0, 10)
ax2.set_aspect('equal')
ax2.axis('off')
ax2.set_title('(b) Classified RAG', fontweight='bold', fontsize=13, pad=10)

# Query
draw_box(ax2, 8, 9.0, 4.5, 1.0, 'User Query', '#e0e7ff', '#4f46e5')

# Classification — dashed border to indicate "this is the variable"
ax2.add_patch(mpatches.FancyBboxPatch((4.5, 6.8), 7, 1.2,
    boxstyle="round,pad=0.15", facecolor='#f0f9ff', edgecolor='#2563eb',
    linewidth=2.5, linestyle='--'))
ax2.text(8, 7.6, 'Classification', ha='center', va='center',
         fontsize=11, fontweight='bold', color='#2563eb')
ax2.text(8, 7.1, '(see variants below)', ha='center', va='center',
         fontsize=8, color='#6b7280', style='italic')
arrow(ax2, 8, 8.5, 8, 8.0)

# Left branch — Programmatic
draw_box(ax2, 3.5, 5.0, 6, 1.5, 'Programmatic Paths', '#d1fae5', '#059669',
         sublabel='meta, glossary, researcher, project, off_topic, non_research')

# Right branch — BM25 + LLM
draw_box(ax2, 12.5, 5.5, 4.5, 0.9, 'BM25 Retrieval', '#fef3c7', '#d97706', fontsize=9)
draw_box(ax2, 12.5, 4.2, 4.5, 0.9, 'LLM Generation', '#fee2e2', '#dc2626', fontsize=9)
arrow(ax2, 12.5, 5.05, 12.5, 4.65, color='#374151', lw=1.5)

# Arrows from classification to branches
arrow(ax2, 6, 6.8, 3.5, 5.75, color='#059669')
arrow(ax2, 10, 6.8, 12.5, 5.95, color='#dc2626')

# Response
draw_box(ax2, 8, 2.0, 4.5, 1.0, 'Response', '#e0e7ff', '#4f46e5')
arrow(ax2, 3.5, 4.25, 6.5, 2.5, color='#059669')
arrow(ax2, 12.5, 3.75, 9.5, 2.5, color='#dc2626')

# Labels
ax2.text(2.0, 3.2, 'Deterministic\n(no LLM, zero hallucination)',
         ha='center', va='center', fontsize=8, color='#059669', style='italic')
ax2.text(14.0, 3.2, 'topic_search, gap,\ngeneral, followup',
         ha='center', va='center', fontsize=8, color='#991b1b')

# ── Arrow between panels ──
fig.text(0.175, 0.32, 'adds classification\n+ response paths',
         ha='center', va='top', fontsize=9, fontweight='bold', color='#059669',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#d1fae5', edgecolor='#059669', lw=1.5))

# ── (c) Classification variants ──
ax3.set_xlim(0, 30)
ax3.set_ylim(0, 5)
ax3.axis('off')
ax3.set_title('Three Classification Approaches Compared', fontweight='bold', fontsize=12, pad=8)

# Production rule-based
ax3.add_patch(mpatches.FancyBboxPatch((0.5, 0.8), 8.5, 3.2,
    boxstyle="round,pad=0.3", facecolor='#f3f4f6', edgecolor='#9ca3af', linewidth=2))
ax3.text(4.75, 3.4, 'Production Rule-based', ha='center', va='center',
         fontsize=10, fontweight='bold', color='#374151')
ax3.text(4.75, 2.6, 'Hand-crafted patterns\n~60 synonym mappings\nReactive feedback (months)',
         ha='center', va='center', fontsize=8, color='#6b7280', linespacing=1.5)
ax3.add_patch(mpatches.FancyBboxPatch((1.5, 0.9), 6.5, 0.7,
    boxstyle="round,pad=0.1", facecolor='#d1fae5', edgecolor='#059669', linewidth=1))
ax3.text(4.75, 1.25, 'Deterministic', ha='center', va='center',
         fontsize=8, fontweight='bold', color='#059669')

# Auto-constructed rule-based
ax3.add_patch(mpatches.FancyBboxPatch((10.5, 0.8), 8.5, 3.2,
    boxstyle="round,pad=0.3", facecolor='#fffbeb', edgecolor='#f59e0b', linewidth=2))
ax3.text(14.75, 3.4, 'Auto-constructed Rule-based', ha='center', va='center',
         fontsize=10, fontweight='bold', color='#92400e')
ax3.text(14.75, 2.6, 'Broad word-class patterns\n~35 synonym families\nBatch feedback (hours)',
         ha='center', va='center', fontsize=8, color='#6b7280', linespacing=1.5)
ax3.add_patch(mpatches.FancyBboxPatch((11.5, 0.9), 6.5, 0.7,
    boxstyle="round,pad=0.1", facecolor='#d1fae5', edgecolor='#059669', linewidth=1))
ax3.text(14.75, 1.25, 'Deterministic', ha='center', va='center',
         fontsize=8, fontweight='bold', color='#059669')

# Auto-constructed LLM-based
ax3.add_patch(mpatches.FancyBboxPatch((20.5, 0.8), 8.5, 3.2,
    boxstyle="round,pad=0.3", facecolor='#eff6ff', edgecolor='#3b82f6', linewidth=2))
ax3.text(24.75, 3.4, 'Auto-constructed LLM-based', ha='center', va='center',
         fontsize=10, fontweight='bold', color='#1e40af')
ax3.text(24.75, 2.6, 'Separate LLM call\nPre-trained knowledge\nBatch feedback (hours)',
         ha='center', va='center', fontsize=8, color='#6b7280', linespacing=1.5)
ax3.add_patch(mpatches.FancyBboxPatch((21.5, 0.9), 6.5, 0.7,
    boxstyle="round,pad=0.1", facecolor='#fef3c7', edgecolor='#d97706', linewidth=1))
ax3.text(24.75, 1.25, 'Non-deterministic', ha='center', va='center',
         fontsize=8, fontweight='bold', color='#d97706')

plt.savefig(os.path.join(FIGDIR, 'fig_web_architecture.png'), bbox_inches='tight')
plt.close()
print("fig_web_architecture.png saved")
