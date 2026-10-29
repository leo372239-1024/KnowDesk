"""Embedding 抽象：dense 向量化。

- FakeEmbedding：确定性哈希向量，无 ML 依赖，用于测试与离线 demo。
- OpenAICompatEmbedding：OpenAI 兼容 HTTP embedding（DashScope text-embedding-v4 等）。
- SentenceTransformerEmbedding：真实 BGE-M3，需 [ml] 可选依赖。
"""
import hashlib
import math
import re
from abc import ABC, abstractmethod

import httpx
import jieba
import jieba.posseg as pseg

from app.core.config import settings

# 中文停用词 + 疑问/功能词：用于「查询内容覆盖度」计算时剥离无信息量词元。
STOP_WORDS: frozenset[str] = frozenset(
    {
        "的", "了", "是", "在", "为", "和", "与", "或", "及", "等", "对", "向", "从",
        "多少", "吗", "呢", "啊", "吧", "呀", "么", "哪", "什么", "怎么", "如何",
        "一个", "这个", "那个", "哪些", "请问", "请问一下", "一下", "我", "你", "他",
        "它", "我们", "你们", "他们", "请", "要", "会", "能", "可以", "应该", "需要",
        "中", "上", "下", "里", "内", "外", "有", "无", "不", "都", "也", "就",
        "共", "每", "各", "这", "那", "其", "该", "分别", "什么", "几", "多",
    }
)

_MEANINGFUL_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")
_PUNCT_ONLY_RE = re.compile(r"^[\W_]+$")


def tokenize(text: str) -> list[str]:
    """中文优先分词，兜底按空白切分。"""
    text = text.strip().lower()
    tokens = [t for t in jieba.lcut(text) if t.strip()]
    return tokens or text.split()


# 内容词词性白名单：只保留携带语义的词，过滤介词/代词/助词/语气词等功能词，
# 避免「后/由/谁/的」等功能词在覆盖率计算中制造假匹配或稀释命中。
_CONTENT_POS: frozenset[str] = frozenset(
    {
        "n", "nr", "ns", "nt", "nz",   # 名词/人名/地名/机构/专名
        "v", "vn",                      # 动词/名动词
        "a", "an",                      # 形容词/名形词
        "m", "q",                       # 数词/量词
        "eng", "x",                     # 英文/未知（型号/编号）
        "i", "j", "l",                  # 成语/简称/习用语
    }
)


def meaningful_tokens(text: str) -> list[str]:
    """提取有信息量的词元：词性过滤（内容词白名单）+ 停用词 + 纯标点剔除。

    用于「query token 在 chunk 中的覆盖率」判定（解决长 chunk + 短 query
    在纯余弦下被长度稀释的问题，并避免功能词污染）。
    """
    result: list[str] = []
    for word, flag in pseg.cut(text.strip()):
        w = word.strip()
        if not w or w in STOP_WORDS:
            continue
        if flag not in _CONTENT_POS:
            continue
        if _PUNCT_ONLY_RE.match(w):
            continue
        if not _MEANINGFUL_RE.search(w):
            continue
        result.append(w.lower())
    return result


def char_ngrams(text: str, n: int = 2) -> list[str]:
    """字符 n-gram（去除空白后），用于型号/编号等精确匹配。"""
    cleaned = re.sub(r"\s+", "", text.strip().lower())
    if len(cleaned) < n:
        return []
    return [cleaned[i : i + n] for i in range(len(cleaned) - n + 1)]


_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*")


def extract_identifiers(text: str) -> list[str]:
    """提取「英文/型号标识符」作为实体锚点（如 Y / XG-2000A / Q3 / CEO / IP54）。

    只保留含字母的 token（过滤纯数字），用于证据门控的实体命中校验：
    真实 embedding 会把「产品参数」这类通用词匹配到语料里的同类属性，但若 query
    的标识符实体（如「Y 公司」）不在任何 chunk 中，说明问的是语料外实体，应拒答。
    """
    ids: list[str] = []
    for m in _IDENTIFIER_RE.finditer(text):
        tok = m.group().lower()
        if any(c.isalpha() for c in tok):
            ids.append(tok)
    return ids


class BaseEmbedding(ABC):
    dim: int = 128

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量向量化文档/chunk。"""

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class FakeEmbedding(BaseEmbedding):
    """确定性哈希 embedding：共享 token 与 char n-gram 的文本有相似向量。

    特征混合 word 分词 + char 2/3-gram，使相关文本余弦相似度足够高，
    同时保持离线可复现、无 ML 依赖。
    """

    dim = 256

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    @staticmethod
    def _features(text: str) -> list[str]:
        text = text.strip().lower()
        feats: list[str] = []
        feats.extend(tokenize(text))
        # char n-gram 增强中文/型号等精确匹配
        for n in (2, 3):
            if len(text) >= n:
                feats.extend(text[i : i + n] for i in range(len(text) - n + 1))
        return feats

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for feat in self._features(text):
            h = hashlib.md5(feat.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "big") % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class SentenceTransformerEmbedding(BaseEmbedding):
    """真实 sentence-transformers 模型（默认 BGE-M3）。"""

    def __init__(self, model_name: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name or settings.embedding_model
        self.model = SentenceTransformer(self.model_name, trust_remote_code=True)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]


class OpenAICompatEmbedding(BaseEmbedding):
    """OpenAI 兼容 HTTP embedding（DashScope text-embedding-v4 等）。

    同步 httpx 调用（embedding 调用点均为同步链路：入库 / 检索 / 重排），
    支持 batch；返回向量按 `index` 重排，保证与输入顺序一致。
    """

    _BATCH_SIZE = 10  # 单次请求最大文本数（DashScope text-embedding-v4 硬上限为 10）

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        dim: int | None = None,
    ) -> None:
        self.base_url = (base_url or settings.embedding_base_url).rstrip("/")
        self.api_key = api_key or settings.embedding_api_key
        self.model = model or settings.embedding_model
        self.dim = dim or settings.embedding_dim
        self.timeout = settings.llm_timeout_seconds
        # 复用连接：每次新建 Client 的 TLS 握手约 6-9s，复用后单次 <0.5s
        self._client = httpx.Client(timeout=self.timeout)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self._BATCH_SIZE):
            vectors.extend(self._embed_batch(self._client, texts[i : i + self._BATCH_SIZE]))
        return vectors

    def _embed_batch(self, client: httpx.Client, texts: list[str]) -> list[list[float]]:
        url = f"{self.base_url}/embeddings"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = client.post(url, json={"model": self.model, "input": texts}, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        items = sorted(data["data"], key=lambda x: x.get("index", 0))
        return [item["embedding"] for item in items]


_embedding_cache: dict[str, BaseEmbedding] = {}


def get_embedding() -> BaseEmbedding:
    """按配置返回 embedding 实现（按 provider 缓存，进程内单例）。

    按 provider 而非单一单例缓存：测试 monkeypatch `embedding_provider` 后可
    正确切换 fake，同时避免 openai_compat 的 HTTP 连接被反复重建。
    """
    provider = settings.embedding_provider
    if provider not in _embedding_cache:
        if provider == "sentence_transformer":
            _embedding_cache[provider] = SentenceTransformerEmbedding()
        elif provider == "openai_compat":
            _embedding_cache[provider] = OpenAICompatEmbedding()
        else:
            _embedding_cache[provider] = FakeEmbedding()
    return _embedding_cache[provider]
