"""自动备份服务"""
import gzip
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.database import get_database_url

logger = logging.getLogger(__name__)


class BackupService:
    """备份服务类"""

    def __init__(self):
        upload_dir = Path(settings.UPLOAD_DIR)
        self.backup_dir = upload_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.max_backups = 30

    def _get_database_path(self) -> Optional[Path]:
        """获取数据库文件路径（仅适用于SQLite）"""
        database_url = get_database_url()
        if "sqlite" in database_url and database_url.startswith("sqlite:///"):
            db_path = database_url.replace("sqlite:///", "")
            return Path(db_path)
        return None
    
    def create_database_backup(self) -> Dict:
        """创建数据库备份"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"database_backup_{timestamp}.db"
            backup_path = self.backup_dir / backup_filename

            db_path = self._get_database_path()
            if not db_path:
                return {
                    "success": False,
                    "error": "当前数据库不是SQLite，无法创建文件备份"
                }

            if not db_path.exists():
                return {
                    "success": False,
                    "error": "数据库文件不存在"
                }

            shutil.copy2(db_path, backup_path)

            compressed_path = backup_path.with_suffix(".db.gz")
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            backup_path.unlink()
            file_size = compressed_path.stat().st_size

            return {
                "success": True,
                "filename": compressed_path.name,
                "path": str(compressed_path),
                "size": file_size,
                "timestamp": timestamp
            }

        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_config_backup(self) -> Dict:
        """创建配置文件备份"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"config_backup_{timestamp}.tar.gz"
            backup_path = self.backup_dir / backup_filename

            upload_dir = Path(settings.UPLOAD_DIR)
            config_dirs = [
                str(upload_dir / "config"),
                str(upload_dir / "avatars"),
                "templates"
            ]

            temp_dir = self.backup_dir / f"temp_config_{timestamp}"
            temp_dir.mkdir(exist_ok=True)

            try:
                for config_dir in config_dirs:
                    if os.path.exists(config_dir):
                        dest_dir = temp_dir / Path(config_dir).name
                        shutil.copytree(config_dir, dest_dir)

                env_files = [".env", "env.example"]
                for env_file in env_files:
                    if os.path.exists(env_file):
                        shutil.copy2(env_file, temp_dir)

                shutil.make_archive(
                    str(backup_path.with_suffix('')),
                    'gztar',
                    str(temp_dir)
                )

                shutil.rmtree(temp_dir)
                file_size = backup_path.stat().st_size

                return {
                    "success": True,
                    "filename": backup_path.name,
                    "path": str(backup_path),
                    "size": file_size,
                    "timestamp": timestamp
                }

            except Exception as e:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                raise

        except Exception as e:
            logger.error(f"配置文件备份失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_full_backup(self) -> Dict:
        """创建完整备份"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"full_backup_{timestamp}.tar.gz"
            backup_path = self.backup_dir / backup_filename

            db_path = self._get_database_path()
            backup_items = [
                str(db_path) if db_path else None,
                settings.UPLOAD_DIR,
                "templates",
                ".env",
                "env.example",
                "requirements.txt"
            ]
            backup_items = [item for item in backup_items if item and os.path.exists(item)]

            temp_dir = self.backup_dir / f"temp_full_{timestamp}"
            temp_dir.mkdir(exist_ok=True)

            try:
                for item in backup_items:
                    if os.path.exists(item):
                        dest_path = temp_dir / item
                        if os.path.isdir(item):
                            shutil.copytree(item, dest_path)
                        else:
                            shutil.copy2(item, dest_path)

                shutil.make_archive(
                    str(backup_path.with_suffix('')),
                    'gztar',
                    str(temp_dir)
                )

                shutil.rmtree(temp_dir)
                file_size = backup_path.stat().st_size

                return {
                    "success": True,
                    "filename": backup_path.name,
                    "path": str(backup_path),
                    "size": file_size,
                    "timestamp": timestamp
                }

            except Exception as e:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                raise

        except Exception as e:
            logger.error(f"完整备份失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_backups(self) -> List[Dict]:
        """列出所有备份文件"""
        try:
            backups = []

            for file_path in self.backup_dir.iterdir():
                if file_path.is_file() and file_path.suffix in ['.gz', '.db']:
                    stat = file_path.stat()
                    backups.append({
                        "filename": file_path.name,
                        "path": str(file_path),
                        "size": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "type": self._get_backup_type(file_path.name)
                    })

            backups.sort(key=lambda x: x["created_at"], reverse=True)
            return backups

        except Exception as e:
            logger.error(f"列出备份文件失败: {e}")
            return []
    
    def _get_backup_type(self, filename: str) -> str:
        """获取备份类型"""
        if "database_backup" in filename:
            return "database"
        elif "config_backup" in filename:
            return "config"
        elif "full_backup" in filename:
            return "full"
        else:
            return "unknown"
    
    def restore_database(self, backup_filename: str) -> Dict:
        """恢复数据库"""
        try:
            backup_path = self.backup_dir / backup_filename

            if not backup_path.exists():
                return {
                    "success": False,
                    "error": "备份文件不存在"
                }

            db_path = self._get_database_path()
            if not db_path:
                return {
                    "success": False,
                    "error": "当前数据库不是SQLite，无法恢复文件备份"
                }

            if db_path.exists():
                backup_current = db_path.parent / f"cboard_backup_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy2(db_path, backup_current)

            if backup_filename.endswith('.gz'):
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(db_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(backup_path, db_path)

            return {
                "success": True,
                "message": "数据库恢复成功"
            }

        except Exception as e:
            logger.error(f"数据库恢复失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_backup(self, backup_filename: str) -> Dict:
        """删除备份文件"""
        try:
            backup_path = self.backup_dir / backup_filename

            if not backup_path.exists():
                return {
                    "success": False,
                    "error": "备份文件不存在"
                }

            backup_path.unlink()

            return {
                "success": True,
                "message": "备份文件删除成功"
            }

        except Exception as e:
            logger.error(f"删除备份文件失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def cleanup_old_backups(self) -> Dict:
        """清理旧备份文件"""
        try:
            backups = self.list_backups()

            if len(backups) <= self.max_backups:
                return {
                    "success": True,
                    "message": "备份文件数量未超过限制",
                    "deleted_count": 0
                }

            backups_to_delete = backups[self.max_backups:]
            deleted_count = 0

            for backup in backups_to_delete:
                try:
                    backup_path = self.backup_dir / backup["filename"]
                    backup_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"删除备份文件失败 {backup['filename']}: {e}")

            return {
                "success": True,
                "message": f"清理完成，删除了 {deleted_count} 个旧备份文件",
                "deleted_count": deleted_count
            }

        except Exception as e:
            logger.error(f"清理旧备份失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_backup_stats(self) -> Dict:
        """获取备份统计信息"""
        try:
            backups = self.list_backups()

            total_size = sum(backup["size"] for backup in backups)
            backup_types = {}

            for backup in backups:
                backup_type = backup["type"]
                if backup_type not in backup_types:
                    backup_types[backup_type] = {"count": 0, "size": 0}
                backup_types[backup_type]["count"] += 1
                backup_types[backup_type]["size"] += backup["size"]

            return {
                "total_backups": len(backups),
                "total_size": total_size,
                "backup_types": backup_types,
                "oldest_backup": backups[-1]["created_at"] if backups else None,
                "newest_backup": backups[0]["created_at"] if backups else None
            }

        except Exception as e:
            logger.error(f"获取备份统计失败: {e}")
            return {}

backup_service = BackupService()
