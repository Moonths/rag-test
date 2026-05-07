"""
===========================================================================
📌 router/user_rt.py — 用户路由（注册、登录、语音Token）
===========================================================================

🔰 新手导读：
这个文件定义了用户相关的 API 接口：
  1. POST /login     → 用户登录，返回 JWT Token
  2. POST /register  → 用户注册
  3. POST /sts-token → 获取语音服务临时凭证（字节跳动语音API）

💡 关键概念 —— RESTful API：
  - POST: 创建资源（注册用户、登录获取Token）
  - GET: 读取资源（查询数据）
  - PUT: 更新资源
  - DELETE: 删除资源

🔗 完整的登录流程：
  前端 → POST /login {username, password}
       → 后端 authenticate() 验证用户名密码
       → 成功：返回 JWT Token
       → 前端保存 Token，后续请求携带 Token
===========================================================================
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from exceptions.auth import AuthError
from service.auth import authenticate, register_user  # 认证服务
from pydantic import BaseModel
import httpx     # httpx: 异步 HTTP 客户端（类似 requests，但支持异步）
import asyncio

router = APIRouter()  # 创建路由器实例

# ==================================================================
# 📌 请求体定义：定义前端发送的数据格式
# ==================================================================

class LoginRequest(BaseModel):
    """登录请求体"""
    username: str   # 用户名
    password: str   # 密码

class RegisterRequest(BaseModel):
    """注册请求体"""
    username: str   # 用户名
    password: str   # 密码

class STSTokenRequest(BaseModel):
    """语音服务 STS Token 请求体"""
    appid: str       # 应用ID
    accessKey: str   # 访问密钥

# ==================================================================
# 📌 API 接口 1：用户登录
# POST /login
#
# 🔑 核心流程：
#   前端发送 {username, password}
#   → authenticate() 验证
#   → 成功返回 {access_token, token_type}
#   → 失败返回 401 错误
# ==================================================================

@router.post("/login")
async def login(request: LoginRequest):
    try:
        # 调用认证服务验证用户名密码，成功返回 JWT Token
        token = authenticate(request.username, request.password)
        return {"access_token": token, "token_type": "bearer"}
        # token_type: "bearer" 表示这是一个 Bearer Token
        # 前端使用时：Authorization: Bearer <token>
    except AuthError as e:
        # 认证失败（用户名不存在或密码错误）
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ==================================================================
# 📌 API 接口 2：用户注册
# POST /register
#
# 🔑 核心流程：
#   前端发送 {username, password}
#   → register_user() 注册
#   → 成功返回 "User registered successfully"
#   → 用户名已存在返回 400 错误
# ==================================================================

@router.post("/register")
async def register(request: RegisterRequest):
    try:
        # 调用注册服务：检查重名 → 加密密码 → 存入数据库
        register_user(request.username, request.password)
        return {"message": "User registered successfully"}
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ==================================================================
# 📌 API 接口 3：获取语音服务 STS Token
# POST /sts-token
#
# 💡 这是一个"代理接口"：前端不直接调用字节跳动的 API，
#    而是通过后端中转，避免在前端暴露 API 密钥。
# ==================================================================

@router.post("/sts-token")
async def get_sts_token(request: STSTokenRequest):
    try:
        headers = {
            "Authorization": f"Bearer; {request.accessKey}",
            "Content-Type": "application/json"
        }
        body = {
            "appid": request.appid,
            "duration": 300  # Token 有效期 300 秒
        }
        
        # 使用 httpx 异步调用字节跳动语音服务 API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openspeech.bytedance.com/api/v1/sts/token",
                headers=headers,
                json=body,
                timeout=30.0
            )
            return response.json()
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Request timeout when calling STS token API"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error calling STS token API: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
