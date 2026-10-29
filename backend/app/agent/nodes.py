"""Agent 节点实现：理解 / 计划 / 检索 / 判定 / 生成 / 拒答。"""
from typing import Any

from app.agent.citation import build_citations, validate_citations
from app.agent.state import AgentState
from app.agent.tools import retrieve_kb, web_search
from app.core.config import settings
from app.core.llm import BaseLLM
from app.core.observability import trace_span
from app.retrieval.embedding import extract_identifiers
from app.retrieval.retriever import RetrievalService, compute_evidence_score
from app.retrieval.vector_store import SearchResult


def _serialize_results(results: list[SearchResult]) -> list[dict[str, Any]]:
    return [
        {
            "chunk": {
                "chunk_id": r.chunk.chunk_id,
                "document_id": r.chunk.document_id,
                "content": r.chunk.content,
                "section_path": r.chunk.section_path,
                "chunk_type": r.chunk.chunk_type,
                "page_num": r.chunk.page_num,
                "bbox": r.chunk.bbox,
            },
            "score": r.score,
        }
        for r in results
    ]


async def understand_node(state: AgentState, llm: BaseLLM) -> dict[str, Any]:
    """查询理解：拆子问题 / HyDE。MVP 简化：原 query 始终保留，LLM 改写仅作补充召回。"""
    with trace_span("understand"):
        query = state["query"]
        # 原 query 始终参与检索（证据门控的主信号），LLM 改写只作补充召回：
        # 避免改写偏航时把原 query 的强证据一并丢弃（导致可答题被误判证据不足）。
        rewritten = [query]
        try:
            resp = await llm.agenerate(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是查询理解器。对用户问题进行同义改写，生成 1-2 个更利于检索的独立子问题，"
                            "用换行分隔，只输出子问题。要求：仅做指代消解、术语归一与同义改写，"
                            "不得改变问题的核心意图，不得扩展到其他话题（如购买、报销、维修步骤等）。"
                        ),
                    },
                    {"role": "user", "content": query},
                ]
            )
            extra = [line.strip() for line in resp.splitlines() if line.strip()]
            rewritten += [e for e in extra if e and e != query][:2]
        except Exception:  # noqa: BLE001
            pass
        return {"rewritten_queries": rewritten, "rounds": 0}


async def plan_node(state: AgentState, llm: BaseLLM) -> dict[str, Any]:
    """检索计划：生成主步骤。"""
    with trace_span("plan"):
        return {"plan": state.get("rewritten_queries", [state["query"]])}


async def retrieve_node(state: AgentState, retrieval: RetrievalService) -> dict[str, Any]:
    """多路检索并合并去重（按 chunk_id 保留最高分）。

    额外用「原 query」单独检索，作为证据门控的主信号（不混入改写子问题的噪声）。
    """
    with trace_span("retrieve"):
        queries = state.get("plan") or [state["query"]]
        orig_query = state["query"]

        # 原 query 单独检索：证据门控主信号
        orig_results = retrieve_kb(
            retrieval,
            orig_query,
            state["tenant_id"],
            state.get("department"),
            state.get("acl_tags", []),
        )
        orig_evidence = compute_evidence_score([r.score for r in orig_results])

        # 合并所有改写 query 的检索结果（生成用召回）
        merged: dict[str, SearchResult] = {}
        for q in queries:
            results = retrieve_kb(
                retrieval,
                q,
                state["tenant_id"],
                state.get("department"),
                state.get("acl_tags", []),
            )
            for r in results:
                cid = r.chunk.chunk_id
                if cid not in merged or r.score > merged[cid].score:
                    merged[cid] = r
        merged_list = sorted(merged.values(), key=lambda x: x.score, reverse=True)
        # 章节上下文扩展：补齐同章节兄弟 chunk（如流程各环节），提升完整覆盖
        merged_list = retrieval.expand_siblings(merged_list)
        retrieved = _serialize_results(merged_list)
        return {"retrieved": retrieved, "orig_evidence_score": orig_evidence}


