"""
===========================================================================
📌 service/core/retrieval.py — ⭐ 知识库检索入口 ⭐
===========================================================================

🔰 新手导读：
这是 RAG 系统"在线阶段"的检索入口。
当用户提问时，系统会调用这个模块从 Elasticsearch 中
检索与问题最相关的文档片段。

⭐ 检索的完整流程：
  ┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
  │ 用户提问     │ ──→ │ 混合检索          │ ──→ │ 重排序       │
  │ "成长性如何" │     │ 关键词 + 向量      │     │ Rerank模型   │
  └─────────────┘     └──────────────────┘     └──────────────┘
                                                      ↓
                                              ┌──────────────┐
                                              │ 返回 Top-K   │
                                              │ 最相关的片段  │
                                              └──────────────┘

💡 关键概念 —— 混合检索（Hybrid Search）：
  本项目同时使用两种检索方式，综合它们的结果：
  1. 关键词检索（BM25）：传统的文字匹配，匹配"字面"相似
     例如：搜索"苹果" → 匹配包含"苹果"这两个字的文档
  2. 向量检索（KNN）：语义相似度，匹配"含义"相似
     例如：搜索"苹果" → 也能匹配"iPhone"、"Apple公司"
  
  混合检索 = 两者加权组合，效果比单独使用任何一种都好

🔗 调用链：
  router/chat_rt.py → retrieve_content() (本文件)
      → dealer.retrieval() (search_v2.py)
          → ES 混合检索
          → Rerank 重排序
          → 返回最相关的 chunks
===========================================================================
"""

from service.core.rag.nlp.search_v2 import Dealer
# ↑ 🔑 Dealer: 检索引擎的核心类，封装了搜索、排序等功能
from service.core.rag.utils.es_conn import ESConnection
# ↑ Elasticsearch 连接（单例模式）

import json

# ==================== 初始化检索引擎 ====================
# 🔑 创建 ES 连接实例（单例，整个应用共用一个连接）
es_connection = ESConnection()

# 🔑 创建检索引擎实例
# Dealer 是检索的核心类，负责：分词→构建查询→执行检索→重排序
dealer = Dealer(dataStore=es_connection)


def retrieve_content(indexNames: str, question: str):
    """
    ⭐ 核心函数：从知识库中检索与问题相关的内容
    
    🔑 完整的检索流程：
      1. 对用户问题进行分词和向量化
      2. 在 ES 中执行混合检索（关键词 + 向量）
      3. 对结果进行重排序（Rerank），按相关度排序
      4. 返回最相关的 Top-5 文档片段
    
    Args:
        indexNames: ES 索引名称（通常是 user_id，每个用户一个独立索引）
        question: 用户的提问内容
    
    Returns:
        list[dict]: 检索到的文档片段列表，每个包含：
          - id: 序号
          - document_id: 文档ID
          - document_name: 文档名称（如"世运电路2023中报.pdf"）
          - content_with_weight: 文档片段的文本内容
    
    示例返回值：
    [
        {
            "id": 1,
            "document_id": "a1b2c3",
            "document_name": "世运电路2023中报.pdf",
            "content_with_weight": "公司营收同比增长25%，净利润..."
        },
        {
            "id": 2,
            "document_id": "d4e5f6",
            "document_name": "世运电路2023中报.pdf",
            "content_with_weight": "公司持续加大研发投入..."
        }
    ]
    """
    # 🔑 执行混合检索 + 重排序
    results = dealer.retrieval(
        question=question,               # 用户问题
        embd_mdl=None,                   # 嵌入模型（内部会自动调用）
        tenant_ids=indexNames,            # ES 索引名（用户ID）
        kb_ids=None,                     # 知识库ID过滤（不限制）
        vector_similarity_weight=0.6,    # 向量相似度权重 60%（关键词 40%）
        page=1,                          # 第几页
        page_size=5                      # 每页返回 5 条结果
    )

    # ========== 提取并格式化检索结果 ==========
    extracted_data = []
    for i, chunk in enumerate(results['chunks'], start=1):
        content_with_weight = chunk.get('content_with_weight', 'N/A')  # 文本内容
        doc_id = chunk.get('doc_id', 'N/A')          # 文档ID
        docnm = chunk.get('docnm_kwd', 'N/A')        # 文档名称
        docnm = docnm.split("/")[-1]                  # 只取文件名（去掉路径）

        message = {
            "id": i,                               # 序号（用于前端引用标注）
            "document_id": doc_id,                 # 文档ID
            "document_name": docnm,                # 文档名称
            'content_with_weight': content_with_weight,  # 文本内容
        }
        
        extracted_data.append(message)

    return extracted_data


# 测试代码：直接运行此文件可以测试检索功能
if __name__ == '__main__':
    res = retrieve_content(question="世运电路成长性如何", indexNames="test01")
    print(res)
