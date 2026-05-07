"""
===========================================================================
📌 models/session.py — 会话表模型
===========================================================================

🔰 新手导读：
这个文件定义了 sessions 表，用于存储用户的"对话会话"。
一个会话 = 一次完整的对话上下文（类似微信里的一个聊天窗口）。
用户每次点击"新建对话"就会创建一条 Session 记录。

💡 业务流程：
  用户点击"新建对话" → 前端调用 /create_session → 生成 session_id
  → 用户开始提问 → 系统根据第一个问题自动生成 session_name
  → session_name 和 session_id 一起存入这张表

📊 sessions 表结构：
  ┌──────────────┬──────────────┬──────────────────────────┐
  │ 字段名        │ 类型          │ 说明                      │
  ├──────────────┼──────────────┼──────────────────────────┤
  │ session_id   │ String(16)   │ 主键，16位UUID             │
  │ session_name │ String(255)  │ 会话名称（由大模型自动生成）  │
  │ user_id      │ String(255)  │ 所属用户ID                 │
  │ created_at   │ TIMESTAMP    │ 创建时间                    │
  │ updated_at   │ TIMESTAMP    │ 更新时间                    │
  └──────────────┴──────────────┴──────────────────────────┘

🔗 在哪里被使用：
  - service/core/chat.py → update_session_name() 创建/更新会话
  - router/history_rt.py → get_sessions 查询用户的所有会话
===========================================================================
"""

from sqlalchemy import Column, String, TIMESTAMP
from sqlalchemy.sql import func  # func.now() 用于获取数据库当前时间
from models.base import Base

class Session(Base):
    __tablename__ = 'sessions'
    
    session_id = Column(String(16), primary_key=True)       # 会话ID，16位字符串，主键
    session_name = Column(String(255), nullable=False)       # 会话名称（大模型根据首次提问自动生成）
    user_id = Column(String(255), nullable=False)            # 所属用户ID
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())  # 创建时间（数据库自动填入）
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now())  # 更新时间