def judge_node(state: AgentState, retrieval: RetrievalService) -> dict[str, Any]:
    """证据门控（前置硬闸）：充分 → 生成；不足 → 改写/网络/拒答。

    门控以「原 query」的检索证据为主信号，避免改写子问题合并引入噪声抬高分数，
    导致语料外问题（拒答题）被误判为证据充分而漏拒。
    """
    with trace_span("judge"):
        retrieved = state.get("retrieved", [])
        evidence_score = state.get(
            "orig_evidence_score",
            compute_evidence_score([r["score"] for r in retrieved]),
        )

        sufficient = evidence_score >= settings.evidence_score_threshold and retrieved
        # 实体标识符校验：query 的英文/型号锚点（Y / XG-2000A / Q3 / CEO…）必须命中语料。
        # 真实 embedding 会把「产品参数」这类通用词匹配到语料同类属性，导致 evidence 虚高，
        # 但若标识符实体不在任何 chunk 中，说明问的是语料外实体，应判证据不足。
        if sufficient:
            identifiers = extract_identifiers(state["query"])
            if identifiers:
                corpus = " ".join(item["chunk"]["content"] for item in retrieved).lower()
                hit = sum(1 for i in identifiers if i in corpus)
                if hit / len(identifiers) < 0.5:
                    sufficient = False
        rounds = state.get("rounds", 0)
        return {"evidence_score": evidence_score, "sufficient": sufficient, "rounds": rounds}


async def generate_node(state: AgentState, llm: BaseLLM) -> dict[str, Any]:
    """生成：强制引用 + 引用硬门禁校验（无引用断言裁掉）。"""
    with trace_span("generate"):
        retrieved = state["retrieved"]
        citations = build_citations(retrieved)
        valid_ids = {c["chunk_id"] for c in citations}

        context_parts = []
        for i, item in enumerate(retrieved):
            chunk = item["chunk"]
            context_parts.append(f"[{chunk['chunk_id']}] {chunk['content']}")
        context = "\n\n".join(context_parts)

        prompt = (
            "基于以下资料回答用户问题。要求：\n"
            "1. 每个事实断言后必须标注引用 [chunk_id]（从资料里的标记选取）。\n"
            "2. 资料未覆盖的内容不要编造。\n"
            "3. 完整覆盖资料中与该问题相关的所有要点，不要遗漏关键环节、数值或条件。\n\n"
            f"<untrusted_document>\n{context}\n</untrusted_document>\n\n"
        )
        # 网络补充资料（不可信来源，与知识库区分，需明确标注来源）
        web = state.get("web_search_results", "")
        if web:
            prompt += f"补充网络资料（不可信，引用时标注「网络」）：\n{web}\n\n"
        prompt += f"用户问题：{state['query']}\n"
        answer = await llm.agenerate([{"role": "user", "content": prompt}])

        # 引用硬门禁：移除无效引用
        cleaned, cited_ids, invalid = validate_citations(answer, valid_ids)
        filtered_citations = [c for c in citations if c["chunk_id"] in cited_ids]

        return {
            "answer": cleaned,
            "citations": filtered_citations,
            "refused": False,
            "refuse_reason": "",
        }


async def web_search_node(state: AgentState) -> dict[str, Any]:
    """网络检索补充：知识库不足时触发，结果包 <untrusted_content> 防注入。"""
    with trace_span("web_search"):
        result = await web_search(state["query"])
        return {"web_search_results": result, "need_web_search": False}


async def refuse_node(state: AgentState) -> dict[str, Any]:
    """拒答：明确承认不知道，给出引导，不编造。"""
    with trace_span("refuse"):
        reason = state.get("refuse_reason", "")
        answer = (
            f"资料中未找到该问题的答案。{('原因：' + reason) if reason else ''}"
            "建议补充相关资料或咨询对应业务负责人。"
        )
        return {"answer": answer, "citations": [], "refused": True, "refuse_reason": reason}
