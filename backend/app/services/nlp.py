"""Sentence-BERT embeddings + FAISS vector store.

Every question is embedded once (normalised vectors). The FAISS index is an exact inner-product
index (cosine similarity). Question.vec_idx stores each question's position in the index.
"""
import re
import threading
import zlib
import numpy as np
import faiss
from ..config import EMBED_MODEL, INDEX_PATH


class HashingModel:
    """Tiny offline stand-in for Sentence-BERT (bag-of-words hashing). Used only when EMBED_MODEL=fake,
    so the automated tests run without downloading a model. Never use it for the real demo."""
    DIM = 128

    def get_sentence_embedding_dimension(self):
        return self.DIM

    def encode(self, texts, **kwargs):
        out = np.zeros((len(texts), self.DIM), dtype="float32")
        for i, t in enumerate(texts):
            for tok in re.findall(r"[a-z0-9]+", str(t).lower()):
                out[i, zlib.crc32(tok.encode()) % self.DIM] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.maximum(norms, 1e-9)


class VectorStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._model = None
        self._index = None
        self._timer = None

    @property
    def model(self):
        with self._lock:
            if self._model is None:
                if EMBED_MODEL == "fake":
                    self._model = HashingModel()
                else:
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(EMBED_MODEL)
            return self._model

    @property
    def index(self):
        with self._lock:
            if self._index is None:
                if INDEX_PATH.exists():
                    self._index = faiss.read_index(str(INDEX_PATH))
                else:
                    dim = self.model.get_sentence_embedding_dimension()
                    self._index = faiss.IndexFlatIP(dim)
            return self._index

    def embed(self, texts, batch_size: int = 128) -> np.ndarray:
        vecs = self.model.encode(list(texts), batch_size=batch_size, normalize_embeddings=True,
                                 show_progress_bar=False, convert_to_numpy=True)
        return np.asarray(vecs, dtype="float32")

    def add(self, vecs: np.ndarray) -> int:
        """Append vectors, return the index position of the first one."""
        with self._lock:
            start = self.index.ntotal
            self.index.add(vecs)
            return start

    def save(self):
        with self._lock:
            self._timer = None
            faiss.write_index(self.index, str(INDEX_PATH))

    def save_later(self, delay: float = 15.0):
        """Debounced save: many quick admin edits cause one disk write."""
        with self._lock:
            if self._timer is None:
                self._timer = threading.Timer(delay, self.save)
                self._timer.daemon = True
                self._timer.start()

    def flush(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self.save()

    def vectors(self, positions) -> np.ndarray:
        positions = np.asarray(positions, dtype="int64")
        with self._lock:
            idx = self.index
            if hasattr(idx, "reconstruct_batch"):
                return idx.reconstruct_batch(positions)
            return np.vstack([idx.reconstruct(int(p)) for p in positions])

    @property
    def total(self) -> int:
        return self.index.ntotal


store = VectorStore()
