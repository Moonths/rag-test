"""
===========================================================================
📌 schemas/chat.py — 对话相关的请求/响应数据结构定义
===========================================================================

🔰 新手导读：
Schema（模式）定义了 API 接口的"数据契约"——即请求应该包含什么字段，
响应应该返回什么字段。使用 Pydantic 库来定义。

💡 关键概念：
- Pydantic BaseModel: 数据验证模型，自动校验请求数据类型和格式
  比如定义了 message: str，如果前端传了一个数字，FastAPI 会自动报错
- 请求模型(Request): 定义前端发给后端的数据格式
- 响应模型(Response): 定义后端返回给前端的数据格式

💡 Schema vs Model 的区别：
  - Model（models/）→ 对应数据库表结构，用于数据库增删改查
  - Schema（schemas/）→ 对应 API 接口数据格式，用于请求校验和响应序列化
  它们长得很像，但职责不同！
===========================================================================
"""

from pydantic import BaseModel
from typing import List

# ==================================================================
# 📌 创建会话相关的数据结构
# 对应 API: POST /create_session
# ==================================================================

class SessionResponse(BaseModel):
    """创建会话的响应模型"""
    session_id: str   # 新创建的会话ID（16位UUID）
    status: str       # 状态：success / error
    message: str      # 提示消息

# ==================================================================
# 📌 文档检索相关的数据结构（目前未使用，保留备用）
# ==================================================================

class ExploreRequest(BaseModel):
    """检索请求：用户发送一条消息来检索相关文档"""
    user_message: str  # 用户消息内容

class DocumentResponse(BaseModel):
    """单个文档的响应结构"""
    document_id: str      # 文档ID
    document_name: str    # 文档名称
    preview: str          # 文档预览内容
    create_time: int      # 创建时间戳
    update_time: int      # 更新时间戳

class ExploreResponse(BaseModel):
    """检索响应：返回匹配到的文档列表"""
    documents: List[DocumentResponse]  # 文档列表
    message: str                       # 提示消息
    status: str                        # 状态

# ==================================================================
# 📌 添加文档到上下文相关的数据结构（目前未使用，保留备用）
# ==================================================================

class AddDocsRequest(BaseModel):
    """添加文档请求"""
    document_id: List[str]  # 要添加的文档ID列表

class AddDocsResponse(BaseModel):
    """添加文档响应"""
    status: str    # 状态
    message: str   # 提示消息

# ==================================================================
# 📌 对话请求数据结构
# 对应 API: POST /chat_on_docs
# 🔑 这是 RAG 对话的核心请求结构
# ==================================================================

class ChatRequest(BaseModel):
    """
    用户对话请求模型
    
    前端发送格式：
    {
        "message": "世运电路的成长性如何？"
    }
    """
    message: str  # 用户的提问内容
