"""
===========================================================================
📌 service/core/file_parse.py — ⭐ 文档解析 + 向量化 + 存储到 ES ⭐
===========================================================================

🔰 新手导读：
这是 RAG 系统"离线阶段"的核心文件！
当用户上传文件到知识库时，文件会经过以下处理流程：

⭐ 文档处理完整管道（Pipeline）：

  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
  │ 1. 文档解析  │ ──→ │ 2. 文本分块   │ ──→ │ 3. 分词处理   │
  │ parse()     │     │ chunk()      │     │ tokenize()   │
  │ PDF→文本    │     │ 长文本→小段落  │     │ 中文分词      │
  └─────────────┘     └──────────────┘     └──────────────┘
        ↓                                        ↓
  ┌──────────────────────────────────────────────────────┐
  │ 4. 向量化（Embedding）                                │
  │ generate_embedding()                                  │
  │ 文本 → 1024维浮点数向量（语义信息的数学表示）            │
  │ 调用阿里云 DashScope text-embedding-v3 模型            │
  └──────────────────────────────────────────────────────┘
        ↓
  ┌──────────────────────────────────────────────────────┐
  │ 5. 存入 Elasticsearch                                │
  │ es_connection.insert()                                │
  │ 文本 + 向量 + 元信息 → ES 索引（支持关键词+向量混合检索）│
  └──────────────────────────────────────────────────────┘

💡 关键概念 —— 为什么需要分块（Chunking）？
  大模型有"上下文窗口"限制（比如 8K tokens），不能一次处理整本书。
  所以需要把长文档切成小段落（chunk），每段 128 个 token 左右。
  检索时只返回最相关的几个 chunk，而不是整个文档。

💡 关键概念 —— 什么是向量化（Embedding）？
  把文本转成一组浮点数（如 1024 维向量），相似的文本向量距离更近。
  例如："巴黎是法国首都" 和 "法国首都巴黎" 的向量非常接近。
  这样就可以用"向量相似度"来做语义检索，不仅仅是关键词匹配。

🔗 调用链：
  router/chat_rt.py 的 upload_files()
      → execute_insert_process() (本文件)
          → parse() → chunk() (rag/app/naive.py)
          → process_items() → generate_embedding() (rag/nlp/model.py)
          → es_connection.insert() (rag/utils/es_conn.py)
===========================================================================
"""

import xxhash          # xxhash: 超快速的哈希算法，用于生成 chunk_id
import datetime
from service.core.rag.app.naive import chunk
# ↑ 🔑 naive chunk: "朴素分块"算法，将文档解析+文本分块
from service.core.rag.utils.es_conn import ESConnection
# ↑ Elasticsearch 连接工具
from service.core.rag.nlp.model import generate_embedding
# ↑ 🔑 向量化模型：将文本转成向量
from typing import List, Dict, Any
import numpy as np

def dummy(prog=None, msg=""):
    """空回调函数，用于不需要进度通知的场景"""
    pass

def parse(file_path):
    """
    🔑 关键函数：解析文档并进行分块
    
    调用 naive chunk 算法：
      1. 根据文件类型（pdf/docx/txt/excel）选择对应的解析器
      2. 提取文本内容
      3. 将长文本按分隔符切分
      4. 将小段落合并成大小合适的 chunk（约128 tokens）
      5. 对每个 chunk 进行分词处理
    
    Args:
        file_path: 文件路径
    
    Returns:
        list[dict]: 分块结果列表，每个 dict 包含：
          - content_with_weight: 原始文本内容
          - content_ltks: 粗粒度分词结果（用于关键词检索）
          - content_sm_ltks: 细粒度分词结果（更细的语义单元）
          - docnm_kwd: 文档名称
          - title_tks: 标题分词结果
    """
    result = chunk(file_path, callback=dummy)
    return result

def batch_generate_embeddings(texts: List[str], batch_size: int = 10) -> List[List[float]]:
    """
    🔑 关键函数：批量生成文本的向量嵌入（Embedding）
    
    将多段文本一次性转成向量，提高效率。
    调用阿里云 DashScope 的 text-embedding-v3 模型。
    
    💡 为什么要批量处理？
      单次 API 调用有数量限制（DashScope 限制为10条/次），
      而且批量处理比逐条调用快很多。
    
    Args:
        texts: 文本列表
        batch_size: 批处理大小（DashScope限制为10）
    
    Returns:
        向量列表，每个向量是 1024 维的 float 数组
    """
    try:
        embeddings = generate_embedding(texts)
        return embeddings if embeddings is not None else []
    except Exception as e:
        print(f"批量生成向量失败: {e}")
        return []

