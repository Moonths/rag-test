"""
===========================================================================
📌 models/document_upload.py — 文档上传记录表模型
===========================================================================

🔰 新手导读：
这张表记录"快速解析"功能中用户上传的文档信息。
与 knowledgebases 表不同，这张表关联的是"会话级别"的文档上传，
即用户在某次对话中临时上传的文档（解析后存 Redis，2小时过期）。

💡 两种文档上传方式对比：
  1. 知识库上传（/upload_files）→ 永久存储 → 记录在 knowledgebases 表 → 存入 ES
  2. 快速解析（/quick_parse）→ 临时存储（2小时）→ 记录在 document_uploads 表 → 存入 Redis

📊 document_uploads 表结构：
  ┌───────────────┬──────────────┬─────────────────────────┐
  │ 字段名         │ 类型          │ 说明                     │
  ├───────────────┼──────────────┼─────────────────────────┤
  │ id            │ Integer      │ 主键，自增                │
  │ session_id    │ String(16)   │ 所属会话ID               │
  │ document_name │ String(255)  │ 文档名称                  │
  │ document_type │ String(50)   │ 文档类型（pdf/docx/txt）   │
  │ file_size     │ Integer      │ 文件大小（字节）            │
  │ upload_time   │ TIMESTAMP    │ 上传时间                   │
  │ created_at    │ TIMESTAMP    │ 创建时间                   │
  │ updated_at    │ TIMESTAMP    │ 更新时间                   │
  └───────────────┴──────────────┴─────────────────────────┘
===========================================================================
"""

from sqlalchemy import Column, Integer, String, TIMESTAMP
from sqlalchemy.sql import func
from models.base import Base

class DocumentUpload(Base):
    __tablename__ = 'document_uploads'
    
    id = Column(Integer, primary_key=True, autoincrement=True)     # 自增主键
    session_id = Column(String(16), nullable=False)                # 所属会话ID
    document_name = Column(String(255), nullable=False)            # 文档名称
    document_type = Column(String(50), nullable=False)             # 文档类型（pdf/docx/txt）
    file_size = Column(Integer)                                    # 文件大小（字节）
    upload_time = Column(TIMESTAMP, nullable=False, server_default=func.now())   # 上传时间
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())    # 创建时间
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now())    # 更新时间
