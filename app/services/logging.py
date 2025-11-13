"""日志管理服务"""
import json
import logging
import logging.handlers
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings


class LogManager:
    """日志管理器类"""

    def __init__(self):
        self.log_dir = Path("uploads/logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.setup_logging()

    def _create_file_handler(self, filename: str, level=logging.INFO, backup_count=30):
        handler = logging.handlers.TimedRotatingFileHandler(
            self.log_dir / filename,
            when='midnight',
            interval=1,
            backupCount=backup_count,
            encoding='utf-8'
        )
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        return handler

    def setup_logging(self):
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        app_logger = logging.getLogger('app')
        app_logger.setLevel(logging.INFO)
        app_logger.addHandler(self._create_file_handler('app.log'))
        app_logger.addHandler(self._create_file_handler('error.log', logging.ERROR))
        access_logger = logging.getLogger('access')
        access_logger.setLevel(logging.INFO)
        access_logger.addHandler(self._create_file_handler('access.log'))
        security_logger = logging.getLogger('security')
        security_logger.setLevel(logging.WARNING)
        security_logger.addHandler(self._create_file_handler('security.log', backup_count=90))
        if settings.DEBUG:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            app_logger.addHandler(console_handler)

    def _log(self, logger_name: str, level: str, prefix: str, data: Dict):
        log_data = {**data, "timestamp": datetime.now().isoformat()}
        getattr(logging.getLogger(logger_name), level.lower())(f"{prefix}: {json.dumps(log_data, ensure_ascii=False)}")

    def log_user_activity(self, user_id: int, activity: str, details: Dict = None):
        self._log('app', 'info', 'USER_ACTIVITY', {"user_id": user_id, "activity": activity, "details": details or {}})

    def log_admin_action(self, admin_id: int, action: str, description: str, db=None):
        """记录管理员操作"""
        self._log('app', 'info', 'ADMIN_ACTION', {
            "admin_id": admin_id,
            "action": action,
            "description": description
        })

    def log_security_event(self, event_type: str, details: Dict = None):
        self._log('security', 'warning', 'SECURITY_EVENT', {"event_type": event_type, "details": details or {}})

    def log_api_access(self, method: str, path: str, status_code: int, response_time: float, user_id: Optional[int] = None, ip_address: str = None):
        self._log('access', 'info', 'API_ACCESS', {"method": method, "path": path, "status_code": status_code, "response_time": response_time, "user_id": user_id, "ip_address": ip_address})

    def log_error(self, error: Exception, context: Dict = None):
        log_data = {"error_type": type(error).__name__, "error_message": str(error), "context": context or {}, "timestamp": datetime.now().isoformat()}
        logging.getLogger('app').error(f"ERROR: {json.dumps(log_data, ensure_ascii=False)}", exc_info=True)

    def _get_log_files(self):
        return [f for f in self.log_dir.iterdir() if f.is_file() and f.suffix == '.log']

    def get_log_files(self) -> List[Dict]:
        log_files = []
        for log_file in self._get_log_files():
            stat = log_file.stat()
            log_files.append({
                "filename": log_file.name,
                "path": str(log_file),
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        return sorted(log_files, key=lambda x: x["modified_at"], reverse=True)

    def _read_log_file(self, log_path: Path) -> List[str]:
        if not log_path.exists():
            return []
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                return f.readlines()
        except Exception as e:
            logging.getLogger('app').error(f"读取日志文件失败: {e}")
            return []

    def read_log_file(self, filename: str, lines: int = 100) -> List[str]:
        all_lines = self._read_log_file(self.log_dir / filename)
        return all_lines[-lines:] if lines > 0 else all_lines

    def search_logs(self, query: str, log_type: str = "app", start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict]:
        results = []
        log_files = self._get_log_files() if log_type == "all" else ([self.log_dir / f"{log_type}.log"] if (self.log_dir / f"{log_type}.log").exists() else [])
        for log_file in log_files:
            try:
                for line_num, line in enumerate(self._read_log_file(log_file), 1):
                    if query.lower() in line.lower():
                        try:
                            timestamp_str = line.split(' - ')[0]
                            timestamp = datetime.fromisoformat(timestamp_str.replace(' ', 'T'))
                            if (start_date and timestamp < start_date) or (end_date and timestamp > end_date):
                                continue
                            results.append({"file": log_file.name, "line": line_num, "timestamp": timestamp.isoformat(), "content": line.strip()})
                        except:
                            results.append({"file": log_file.name, "line": line_num, "timestamp": None, "content": line.strip()})
            except Exception as e:
                logging.getLogger('app').error(f"搜索日志文件失败 {log_file.name}: {e}")
        return sorted(results, key=lambda x: x["timestamp"] or "", reverse=True)

    def cleanup_old_logs(self, days: int = 30) -> Dict:
        try:
            deleted_count = 0
            deleted_files = []
            cutoff_date = None if days == 0 else datetime.now() - timedelta(days=days)
            for log_file in self._get_log_files():
                if days == 0 or datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff_date:
                    log_file.unlink()
                    deleted_count += 1
                    deleted_files.append(log_file.name)
            return {"success": True, "deleted_count": deleted_count, "deleted_files": deleted_files, "cutoff_date": cutoff_date.isoformat() if cutoff_date else "所有日志"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_log_stats(self) -> Dict:
        try:
            all_logs = self.get_recent_logs(limit=10000)
            levels = {"ERROR": 0, "WARNING": 0, "INFO": 0, "DEBUG": 0}
            for log in all_logs:
                level = log.get("level", "").upper()
                if level in levels:
                    levels[level] += 1
            file_stats = {"total_files": 0, "total_size": 0, "file_types": {}, "oldest_log": None, "newest_log": None}
            for log_file in self._get_log_files():
                stat = log_file.stat()
                file_stats["total_files"] += 1
                file_stats["total_size"] += stat.st_size
                log_type = log_file.stem
                if log_type not in file_stats["file_types"]:
                    file_stats["file_types"][log_type] = {"count": 0, "size": 0}
                file_stats["file_types"][log_type]["count"] += 1
                file_stats["file_types"][log_type]["size"] += stat.st_size
                file_time = datetime.fromtimestamp(stat.st_mtime)
                if not file_stats["newest_log"] or file_time > datetime.fromisoformat(file_stats["newest_log"]):
                    file_stats["newest_log"] = file_time.isoformat()
                if not file_stats["oldest_log"] or file_time < datetime.fromisoformat(file_stats["oldest_log"]):
                    file_stats["oldest_log"] = file_time.isoformat()
            log_files = list(self.log_dir.glob("*.log"))
            return {"total": len(all_logs), "error": levels["ERROR"], "warning": levels["WARNING"], "info": levels["INFO"], "debug": levels["DEBUG"], "file_stats": file_stats, "debug_info": {"files_read": len(log_files), "total_files_available": len(log_files), "logs_processed": len(all_logs)}}
        except Exception as e:
            return {"total": 0, "error": 0, "warning": 0, "info": 0, "debug": 0, "error": str(e)}

    def get_recent_logs(self, limit: int = 100) -> List[Dict]:
        try:
            results = []
            log_files = sorted(self.log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:20]
            for log_file in log_files:
                try:
                    lines = self._read_log_file(log_file)
                    recent_lines = lines[-1000:] if len(lines) > 1000 else lines
                    for line in recent_lines:
                        if line.strip():
                            log_entry = self._parse_log_line(line.strip())
                            if log_entry:
                                results.append(log_entry)
                except Exception as e:
                    logging.getLogger('app').error(f"读取日志文件失败 {log_file.name}: {e}")
            def sort_key(log_entry):
                timestamp = log_entry.get("timestamp", "")
                if isinstance(timestamp, str):
                    try:
                        return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    except:
                        return datetime.min
                return timestamp
            results.sort(key=sort_key, reverse=True)
            return results[:limit]
        except Exception as e:
            logging.getLogger('app').error(f"获取最近日志失败: {e}")
            return []

    def _parse_log_line(self, line: str) -> Optional[Dict]:
        try:
            patterns = [
                (r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3} - (\w+) - (\w+) - (.+)', lambda g: (g[1], g[2], g[3])),
                (r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) - (\w+) - (\w+) - (.+)', lambda g: (g[2], g[3], g[4])),
                (r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (\w+): (.+)', lambda g: (g[1], "system", g[2]))
            ]
            for pattern, extractor in patterns:
                match = re.match(pattern, line)
                if match:
                    groups = match.groups()
                    timestamp = groups[0]
                    module, level, message = extractor(groups)
                    return {"timestamp": timestamp, "level": level, "module": module, "message": message, "username": "system", "ip_address": "127.0.0.1", "user_agent": "System/1.0", "details": ""}
            return {"timestamp": datetime.now().isoformat(), "level": "INFO", "module": "system", "message": line[:100] + "..." if len(line) > 100 else line, "username": "system", "ip_address": "127.0.0.1", "user_agent": "System/1.0", "details": ""}
        except Exception:
            return None

log_manager = LogManager()

def get_logger(name: str = 'app') -> logging.Logger:
    return logging.getLogger(name)
