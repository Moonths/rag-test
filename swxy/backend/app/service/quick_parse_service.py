"""
===========================================================================
📌 service/quick_parse_service.py — 快速文档解析服务
===========================================================================

🔰 新手导读：
这个服务处理"临时文档"的解析和存储：
  - 用户在对话中上传一个小文档（不超过4页/4000字符）
  - 系统快速提取文本内容
  - 存入 Redis（2小时过期）
  - 后续对话时可以基于这个文档回答问题

💡 与"知识库上传"（/upload_files）的区别：
  ┌────────────┬──────────────────┬──────────────────┐
  │            │ 快速解析          │ 知识库上传         │
  ├────────────┼──────────────────┼──────────────────┤
  │ 接口       │ /quick_parse     │ /upload_files    │
  │ 存储位置   │ Redis（内存）     │ Elasticsearch     │
  │ 有效期     │ 2小时过期         │ 永久存储          │
  │ 文件限制   │ 4页/4000字符     │ 无限制            │
  │ 是否向量化  │ 否              │ 是（Embedding）   │
  │ 检索方式   │ 全文放入Prompt   │ 向量+关键词混合   │
  │ 适用场景   │ 快速问答小文档    │ 构建长期知识库    │
  └────────────┴──────────────────┴──────────────────┘

🔗 调用链：
  router/chat_rt.py → quick_parse_service.quick_parse_document()
      → 验证格式 → 解析文本 → 存入 Redis
===========================================================================
"""

import os
import redis
from docx import Document       # python-docx: Word 文档解析库
import pdfplumber               # pdfplumber: PDF 文档解析库（比 PyPDF2 更好用）
from io import BytesIO          # 内存中的"虚拟文件"
from fastapi import HTTPException
from utils import logger
from typing import Tuple


