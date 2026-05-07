"""
===========================================================================
📌 models/user.py — 用户表模型
===========================================================================

🔰 新手导读：
这个文件定义了 users 表的结构，对应数据库中存储用户信息的表。
每个注册用户在这张表里都有一条记录。

💡 ORM 映射关系：
  Python 类 User ←→ 数据库表 users
  类的属性    ←→ 表的列（字段）
  类的实例    ←→ 表的一行数据

📊 users 表结构：
  ┌──────────────┬─────────────┬─────────────────────────┐
  │ 字段名        │ 类型         │ 说明                     │
  ├──────────────┼─────────────┼─────────────────────────┤
  │ id           │ Integer     │ 主键，自动递增             │
  │ username     │ String(50)  │ 用户名，唯一，不可为空       │
  │ password_hash│ String(100) │ 密码哈希值，不可为空        │
  └──────────────┴─────────────┴─────────────────────────┘

🔗 在哪里被使用：
  - service/auth.py → 注册时创建用户、登录时查询用户验证密码
===========================================================================
"""

from sqlalchemy import Column, Integer, String
from models.base import Base

class User(Base):
    __tablename__ = 'users'  # 指定对应的数据库表名
    
    id = Column(Integer, primary_key=True)              # 用户ID，自增主键
    username = Column(String(50), unique=True, nullable=False)   # 用户名，唯一且不能为空
    password_hash = Column(String(100), nullable=False)  # 密码的哈希值（不存明文密码！）
