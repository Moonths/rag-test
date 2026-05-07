"""
===========================================================================
📌 router/chat_rt.py — 对话路由（⭐ 项目最核心的文件之一 ⭐）
===========================================================================

🔰 新手导读：
这个文件是整个 RAG 系统的"前台入口"，定义了最核心的 API 接口：
  1. POST /create_session     → 创建新对话会话
  2. POST /quick_parse        → 快速文档解析（临时，2小时过期）
  3. GET  /get_parsed_content  → 获取已解析的文档内容
  4. POST /chat_on_docs       → ⭐ RAG 对话（核心！检索 + 大模型生成回答）
  5. POST /upload_files       → 上传文件到永久知识库（解析→向量化→存ES）
  6. GET  /sessions/{id}/documents → 获取会话的文档列表
  7. GET  /sessions/{id}/documents/summary → 获取会话文档摘要

⭐ RAG 对话的完整流程（/chat_on_docs）：
  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │ 用户提问     │ ──→ │ 检索知识库    │ ──→ │ 构造提示词    │ ──→ │ 大模型生成   │
  │ "世运电路    │     │ ES向量+关键词 │     │ 参考内容+问题 │     │ 流式回答     │
  │  成长性如何" │     │ 混合检索      │     │ 拼接成 prompt │     │ SSE推送前端  │
  └─────────────┘     └──────────────┘     └──────────────┘     └──────────────┘

⭐ 文件上传到知识库的完整流程（/upload_files）：
  ┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │ 用户上传  │ ──→ │ 文档解析      │ ──→ │ 文本分块      │ ──→ │ 向量化+存ES  │
  │ PDF/DOCX │     │ 提取文本内容   │     │ 切成小段落    │     │ 建立索引     │
  └──────────┘     └──────────────┘     └──────────────┘     └──────────────┘
===========================================================================
"""

from fastapi import APIRouter, Body, UploadFile, File, HTTPException, Query, Security, status, Depends
import uuid
from schemas.chat import SessionResponse, ChatRequest
from fastapi.responses import StreamingResponse  # 流式响应，用于 SSE（Server-Sent Events）
import os
from dotenv import load_dotenv
from typing import List, Optional

# ==================== 导入核心服务模块 ====================
from service.core.file_parse import execute_insert_process
# ↑ 🔑 文件解析+向量化+插入ES 的完整流程

from service.core.api.utils.file_utils import get_project_base_directory
from fastapi_jwt import JwtAuthorizationCredentials

from service.core.retrieval import retrieve_content
# ↑ 🔑 从 Elasticsearch 检索相关内容

from service.core.chat import get_chat_completion
# ↑ 🔑 调用大模型生成流式回答

from service.auth import access_security
from utils import logger
from database.knowledgebase_operations import insert_knowledgebase, verify_user_knowledgebase
from sqlalchemy.orm import Session
from sqlalchemy import select
from models.message import KnowledgeBase
from utils.database import get_db
from service.quick_parse_service import quick_parse_service
from service.document_upload_service import DocumentUploadService
from schemas.document_upload import DocumentUploadResponse, SessionDocumentsResponse, SessionDocumentSummary
import os

# 加载 .env 环境变量
load_dotenv()

# 启动时打印 ES 连接信息，方便排查问题
logger.info(f"ES_HOST: {os.getenv('ES_HOST')}")
logger.info(f"ELASTICSEARCH_URL: {os.getenv('ELASTICSEARCH_URL')}")

router = APIRouter()

# ==================================================================
# 📌 API 接口 1：创建新的对话会话
# POST /create_session
#
# 💡 每次用户点击"新建对话"时调用
# 🔑 核心逻辑：生成一个 16 位的唯一会话ID
# ==================================================================