def process_items(items: List[Dict[str, Any]], file_name: str, index_name: str) -> List[Dict[str, Any]]:
    """
    🔑 关键函数：将分块后的文本数据处理成可以存入 ES 的格式
    
    对每个文本块（chunk）进行：
      1. 生成唯一的 chunk_id（使用 xxhash）
      2. 调用 Embedding 模型生成向量
      3. 组装成 ES 文档格式
    
    Args:
        items: 文本块列表（parse() 的返回值）
        file_name: 原始文件名
        index_name: ES 索引名称（通常是 user_id）
    
    Returns:
        list[dict]: 可以直接插入 ES 的文档列表
    """
    try:
        # 步骤1：提取所有文本块的内容
        texts = [item["content_with_weight"] for item in items]
        
        # 步骤2：🔑 批量调用 Embedding 模型生成向量
        embeddings = batch_generate_embeddings(texts)
        
        # 步骤3：组装每个文档块的完整数据
        results = []
        for item, embedding in zip(items, embeddings):
            # 使用 xxhash 生成唯一的 chunk_id
            # 基于"文本内容+索引名"生成，保证相同内容的ID一致
            chunck_id = xxhash.xxh64((item["content_with_weight"] + index_name).encode("utf-8")).hexdigest()

            # 构建存入 ES 的文档字典
            d = {
                "id": chunck_id,                      # 唯一标识符
                "content_ltks": item["content_ltks"],  # 粗粒度分词（用于关键词匹配检索）
                "content_with_weight": item["content_with_weight"],  # 原始文本（用于显示给用户）
                "content_sm_ltks": item["content_sm_ltks"],  # 细粒度分词（更精细的语义单元）
                "important_kwd": [],                   # 重要关键词（当前为空）
                "important_tks": [],                   # 重要分词（当前为空）
                "question_kwd": [],                    # 关联问题关键词
                "question_tks": [],                    # 关联问题分词
                "create_time": str(datetime.datetime.now()).replace("T", " ")[:19],
                "create_timestamp_flt": datetime.datetime.now().timestamp()
            }

            d["kb_id"] = index_name                    # 知识库ID（即 ES 索引名）
            d["docnm_kwd"] = item["docnm_kwd"]        # 文档名称关键词（用于按文档过滤）
            d["title_tks"] = item["title_tks"]         # 文档标题分词
            d["doc_id"] = xxhash.xxh64(file_name.encode("utf-8")).hexdigest()  # 文档ID
            d["docnm"] = file_name                     # 完整文件名
            
            # 🔑 存储向量！字段名格式为 "q_1024_vec"（1024是向量维度）
            # ES 会用这个向量进行 KNN（K近邻）向量检索
            d[f"q_{len(embedding)}_vec"] = embedding
            
            # 💡 字段说明：
            # content_ltks: 粗粒度分词 → ["人工智能", "是", "一门", "新兴", "技术"]
            # content_sm_ltks: 细粒度分词 → ["人工", "智能", "是", "一门", "新兴", "的", "技术"]
            # content_with_weight: 原始文本 → "人工智能是一门新兴技术..."
            # q_1024_vec: 1024维向量 → [0.012, -0.045, 0.078, ...]

            results.append(d)

        return results

    except Exception as e:
        print(f"process_items error: {e}")
        return []

def execute_insert_process(file_path: str, file_name: str, index_name: str):
    """
    ⭐ 核心入口函数：执行"文档解析 → 向量化 → 存入 ES"的完整流程
    
    这是 RAG 离线阶段的总入口。每次用户上传文件时调用。
    
    完整流程：
      1. parse()：解析文档 → 文本分块 → 分词
      2. process_items()：为每个块生成向量
      3. es_connection.insert()：批量插入 Elasticsearch
    
    Args:
        file_path: 文件路径（如 storage/file/user1/report.pdf）
        file_name: 文件名（如 report.pdf）
        index_name: ES 索引名称（通常是 user_id 或 session_id）
    """
    # 步骤1：🔑 解析文档 + 分块 + 分词
    documents = parse(file_path)
    if not documents:
        print(f"No documents found in {file_path}")
        return

    # 步骤2：🔑 为每个文本块生成向量嵌入
    processed_documents = process_items(documents, file_name, index_name)
    if not processed_documents:
        print(f"Failed to process documents from {file_path}")
        return

    # 步骤3：🔑 批量插入 Elasticsearch
    try:
        es_connection = ESConnection()
        es_connection.insert(documents=processed_documents, indexName=index_name)
        # ↑ index_name 就是 ES 的索引名，每个用户一个独立索引
        print(f"Successfully inserted {len(processed_documents)} documents into ES")
    except Exception as e:
        print(f"Failed to insert documents into ES: {e}")

# 测试代码（直接运行此文件时执行）
if __name__ == "__main__":
    file_path = "/mnt/d/wsl/project/gsk-poc/storage/file/【兴证电子】世运电路2023中报点评.pdf"
    session_id = "40e2743ccffa4207"
    output_file = "/mnt/d/wsl/project/gsk-poc/storage/output/result.json"

    if not os.path.exists(output_file):
        documents = parse(file_path)
        result = process_items(documents, file_path, session_id)

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        print(f"结果已保存到本地文件: {output_file}")
    else:
        with open(output_file, "r", encoding="utf-8") as f:
            result = json.load(f)
        print(f"从本地文件加载结果: {output_file}")

    es_connection = ESConnection()
    es_connection.insert(documents=result, indexName="世运电路2023中报点评")
