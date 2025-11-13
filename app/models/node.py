from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.sql import func
from typing import Optional, Dict, Any
import re
import base64
import json

from app.core.database import Base

class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="节点名称")
    region = Column(String(50), nullable=False, comment="地区")
    type = Column(String(20), nullable=False, comment="节点类型")
    status = Column(String(20), default="offline", comment="节点状态")
    load = Column(Float, default=0.0, comment="负载百分比")
    speed = Column(Float, default=0.0, comment="速度(MB/s)")
    uptime = Column(Integer, default=0, comment="在线时间(秒)")
    latency = Column(Integer, default=0, comment="延迟(毫秒)")
    description = Column(Text, comment="节点描述")
    config = Column(Text, comment="节点配置")
    is_recommended = Column(Boolean, default=False, comment="是否推荐")
    is_active = Column(Boolean, default=True, comment="是否启用")
    last_test = Column(DateTime, comment="最后测试时间")
    last_update = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="最后更新时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def get_config_dict(self) -> Optional[Dict[str, Any]]:
        """解析配置字符串，返回配置字典"""
        if not self.config:
            return None
        
        try:
            # 解析vmess://配置
            if self.config.startswith('vmess://'):
                return self._parse_vmess_config()
            # 解析trojan://配置
            elif self.config.startswith('trojan://'):
                return self._parse_trojan_config()
            # 解析ssr://配置
            elif self.config.startswith('ssr://'):
                return self._parse_ssr_config()
            # 解析ss://配置
            elif self.config.startswith('ss://'):
                return self._parse_ss_config()
            else:
                return {"raw_config": self.config}
        except Exception:
            return {"raw_config": self.config}

    def _parse_vmess_config(self) -> Dict[str, Any]:
        """解析vmess配置"""
        try:
            # 移除vmess://前缀
            config_str = self.config[8:]
            # Base64解码
            decoded = base64.b64decode(config_str).decode('utf-8')
            # JSON解析
            config = json.loads(decoded)
            return {
                "protocol": "vmess",
                "server": config.get("add", ""),
                "port": config.get("port", ""),
                "uuid": config.get("id", ""),
                "alterId": config.get("aid", ""),
                "security": config.get("security", "auto"),
                "network": config.get("net", "tcp"),
                "ws_path": config.get("path", ""),
                "ws_headers": config.get("headers", {}),
                "tls": config.get("tls", "none")
            }
        except Exception:
            return {"raw_config": self.config}

    def _parse_trojan_config(self) -> Dict[str, Any]:
        """解析trojan配置"""
        try:
            # 移除trojan://前缀
            config_str = self.config[9:]
            # 分割密码和服务器信息
            if '@' in config_str:
                password, server_info = config_str.split('@', 1)
                if '#' in server_info:
                    server_port, name = server_info.split('#', 1)
                    if ':' in server_port:
                        server, port = server_port.split(':', 1)
                        return {
                            "protocol": "trojan",
                            "server": server,
                            "port": port,
                            "password": password,
                            "name": name
                        }
            return {"raw_config": self.config}
        except Exception:
            return {"raw_config": self.config}

    def _parse_ssr_config(self) -> Dict[str, Any]:
        """解析SSR配置"""
        try:
            # 移除ssr://前缀
            config_str = self.config[6:]
            # Base64解码
            decoded = base64.b64decode(config_str).decode('utf-8')
            # 分割参数
            parts = decoded.split('/?')
            if len(parts) == 2:
                server_part = parts[0]
                params_part = parts[1]
                
                # 解析服务器部分
                server_parts = server_part.split(':')
                if len(server_parts) >= 6:
                    server = server_parts[0]
                    port = server_parts[1]
                    protocol = server_parts[2]
                    method = server_parts[3]
                    obfs = server_parts[4]
                    password = server_parts[5]
                    
                    # 解析参数部分
                    params = {}
                    for param in params_part.split('&'):
                        if '=' in param:
                            key, value = param.split('=', 1)
                            params[key] = value
                    
                    return {
                        "protocol": "ssr",
                        "server": server,
                        "port": port,
                        "protocol_param": protocol,
                        "method": method,
                        "obfs": obfs,
                        "password": password,
                        "obfs_param": params.get("obfsparam", ""),
                        "protocol_param": params.get("protoparam", ""),
                        "remarks": params.get("remarks", ""),
                        "group": params.get("group", "")
                    }
            return {"raw_config": self.config}
        except Exception:
            return {"raw_config": self.config}

    def _parse_ss_config(self) -> Dict[str, Any]:
        """解析SS配置"""
        try:
            # 移除ss://前缀
            config_str = self.config[5:]
            # Base64解码
            decoded = base64.b64decode(config_str).decode('utf-8')
            # 分割密码和服务器信息
            if '@' in decoded:
                method, server_info = decoded.split('@', 1)
                if '#' in server_info:
                    server_port, name = server_info.split('#', 1)
                    if ':' in server_port:
                        server, port = server_port.split(':', 1)
                        return {
                            "protocol": "ss",
                            "server": server,
                            "port": port,
                            "method": method,
                            "name": name
                        }
            return {"raw_config": self.config}
        except Exception:
            return {"raw_config": self.config}

    @property
    def server(self) -> str:
        """获取服务器地址"""
        config = self.get_config_dict()
        return config.get("server", "") if config else ""

    @property
    def port(self) -> str:
        """获取端口"""
        config = self.get_config_dict()
        return config.get("port", "") if config else ""

    @property
    def protocol(self) -> str:
        """获取协议"""
        config = self.get_config_dict()
        return config.get("protocol", "") if config else ""

    @property
    def method(self) -> str:
        """获取加密方法"""
        config = self.get_config_dict()
        return config.get("method", "") if config else ""

    @property
    def obfs(self) -> str:
        """获取混淆方式"""
        config = self.get_config_dict()
        return config.get("obfs", "") if config else ""

    @property
    def password(self) -> str:
        """获取密码"""
        config = self.get_config_dict()
        return config.get("password", "") if config else ""

    @property
    def obfs_param(self) -> str:
        """获取混淆参数"""
        config = self.get_config_dict()
        return config.get("obfs_param", "") if config else ""

    @property
    def protocol_param(self) -> str:
        """获取协议参数"""
        config = self.get_config_dict()
        return config.get("protocol_param", "") if config else "" 