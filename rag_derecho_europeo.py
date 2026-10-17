from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

BLUE_DARK  = RGBColor(0x0D, 0x47, 0xA1)
BLUE_MID   = RGBColor(0x15, 0x65, 0xC0)
BLUE_LIGHT = RGBColor(0xE3, 0xF2, 0xFD)
GOLD       = RGBColor(0xFF, 0xD6, 0x00)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
GRAY_DARK  = RGBColor(0x37, 0x47, 0x4F)
GRAY_LIGHT = RGBColor(0xF5, 0xF5, 0xF5)

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)
blank_layout = prs.slide_layouts[6]

def add_rect(slide, left, top, width, height, fill_color=None):
    shape = slide.shapes.add_shape(
        1, Inches(left), Inches(top), Inches(width), Inches(height)
    )
    if fill_color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_color
    else:
        shape.fill.background()
    shape.line.fill.background()
    return shape

def add_text(slide, text, left, top, width, height,
             font_size=18, bold=False, color=None,
             align=PP_ALIGN.LEFT, italic=False):
    txBox = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = "Calibri"
    if color:
        run.font.color.rgb = color
    return txBox

def add_bullets(slide, items, left, top, width, height,
                font_size=14, color=None, bg=None, title=None):
    if bg:
        add_rect(slide, left, top, width, height, fill_color=bg)
    box = slide.shapes.add_textbox(
        Inches(left + 0.12), Inches(top + 0.08),
        Inches(width - 0.24), Inches(height - 0.16)
    )
    tf = box.text_frame
    tf.word_wrap = True
    first = True
    if title:
        p = tf.paragraphs[0]
        first = False
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(font_size + 1)
        run.font.bold = True
        run.font.name = "Calibri"
        if color:
            run.font.color.rgb = color
    for item in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_before = Pt(2)
        run = p.add_run()
        run.text = item
        run.font.size = Pt(font_size)
        run.font.name = "Calibri"
        if color:
            run.font.color.rgb = color


# ── SLIDE 1 · Title ──────────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, 13.33, 7.5, fill_color=BLUE_DARK)
add_rect(slide, 0, 5.8, 13.33, 0.18, fill_color=GOLD)

add_text(slide, "* * * * * * * * * * * *",
         0.5, 0.35, 12, 0.5, font_size=16, color=GOLD, align=PP_ALIGN.CENTER)
