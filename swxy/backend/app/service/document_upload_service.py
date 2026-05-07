"""
===========================================================================
📌 service/document_upload_service.py — 文档上传记录服务
===========================================================================

🔰 新手导读：
这个服务负责管理 document_uploads 表的增删改查。
它记录了用户通过"快速解析"上传的文档元信息。

💡 注意：这个服务只管"记录"（元信息），不管文档解析本身。
  文档解析在 quick_parse_service.py 中完成。

🔗 调用关系：
  router/chat_rt.py → DocumentUploadService.create_upload_record()
  router/chat_rt.py → DocumentUploadService.get_session_documents()
===========================================================================
"""

from sqlalchemy.orm import Session
from models.document_upload import DocumentUpload
from typing import List, Optional
from datetime import datetime


class DocumentUploadService:
    """文档上传记录服务——管理 document_uploads 表"""
    
    @staticmethod
    def create_upload_record(
        db: Session,
        session_id: str,
        document_name: str,
        document_type: str,
        file_size: Optional[int] = None
    ) -> DocumentUpload:
        """
        创建一条文档上传记录
        
        在用户通过 /quick_parse 上传文档时调用，
        将文档的元信息保存到数据库。
        """
        upload_record = DocumentUpload(
            session_id=session_id,
            document_name=document_name,
            document_type=document_type,
            file_size=file_size,
            upload_time=datetime.now()
        )
        db.add(upload_record)    # 添加到数据库会话
        db.commit()              # 提交事务
        db.refresh(upload_record)  # 刷新获取数据库生成的字段（如 id）
        return upload_record
    
    @staticmethod
    def get_session_documents(db: Session, session_id: str) -> List[DocumentUpload]:
        """获取指定会话的所有文档记录，按上传时间倒序排列"""
        return db.query(DocumentUpload).filter(
            DocumentUpload.session_id == session_id
        ).order_by(DocumentUpload.upload_time.desc()).all()
    
    @staticmethod
    def has_uploaded_documents(db: Session, session_id: str) -> bool:
        """检查指定会话是否有上传的文档"""
        count = db.query(DocumentUpload).filter(
            DocumentUpload.session_id == session_id
        ).count()
        return count > 0
    
    @staticmethod
    def get_latest_document(db: Session, session_id: str) -> Optional[DocumentUpload]:
        """获取指定会话最新上传的文档"""
        return db.query(DocumentUpload).filter(
            DocumentUpload.session_id == session_id
        ).order_by(DocumentUpload.upload_time.desc()).first()
