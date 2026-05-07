"""
===========================================================================
📌 schemas/document_upload.py — 文档上传相关的响应数据结构
===========================================================================

🔰 新手导读：
这个文件定义了"快速文档解析"功能相关的响应格式：
  - DocumentUploadResponse: 单个文档上传记录
  - SessionDocumentsResponse: 某个会话的所有文档列表
  - SessionDocumentSummary: 某个会话的文档摘要信息

🔗 被哪些 API 使用：
  - GET /sessions/{session_id}/documents → 返回完整文档列表
  - GET /sessions/{session_id}/documents/summary → 返回文档摘要
===========================================================================
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class DocumentUploadResponse(BaseModel):
    """单个文档上传记录的响应模型"""
    id: int                     # 记录ID
    session_id: str             # 所属会话ID
    document_name: str          # 文档名称
    document_type: str          # 文档类型（pdf/docx/txt）
    file_size: Optional[int]    # 文件大小（字节），可选
    upload_time: datetime       # 上传时间
    created_at: datetime        # 创建时间
    updated_at: datetime        # 更新时间
    
    class Config:
        from_attributes = True  # Pydantic v2 写法，等同于 orm_mode = True


class SessionDocumentsResponse(BaseModel):
    """会话文档列表响应模型——返回某个会话上传的所有文档"""
    session_id: str                            # 会话ID
    has_documents: bool                        # 是否有上传的文档
    documents: List[DocumentUploadResponse]    # 文档列表
    total_count: int                           # 文档总数
    
    class Config:
        from_attributes = True


class SessionDocumentSummary(BaseModel):
    """
    会话文档摘要响应模型——只返回概要信息（更轻量）
    
    适合前端"快速判断"该会话是否有文档，
    不需要拿到完整文档列表的场景。
    """
    session_id: str                                    # 会话ID
    has_documents: bool                                # 是否有文档
    latest_document_name: Optional[str] = None         # 最新上传的文档名
    latest_document_type: Optional[str] = None         # 最新上传的文档类型
    latest_upload_time: Optional[datetime] = None      # 最新上传时间
    total_documents: int = 0                           # 文档总数
    
    class Config:
        from_attributes = True
