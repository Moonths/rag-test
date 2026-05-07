"""
===========================================================================
📌 service/document_operations.py — 文档删除服务
===========================================================================

🔰 新手导读：
这个文件负责"删除知识库文件"的完整逻辑。
删除一个文件涉及三个地方的数据清理：
  1. Elasticsearch 中的向量数据和文本分块
  2. 本地磁盘上保存的文件
  3. PostgreSQL 数据库中的知识库记录

💡 为什么要删三个地方？
  上传文件时，文件数据被存到了三个地方：
  - ES：文件被分块+向量化后存入（用于检索）
  - 本地磁盘：原始文件保存在 storage/file/ 目录
  - PG数据库：knowledgebases 表记录了文件元信息

🔗 调用链：
  router/history_rt.py → delete_document() (本文件)
      → ES 删除 → 本地文件删除 → 数据库记录删除
===========================================================================
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from models.message import KnowledgeBase
from service.core.rag.utils.es_conn import ESConnection
import os
import logging

logger = logging.getLogger(__name__)

def delete_document(user_id: str, file_name: str, db: Session) -> dict:
    """
    🔑 核心函数：删除文档及其所有关联数据
    
    完整删除流程：
      1. 查询数据库确认文档存在
      2. 从 ES 中删除该文件的所有分块数据
      3. 删除本地磁盘上的文件
      4. 从数据库中删除记录
    
    Args:
        user_id: 用户ID（同时作为 ES 索引名）
        file_name: 要删除的文件名
        db: 数据库会话
    
    Returns:
        dict: {"status": "success/error", "message": "..."}
    """
    try:
        # ========== 步骤1：从数据库确认文档存在 ==========
        db_document = db.query(KnowledgeBase).filter(
            and_(
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.file_name == file_name
            )
        ).first()
        
        if not db_document:
            return {"status": "error", "message": "Document not found"}
            
        # user_id 同时作为 ES 的索引名
        index_name = user_id
        
        # ========== 步骤2：从 Elasticsearch 中删除数据 ==========
        es_connection = ESConnection()
        
        # 先搜索确认 ES 中有这些文档
        print(f"搜索索引 {index_name} 中的所有文档...")
        try:
            search_result = es_connection.es.search(
                index=index_name,
                body={"query": {"match_all": {}}, "size": 100}
            )
            print(f"找到 {search_result['hits']['total']['value']} 个文档")
            
            for i, hit in enumerate(search_result['hits']['hits'][:3]):
                source = hit['_source']
                print(f"文档 {i+1}:")
                print(f"  docnm: {source.get('docnm', 'N/A')}")
                print(f"  docnm_kwd: {source.get('docnm_kwd', 'N/A')}")
                print(f"  kb_id: {source.get('kb_id', 'N/A')} (类型: {type(source.get('kb_id', 'N/A'))})")
                print(f"  doc_id: {source.get('doc_id', 'N/A')}")
                
        except Exception as e:
            print(f"搜索文档失败: {e}")
        
        try:
            mapping = es_connection.es.indices.get_mapping(index=index_name)
            print(f"索引映射信息: {mapping}")
        except Exception as e:
            print(f"获取映射失败: {e}")
        
        # 尝试删除文档（同时支持字符串和数字类型的 kb_id）
        deleted_count = 0
        kb_id_candidates = [user_id]
        try:
            kb_id_int = int(user_id)
            if kb_id_int != user_id:
                kb_id_candidates.append(kb_id_int)
        except ValueError:
            pass
        
        print(f"尝试的 kb_id 候选值: {kb_id_candidates}")
        
        for kb_id_candidate in kb_id_candidates:
            if deleted_count > 0:
                break
                
            print(f"尝试使用 kb_id={kb_id_candidate} (类型: {type(kb_id_candidate)}) 删除文档")
            
            # 使用 match 查询删除（比 term 查询更灵活）
            try:
                delete_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"match": {"docnm": file_name}},
                                {"term": {"kb_id": kb_id_candidate}}
                            ]
                        }
                    }
                }
                
                response = es_connection.es.delete_by_query(
                    index=index_name,
                    body=delete_query,
                    refresh=True  # 立即刷新索引，确保删除生效
                )
                
                deleted_count = response["deleted"]
                
                if deleted_count > 0:
                    print(f"使用 match 查询成功删除 {deleted_count} 个文档")
                    break
                    
            except Exception as e:
                print(f"match 查询删除失败: {e}")
            
            # 回退到 term 查询
            deleted_count = es_connection.delete(
                condition={"docnm": file_name, "kb_id": kb_id_candidate},
                indexName=index_name,
                knowledgebaseId=None
            )
            
            if deleted_count > 0:
                print(f"成功删除 {deleted_count} 个文档")
                break
        
        print(f"从 ES 中删除了 {deleted_count} 个文档")
        
        # ========== 步骤3：删除本地文件 ==========
        file_path = f"storage/file/{user_id}/{file_name}"
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"删除本地文件: {file_path}")
            
        # ========== 步骤4：从数据库中删除记录 ==========
        db.delete(db_document)
        db.commit()
        
        return {
            "status": "success",
            "message": f"Successfully deleted {deleted_count} document(s) from ES and database"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting document: {str(e)}")
        return {"status": "error", "message": f"Failed to delete document: {str(e)}"}
