"""
===========================================================================
📌 schemas/message.py — 消息、文档、会话的响应数据结构
===========================================================================

🔰 新手导读：
这个文件定义了"历史记录查询"相关的响应格式：
  - MessageResponse: 单条对话消息
  - FilestResponse: 用户上传的文件信息
  - SessionResponse: 单个会话信息
  - SessionListResponse: 会话列表

🔗 被哪些 API 使用：
  - GET /get_messages → 使用 MessageResponse
  - GET /get_files → 使用 FilestResponse
  - GET /get_sessions → 使用 SessionListResponse
===========================================================================
"""

from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime
from typing import List, Union


class MessageResponse(BaseModel):
    """
    单条对话消息的响应模型
    
    包含一次完整的"问答对"信息：
    - 用户问了什么
    - 模型回答了什么
    - 引用了哪些文档
    - 推荐了哪些后续问题
    - 模型的思考过程（deepseek-r1 特有的 reasoning）
    """
    message_id: UUID4                                        # 消息UUID
    session_id: str                                          # 所属会话ID
    user_question: str                                       # 用户的提问
    model_answer: str                                        # 大模型的回答
    created_at: datetime                                     # 创建时间
    documents: Optional[Union[list, dict]] = None            # 引用的参考文档列表
    recommended_questions: Optional[Union[list, dict]] = None # 推荐的后续问题
    think: Optional[str]                                     # 模型的思考过程（deepseek-r1 的 reasoning_content）

    class Config:
        orm_mode = True  # 允许直接从 ORM 模型实例转换（SQLAlchemy 对象 → Pydantic 模型）

class FilestResponse(BaseModel):
    """用户上传的文件信息响应模型"""
    user_id: str       # 用户ID
    file_name: str     # 文件名
    created_at: str    # 创建时间
    updated_at: str    # 更新时间

class SessionResponse(BaseModel):
    """单个会话的响应模型"""
    session_id: str     # 会话ID
    session_name: str   # 会话名称（大模型自动生成）
    user_id: str        # 所属用户ID
    created_at: str     # 创建时间
    updated_at: str     # 更新时间

class SessionListResponse(BaseModel):
    """
    会话列表的响应模型
    
    返回格式：
    {
        "user_id": "123",
        "sessions": [
            {"session_id": "abc", "session_name": "关于世运电路的讨论", ...},
            {"session_id": "def", "session_name": "AI技术问答", ...}
        ]
    }
    """
    user_id: str                     # 用户ID
    sessions: List[SessionResponse]  # 该用户的所有会话列表
