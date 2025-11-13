"""文件上传工具函数"""
import hashlib
import os
import time
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

ALLOWED_IMAGE_TYPES = {
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/gif',
    'image/webp'
}

ALLOWED_DOCUMENT_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

ALLOWED_FILE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf', '.doc', '.docx'
}

MAX_FILE_SIZE = getattr(settings, 'MAX_FILE_SIZE', 10 * 1024 * 1024)
MAX_IMAGE_SIZE = 2 * 1024 * 1024


def validate_file_type(file: UploadFile, allowed_types: Optional[set] = None) -> Tuple[bool, str]:
    """验证文件类型"""
    if allowed_types is None:
        allowed_types = ALLOWED_IMAGE_TYPES | ALLOWED_DOCUMENT_TYPES

    if not file.content_type:
        return False, "无法检测文件类型"

    if file.content_type not in allowed_types:
        return False, f"不支持的文件类型: {file.content_type}"

    return True, ""


def validate_file_size(file: UploadFile, max_size: int = MAX_FILE_SIZE) -> Tuple[bool, str]:
    """验证文件大小"""
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > max_size:
        return False, f"文件大小超过限制: {max_size / (1024 * 1024):.1f}MB"

    return True, ""


def validate_file_extension(filename: str) -> Tuple[bool, str]:
    """验证文件扩展名"""
    if not filename:
        return False, "文件名不能为空"

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_FILE_EXTENSIONS:
        return False, f"不支持的文件扩展名: {ext}"

    return True, ""


def sanitize_filename(filename: str) -> str:
    """清理文件名"""
    filename = os.path.basename(filename)
    filename = "".join(c for c in filename if c.isalnum() or c in "._-")
    if not filename:
        filename = "upload"
    return filename


def generate_safe_filename(original_filename: str, prefix: str = "") -> str:
    """生成安全的文件名"""
    ext = Path(original_filename).suffix.lower()
    safe_name = sanitize_filename(Path(original_filename).stem)
    if prefix:
        safe_name = f"{prefix}_{safe_name}"
    timestamp = int(time.time())
    hash_suffix = hashlib.md5(f"{safe_name}{timestamp}".encode()).hexdigest()[:8]
    return f"{safe_name}_{hash_suffix}{ext}"

def validate_upload_file(file: UploadFile, is_image: bool = True, max_size: Optional[int] = None) -> Tuple[bool, str]:
    """验证上传文件"""
    if max_size is None:
        max_size = MAX_IMAGE_SIZE if is_image else MAX_FILE_SIZE

    allowed_types = ALLOWED_IMAGE_TYPES if is_image else (ALLOWED_IMAGE_TYPES | ALLOWED_DOCUMENT_TYPES)

    valid, msg = validate_file_extension(file.filename or "")
    if not valid:
        return False, msg

    valid, msg = validate_file_type(file, allowed_types)
    if not valid:
        return False, msg

    valid, msg = validate_file_size(file, max_size)
    if not valid:
        return False, msg

    return True, ""


async def save_upload_file(file: UploadFile, upload_dir: Path, filename: Optional[str] = None) -> Path:
    """保存上传文件"""
    if filename is None:
        filename = generate_safe_filename(file.filename or "upload")

    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename

    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    file.file.seek(0)
    return file_path


async def validate_and_save_file(
    file: UploadFile,
    upload_dir: Path,
    is_image: bool = True,
    max_size: Optional[int] = None
) -> Tuple[Path, str]:
    """验证并保存文件"""
    valid, error_msg = validate_upload_file(file, is_image, max_size)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    filename = generate_safe_filename(file.filename or "upload")
    file_path = await save_upload_file(file, upload_dir, filename)

    return file_path, filename
