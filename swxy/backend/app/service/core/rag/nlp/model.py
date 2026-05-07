"""
===========================================================================
📌 service/core/rag/nlp/model.py — ⭐ 大模型 API 调用（Embedding + Rerank）⭐
===========================================================================

🔰 新手导读：
这个文件封装了与大模型 API 交互的核心功能：
  1. generate_embedding() → 文本向量化（将文字变成数学向量）
  2. rerank_similarity() → 重排序（对检索结果按相关度重新排序）
  3. get_chat_completion_block() → 非流式对话（测试用）

💡 关键概念 —— Embedding（向量嵌入）：
  人类理解文字含义，但计算机只理解数字。
  Embedding 模型可以把文字转成一串数字（向量），而且：
    - 含义相似的文字 → 向量距离近
    - 含义不同的文字 → 向量距离远
  
  例如（简化示例，实际是1024维）：
    "猫" → [0.2, 0.8, 0.1, ...]
    "狗" → [0.3, 0.7, 0.2, ...]  ← 和"猫"很近（都是动物）
    "汽车" → [0.9, 0.1, 0.8, ...] ← 和"猫"很远
  
  这样就可以通过"计算向量距离"来找到语义最相关的文档片段。

💡 关键概念 —— Rerank（重排序）：
  初步检索可能返回很多结果，但排序不够精确。
  Rerank 模型会对这些结果重新评分排序，让最相关的排在前面。
  相当于"粗筛"之后再"精筛"。

🔗 使用的 API：
  - 向量化：阿里云 DashScope text-embedding-v3
  - 重排序：阿里云 DashScope Rerank 模型
  - 对话：OpenAI 兼容接口（deepseek-r1）
  
  这些 API 都通过 OpenAI 兼容接口调用（DashScope 提供了兼容层）。
===========================================================================
"""

from openai import OpenAI
from llama_index.core.data_structs import Node
from llama_index.core.schema import NodeWithScore
from llama_index.postprocessor.dashscope_rerank import DashScopeRerank
# ↑ llama_index: 流行的 RAG 框架，这里只用它的 Rerank 功能
import numpy as np
from typing import List

import os
from dotenv import load_dotenv
load_dotenv()

def get_chat_completion_block(session_id, question, references):
    """
    非流式对话（测试用，实际生产使用 chat.py 中的流式版本）
    
    结合知识库内容生成回答，并在回答中标注引用来源。
    """
    try:
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL")
        )
        formatted_references = "\n".join([f"[{ref['id']}] {ref['content']}" for ref in references])
    
        completion = client.chat.completions.create(
            model="deepseek-r1",
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
    
        return completion.choices[0].message.content

    except Exception as e:
        return f"Error: {str(e)}"

def rerank_similarity(query, texts):
    """
    🔑 关键函数：使用重排序模型对检索结果进行精排
    
    💡 工作原理：
      初步检索返回的结果可能包含一些不太相关的内容。
      Rerank 模型会对每个结果与查询的相关度打分（0-1），
      分数越高表示越相关。
    
    使用的是阿里云 DashScope 的 Rerank 模型。
    
    Args:
        query: 用户的查询问题
        texts: 候选文本列表（初步检索的结果）
    
    Returns:
        tuple: (scores, None)
          - scores: numpy 数组，每个文本的相关度分数
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    
    # 将文本包装成 llama_index 的 Node 格式
    nodes = [NodeWithScore(node=Node(text=text), score=1.0) for text in texts]

    # 初始化 DashScope Rerank 重排序器
    dashscope_rerank = DashScopeRerank(top_n=len(texts), api_key=api_key)

    # 执行重排序：Rerank 模型会重新计算每个文本与 query 的相关度
    results = dashscope_rerank.postprocess_nodes(nodes, query_str=query)

    # 提取重排序分数
    scores = [res.score for res in results]
    scores = np.array(scores)

    return scores, None


def generate_embedding(text: str | List[str], api_key: str = None, base_url: str = None, model_name: str = "text-embedding-v3", dimensions: int = 1024, encoding_format: str = "float", max_batch_size: int = 10):
    """
    ⭐ 核心函数：生成文本的向量嵌入（Embedding）
    
    将文本转成 1024 维的浮点数向量，用于语义检索。
    
    💡 这个函数在两个地方被调用：
      1. 文档入库时：将每个文本块转成向量 → 存入 ES
      2. 查询时：将用户问题转成向量 → 在 ES 中做向量相似度检索
    
    💡 使用的模型：
      阿里云 DashScope 的 text-embedding-v3
      输出维度：1024 维浮点数向量
      通过 OpenAI 兼容接口调用
    
    Args:
        text: 单个文本字符串，或文本列表
        model_name: 向量化模型名称（默认 text-embedding-v3）
        dimensions: 输出向量维度（默认 1024）
        max_batch_size: 每次 API 调用最多处理的文本数（DashScope 限制 10）
    
    Returns:
        - 单个文本时：返回一个 1024 维向量 [float, float, ...]
        - 文本列表时：返回向量列表 [[float, ...], [float, ...], ...]
    
    示例：
        # 单个文本
        vec = generate_embedding("人工智能技术")
        # vec = [0.012, -0.045, 0.078, ..., 0.034]  # 1024 个浮点数
        
        # 批量文本
        vecs = generate_embedding(["你好", "世界", "AI"])
        # vecs = [[...], [...], [...]]  # 3 个 1024 维向量
    """
    # 从环境变量读取 API 配置
    api_key = os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("DASHSCOPE_BASE_URL")    

    # 初始化 OpenAI 兼容客户端（DashScope 提供了兼容层）
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    # ========== 处理单个文本 ==========
    if isinstance(text, str):
        try:
            completion = client.embeddings.create(
                model=model_name,         # 模型名称
                input=text,               # 输入文本
                dimensions=dimensions,     # 向量维度
                encoding_format=encoding_format  # 编码格式
            )
            # 🔑 返回向量：completion.data[0].embedding 就是 1024 维向量
            return completion.data[0].embedding
        except Exception as e:
            print(f"OpenAI API 请求失败: {e}")
            return None
    
    # ========== 处理文本列表（分批调用 API）==========
    if isinstance(text, list):
        all_embeddings = []
        
        # 按 max_batch_size 分批处理（DashScope 限制每次最多 10 条）
        for i in range(0, len(text), max_batch_size):
            batch = text[i:i + max_batch_size]
            
            try:
                completion = client.embeddings.create(
                    model=model_name,
                    input=batch,
                    dimensions=dimensions,
                    encoding_format=encoding_format
                )
                
                batch_embeddings = [item.embedding for item in completion.data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                print(f"OpenAI API 批量请求失败 (batch {i//max_batch_size + 1}): {e}")
                all_embeddings.extend([None] * len(batch))
        
        return all_embeddings


# 测试代码
if __name__ == "__main__":
    question = "法国的首都是哪里？"
    references = [
        {"id": 1, "content": "法国的首都是巴黎。"},
        {"id": 2, "content": "巴黎是欧洲的文化中心之一。"},
    ]
    session_id = "sd"
    
    response = get_chat_completion_block(session_id, question, references)
    print(response)