@router.post("/create_session", response_model=SessionResponse)
async def create_session(
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        user_id = credentials.subject.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 生成 16 位的 session_id（UUID去掉横线后取前16位）
        session_id = str(uuid.uuid4()).replace("-", "")[:16]

        return {
            "session_id": session_id,
            "status": "success",
            "message": "Session created successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ==================================================================
# 📌 API 接口 2：快速文档解析
# POST /quick_parse?session_id=xxx
#
# 💡 这是"临时文档"功能：用户在对话中上传一个小文档（不超过4页），
#    系统快速解析文本内容 → 存到 Redis（2小时过期）
#    之后对话时可以基于这个文档内容回答问题
#
# 🔑 与 /upload_files 的区别：
#    - quick_parse: 小文档、临时存 Redis、2小时过期、不做向量化
#    - upload_files: 大文档、永久存 ES、做向量化、支持语义检索
# ==================================================================

@router.post("/quick_parse")
async def quick_parse_document(
    session_id: str = Query(..., description="会话ID"),
    # ↑ Query(...) 表示这是必填的查询参数，写在 URL 里: /quick_parse?session_id=xxx
    file: UploadFile = File(..., description="要解析的文档"),
    # ↑ File(...) 表示这是文件上传参数
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    """
    快速文档解析接口
    - 支持文档格式：docx, pdf, txt
    - 限制文档页数不超过4页
    - 每个session_id只能传递一个文档
    - 解析结果存储到Redis，保存时间为2小时
    """
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 步骤1：读取上传文件的二进制内容
        file_content = await file.read()
        
        # 步骤2：获取文件元信息
        file_size = len(file_content)
        file_extension = os.path.splitext(file.filename)[1].lower() if file.filename else ""
        document_type = file_extension.replace(".", "") if file_extension else "unknown"
        
        # 步骤3：🔑 调用快速解析服务（核心逻辑在 service/quick_parse_service.py）
        # 内部流程：验证格式 → 解析文本 → 存入 Redis
        result = quick_parse_service.quick_parse_document(
            session_id=session_id,
            filename=file.filename,
            file_content=file_content
        )
        
        # 步骤4：记录文档上传信息到 PostgreSQL（方便后续查询）
        try:
            DocumentUploadService.create_upload_record(
                db=db,
                session_id=session_id,
                document_name=file.filename,
                document_type=document_type,
                file_size=file_size
            )
            logger.info(f"文档上传记录已保存: session_id={session_id}, document_name={file.filename}")
        except Exception as db_error:
            logger.error(f"保存文档上传记录失败: {str(db_error)}")
            # 数据库记录失败不影响主要功能
        
        logger.info(f"用户 {user_id} 的文档解析完成，session_id: {session_id}")
        return result

    except HTTPException as e:
        logger.error(f"快速解析错误: {str(e)}")
        raise e
    except Exception as e:
        logger.exception(f"快速解析发生未知错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部服务器错误: {str(e)}"
        )

# ==================================================================
# 📌 API 接口 3：获取已解析的文档内容
# GET /get_parsed_content?session_id=xxx
#
# 💡 从 Redis 中读取之前快速解析的文档文本内容
# ==================================================================

@router.get("/get_parsed_content")
async def get_parsed_content(
    session_id: str = Query(..., description="会话ID"),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    """获取已解析的文档内容"""
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 从 Redis 获取解析内容
        result = quick_parse_service.get_parsed_content(session_id)
        
        logger.info(f"用户 {user_id} 获取解析内容，session_id: {session_id}")
        return result

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ==================================================================
# ⭐ API 接口 4：RAG 对话（最核心的接口！！！）
# POST /chat_on_docs?session_id=xxx
# Body: {"message": "用户的问题"}
#
# 🔑🔑🔑 这就是 RAG（Retrieval Augmented Generation）的核心流程：
#
#   第一步【检索 Retrieval】：
#     用户问题 → 从 Elasticsearch 知识库中检索相关文档片段
#     使用混合检索：关键词匹配 + 向量语义相似度
#
#   第二步【增强 Augmented】：
#     将检索到的文档片段 + 快速解析的文档内容 → 拼接成"参考资料"
#     构造 Prompt: "基于以下参考资料回答问题..."
#
#   第三步【生成 Generation】：
#     将 Prompt 发送给大模型（deepseek-r1）→ 流式生成回答
#     通过 SSE（Server-Sent Events）实时推送给前端
#
#   附加步骤：
#     - 生成推荐问题（让用户可以继续深入探索）
#     - 保存对话到数据库（用于历史记录）
#     - 自动生成会话名称（基于第一个问题）
# ==================================================================

@router.post("/chat_on_docs")
async def chat_on_docs(
    session_id: str = Query(...),
    request: ChatRequest = Body(..., description="User message"),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        logger.info(f"开始处理用户 {user_id} 的请求")
        logger.info(f"问题内容: {request.message}")
        
        question = request.message
        
        # ========== 🔑 RAG 第一步：检索（Retrieval）==========
        # 从 Elasticsearch 知识库中检索与问题相关的内容
        # user_id 同时作为 ES 的索引名（每个用户一个独立的知识库索引）
        references = []
        try:
            logger.info("开始检索相关内容...")
            references = retrieve_content(user_id, question)
            # ↑ 🔑 核心调用！会执行：
            #   1. 对问题进行分词
            #   2. 将问题转成向量
            #   3. 在 ES 中进行关键词+向量混合检索
            #   4. 对结果进行重排序
            #   5. 返回最相关的文档片段
            logger.info(f"检索到 {len(references)} 条相关内容")
        except Exception as e:
            logger.info(f"用户 {user_id} 没有知识库或检索失败: {str(e)}，将不使用知识库内容")
            references = []

        # ========== 🔑 RAG 第二步+第三步：增强 + 生成 ==========
        logger.info("开始生成回答...")
        # 返回 SSE 流式响应
        # 💡 StreamingResponse 会持续推送数据给前端，实现"打字机效果"
        return StreamingResponse(
            get_chat_completion(session_id, question, references, user_id),
            # ↑ 🔑 核心调用！内部会：
            #   1. 从 Redis 获取快速解析的文档内容
            #   2. 将检索内容 + 快速解析内容 → 组合成参考资料
            #   3. 构造 Prompt（提示词）
            #   4. 调用大模型（deepseek-r1）流式生成回答
            #   5. 实时推送每个字给前端（SSE格式）
            #   6. 完成后生成推荐问题
            #   7. 保存对话到数据库
            media_type="text/event-stream"
            # ↑ SSE 的 MIME 类型，告诉浏览器这是事件流
        )
    
    except HTTPException as e:
        logger.error(f"HTTP错误: {str(e)}")
        raise e
    except Exception as e:
        logger.exception(f"发生未知错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ==================================================================
# 📌 API 接口 5：上传文件到永久知识库
# POST /upload_files?session_id=xxx
#
# ⭐ 这是知识库构建的核心接口！
# 🔑 完整流程：
#   1. 接收上传的文件
#   2. 保存到本地 storage/file/{session_id}/ 目录
#   3. 🔑 解析文档 → 文本分块 → 向量化 → 存入 Elasticsearch
#   4. 在 PostgreSQL 中记录知识库元信息
#
# 💡 这个过程就是 RAG 的"离线阶段"——预处理文档，为后续检索做准备
# ==================================================================

@router.post("/upload_files")
async def upload_files(
    session_id: Optional[str] = Query(None),
    files: List[UploadFile] = File(...),  # 支持多文件上传
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 如果没有 session_id，使用 user_id（知识库与用户绑定）
        if session_id is None:
            session_id = user_id

        # ========== 步骤1：准备文件存储目录 ==========
        storage_dir = os.path.join(get_project_base_directory(), "storage/file")
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
        
        session_dir = os.path.join(storage_dir, session_id)
        if not os.path.exists(session_dir):
            os.makedirs(session_dir)
        
        # ========== 步骤2：检查文件名是否重复 ==========
        existing_files = []
        for file in files:
            file_name = file.filename
            stmt = select(KnowledgeBase).where(
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.file_name == file_name
            )
            existing_file = db.execute(stmt).scalar_one_or_none()
            if existing_file:
                existing_files.append(file_name)
        
        if existing_files:
            raise HTTPException(
                status_code=400,
                detail=f"以下文件已存在，请勿重复上传: {', '.join(existing_files)}"
            )

        # ========== 步骤3：逐个处理文件上传 ==========
        successful_files = []
        failed_files = []
        
        for file in files:
            file_name = file.filename
            file_path = os.path.join(session_dir, file_name)
            
            try:
                # 读取文件内容
                file_content = await file.read()
                
                if not file_content:
                    failed_files.append(f"{file_name}: 文件内容为空")
                    continue
                
                # Excel 文件格式验证（检查文件头魔数）
                if file_name.lower().endswith(('.xlsx', '.xls')):
                    if file_name.lower().endswith('.xlsx'):
                        if not file_content.startswith(b'PK'):
                            failed_files.append(f"{file_name}: 不是有效的 XLSX 文件格式，可能是 XLS 文件")
                            continue
                    elif file_name.lower().endswith('.xls'):
                        if not (file_content.startswith(b'\xd0\xcf\x11\xe0') or 
                               file_content.startswith(b'\x09\x08')):
                            failed_files.append(f"{file_name}: 不是有效的 XLS 文件格式")
                            continue
                
                # 保存文件到本地
                with open(file_path, "wb") as buffer:
                    buffer.write(file_content)
                
                # 验证文件大小一致
                if os.path.getsize(file_path) != len(file_content):
                    failed_files.append(f"{file_name}: 文件保存失败，大小不匹配")
                    continue
                
                file_url = f"{storage_dir}/{session_id}/{file_name}"
                logger.info(f"Processing file: {file_url}")

                # ========== 🔑🔑🔑 步骤4：文档解析 → 向量化 → 存入 ES ==========
                # 这是 RAG "离线阶段"的核心步骤！
                try:
                    execute_insert_process(file_url, file_name, session_id)
                    # ↑ 🔑 核心调用！内部完整流程：
                    #   1. parse(): 解析文档（PDF/DOCX/Excel/TXT）→ 提取文本
                    #   2. chunk(): 将长文本切分成小块（chunking）
                    #   3. tokenize(): 对每个小块进行分词
                    #   4. generate_embedding(): 调用大模型API将文本转成向量
                    #   5. es_connection.insert(): 将文本+向量存入 Elasticsearch
                    logger.info(f"数据插入es成功: {file_name}")
                    
                    # 在 PostgreSQL 中记录知识库元信息
                    insert_knowledgebase(user_id, file_name)
                    logger.info(f"数据插入pg成功: {file_name}")
                    
                    successful_files.append(file_name)
                    
                except Exception as parse_error:
                    logger.error(f"文件解析失败 {file_name}: {str(parse_error)}")
                    failed_files.append(f"{file_name}: 文件解析失败 - {str(parse_error)}")
                    if os.path.exists(file_path):
                        os.remove(file_path)  # 解析失败则删除已保存的文件
                    continue
                        
            except Exception as e:
                logger.error(f"处理文件失败 {file_name}: {str(e)}")
                failed_files.append(f"{file_name}: 处理失败 - {str(e)}")
                continue

        # ========== 步骤5：构建返回结果 ==========
        if successful_files and not failed_files:
            return {
                "status": "success",
                "message": "所有文件解析成功",
                "successful_files": successful_files,
                "total_files": len(files)
            }
        elif successful_files and failed_files:
            return {
                "status": "partial_success",
                "message": f"部分文件解析成功，{len(successful_files)} 个成功，{len(failed_files)} 个失败",
                "successful_files": successful_files,
                "failed_files": failed_files,
                "total_files": len(files)
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "failed",
                    "message": "所有文件解析失败",
                    "failed_files": failed_files,
                    "total_files": len(files)
                }
            )
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ==================================================================
# 📌 API 接口 6：获取会话的文档上传记录列表
# GET /sessions/{session_id}/documents
# ==================================================================

@router.get("/sessions/{session_id}/documents", response_model=SessionDocumentsResponse)
async def get_session_documents(
    session_id: str,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    """获取指定会话的所有文档上传记录"""
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        documents = DocumentUploadService.get_session_documents(db, session_id)
        has_documents = len(documents) > 0
        
        return SessionDocumentsResponse(
            session_id=session_id,
            has_documents=has_documents,
            documents=[DocumentUploadResponse.from_orm(doc) for doc in documents],
            total_count=len(documents)
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"获取会话文档信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ==================================================================
# 📌 API 接口 7：获取会话文档摘要
# GET /sessions/{session_id}/documents/summary
# ==================================================================

@router.get("/sessions/{session_id}/documents/summary", response_model=SessionDocumentSummary)
async def get_session_document_summary(
    session_id: str,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    """获取指定会话的文档上传摘要信息"""
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        has_documents = DocumentUploadService.has_uploaded_documents(db, session_id)
        latest_document = DocumentUploadService.get_latest_document(db, session_id)
        all_documents = DocumentUploadService.get_session_documents(db, session_id)
        total_documents = len(all_documents)
        
        return SessionDocumentSummary(
            session_id=session_id,
            has_documents=has_documents,
            latest_document_name=latest_document.document_name if latest_document else None,
            latest_document_type=latest_document.document_type if latest_document else None,
            latest_upload_time=latest_document.upload_time if latest_document else None,
            total_documents=total_documents
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"获取会话文档摘要失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
