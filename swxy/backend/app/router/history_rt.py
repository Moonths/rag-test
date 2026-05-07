"""
===========================================================================
📌 router/history_rt.py — 历史记录路由（查询文档/消息/会话列表）
===========================================================================

🔰 新手导读：
这个文件提供"查看历史"相关的 API 接口：
  1. GET /get_files    → 获取用户上传的知识库文件列表
  2. DELETE /delete_file/{file_name} → 删除知识库中的文件
  3. GET /get_messages  → 获取某个会话的所有对话消息
  4. GET /get_sessions  → 获取用户的所有会话列表

💡 这些接口都需要 JWT 认证才能访问（通过 Security(access_security)）。
  FastAPI 会自动从请求头的 Authorization 中提取 Token，
  验证后把用户信息放到 credentials 对象中。

🔗 前端使用场景：
  - 侧边栏显示会话列表 → GET /get_sessions
  - 点击某个会话加载历史消息 → GET /get_messages?session_id=xxx
  - 知识库页面显示文件列表 → GET /get_files
  - 点击删除某个文件 → DELETE /delete_file/xxx.pdf
===========================================================================
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy.orm import Session
from utils.database import get_db
from models.message import KnowledgeBase  
from schemas.message import FilestResponse, SessionListResponse, SessionResponse
from fastapi_jwt import JwtAuthorizationCredentials
from service.auth import access_security  # JWT 验证器
from typing import List
from sqlalchemy import text, select
from urllib.parse import unquote
from service.document_operations import delete_document

router = APIRouter()

# ==================================================================
# 📌 API 接口 1：获取用户的知识库文件列表
# GET /get_files
#
# 🔑 核心流程：
#   从 JWT Token 中提取 user_id → 查询 knowledgebases 表 → 返回文件列表
# ==================================================================

@router.get("/get_files", response_model=List[FilestResponse])
async def get_documents_by_user_id(
    credentials: JwtAuthorizationCredentials = Security(access_security),
    # ↑ 🔑 JWT 认证：FastAPI 自动验证 Token，提取用户信息到 credentials
    db: Session = Depends(get_db)
    # ↑ 🔑 依赖注入：FastAPI 自动调用 get_db() 获取数据库会话
):
    """获取用户上传的文档列表，需要用户认证"""
    try:
        # 步骤1：从 Token 载荷中提取 user_id
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 步骤2：使用 SQLAlchemy ORM 查询该用户的所有知识库文件
        stmt = select(KnowledgeBase).where(KnowledgeBase.user_id == user_id)
        result = db.execute(stmt).scalars().all()
        # .scalars() 把结果转成 Python 对象列表
        # .all() 获取所有结果

        if not result:
            return []  # 没有文件就返回空列表

        # 步骤3：将 ORM 对象转成 Pydantic 响应模型
        documents = [
            FilestResponse(
                user_id=row.user_id,
                file_name=row.file_name,
                created_at=row.created_at.isoformat(),
                updated_at=row.updated_at.isoformat()
            )
            for row in result
        ]

        return documents

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve documents: {str(e)}"
        )

# ==================================================================
# 📌 API 接口 2：删除知识库中的文件
# DELETE /delete_file/{file_name}
#
# 🔑 核心流程：
#   1. 从 ES（Elasticsearch）中删除该文件的所有分块数据
#   2. 删除本地存储的文件
#   3. 从 PostgreSQL 数据库中删除记录
# ==================================================================

@router.delete("/delete_file/{file_name}")
async def delete_document_endpoint(
    file_name: str,  # 从 URL 路径中获取文件名
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        # URL 解码文件名（中文文件名会被 URL 编码）
        decoded_file_name = unquote(file_name)
        
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 调用 service 层执行删除操作（ES + 本地文件 + 数据库）
        result = delete_document(user_id, decoded_file_name, db)
        
        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])
            
        return {"message": result["message"]}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================================================================
# 📌 API 接口 3：获取某个会话的所有消息记录
# GET /get_messages?session_id=xxx
#
# 🔑 核心流程：
#   根据 session_id 查询 messages 表 → 返回该会话的所有对话记录
#   每条记录包含：用户问题、模型回答、参考文档、推荐问题、思考过程
# ==================================================================

@router.get("/get_messages")
async def get_messages_by_session_id(
    session_id: str,  # 从查询参数获取会话ID
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 使用原生 SQL 查询该会话的所有消息
        messages_data = db.execute(
            text("SELECT message_id, session_id, user_question, model_answer, documents, recommended_questions, think, created_at FROM messages WHERE session_id = :session_id"),
            {"session_id": session_id}
        ).fetchall()

        # 构造返回数据列表
        messages = []
        for message in messages_data:
            messages.append(
                {
                    "message_id": message.message_id,
                    "session_id": message.session_id,
                    "user_question": message.user_question,     # 用户问题
                    "model_answer": message.model_answer,       # 模型回答
                    "documents": message.documents,             # 参考文档（JSON）
                    "recommended_questions": message.recommended_questions,  # 推荐问题
                    "think": message.think,                     # 思考过程（deepseek-r1）
                    "created_at": message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                }
            )

        return messages

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve messages: {str(e)}"
        )

# ==================================================================
# 📌 API 接口 4：获取用户的所有会话列表
# GET /get_sessions
#
# 🔑 核心流程：
#   根据 user_id 查询 sessions 表 → 返回该用户的所有会话
#   前端侧边栏的"会话列表"就是由这个 API 提供数据
# ==================================================================
    
@router.get("/get_sessions", response_model=SessionListResponse)
async def get_sessions_by_user_id(
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 查询该用户的所有会话
        sessions_data = db.execute(
            text("SELECT * FROM sessions WHERE user_id = :user_id"),
            {"user_id": user_id}
        ).fetchall()

        # 构造返回数据
        sessions = []
        for session in sessions_data:
            sessions.append(
                SessionResponse(
                    session_id=session.session_id,
                    session_name=session.session_name,   # 会话名称（大模型自动生成）
                    user_id=session.user_id,
                    created_at=session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    updated_at=session.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                )
            )

        return {"user_id": user_id, "sessions": sessions}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
