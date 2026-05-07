"""
===========================================================================
📌 exceptions/auth.py — 自定义认证异常
===========================================================================

🔰 新手导读：
自定义异常类可以让错误处理更加精确和清晰。
当认证失败时（用户名不存在、密码错误、用户名已被注册等），
抛出 AuthError 而不是通用的 Exception，这样调用者可以精确地捕获和处理。

💡 使用方式：
  from exceptions.auth import AuthError
  
  if not user:
      raise AuthError("用户名不存在")  # 抛出自定义异常
  
  try:
      authenticate(...)
  except AuthError as e:
      print(e.message)  # 捕获并处理
===========================================================================
"""

class AuthError(Exception):
    """
    自定义认证异常
    
    当认证/注册过程中出现错误时抛出。
    继承自 Python 内置的 Exception 类。
    """
    def __init__(self, message):
        self.message = message       # 保存错误消息
        super().__init__(message)    # 调用父类构造函数
