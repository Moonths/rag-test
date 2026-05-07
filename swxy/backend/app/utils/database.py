"""
===========================================================================
📌 utils/database.py — 数据库连接与会话管理
===========================================================================

🔰 新手导读：
本项目使用 PostgreSQL 作为关系型数据库，通过 SQLAlchemy ORM 来操作数据库。
这个文件负责：
  1. 创建数据库连接引擎（engine）——相当于打开一条通往数据库的"通道"
  2. 创建会话工厂（SessionLocal）——每次操作数据库都需要一个"会话"
  3. 提供 get_db() 函数——给 FastAPI 的依赖注入系统使用

💡 关键概念：
- SQLAlchemy: Python 最流行的 ORM（对象关系映射）库，让你用 Python 类操作数据库表
- Engine: 数据库连接引擎，管理数据库连接池
- Session: 数据库会话，每次增删改查都在一个 Session 里完成
- ORM: 把数据库表映射成 Python 类，一行数据 = 一个对象

🔗 被谁使用：
  几乎所有需要读写数据库的模块都依赖此文件，比如：
  - router/chat_rt.py → 查询/插入知识库记录
  - service/auth.py → 查询/创建用户
  - service/core/chat.py → 保存对话记录
===========================================================================
"""

from sqlalchemy import create_engine
# create_engine: 创建数据库连接引擎，是 SQLAlchemy 连接数据库的第一步

from sqlalchemy.orm import sessionmaker
# sessionmaker: 会话工厂，用来批量创建数据库会话

from models.base import Base
# Base: 所有数据库模型的基类（见 models/base.py）

import os
from dotenv import load_dotenv
# dotenv: 从 .env 文件加载环境变量（如数据库地址、密钥等敏感信息）

# ==================== 加载环境变量 ====================
load_dotenv()
# 从项目根目录的 .env 文件读取配置，比如：
# DATABASE_URL=postgresql://postgres:pg123456@localhost:5432/gsk

# ==================== 创建数据库连接 ====================
# 🔑 关键步骤：读取数据库连接 URL 并创建引擎
# DATABASE_URL 格式: postgresql://用户名:密码@主机地址:端口/数据库名
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
# engine 就像是一个"连接池管理器"，自动管理多个数据库连接

# ==================== 创建会话工厂 ====================
# 🔑 关键步骤：配置会话的行为
SessionLocal = sessionmaker(
    autocommit=False,  # 不自动提交，需要手动 db.commit()
    autoflush=False,   # 不自动刷新，避免意外的数据库写入
    bind=engine        # 绑定到上面创建的引擎
)

def get_db():
    """
    🔑 关键函数：获取数据库会话（给 FastAPI 依赖注入使用）
    
    💡 使用方式（在路由函数中）：
        @router.get("/xxx")
        async def some_api(db: Session = Depends(get_db)):
            result = db.query(User).all()
            return result
    
    使用 yield 是因为这是一个"生成器"，FastAPI 会：
      1. 调用 get_db()，拿到 db 会话
      2. 把 db 传给路由函数使用
      3. 路由函数执行完后，自动执行 finally 里的 db.close()
    这样确保每次请求结束后数据库连接都会被正确关闭，不会造成连接泄漏
    """
    db = SessionLocal()  # 创建一个新的数据库会话
    try:
        yield db  # 把会话交给调用者使用
    finally:
        db.close()  # 无论成功还是失败，最后都关闭会话

def init_db():
    """
    初始化数据库：根据模型定义自动创建数据库表
    
    💡 这个函数会检查 models/ 目录下定义的所有表，
    如果数据库里没有对应的表，就自动创建。
    """
    Base.metadata.create_all(bind=engine)
