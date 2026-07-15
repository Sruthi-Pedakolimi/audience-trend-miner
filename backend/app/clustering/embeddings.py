from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from app.agent.schemas import Article

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def article_text(article: Article) -> str:
    categories = ", ".join(article.categories)
    return f"{article.title}. {article.summary} Categories: {categories}"


def embed_articles(articles: list[Article]) -> np.ndarray:
    texts = [article_text(article) for article in articles]
    return _get_model().encode(texts, convert_to_numpy=True)
