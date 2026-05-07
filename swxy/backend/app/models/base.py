"""
===========================================================================
📌 models/base.py — 数据库模型基类
===========================================================================

🔰 新手导读：
这是所有数据库模型（表）的"祖先类"。
在 SQLAlchemy ORM 中，每个 Python 类对应数据库中的一张表，
但这些类都需要继承同一个基类 Base，SQLAlchemy 才能识别和管理它们。

💡 类比理解：
  Base 就像是一个"模板工厂"，所有表的定义（User、Session、Message等）
  都要从这个工厂"继承"出来，SQLAlchemy 才知道它们是数据库表。

🔗 被谁继承：
  - models/user.py → User 表
  - models/session.py → Session 表（会话）
  - models/message.py → Message 表（消息）、KnowledgeBase 表（知识库）
  - models/document_upload.py → DocumentUpload 表（文档上传记录）
===========================================================================
"""

from sqlalchemy.ext.declarative import declarative_base

# 🔑 关键步骤：创建 ORM 基类
# 所有数据模型类都必须继承这个 Base
# 这样 SQLAlchemy 就能自动追踪所有表的定义，并在需要时创建/修改它们
Base = declarative_base()
