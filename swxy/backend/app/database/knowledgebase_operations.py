"""
===========================================================================
📌 database/knowledgebase_operations.py — 知识库数据库操作
===========================================================================

🔰 新手导读：
这个文件提供知识库表（knowledgebases）的基本操作：
  1. insert_knowledgebase() → 插入一条知识库记录
  2. verify_user_knowledgebase() → 检查用户是否有知识库

🔗 调用关系：
  router/chat_rt.py → upload_files()
      → execute_insert_process() → 向量化存入 ES
      → insert_knowledgebase() → 在 PG 中记录文件信息
===========================================================================
"""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from utils.database import get_db
from fastapi import HTTPException

def insert_knowledgebase(user_id: str, file_name: str):
    """
    🔑 关键函数：在 knowledgebases 表中记录上传的文件
    
    当用户通过 /upload_files 上传文件并成功存入 ES 后，
    调用此函数在 PostgreSQL 中保存文件元信息。
    
    Args:
        user_id: 用户ID
        file_name: 文件名称
    """
    db = next(get_db())
    try:
        db.execute(
            text(
                """
                INSERT INTO knowledgebases (user_id, file_name)
                VALUES (:user_id, :file_name)
                """
            ),
            {"user_id": user_id, "file_name": file_name}
        )
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Failed to insert into knowledgebases: {str(e)}")
    finally:
        db.close()

def verify_user_knowledgebase(user_id: str):
    """
    验证用户是否已有自己的知识库
    
    如果用户没有上传过任何文件（knowledgebases 表中没有记录），
    抛出 461 状态码错误，提示用户需要先上传文件。
    
    Args:
        user_id: 用户ID
    
    Raises:
        HTTPException: 461 表示用户还没有知识库
    """
    db = next(get_db())
    try:
        query_result = db.execute(
            text("SELECT id FROM knowledgebases WHERE user_id = :user_id LIMIT 1"),
            {"user_id": user_id}
        ).fetchone()

        if not query_result:
            raise HTTPException(
                status_code=461,
                detail="You do not have your own knowledge base yet."
            )
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database operation failed: {str(e)}"
        )
    finally:
        db.close()
