"""
===========================================================================
📌 app_main.py — 整个后端项目的"总入口"（相当于一栋大楼的大门）
===========================================================================

🔰 新手导读：
这是你阅读这个 RAG（检索增强生成）项目的第一个文件。
整个后端使用 FastAPI 框架搭建，FastAPI 是一个现代、高性能的 Python Web 框架。
本文件的职责很简单：
  1. 创建 FastAPI 应用实例
  2. 配置跨域中间件（让前端能正常访问后端）
  3. 注册所有路由（把不同功能的 API 接口挂载进来）
  4. 启动 Web 服务器

💡 关键概念：
- FastAPI: Python Web 框架，自动生成 API 文档，支持异步请求
- CORS: 跨域资源共享，浏览器安全机制，允许前端(如localhost:3000)访问后端(如localhost:8000)
- Router: 路由器，将不同功能的 API 接口分模块管理
- uvicorn: ASGI 服务器，用于运行 FastAPI 应用

🔗 项目整体架构（建议按此顺序阅读代码）：
  app_main.py（你在这里）
      ↓ 注册路由
  router/user_rt.py     → 用户注册/登录
  router/chat_rt.py     → 文档上传/解析/对话（核心！）
  router/history_rt.py  → 历史记录查询
      ↓ 路由调用服务层
  service/auth.py       → 认证服务（JWT Token）
  service/core/chat.py  → 对话生成（调用大模型）
  service/core/retrieval.py → 知识检索（从ES检索相关内容）
  service/core/file_parse.py → 文档解析+向量化+存储到ES
      ↓ 底层支撑
  utils/database.py     → 数据库连接（PostgreSQL）
  service/core/rag/     → RAG 引擎（分词、检索、排序）
===========================================================================
"""

# ==================== 第一步：导入依赖 ====================
from fastapi import FastAPI
# FastAPI 是本项目使用的 Web 框架，类似于 Flask，但性能更好，支持异步

from fastapi.middleware.cors import CORSMiddleware
# CORS 中间件：解决"跨域"问题
# 比如前端运行在 http://localhost:3000，后端在 http://localhost:8000
# 浏览器默认会阻止跨域请求，加了这个中间件就允许了

from router import chat_rt    # 💬 对话相关路由（文档上传、解析、RAG对话 —— 项目核心功能）
from router import user_rt    # 👤 用户相关路由（注册、登录）
from router import history_rt # 📜 历史记录路由（查询会话、消息、文档列表）
import os

# ==================== 第二步：读取配置 ====================
# 从环境变量获取 root_path（部署时可能通过 Nginx 反向代理，需要设置根路径）
root_path = os.getenv("ROOT_PATH", "http://localhost:8000")

# ==================== 第三步：创建 FastAPI 应用实例 ====================
# 💡 这一行创建了整个 Web 应用，所有 API 接口都会注册到这个 app 上
app = FastAPI(root_path=root_path)

# ==================== 第四步：配置 CORS 跨域中间件 ====================
# 🔑 关键步骤：没有这个配置，前端无法正常调用后端 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 允许所有来源访问（生产环境应该限制为前端域名）
    allow_credentials=True,   # 允许携带 Cookie
    allow_methods=["*"],      # 允许所有 HTTP 方法（GET、POST、PUT、DELETE 等）
    allow_headers=["*"],      # 允许所有请求头
)

# ==================== 第五步：注册路由（挂载各功能模块的 API） ====================
# 💡 相当于告诉 FastAPI："这些路由里定义的 API 接口，都归我管"
# 每个路由文件里定义了一组相关的 API，比如：
#   chat_rt → /create_session, /upload_files, /chat_on_docs, /quick_parse 等
#   user_rt → /login, /register 等
#   history_rt → /get_sessions, /get_messages, /get_files 等
app.include_router(chat_rt.router)     # 挂载对话功能路由
app.include_router(user_rt.router)     # 挂载用户功能路由
app.include_router(history_rt.router)  # 挂载历史记录路由

# ==================== 第六步：启动服务器 ====================
if __name__=='__main__':
    import uvicorn
    # uvicorn 是 ASGI 服务器，负责接收 HTTP 请求并转发给 FastAPI 处理
    # host="0.0.0.0" 表示监听所有网络接口（局域网内其他机器也能访问）
    # port=8000 表示在 8000 端口启动服务
    # 启动后可以访问 http://localhost:8000/docs 查看自动生成的 API 文档
    uvicorn.run(app, host="0.0.0.0", port=8000)
