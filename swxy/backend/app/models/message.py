"""
===========================================================================
📌 models/message.py — 消息表 + 知识库表模型
===========================================================================

🔰 新手导读：
这个文件定义了两张核心表：
  1. messages 表：存储每一轮对话（用户问题 + 模型回答 + 检索内容）
  2. knowledgebases 表：记录用户上传了哪些文件到知识库

💡 RAG 对话的数据流：
  用户提问 → 检索知识库 → 大模型生成回答 → 一整条记录存入 messages 表
  包含：用户问题、模型回答、参考文档、推荐问题、思考过程

📊 messages 表结构：
  ┌────────────────────────┬────────────┬──────────────────────────┐
  │ 字段名                  │ 类型        │ 说明                      │
  ├────────────────────────┼────────────┼──────────────────────────┤
  │ message_id             │ UUID       │ 主键，自动生成UUID          │
  │ session_id             │ String(16) │ 所属会话ID                 │
  │ user_question          │ Text       │ 用户的提问内容              │
  │ model_answer           │ Text       │ 大模型的回答内容            │
  │ create_time            │ TIMESTAMP  │ 创建时间                   │
  │ retrieval_content      │ Text       │ 检索到的参考文档内容（JSON） │
  └────────────────────────┴────────────┴──────────────────────────┘

📊 knowledgebases 表结构：
  ┌──────────────┬──────────────┬──────────────────────────┐
  │ 字段名        │ 类型          │ 说明                      │
  ├──────────────┼──────────────┼──────────────────────────┤
  │ id           │ Integer      │ 主键，自增                 │
  │ user_id      │ String(255)  │ 用户ID                    │
  │ file_name    │ String(255)  │ 上传的文件名               │
  │ created_at   │ TIMESTAMP    │ 创建时间                   │
  │ updated_at   │ TIMESTAMP    │ 更新时间                   │
  └──────────────┴──────────────┴──────────────────────────┘

🔗 在哪里被使用：
  - messages 表: service/core/chat.py → write_chat_to_db() 保存对话
  - knowledgebases 表: router/chat_rt.py → upload_files 检查文件重复
  - knowledgebases 表: database/knowledgebase_operations.py → 插入知识库记录
===========================================================================
"""

from sqlalchemy import Column, String, Text, TIMESTAMP, Integer
from sqlalchemy.dialects.postgresql import UUID  # PostgreSQL 特有的 UUID 类型
from sqlalchemy.sql import func
from models.base import Base

class Message(Base):
    """
    消息表：存储每一轮 RAG 对话的完整信息
    
    一条 Message = 一次完整的"问答对"，包含：
    - 用户问了什么
    - 模型回答了什么
    - 检索到了哪些参考文档
    """
    __tablename__ = "messages"

    message_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    # 消息ID，使用 PostgreSQL 的 gen_random_uuid() 自动生成
    
    session_id = Column(String(16), nullable=False)
    # 所属会话ID，关联到 sessions 表
    
    user_question = Column(Text, nullable=False)
    # 用户的提问内容
    
    model_answer = Column(Text, nullable=False)
    # 大模型生成的回答内容
    
    create_time = Column(TIMESTAMP, server_default=func.now())
    # 创建时间
    
    retrieval_content = Column(Text)
    # 检索到的参考文档内容（JSON格式存储）

class KnowledgeBase(Base):
    """
    知识库表：记录用户上传的文件信息
    
    💡 注意：这里存的是"文件元信息"（文件名、用户ID等），
    文件的实际内容被解析成向量后存在 Elasticsearch 中。
    
    每当用户上传一个文件到知识库，就在这张表里添加一条记录。
    """
    __tablename__ = 'knowledgebases'
    
    id = Column(Integer, primary_key=True, autoincrement=True)  # 自增主键
    user_id = Column(String(255), nullable=False)               # 用户ID（以用户为单位隔离知识库）
    file_name = Column(String(255), nullable=False)             # 文件名称
    created_at = Column(TIMESTAMP, nullable=False, server_default='CURRENT_TIMESTAMP')
    updated_at = Column(TIMESTAMP, nullable=False, server_default='CURRENT_TIMESTAMP')
