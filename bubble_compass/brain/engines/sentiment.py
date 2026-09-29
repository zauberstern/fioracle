"""Layer 4: FinBERT sentiment velocity overlay."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)

try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    import torch

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    torch = None
    logger.warning("transformers/torch not installed. Sentiment layer will use placeholders.")


@dataclass
class SentimentOutput:
    effective_date: pd.Timestamp
    sentiment_level: float
    sentiment_velocity: float
    headline_count: int


class SentimentEngine:
    def __init__(
        self,
        model_name: str = "ProsusAI/finbert",
        velocity_window: int = 5,
        device: str = "cpu",
    ):
        self.model_name = model_name
        self.velocity_window = velocity_window
        self.device = device
        self._model = None
        self._tokenizer = None

    def _load_model(self) -> None:
        if not TRANSFORMERS_AVAILABLE:
            return
        if self._model is None:
            logger.info("Loading FinBERT model: %s", self.model_name)
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self._model.to(self.device)
            self._model.eval()

    def score_headline(self, headline: str) -> float:
        if not TRANSFORMERS_AVAILABLE or self._model is None:
            return 0.0
        inputs = self._tokenizer(
            headline, return_tensors="pt", truncation=True, max_length=512
        ).to(self.device)
        with torch.no_grad():
            outputs = self._model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)
        neg, _neu, pos = probs[0].cpu().numpy()
        return float(pos - neg)

    def score_headlines_batch(self, headlines: list[str]) -> list[float]:
        self._load_model()
        if not TRANSFORMERS_AVAILABLE or self._model is None:
            return [0.0] * len(headlines)
        batch_size = 32
        scores: list[float] = []
        for i in range(0, len(headlines), batch_size):
            batch = headlines[i : i + batch_size]
            inputs = self._tokenizer(
                batch,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=512,
            ).to(self.device)
            with torch.no_grad():
                outputs = self._model(**inputs)
                probs = torch.softmax(outputs.logits, dim=-1)
            for prob in probs.cpu().numpy():
                neg, _neu, pos = prob
                scores.append(float(pos - neg))
        return scores

    def compute(
        self,
        headlines_df: pd.DataFrame,
        as_of_date: pd.Timestamp,
        ticker: str | None = None,
    ) -> SentimentOutput:
        as_of = pd.Timestamp(as_of_date)
        df = headlines_df.copy()
        if df.empty:
            return SentimentOutput(as_of, 0.0, 0.0, 0)
        date_col = "date" if "date" in df.columns else "published_at"
        if date_col not in df.columns:
            return SentimentOutput(as_of, 0.0, 0.0, 0)
        df["date"] = pd.to_datetime(df[date_col])
        df = df[df["date"] <= as_of]
        if ticker is not None and "ticker" in df.columns:
            df = df[df["ticker"] == ticker]
        if df.empty:
            return SentimentOutput(as_of, 0.0, 0.0, 0)

        if "sentiment_score" not in df.columns:
            df["sentiment_score"] = self.score_headlines_batch(df["headline"].tolist())

        daily = df.groupby("date").agg({"sentiment_score": "mean", "headline": "count"})
        daily = daily.rename(columns={"headline": "count"})
        daily["velocity"] = (
            daily["sentiment_score"].diff().rolling(window=self.velocity_window, min_periods=1).mean()
        )
        recent = daily[daily.index <= as_of]
        if recent.empty:
            return SentimentOutput(as_of, 0.0, 0.0, 0)
        row = recent.iloc[-1]
        level = row["sentiment_score"]
        velocity = row["velocity"]
        count = int(row["count"])
        return SentimentOutput(
            effective_date=as_of,
            sentiment_level=float(level) if pd.notna(level) else 0.0,
            sentiment_velocity=float(velocity) if pd.notna(velocity) else 0.0,
            headline_count=count,
        )
