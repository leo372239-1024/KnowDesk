# -*- coding: utf-8 -*-
"""临时：测试 DeepSeek LLM 连通性。"""
import asyncio

from app.core.config import settings
from app.core.llm import OpenAICompatLLM, get_llm

async def main():
    print("provider:", type(get_llm()).__name__)
    print("base_url:", settings.llm_base_url)
    print("model:", settings.llm_model)
    llm = OpenAICompatLLM()
    resp = await llm.agenerate([
        {"role": "system", "content": "你是助手，简洁回答。"},
        {"role": "user", "content": "用一句话介绍你自己"},
    ])
    print("RESP:", resp[:200])

asyncio.run(main())
