"""
===========================================================================
📌 models/__init__.py — 数据模型包初始化
===========================================================================

🔰 新手导读：
这个文件把所有数据模型类"汇总导出"，方便其他模块一次性导入。
比如其他模块可以写: from models import User, Message, Session

📊 本项目的数据库表一览：
  ┌──────────────────┬──────────────────────────────────┐
  │ 模型类名          │ 对应数据库表及用途                   │
  ├──────────────────┼──────────────────────────────────┤
  │ User             │ users 表 → 存储用户账号信息          │
  │ Session          │ sessions 表 → 存储对话会话           │
  │ Message          │ messages 表 → 存储对话消息记录        │
  │ KnowledgeBase    │ knowledgebases 表 → 存储知识库文件信息 │
  │ DocumentUpload   │ document_uploads 表 → 快速解析上传记录 │
  └──────────────────┴──────────────────────────────────┘
===========================================================================
"""

from models.base import Base
from models.user import User
from models.message import Message, KnowledgeBase
from models.session import Session
from models.document_upload import DocumentUpload

# __all__ 定义了 "from models import *" 时会导出哪些名字
__all__ = ['Base', 'User', 'Message', 'KnowledgeBase', 'Session', 'DocumentUpload']
