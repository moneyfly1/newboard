"""节点服务"""
import base64
import json
import logging
import random
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import yaml
from sqlalchemy import text

from app.core.cache import redis_cache
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

CACHE_KEY_NODES = "nodes:clash_config"
CACHE_KEY_TIMESTAMP = "nodes:cache_timestamp"


class NodeService:
    """节点服务类"""

    def __init__(self, db=None):
        self.db = db or SessionLocal()
        self._cache_ttl = 300
        self._max_cache_size = 500
        self._fallback_cache = None
        self._fallback_timestamp = None

    def clear_cache(self):
        """清理节点缓存，释放内存"""
        redis_cache.delete(CACHE_KEY_NODES)
        redis_cache.delete(CACHE_KEY_TIMESTAMP)
        self._fallback_cache = None
        self._fallback_timestamp = None

    def get_nodes_from_clash_config(self, clash_config_content: str = None) -> List[Dict[str, Any]]:
        current_time = time.time()
        
        # 尝试从 Redis 获取缓存
        if redis_cache.is_connected():
            cache_timestamp = redis_cache.get(CACHE_KEY_TIMESTAMP)
            if cache_timestamp and current_time - cache_timestamp < self._cache_ttl:
                cached_nodes = redis_cache.get(CACHE_KEY_NODES)
                if cached_nodes:
                    logger.debug("从 Redis 缓存获取节点数据")
                    return cached_nodes
        
        # 如果 Redis 不可用，使用内存缓存作为后备
        if (self._fallback_cache is not None and self._fallback_timestamp is not None and 
            current_time - self._fallback_timestamp < self._cache_ttl):
            logger.debug("从内存缓存获取节点数据")
            return self._fallback_cache
        config_content = None
        # 优先从数据库读取
        try:
            from sqlalchemy import text
            query = text('SELECT value FROM system_configs WHERE "key" = :key AND type = :type')
            result = self.db.execute(query, {'key': 'clash_config', 'type': 'clash'}).first()
            if result and result.value:
                config_content = result.value
                logger.info(f"✅ 从数据库读取Clash配置")
        except Exception as e:
            logger.warning(f"从数据库读取Clash配置失败: {e}")
        # 如果数据库没有，从文件读取
        if not config_content:
            import os
            from pathlib import Path
            clash_path = Path("uploads/config/clash.yaml")
            if clash_path.exists():
                try:
                    with open(clash_path, 'r', encoding='utf-8') as f:
                        config_content = f.read()
                        logger.info(f"✅ 从文件读取Clash配置: {clash_path}")
                except Exception as e:
                    logger.warning(f"读取Clash配置文件失败: {e}")
                    config_content = None
            else:
                logger.warning(f"Clash配置文件不存在: {clash_path}")
        # 如果提供了配置内容参数，使用参数（用于导入功能）
        if clash_config_content:
            config_content = clash_config_content
        if not config_content:
            logger.warning("未找到Clash配置")
            return []
        try:
            config_data = yaml.safe_load(config_content)
            if not config_data or 'proxies' not in config_data:
                logger.warning("Clash配置格式错误或没有proxies部分")
                return []
            proxies = config_data['proxies']
            if not isinstance(proxies, list):
                logger.warning("proxies部分不是列表格式")
                return []
            nodes = []
            for i, proxy in enumerate(proxies, 1):
                if not isinstance(proxy, dict):
                    continue
                if len(nodes) >= self._max_cache_size:
                    logger.warning(f"节点数量超过缓存限制 {self._max_cache_size}，已截断")
                    break
                node_data = self._build_node_data(proxy, i)
                if node_data:
                    nodes.append(node_data)
            
            # 保存到 Redis 缓存
            if redis_cache.is_connected():
                redis_cache.set(CACHE_KEY_NODES, nodes, ttl=self._cache_ttl)
                redis_cache.set(CACHE_KEY_TIMESTAMP, current_time, ttl=self._cache_ttl)
                logger.debug("节点数据已保存到 Redis 缓存")
            
            # 同时保存到内存缓存作为后备
            self._fallback_cache = nodes
            self._fallback_timestamp = current_time
            
            return nodes
        except yaml.YAMLError as e:
            logger.warning(f"YAML解析失败: {e}")
            return self._parse_clash_config_manually(config_content)

    def _build_node_data(self, node_info: dict, node_id: int) -> Dict[str, Any]:
        node_name = node_info.get('name', '')
        node_type = node_info.get('type', '')
        server = node_info.get('server', '')
        port = node_info.get('port', '')
        if not node_name or not node_type or not server:
            return None
        return {
            "id": node_id,
            "name": node_name,
            "region": self._detect_region(node_name),
            "type": node_type,
            "status": "online",
            "load": self._generate_load(),
            "speed": 0.0,
            "uptime": 0,
            "latency": 0,
            "description": f"从Clash配置解析的{node_type}节点",
            "is_recommended": self._is_recommended(node_name),
            "is_active": True,
            "server": server,
            "port": port
        }

    def _parse_clash_config_manually(self, config_text: str) -> List[Dict[str, Any]]:
        try:
            proxies_start = config_text.find('proxies:')
            if proxies_start == -1:
                logger.warning("未找到proxies部分")
                return []
            proxy_groups_start = config_text.find('proxy-groups:', proxies_start)
            if proxy_groups_start == -1:
                rules_start = config_text.find('rules:', proxies_start)
                if rules_start == -1:
                    logger.warning("未找到proxies部分的结束位置")
                    return []
                proxies_section = config_text[proxies_start:rules_start]
            else:
                proxies_section = config_text[proxies_start:proxy_groups_start]
            nodes = []
            current_node = {}
            node_id = 1
            field_mappings = {
                '- name:': 'name',
                'type:': 'type',
                'server:': 'server',
                'port:': 'port',
                'uuid:': 'uuid',
                'password:': 'password',
                'cipher:': 'cipher',
                'network:': 'network',
                'ws-path:': 'ws-path',
                'ws-headers:': 'ws-headers',
                'tls:': 'tls',
                'udp:': 'udp'
            }
            for line in proxies_section.split('\n'):
                line = line.strip()
                for prefix, field in field_mappings.items():
                    if line.startswith(prefix):
                        value = line.replace(prefix, '').strip()
                        if prefix == '- name:':
                            if current_node and 'name' in current_node:
                                node_data = self._build_node_data(current_node, node_id)
                                if node_data:
                                    nodes.append(node_data)
                                node_id += 1
                            current_node = {'name': value}
                        else:
                            current_node[field] = value
                        break
            if current_node and 'name' in current_node:
                node_data = self._build_node_data(current_node, node_id)
                if node_data:
                    nodes.append(node_data)
            self._nodes_cache = nodes
            self._cache_timestamp = time.time()
            return nodes
        except Exception as e:
            logger.error(f"手动解析失败: {e}", exc_info=True)
            return []

    def _detect_region(self, node_name: str) -> str:
        region_keywords = {
            '香港': ['香港', 'HK', 'Hong Kong', 'hongkong'],
            '美国': ['美国', 'US', 'United States', 'america', 'usa'],
            '日本': ['日本', 'JP', 'Japan', 'japan'],
            '新加坡': ['新加坡', 'SG', 'Singapore', 'singapore'],
            '英国': ['英国', 'UK', 'United Kingdom', 'britain'],
            '德国': ['德国', 'DE', 'Germany', 'germany'],
            '法国': ['法国', 'FR', 'France', 'france'],
            '加拿大': ['加拿大', 'CA', 'Canada', 'canada'],
            '澳洲': ['澳洲', 'AU', 'Australia', 'australia'],
            '台湾': ['台湾', 'TW', 'Taiwan', 'taiwan'],
            '韩国': ['韩国', 'KR', 'Korea', 'korea'],
            '俄罗斯': ['俄罗斯', 'RU', 'Russia', 'russia'],
            '印度': ['印度', 'IN', 'India', 'india'],
            '巴西': ['巴西', 'BR', 'Brazil', 'brazil'],
            '荷兰': ['荷兰', 'NL', 'Netherlands', 'netherlands'],
            '瑞士': ['瑞士', 'CH', 'Switzerland', 'switzerland'],
            '瑞典': ['瑞典', 'SE', 'Sweden', 'sweden'],
            '挪威': ['挪威', 'NO', 'Norway', 'norway'],
            '丹麦': ['丹麦', 'DK', 'Denmark', 'denmark'],
            '芬兰': ['芬兰', 'FI', 'Finland', 'finland'],
            '意大利': ['意大利', 'IT', 'Italy', 'italy'],
            '西班牙': ['西班牙', 'ES', 'Spain', 'spain'],
            '波兰': ['波兰', 'PL', 'Poland', 'poland'],
            '捷克': ['捷克', 'CZ', 'Czech', 'czech'],
            '奥地利': ['奥地利', 'AT', 'Austria', 'austria'],
            '比利时': ['比利时', 'BE', 'Belgium', 'belgium'],
            '葡萄牙': ['葡萄牙', 'PT', 'Portugal', 'portugal'],
            '希腊': ['希腊', 'GR', 'Greece', 'greece'],
            '土耳其': ['土耳其', 'TR', 'Turkey', 'turkey'],
            '以色列': ['以色列', 'IL', 'Israel', 'israel'],
            '阿联酋': ['阿联酋', 'AE', 'UAE', 'uae'],
            '沙特': ['沙特', 'SA', 'Saudi', 'saudi'],
            '埃及': ['埃及', 'EG', 'Egypt', 'egypt'],
            '南非': ['南非', 'ZA', 'South Africa', 'south africa'],
            '阿根廷': ['阿根廷', 'AR', 'Argentina', 'argentina'],
            '智利': ['智利', 'CL', 'Chile', 'chile'],
            '墨西哥': ['墨西哥', 'MX', 'Mexico', 'mexico'],
            '泰国': ['泰国', 'TH', 'Thailand', 'thailand'],
            '越南': ['越南', 'VN', 'Vietnam', 'vietnam'],
            '菲律宾': ['菲律宾', 'PH', 'Philippines', 'philippines'],
            '印尼': ['印尼', 'ID', 'Indonesia', 'indonesia'],
            '马来西亚': ['马来西亚', 'MY', 'Malaysia', 'malaysia'],
            '新西兰': ['新西兰', 'NZ', 'New Zealand', 'new zealand']
        }
        node_name_lower = node_name.lower()
        for region, keywords in region_keywords.items():
            if any(keyword.lower() in node_name_lower for keyword in keywords):
                return region
        return '未知'

    def _generate_load(self) -> float:
        return round(random.uniform(5, 25), 1)

    def _is_recommended(self, node_name: str) -> bool:
        recommended_keywords = ['推荐', 'recommended', 'premium', '高速', 'fast', '稳定', 'stable']
        node_name_lower = node_name.lower()
        return any(keyword.lower() in node_name_lower for keyword in recommended_keywords)

    def get_node_statistics(self) -> Dict[str, Any]:
        nodes = self.get_nodes_from_clash_config()
        if not nodes:
            return {"total": 0, "online": 0, "offline": 0, "regions": [], "types": [], "avg_latency": 0, "avg_load": 0}
        total_nodes = len(nodes)
        online_nodes = len([n for n in nodes if n.get("status") == "online"])
        offline_nodes = total_nodes - online_nodes
        regions = list(set([n["region"] for n in nodes if n.get("region") and n["region"] != "未知"]))
        types = list(set([n["type"] for n in nodes if n.get("type")]))
        avg_latency = sum([n.get("latency", 0) for n in nodes]) / total_nodes if total_nodes > 0 else 0
        avg_load = sum([n.get("load", 0) for n in nodes]) / total_nodes if total_nodes > 0 else 0
        return {
            "total": total_nodes,
            "online": online_nodes,
            "offline": offline_nodes,
            "regions": regions,
            "types": types,
            "avg_latency": round(avg_latency, 2),
            "avg_load": round(avg_load, 2)
        }
    
    def get_nodes_with_pagination(self, skip: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
        """从文件获取节点列表（分页）"""
        nodes = self.get_nodes_from_clash_config()
        return nodes[skip:skip + limit]
    
    def get_total_nodes(self) -> int:
        """获取节点总数"""
        nodes = self.get_nodes_from_clash_config()
        return len(nodes)
    
    def get_node(self, node_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取节点"""
        nodes = self.get_nodes_from_clash_config()
        return next((n for n in nodes if n.get("id") == node_id), None)

    def clear_cache(self):
        self._nodes_cache = None
        self._cache_timestamp = None

    def close(self):
        if self.db:
            self.db.close()
