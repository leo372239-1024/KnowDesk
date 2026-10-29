"""模型网关：LLM 调用抽象 + OpenAI 兼容实现 + 离线抽取式实现。

- OpenAICompatLLM：真实 OpenAI 兼容模型（DeepSeek/Ollama/vLLM），主备降级。
- ExtractiveLLM：离线抽取式问答（无外部依赖），从检索 chunk 中抽取相关句并带
  引用，保证答案 100% 忠实、零幻觉；understand 阶段返回空以跳过改写污染。

「一套代码、两种部署」：无 LLM_API_KEY 时自动用 ExtractiveLLM 离线可跑，
配置 API Key 后无缝切换真实模型。
"""
import asyncio
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import ModelDegradedError
from app.retrieval.embedding import meaningful_tokens


class BaseLLM(ABC):
    @abstractmethod
    async def agenerate(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """异步生成，messages 为 OpenAI 格式。"""


class OpenAICompatLLM(BaseLLM):
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = base_url or settings.llm_base_url
        self.api_key = api_key or settings.llm_api_key

    async def agenerate(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        model = kwargs.get("model", settings.llm_model)
        last_exc: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            try:
                return await self._call(model, messages)
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                # HTTP 层错误：降级到备用模型（不重试主模型）
                backup = settings.llm_backup_model
                if backup and backup != model:
                    try:
                        return await self._call(backup, messages)
                    except Exception as inner:  # noqa: BLE001
                        raise ModelDegradedError("主模型与备用模型均不可用") from inner
                raise ModelDegradedError("模型调用失败") from exc
            except httpx.TransportError as exc:
                # 网络层错误（连接重置/中断）：指数退避重试，仅重试主模型
                last_exc = exc
                if attempt < settings.llm_max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
        raise ModelDegradedError("模型网络错误") from last_exc

    async def _call(self, model: str, messages: list[dict[str, str]]) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {"model": model, "messages": messages, "temperature": 0.2}
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]


class ExtractiveLLM(BaseLLM):
    """离线抽取式问答：确定性、可复现、零幻觉，供测试与离线演示。

    根据 prompt 类型分派：
    - 查询改写/理解 prompt → 返回空字符串（由上层回退用原始 query）。
    - 生成 prompt（含 <untrusted_document>）→ 抽取相关 chunk 句子并带 [chunk_id] 引用。
    """

    # 离线规则型实现标记（节点据此决定是否跳过 LLM 改写）
    is_rule_based = True

    _UNTRUSTED_RE = re.compile(r"<untrusted_document>\s*(.*?)\s*</untrusted_document>", re.S)
    _UNTRUSTED_CONTENT_RE = re.compile(r"<untrusted_content>\s*(.*?)\s*</untrusted_content>", re.S)
    _ENTRY_RE = re.compile(r"\[([^\]]+)\]\s*(.*)", re.S)
    _QUERY_RE = re.compile(r"用户问题[:：]\s*(.+)")

    async def agenerate(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        system = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")
        user = messages[-1].get("content", "") if messages else ""

        # 查询理解/改写：离线不改写，返回空让上层用原 query
        if "改写" in system or "查询理解" in system or "子问题" in system:
            return ""
        # 生成：抽取式回答
        if "<untrusted_document>" in user:
            return self._extractive_answer(user)
        return ""

    _SENT_SPLIT_RE = re.compile(r"(?<=[。！？；\n])")
    _MAX_ANSWER_SENTENCES = 6

    def _extractive_answer(self, user: str) -> str:
        entries, query = self._parse_generate_prompt(user)
        if not query or not entries:
            return ""

        q_tokens = set(meaningful_tokens(query))
        # 句级抽取：对每个候选 chunk 的句子按 query 词元重叠打分
        scored: list[tuple[float, str, str]] = []
        for chunk_id, content in entries:
            for sent in self._split_sentences(content):
                s_tokens = set(meaningful_tokens(sent))
                overlap = q_tokens & s_tokens
                if not overlap:
                    continue
                coverage = len(overlap) / len(q_tokens) if q_tokens else 0.0
                scored.append((coverage, chunk_id, sent))

        if not scored:
            # KB 无匹配句时，若有网络补充资料则回退（明确标注来源，无 KB 引用）
            wm = self._UNTRUSTED_CONTENT_RE.search(user)
            if wm:
                web_text = wm.group(1).strip()
                if web_text:
                    return f"根据网络搜索（未在内部资料找到）：\n{web_text[:400]}"
            return ""
        scored.sort(key=lambda x: x[0], reverse=True)

        # 去重（按句子内容），取 top-N 句
        seen: set[str] = set()
        selected: list[tuple[str, str]] = []
        for _cov, chunk_id, sent in scored:
            if sent in seen:
                continue
            seen.add(sent)
            selected.append((chunk_id, sent))
            if len(selected) >= self._MAX_ANSWER_SENTENCES:
                break

        lines = [f"[{chunk_id}] {sent}" for chunk_id, sent in selected]
        return "根据资料：\n" + "\n".join(lines)

    @classmethod
    def _split_sentences(cls, text: str) -> list[str]:
        parts = [p.strip() for p in cls._SENT_SPLIT_RE.split(text) if p.strip()]
        return parts or ([text.strip()] if text.strip() else [])

    @classmethod
    def _parse_generate_prompt(
        cls, user: str
    ) -> tuple[list[tuple[str, str]], str]:
        """从生成 prompt 解析 (chunk_id, content) 列表与 query。"""
        entries: list[tuple[str, str]] = []
        m = cls._UNTRUSTED_RE.search(user)
        if m:
            # chunk 之间以空行分隔；每个 chunk 内容可含多行（如表格），故按空行切分
            for seg in re.split(r"\n\s*\n", m.group(1)):
                seg = seg.strip()
                if not seg:
                    continue
                mm = cls._ENTRY_RE.match(seg)
                if mm:
                    entries.append((mm.group(1), mm.group(2).strip()))
        query = ""
        qm = cls._QUERY_RE.search(user)
        if qm:
            query = qm.group(1).strip()
        return entries, query


# 兼容旧名：早期测试与文档使用 FakeLLM
FakeLLM = ExtractiveLLM


def get_llm() -> BaseLLM:
    if settings.llm_api_key:
        return OpenAICompatLLM()
    return ExtractiveLLM()
