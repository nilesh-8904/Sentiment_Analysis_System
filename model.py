# model.py — loads and runs the HuggingFace sentiment pipeline

import threading

try:
    from transformers import pipeline as hf_pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

from config import MODEL_NAME, EMOTION_LABELS, MAX_TOKENS


class SentimentModel:
    """Wraps the HuggingFace pipeline; loads in a background thread."""

    def __init__(self, on_ready=None, on_error=None):
        self._pipe     = None
        self._on_ready = on_ready
        self._on_error = on_error

        if not TRANSFORMERS_AVAILABLE:
            if self._on_error:
                self._on_error(
                    "transformers not installed.\n"
                    "Run:  pip install transformers torch"
                )
            return

        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            self._pipe = hf_pipeline("zero-shot-classification", model=MODEL_NAME)
            if self._on_ready:
                self._on_ready()
        except Exception as exc:
            if self._on_error:
                self._on_error(str(exc))

    @property
    def ready(self):
        return self._pipe is not None

    def predict(self, text: str) -> dict:
        if not self.ready:
            raise RuntimeError("Model is not loaded yet.")
        result = self._pipe(text[:MAX_TOKENS], candidate_labels=EMOTION_LABELS)
        return {
            "label": result["labels"][0],
            "score": result["scores"][0],
        }