add_text(slide, "RAG aplicado al Derecho Europeo",
         0.8, 1.3, 11.7, 1.2, font_size=40, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
add_text(slide, "para estudiantes de Ciencia de Datos",
         0.8, 2.55, 11.7, 0.8, font_size=26, color=GOLD, align=PP_ALIGN.CENTER)
add_text(slide, "Retrieval-Augmented Generation  |  Aprendizaje activo  |  Normativa vigente",
         0.8, 3.5, 11.7, 0.6, font_size=17, italic=True, color=WHITE, align=PP_ALIGN.CENTER)
add_text(slide, "* * * * * * * * * * * *",
         0.5, 6.1, 12, 0.5, font_size=16, color=GOLD, align=PP_ALIGN.CENTER)


# ── SLIDE 2 · Por que Derecho Europeo ───────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, 13.33, 1.1, fill_color=BLUE_DARK)
add_rect(slide, 0, 1.1, 13.33, 0.06, fill_color=GOLD)
add_text(slide, "Por que Derecho Europeo para Ciencia de Datos?",
         0.3, 0.1, 12.7, 0.9, font_size=26, bold=True, color=WHITE)

cards = [
    ("RGPD (2016/679)", [
        "Base legal de todo proyecto",
        "que use datos personales",
        "Consentimiento, anonimizacion,",
        "minimizacion de datos",
        "Multas hasta 4% facturacion",
        "global o 20 M EUR",
    ]),
    ("AI Act (2024/1689)", [
        "1a regulacion mundial de la IA",
        "por nivel de riesgo",
        "Obligaciones para sistemas",
        "de alto riesgo",
        "Prohibiciones absolutas",
        "En vigor agosto 2024",
    ]),
    ("Data Act / DGA", [
        "Acceso a datos industriales",
        "y dispositivos IoT",
        "Gobernanza: intermediarios,",
        "altruismo de datos",
        "Espacios europeos de datos",
        "Datos abiertos del sector publico",
    ]),
]
for i, (title, bullets) in enumerate(cards):
    x = 0.3 + i * 4.35
    add_rect(slide, x, 1.35, 4.1, 5.85, fill_color=BLUE_LIGHT)
    add_rect(slide, x, 1.35, 4.1, 0.7, fill_color=BLUE_MID)
    add_text(slide, title, x + 0.1, 1.38, 3.9, 0.65,
             font_size=17, bold=True, color=WHITE)
    add_bullets(slide, ["- " + b for b in bullets],
                x, 2.1, 4.1, 5.0, font_size=14, color=GRAY_DARK)


# ── SLIDE 3 · Que es RAG ─────────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, 13.33, 1.1, fill_color=BLUE_DARK)
add_rect(slide, 0, 1.1, 13.33, 0.06, fill_color=GOLD)
add_text(slide, "Que es RAG y por que es ideal para el Derecho?",
         0.3, 0.1, 12.7, 0.9, font_size=26, bold=True, color=WHITE)

flow = [
    ("Documentos\nlegales", 0.4),
    ("Busqueda\nsemantica", 3.1),
    ("LLM genera\nrespuesta", 5.8),
    ("Respuesta\ncitada", 8.5),
]
for label, x in flow:
    add_rect(slide, x, 1.5, 2.4, 1.55, fill_color=BLUE_MID)
    add_text(slide, label, x + 0.05, 1.58, 2.3, 1.4,
             font_size=15, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
for x in [2.85, 5.55, 8.25]:
    add_text(slide, "->", x, 2.0, 0.3, 0.7,
             font_size=26, bold=True, color=BLUE_DARK, align=PP_ALIGN.CENTER)

add_rect(slide, 0.4, 3.3, 12.5, 3.9, fill_color=GRAY_LIGHT)
add_text(slide, "Por que RAG es perfecto para derecho?",
         0.6, 3.4, 11, 0.5, font_size=17, bold=True, color=BLUE_DARK)
add_bullets(slide, [
    "[OK]  Cita las fuentes: el estudiante puede verificar en el texto original del reglamento",
    "[OK]  Respuestas actualizadas: si la norma cambia, basta actualizar el documento base",
    "[OK]  No alucina articulos: el modelo solo usa lo que esta en el corpus legal",
    "[OK]  Diferencia versiones: RGPD vs AI Act vs Data Act sin confundirlos",
    "[OK]  Adaptable por asignatura: privacidad, gobernanza, etica, seguridad...",
], 0.4, 3.95, 12.5, 3.2, font_size=14, color=GRAY_DARK)


# ── SLIDE 4 · Corpus legal ───────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, 13.33, 1.1, fill_color=BLUE_DARK)
add_rect(slide, 0, 1.1, 13.33, 0.06, fill_color=GOLD)
add_text(slide, "Corpus legal: normativa europea relevante para datos e IA",
         0.3, 0.1, 12.7, 0.9, font_size=26, bold=True, color=WHITE)

rows = [
    ("RGPD (2016/679)",       "2018",    "Proteccion datos personales. Base de todo tratamiento de datos."),
    ("AI Act (2024/1689)",    "2024",    "Regulacion de sistemas IA por nivel de riesgo (prohibido / alto / limitado / minimo)."),
    ("Data Governance Act",   "2022",    "Gobernanza: intermediarios de datos, altruismo, reutilizacion datos publicos."),
    ("Data Act (2023/2854)",  "2024",    "Acceso a datos generados por IoT. Portabilidad y comparticion industrial."),
    ("Directiva NIS2",        "2022",    "Ciberseguridad de entidades esenciales e importantes. Notificacion de incidentes."),
    ("ePrivacy (propuesta)",  "Pendiente","Privacidad en comunicaciones: cookies, metadatos, comunicaciones M2M."),
    ("Regl. Europeo de Chips","2023",    "Soberania tecnologica: produccion de semiconductores en Europa."),
]
headers = ["Norma", "En vigor", "Relevancia para Ciencia de Datos"]
col_w   = [3.1, 1.2, 8.7]
col_x   = [0.25, 3.4, 4.65]
y = 1.28

for j, (col, w, x) in enumerate(zip(headers, col_w, col_x)):
    add_rect(slide, x, y, w, 0.44, fill_color=BLUE_MID)
    add_text(slide, col, x + 0.06, y + 0.03, w - 0.12, 0.38,
             font_size=13, bold=True, color=WHITE)
y += 0.44
for i, (norma, vigor, desc) in enumerate(rows):
    bg = BLUE_LIGHT if i % 2 == 0 else WHITE
    rh = 0.6
    for val, w, x in zip([norma, vigor, desc], col_w, col_x):
        add_rect(slide, x, y, w, rh, fill_color=bg)
        add_text(slide, val, x + 0.06, y + 0.05, w - 0.12, rh - 0.1,
                 font_size=12, bold=(val == norma), color=GRAY_DARK)
    y += rh


# ── SLIDE 5 · Casos de uso ───────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, 13.33, 1.1, fill_color=BLUE_DARK)
add_rect(slide, 0, 1.1, 13.33, 0.06, fill_color=GOLD)
add_text(slide, "Casos de uso: que puede hacer el estudiante",
         0.3, 0.1, 12.7, 0.9, font_size=26, bold=True, color=WHITE)

use_cases = [
    ("Consulta legal interactiva",
     "Pregunta: 'Necesito consentimiento explicito para entrenar un modelo con datos de clientes?'\n"
     "-> El RAG localiza el articulo 6 RGPD y explica las bases legales disponibles.",
     0.3, 1.3),
    ("Analisis de escenario",
     "El sistema genera un supuesto real (empresa, dataset, pais) y el estudiante\n"
     "determina que normativa aplica y que obligaciones conlleva.",
     6.9, 1.3),
    ("Comparador de normas",
     "Pregunta: 'En que se diferencia el RGPD del AI Act para sistemas de deteccion facial?'\n"
     "-> Respuesta estructurada citando ambos reglamentos con referencias exactas.",
     0.3, 4.05),
    ("Generador de checklist",
     "Dado un proyecto de ML descrito por el estudiante, el RAG genera\n"
     "un checklist de cumplimiento normativo con referencias a articulos especificos.",
     6.9, 4.05),
]
for title, body, x, y in use_cases:
    add_rect(slide, x, y, 6.3, 2.5, fill_color=BLUE_LIGHT)
    add_rect(slide, x, y, 6.3, 0.55, fill_color=BLUE_MID)
    add_text(slide, title, x + 0.1, y + 0.06, 6.1, 0.46,
             font_size=15, bold=True, color=WHITE)
    add_text(slide, body, x + 0.1, y + 0.65, 6.1, 1.75,
             font_size=13, color=GRAY_DARK)


# ── SLIDE 6 · Arquitectura ───────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, 13.33, 1.1, fill_color=BLUE_DARK)
add_rect(slide, 0, 1.1, 13.33, 0.06, fill_color=GOLD)
add_text(slide, "Arquitectura del sistema",
         0.3, 0.1, 12.7, 0.9, font_size=26, bold=True, color=WHITE)

cols = [
    (0.3,  3.6, BLUE_DARK,  "Corpus legal", [
        "RGPD (EUR-Lex PDF)",
        "AI Act (texto consolidado)",
        "Data Act / DGA",
        "NIS2",
        "Sentencias relevantes",
        "Guias AEPD / EDPB",
        "Considerandos + articulos",
    ]),
    (4.2,  4.9, BLUE_MID, "Pipeline RAG", [
        "1. Chunking por articulo",
        "   (preserva estructura legal)",
        "2. Embeddings multilingue",
        "   (paraphrase-multilingual)",
        "3. Vector store (ChromaDB)",
        "4. Retrieval semantico top-k",
        "5. Prompt con contexto",
        "   + historial conversacion",
        "6. LLM genera respuesta",
        "   citando articulo y norma",
    ]),
    (9.35, 3.7, BLUE_DARK, "Interfaz estudiante", [
        "Chat conversacional",
        "Fuentes citadas en",
        "  cada respuesta",
        "Ejercicios con correccion",
        "  automatica",
        "Progreso por norma",
        "LLM-as-judge:",
        "  responde del corpus?",
        "Integracion Moodle LTI 1.3",
    ]),
]
for x, w, hdr_color, title, bullets in cols:
    add_rect(slide, x, 1.3, w, 5.9, fill_color=BLUE_LIGHT)
    add_rect(slide, x, 1.3, w, 0.55, fill_color=hdr_color)
    add_text(slide, title, x + 0.1, 1.33, w - 0.2, 0.5,
             font_size=14, bold=True, color=WHITE)
    add_bullets(slide, ["- " + b for b in bullets],
                x, 1.88, w, 5.3, font_size=12, color=GRAY_DARK)

add_text(slide, "->", 3.92, 3.9, 0.32, 0.6,
         font_size=26, bold=True, color=BLUE_DARK, align=PP_ALIGN.CENTER)
add_text(slide, "->", 9.08, 3.9, 0.32, 0.6,
         font_size=26, bold=True, color=BLUE_DARK, align=PP_ALIGN.CENTER)


# ── SLIDE 7 · Como aprende el estudiante ─────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, 13.33, 1.1, fill_color=BLUE_DARK)
add_rect(slide, 0, 1.1, 13.33, 0.06, fill_color=GOLD)
add_text(slide, "Como aprende el estudiante?",
         0.3, 0.1, 12.7, 0.9, font_size=26, bold=True, color=WHITE)

levels = [
    ("Nivel 1 - Consulta libre",
     "El estudiante pregunta libremente sobre la normativa.\n"
     "El sistema responde citando el articulo exacto.\n"
     "Ideal para resolver dudas de clase o TFG.",
     "[VERDE] Exploracion"),
    ("Nivel 2 - Escenario guiado",
     "Se presenta un caso real: empresa, tipo de datos, pais.\n"
     "El estudiante determina que norma aplica y por que.\n"
     "El RAG evalua el razonamiento con LLM-as-judge.",
     "[AMARILLO] Aplicacion"),
    ("Nivel 3 - Caso abierto",
     "El estudiante disenha un proyecto de ML completo.\n"
     "Identifica riesgos, obligaciones y medidas tecnicas.\n"
     "El tutor genera feedback estructurado por seccion.",
     "[ROJO] Analisis critico"),
]
for i, (title, body, badge) in enumerate(levels):
    y = 1.38 + i * 1.9
    add_rect(slide, 0.3, y, 12.7, 1.78, fill_color=BLUE_LIGHT)
    add_rect(slide, 0.3, y, 3.0, 1.78, fill_color=BLUE_MID)
    add_text(slide, title, 0.42, y + 0.08, 2.78, 0.75,
             font_size=14, bold=True, color=WHITE)
    add_text(slide, badge, 0.42, y + 1.15, 2.78, 0.52,
             font_size=13, italic=True, color=GOLD)
    add_text(slide, body, 3.45, y + 0.18, 9.4, 1.5,
             font_size=14, color=GRAY_DARK)


# ── SLIDE 8 · Proximos pasos ─────────────────────────────────────────────────
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, 13.33, 7.5, fill_color=BLUE_DARK)
add_rect(slide, 0, 5.8, 13.33, 0.18, fill_color=GOLD)
add_text(slide, "* * * * * * * * * * * *",
         0.5, 0.35, 12, 0.5, font_size=16, color=GOLD, align=PP_ALIGN.CENTER)
add_text(slide, "Proximos pasos",
         1, 1.1, 11.3, 0.85, font_size=34, bold=True,
         color=WHITE, align=PP_ALIGN.CENTER)
add_bullets(slide, [
    "1.  Seleccionar asignatura piloto (Privacidad, Etica IA, Gobernanza de datos...)",
    "2.  Construir corpus: RGPD + AI Act + guias EDPB en EUR-Lex (open access)",
    "3.  Adaptar la arquitectura RAG existente (base_RAGagent.py)",
    "4.  Disenar banco de casos practicos por norma y nivel de complejidad",
    "5.  Integrar via LTI 1.3 en el Moodle de la asignatura",
    "6.  Evaluacion con LLM-as-judge: responde del corpus o alucina?",
], 1.5, 2.15, 10.3, 3.3, font_size=16, color=WHITE)
add_text(slide, "Con que asignatura empezamos?",
         1, 5.3, 11.3, 0.6, font_size=20, italic=True,
         color=GOLD, align=PP_ALIGN.CENTER)
add_text(slide, "* * * * * * * * * * * *",
         0.5, 6.1, 12, 0.5, font_size=16, color=GOLD, align=PP_ALIGN.CENTER)


prs.save("/Users/ignaciomoreno-torres/tommi3/RAG_Derecho_Europeo_DataScience.pptx")
print("Guardado correctamente.")
