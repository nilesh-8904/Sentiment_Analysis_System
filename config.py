# config.py — colors, fonts, and app-wide constants

PALETTE = {
    "bg":           "#0A0E1A",
    "bg2":          "#0D1220",
    "surface":      "#111827",
    "surface2":     "#1A2234",
    "border":       "#1E2D45",
    "border2":      "#243552",

    "accent":       "#00D4FF",
    "accent_dim":   "#0099CC",   # ← added this line
    "accent2":      "#7B61FF",
    "accent_glow":  "#00D4FF33",

    "positive":     "#00FF88",
    "positive_dim": "#00FF8833",

    "negative":     "#FF4466",
    "negative_dim": "#FF446633",

    "neutral":      "#FFB800",
    "neutral_dim":  "#FFB80033",

    "text":         "#CDD6F4",
    "text_muted":   "#45506B",
    "text_dim":     "#6B7A99",

    "highlight":    "#FFFFFF",
}

FONT_TITLE    = ("Consolas", 22, "bold")
FONT_SUBTITLE = ("Consolas", 10)
FONT_LABEL    = ("Consolas", 9, "bold")
FONT_BODY     = ("Consolas", 11)
FONT_RESULT   = ("Consolas", 30, "bold")
FONT_SCORE    = ("Consolas", 14, "bold")
FONT_SMALL    = ("Consolas", 9)
FONT_TINY     = ("Consolas", 8)
FONT_MONO     = ("Consolas", 10)

PLACEHOLDER_TEXT = "Paste or type text here…  (Ctrl+Enter to analyse)"

MODEL_NAME = "valhalla/distilbart-mnli-12-1"
EMOTION_LABELS = ["Happy", "Angry", "Sad", "Fear", "Surprise", "Neutral"]
TRANSLATION_MODELS = {
    "hi": "Helsinki-NLP/opus-mt-hi-en",
    "mr": "Helsinki-NLP/opus-mt-mr-en",
    "fr": "Helsinki-NLP/opus-mt-fr-en",
    "es": "Helsinki-NLP/opus-mt-es-en",
}
SUMMARY_MODEL = "sshleifer/distilbart-cnn-12-6"
MAX_TOKENS = 512
APP_VERSION = "v2.0"

POSITIVE_WORDS = [
    "love", "great", "excellent", "good", "amazing", "happy", "satisfied", "awesome", "best", "fantastic",
    "like", "wonderful", "pleased", "delighted", "enjoyed"
]
NEGATIVE_WORDS = [
    "hate", "bad", "terrible", "worst", "awful", "disappointed", "poor", "angry", "sad", "problem",
    "disgusting", "horrible", "annoying", "boring", "frustrating"
]