class QuickParseService:
    """
    快速文档解析服务类
    
    支持的文件格式及限制:
    - PDF: 不超过4页
    - DOCX: 不超过4000字符
    - TXT: 不超过4000字符
    
    解析结果存储到Redis，默认保存2小时
    """
    
    def __init__(self):
        # ========== Redis 连接配置 ==========
        self.redis_host = os.getenv('REDIS_HOST', 'redis')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        
        # 创建 Redis 客户端
        # 💡 Redis 是一个内存数据库，读写速度极快，适合存临时数据
        self.redis_client = redis.Redis(
            host=self.redis_host, 
            port=self.redis_port, 
            db=self.redis_db, 
            decode_responses=True  # 自动将字节解码为字符串
        )
        
        self.supported_formats = ['docx', 'pdf', 'txt']  # 支持的文件格式
        self.max_pages = 4                                # PDF 页数限制
        self.max_characters = 4000                        # 文本字符数限制
        self.redis_expire_seconds = 7200                  # Redis 过期时间（2小时）

    def validate_file_format(self, filename: str) -> str:
        """验证文件格式并返回扩展名"""
        if not filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        
        file_extension = filename.lower().split('.')[-1]
        if file_extension not in self.supported_formats:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式，仅支持 {', '.join(self.supported_formats)}"
            )
        return file_extension

    def check_session_exists(self, session_id: str) -> bool:
        """检查 Redis 中该会话是否已有文档（每个会话只能上传一个文档）"""
        return self.redis_client.exists(session_id)

    def parse_docx(self, file_content: bytes) -> Tuple[str, int]:
        """
        解析 DOCX 文件
        
        使用 python-docx 库读取 Word 文档中的段落文本。
        
        Returns:
            tuple: (文本内容, 字符数)
        """
        try:
            # BytesIO 把字节数据包装成"文件对象"，让 Document 可以读取
            doc = Document(BytesIO(file_content))
            text = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text.append(paragraph.text.strip())
            
            content = '\n'.join(text)
            char_count = len(content)
            
            if char_count > self.max_characters:
                raise HTTPException(
                    status_code=400, 
                    detail=f"DOCX 文档字符数({char_count})超过限制({self.max_characters}字符)"
                )
            
            return content, char_count
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"DOCX 文件解析失败: {str(e)}")

    def parse_pdf(self, file_content: bytes) -> Tuple[str, int]:
        """
        解析 PDF 文件
        
        使用 pdfplumber 库读取 PDF 中的文本。
        pdfplumber 比 PyPDF2 对中文和表格的支持更好。
        
        Returns:
            tuple: (文本内容, 页数)
        """
        try:
            pdf_file = BytesIO(file_content)
            
            with pdfplumber.open(pdf_file) as pdf:
                pages = len(pdf.pages)
                if pages > self.max_pages:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"PDF 文档页数({pages})不能超过 {self.max_pages} 页"
                    )
                
                text = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text)
                
                return '\n'.join(text), pages
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF 文件解析失败: {str(e)}")

    def parse_txt(self, file_content: bytes) -> Tuple[str, int]:
        """
        解析 TXT 文件
        
        自动尝试多种编码（utf-8, gbk, gb2312, ascii）
        以兼容不同来源的文本文件。
        
        Returns:
            tuple: (文本内容, 字符数)
        """
        try:
            encodings = ['utf-8', 'gbk', 'gb2312', 'ascii']
            content = None
            
            for encoding in encodings:
                try:
                    content = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                raise HTTPException(status_code=400, detail="无法识别文本文件编码")
            
            char_count = len(content)
            if char_count > self.max_characters:
                raise HTTPException(
                    status_code=400, 
                    detail=f"TXT 文档字符数({char_count})超过限制({self.max_characters}字符)"
                )
            
            return content, char_count
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"TXT 文件解析失败: {str(e)}")

    def parse_document(self, file_content: bytes, file_extension: str) -> Tuple[str, int]:
        """根据文件扩展名选择对应的解析器"""
        if file_extension == 'docx':
            return self.parse_docx(file_content)
        elif file_extension == 'pdf':
            return self.parse_pdf(file_content)
        elif file_extension == 'txt':
            return self.parse_txt(file_content)
        else:
            raise HTTPException(status_code=400, detail="不支持的文件格式")

    def store_to_redis(self, session_id: str, content: str) -> None:
        """
        🔑 将解析后的文本内容存入 Redis
        
        使用 setex 命令：同时设置值和过期时间
        key = session_id, value = 文档文本内容, expire = 7200秒（2小时）
        """
        try:
            self.redis_client.setex(
                session_id, 
                self.redis_expire_seconds,  # 2小时后自动过期
                content
            )
            logger.info(f"文档内容已存储到Redis，session_id: {session_id}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"存储到Redis失败: {str(e)}")

    def get_from_redis(self, session_id: str) -> str:
        """从 Redis 获取文档内容"""
        content = self.redis_client.get(session_id)
        if not content:
            raise HTTPException(
                status_code=404, 
                detail="未找到该会话的文档内容，可能已过期或未上传"
            )
        return content

    def get_ttl(self, session_id: str) -> int:
        """获取 Redis 键的剩余过期时间（秒）"""
        return self.redis_client.ttl(session_id)

    def quick_parse_document(self, session_id: str, filename: str, file_content: bytes) -> dict:
        """
        ⭐ 快速解析文档的主入口函数
        
        完整流程：
          1. 验证文件格式
          2. 检查会话是否已有文档（每个会话只能一个）
          3. 验证文件内容
          4. 解析文档提取文本
          5. 存入 Redis
          6. 返回解析结果
        """
        # 步骤1：验证文件格式
        file_extension = self.validate_file_format(filename)
        
        # 步骤2：检查是否重复上传
        if self.check_session_exists(session_id):
            raise HTTPException(
                status_code=400, 
                detail="该会话已有文档，每个session_id只能上传一个文档"
            )
        
        # 步骤3：验证文件内容
        if not file_content:
            raise HTTPException(status_code=400, detail="文件内容为空")
        
        # 步骤4：🔑 解析文档提取文本
        content, count_value = self.parse_document(file_content, file_extension)
        
        # 步骤5：🔑 存入 Redis
        self.store_to_redis(session_id, content)
        
        # 步骤6：返回解析结果
        if file_extension == 'pdf':
            return {
                "status": "success",
                "message": "文档解析完成",
                "session_id": session_id,
                "filename": filename,
                "file_type": file_extension,
                "pages": count_value,
                "content_length": len(content),
                "limit_info": f"PDF页数限制: {self.max_pages}页",
                "expiry_hours": self.redis_expire_seconds // 3600
            }
        else:
            return {
                "status": "success",
                "message": "文档解析完成",
                "session_id": session_id,
                "filename": filename,
                "file_type": file_extension,
                "character_count": count_value,
                "content_length": len(content),
                "limit_info": f"字符数限制: {self.max_characters}字符",
                "expiry_hours": self.redis_expire_seconds // 3600
            }

    def get_parsed_content(self, session_id: str) -> dict:
        """获取已解析的文档内容及剩余有效时间"""
        content = self.get_from_redis(session_id)
        ttl = self.get_ttl(session_id)
        
        return {
            "status": "success",
            "session_id": session_id,
            "content": content,
            "content_length": len(content),
            "remaining_seconds": ttl if ttl > 0 else 0
        }


# 创建全局服务实例（整个应用共用一个实例）
quick_parse_service = QuickParseService() 
