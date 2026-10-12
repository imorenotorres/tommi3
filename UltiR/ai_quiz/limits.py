"""Caps of the AI Quiz tool. Code reads them as `limits.NAME` at the time of use."""

# Uploads
ALLOWED_EXTENSIONS = (".pdf", ".md", ".txt")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_DOCUMENTS_PER_COURSE = 50
MAX_LABEL_CHARS = 120

# Reading
MAX_PAGES = 300
MAX_TEXT_CHARS = 1_500_000

# Full reading (formulas, figures): slow, so it runs as a background job
MAX_FULL_READING_PAGES = 40     # about 40 s per page without a graphics card
FULL_READING_SECONDS = 45 * 60  # per document; the job is stopped after this
MAX_FORMULA_CHARS = 600         # a longer "formula" is a block of text that was misread as one
MIN_FIGURE_PIXELS = 100         # smaller in either direction: a logo, not a figure
MAX_FIGURES_PER_DOCUMENT = 60
MAX_FIGURE_BYTES = 3 * 1024 * 1024
MAX_CAPTION_CHARS = 500

# Generation
MAX_QUESTIONS_PER_REQUEST = 15
MAX_DOCS_PER_REQUEST = 5
MAX_TOPIC_CHARS = 200
MAX_TITLE_CHARS = 200
QUESTIONS_PER_CALL = 5          # a large request is split into calls of this many questions
SOURCES_PER_CALL = 6            # chunks handed to the model in one call
MAX_MODEL_ATTEMPTS = 3          # calls for one batch, the first one included
MAX_OUTPUT_TOKENS = 3000        # reply length asked of the model, per call
MAX_REPLY_CHARS = 60_000        # anything longer is not read at all
MODEL_TIMEOUT_SECONDS = 60      # per call
MAX_GENERATIONS_PER_HOUR = 20   # per course, failed ones included

# Quizzes
MAX_QUIZZES_PER_COURSE = 100
MAX_QUESTIONS_PER_QUIZ = 60
MAX_QUESTION_CHARS = 600
MAX_OPTION_CHARS = 300
MAX_EXPLANATION_CHARS = 800
MAX_EXCERPT_CHARS = 600
MIN_EXCERPT_LETTERS = 30        # a located excerpt shorter than this proves nothing

# Analysis of the class summary by the model
MAX_ANALYSIS_POINTS = 4         # points kept from one reply
MAX_ANALYSIS_POINT_CHARS = 400  # a longer point is dropped, never cut
MAX_ANALYSIS_ATTEMPTS = 2       # calls for one analysis, the first one included
MAX_ANALYSIS_TOKENS = 700       # reply length asked of the model

# Attempts
MAX_ATTEMPTS_PER_QUIZ = 50      # per learner and quiz
