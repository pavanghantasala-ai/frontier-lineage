import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from .paths import CORPUS
from .text import tokens


@dataclass
class Chunk:
    doc_id: str
    title: str
    section: str
    text: str
    contextual: bool

    @property
    def index_text(self):
        if self.contextual:
            return f"{self.title}. {self.section}. {self.text}"
        return self.text


def load_docs():
    docs = {}
    for path in sorted(CORPUS.glob("*.md")):
        docs[path.stem] = path.read_text()
    return docs


def chunk_docs(chunk_size, contextual):
    chunks = []
    for doc_id, text in load_docs().items():
        title = re.search(r"^# (.+)$", text, re.M).group(1)
        for block in re.split(r"^## ", text, flags=re.M)[1:]:
            section, _, body = block.partition("\n")
            words = body.split()
            for i in range(0, len(words), chunk_size):
                chunks.append(Chunk(doc_id, title, section.strip(), " ".join(words[i : i + chunk_size]), contextual))
    return chunks


class BM25:
    def __init__(self, chunks, k1=1.5, b=0.75):
        self.chunks = chunks
        self.docs = [tokens(c.index_text) for c in chunks]
        self.avg = sum(map(len, self.docs)) / max(1, len(self.docs))
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in self.docs]
        self.k1, self.b = k1, b

    def search(self, query, k):
        q = tokens(query)
        scores = []
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i])
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avg))
            scores.append((s, i))
        scores.sort(reverse=True)
        return [self.chunks[i] for s, i in scores[:k] if s > 0]


@lru_cache(maxsize=32)
def get_index(chunk_size, contextual):
    return BM25(chunk_docs(chunk_size, contextual))
