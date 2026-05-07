"""
===========================================================================
📌 utils/password.py — 密码加密与验证工具
===========================================================================

🔰 新手导读：
密码安全是 Web 应用的基本要求。绝对不能明文存储用户密码！
这个文件使用 bcrypt 算法对密码进行"哈希"处理：
  - 注册时：明文密码 → bcrypt哈希 → 存入数据库
  - 登录时：用户输入密码 → 与数据库中的哈希值比对 → 验证是否匹配

💡 关键概念：
- 哈希(Hash): 一种单向加密，只能加密不能解密
  例如: "mypassword" → "$2b$12$xxx...xxx" (一长串乱码)
- bcrypt: 专门为密码设计的哈希算法，自带"盐值(salt)"防止彩虹表攻击
- 盐值(Salt): 在哈希前添加的随机字符串，即使两个用户密码相同，哈希结果也不同
===========================================================================
"""

import bcrypt  # bcrypt: 业界标准的密码哈希库

def hash_password(password: str) -> str:
    """
    🔑 关键函数：对明文密码进行哈希加密
    
    使用场景：用户注册时，把密码加密后存入数据库
    
    流程：
      "mypassword" → encode('utf-8') → bcrypt.hashpw() → "$2b$12$xxx..."
    
    Args:
        password: 用户输入的明文密码
    Returns:
        哈希后的密码字符串（存入数据库的就是这个值）
    """
    return bcrypt.hashpw(
        password.encode('utf-8'),   # 先把字符串转成字节
        bcrypt.gensalt()            # 自动生成随机盐值
    ).decode('utf-8')               # 把字节转回字符串

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    🔑 关键函数：验证密码是否匹配
    
    使用场景：用户登录时，比对输入的密码与数据库中存储的哈希值
    
    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的哈希密码
    Returns:
        True = 密码正确，False = 密码错误
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),    # 明文密码转字节
        hashed_password.encode('utf-8')    # 哈希密码转字节
    )
