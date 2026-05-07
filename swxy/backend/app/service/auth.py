"""
===========================================================================
📌 service/auth.py — 用户认证服务（登录/注册/JWT Token）
===========================================================================

🔰 新手导读：
这个文件是用户认证的核心，处理：
  1. 用户登录 → 验证用户名密码 → 生成 JWT Token
  2. 用户注册 → 检查用户名是否存在 → 密码加密 → 存入数据库
  3. JWT Token 验证 → 保护需要登录才能访问的 API

💡 关键概念 —— JWT (JSON Web Token)：
  JWT 是一种"令牌"机制，相当于一张"通行证"：
  1. 用户登录成功 → 后端生成一个 Token（加密的字符串）
  2. 前端把 Token 保存起来（localStorage）
  3. 之后每次请求 API 时，在请求头里带上: Authorization: Bearer <token>
  4. 后端收到请求后，验证 Token 的合法性，从中提取 user_id
  
  Token 内容示例（解码后）：
  {
      "user_id": 1,
      "user_name": "zhangsan",
      "salting": "abc123..."  ← 随机盐值，增加安全性
  }

🔗 认证流程图：
  用户输入用户名密码 → POST /login
      → service/auth.py 的 authenticate() 函数
      → 查数据库验证密码
      → 生成 JWT Token 返回给前端
      
  前端拿着 Token → GET /get_sessions（或其他需要认证的 API）
      → FastAPI 自动用 access_security 验证 Token
      → 提取 user_id → 执行对应业务逻辑
===========================================================================
"""

from utils.database import get_db, SessionLocal
from models.user import User
from utils.password import verify_password  # 密码验证工具
from sqlalchemy.exc import SQLAlchemyError
from exceptions.auth import AuthError       # 自定义认证异常
from fastapi_jwt import JwtAccessBearerCookie  # JWT 令牌工具库
import secrets                              # Python 内置的安全随机数生成器
from datetime import timedelta
import os
import logging

# ==================== JWT 配置 ====================
# 🔑 关键配置：JWT 密钥（用于加密/解密 Token）
# 从环境变量读取密钥，加上后缀 'happy' 增加唯一性
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'default_secret_key') + 'happy'

# 🔑 关键对象：JWT 安全验证器
# 这个对象会被其他路由文件引用，用于保护 API 接口
# 使用方式：credentials: JwtAuthorizationCredentials = Security(access_security)
access_security = JwtAccessBearerCookie(
    secret_key=JWT_SECRET_KEY,
    auto_error=True,                          # Token 无效时自动报错（返回 401）
    access_expires_delta=timedelta(days=2)     # Token 有效期为 2 天
)

def create_token(user_id: int, user_name: str, salting: str = ""):
    """
    🔑 关键函数：创建 JWT Token
    
    将用户信息加密成一个 Token 字符串，前端保存后每次请求携带。
    
    Args:
        user_id: 用户ID（从数据库查到的）
        user_name: 用户名
        salting: 盐值（这里未使用外部传入，内部自动生成）
    
    Returns:
        str: JWT Token 字符串，如 "eyJhbGciOiJIUzI1NiIs..."
    """
    # Token 的"载荷"部分，包含用户信息
    subject = {
        "user_id": user_id,
        "user_name": user_name,
        "salting": secrets.token_hex(16)  # 16字节随机盐值，防止Token被猜测
    }
    
    # 使用 access_security 创建 Token
    access_token = access_security.create_access_token(subject=subject)
    
    return access_token


def authenticate(username: str, password: str) -> str:
    """
    🔑 关键函数：用户登录认证
    
    完整流程：
      1. 根据用户名查询数据库
      2. 如果用户不存在 → 抛出 AuthError
      3. 验证密码哈希是否匹配
      4. 如果密码错误 → 抛出 AuthError
      5. 密码正确 → 创建 JWT Token 返回
    
    Args:
        username: 用户名
        password: 明文密码
    
    Returns:
        str: JWT Token（登录成功时）
    
    Raises:
        AuthError: 认证失败时抛出
    """
    db = next(get_db())  # 获取数据库会话
    try:
        # 步骤1：根据用户名查询用户
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            raise AuthError("认证失败")  # 用户不存在
        
        # 步骤2：验证密码（明文密码 vs 数据库中的哈希密码）
        if not verify_password(password, user.password_hash):
            raise AuthError("认证失败")  # 密码不匹配
        
        # 步骤3：生成并返回 JWT Token
        return create_token(user.id, user.username)
    
    except SQLAlchemyError as e:
        raise AuthError("认证失败") from e
    finally:
        db.close()  # 确保数据库连接关闭

def register_user(username: str, password: str):
    """
    🔑 关键函数：用户注册
    
    完整流程：
      1. 检查用户名是否已被注册
      2. 对密码进行 bcrypt 哈希加密
      3. 创建新用户记录
      4. 提交到数据库
    
    Args:
        username: 用户名
        password: 明文密码
    
    Raises:
        AuthError: 用户名已存在或注册失败时抛出
    """
    from utils.password import hash_password  # 密码加密工具
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info(f"开始注册用户: {username}")
    db = next(get_db())
    try:
        # 步骤1：检查用户名是否已存在
        logger.info("检查用户名是否已存在...")
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            logger.warning(f"用户名 {username} 已存在")
            raise AuthError("用户名已存在")
        
        # 步骤2：对密码进行哈希加密（永远不存明文密码！）
        logger.info("开始密码哈希处理...")
        password_hash = hash_password(password)
        logger.info("密码哈希处理完成")
        
        # 步骤3：创建新用户对象
        logger.info("创建新用户记录...")
        new_user = User(username=username, password_hash=password_hash)
        db.add(new_user)  # 添加到数据库会话
        
        # 步骤4：提交事务（真正写入数据库）
        logger.info("提交数据库事务...")
        db.commit()
        logger.info(f"用户 {username} 注册成功")
        
    except SQLAlchemyError as e:
        logger.error(f"数据库操作失败: {str(e)}")
        db.rollback()  # 出错时回滚事务
        raise AuthError(f"注册失败: {str(e)}")
    except Exception as e:
        logger.error(f"注册过程中发生未知错误: {str(e)}")
        db.rollback()
        raise AuthError(f"注册失败: {str(e)}")
    finally:
        db.close()
        logger.info("数据库连接已关闭")
