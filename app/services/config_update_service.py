"""配置更新服务"""
import base64
import json
import logging
import os
import re
import threading
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.config import SystemConfig

logger = logging.getLogger(__name__)


def unicode_decode(s):
    try:
        return json.loads(f'"{s}"')
    except Exception:
        return s


class ConfigUpdateService:
    """配置更新服务类"""

    def __init__(self, db: Session):
        self.db = db
        self.is_running_flag = False
        self.scheduled_task = None
        self.scheduled_thread = None
        self.logs = []
        self.max_logs = 100
        self.default_config = {
            "urls": [],
            "target_dir": "./uploads/config",
            "v2ray_file": "xr",
            "clash_file": "clash.yaml",
            "update_interval": 3600,
            "enable_schedule": False,
            "filter_keywords": []
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running_flag,
            "scheduled_enabled": self.scheduled_task is not None,
            "last_update": self._get_last_update_time(),
            "next_update": self._get_next_update_time(),
            "config_exists": self._check_config_files_exist()
        }
    
    def is_running(self) -> bool:
        return self.is_running_flag
    
    def run_update_task(self):
        if self.is_running_flag:
            self._add_log("任务已在运行中", "warning")
            return
        self.is_running_flag = True
        self._add_log("开始执行配置更新任务", "info")
        db = SessionLocal()
        try:
            self.db = db
            config = self.get_config()
            target_dir = config.get("target_dir", "./uploads/config")
            # 确保使用绝对路径
            if not os.path.isabs(target_dir):
                # 获取项目根目录（main.py所在目录）
                project_root = Path(__file__).parent.parent.parent
                target_dir = os.path.join(project_root, target_dir.lstrip('./'))
            target_dir = os.path.abspath(target_dir)
            os.makedirs(target_dir, exist_ok=True)
            self._add_log(f"📁 目标目录: {target_dir}", "info")
            nodes = self._download_and_process_nodes(config)
            if nodes:
                self._add_log(f"📝 开始生成配置文件，共 {len(nodes)} 个节点", "info")
                filter_keywords = config.get("filter_keywords", [])
                v2ray_file = os.path.join(target_dir, config.get("v2ray_file", "xr"))
                self._add_log(f"🔧 正在生成V2Ray配置文件: {v2ray_file}", "info")
                self._generate_v2ray_config(nodes, v2ray_file, filter_keywords)
                clash_file = os.path.join(target_dir, config.get("clash_file", "clash.yaml"))
                self._add_log(f"🔧 正在生成Clash配置文件: {clash_file}", "info")
                self._generate_clash_config(nodes, clash_file, filter_keywords)
                self._add_log(f"🎉 配置更新完成！成功处理了 {len(nodes)} 个节点", "success")
                self._update_last_update_time()
            else:
                self._add_log("❌ 未获取到有效节点，跳过配置文件生成", "error")
            self._add_log("配置更新任务完成", "success")
        except Exception as e:
            self._add_log(f"配置更新失败: {str(e)}", "error")
            logger.error(f"配置更新失败: {str(e)}", exc_info=True)
        finally:
            time.sleep(1)
            self.is_running_flag = False
            if db:
                db.close()
    
    def run_test_task(self):
        if self.is_running_flag:
            self._add_log("任务已在运行中", "warning")
            return
        self.is_running_flag = True
        self._add_log("开始执行验证任务", "info")
        db = SessionLocal()
        try:
            self.db = db
            config = self.get_config()
            nodes = self._download_and_process_nodes(config)
            if nodes:
                self._add_log(f"验证完成，处理了 {len(nodes)} 个节点", "success")
            else:
                self._add_log("验证失败，未获取到有效节点", "error")
            self._add_log("验证任务完成", "success")
        except Exception as e:
            self._add_log(f"验证失败: {str(e)}", "error")
            logger.error(f"验证失败: {str(e)}", exc_info=True)
        finally:
            self.is_running_flag = False
            if db:
                db.close()
    
    def stop_update_task(self):
        if self.is_running_flag:
            self.is_running_flag = False
            self._add_log("任务已停止", "info")
        else:
            self._add_log("任务未在运行", "warning")
    
    def _download_and_process_nodes(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        urls = config.get("urls", [])
        filter_keywords = config.get("filter_keywords", [])
        nodes = []
        urls = [url.strip() for url in urls if isinstance(url, str) and url.strip() and url.strip().startswith(('http://', 'https://'))]
        if not urls:
            self._add_log("❌ 错误：未配置节点源URL，请在后台设置中添加节点源", "error")
            raise ValueError("未配置节点源URL，请在后台设置中添加节点源")
        self._add_log(f"🚀 开始节点采集，共 {len(urls)} 个节点源", "info")
        if not filter_keywords:
            self._add_log("⚠️ 警告：未配置过滤关键词，将不过滤任何节点", "warning")
        else:
            self._add_log(f"🔍 过滤关键词: {', '.join(filter_keywords)} (将根据节点名称过滤)", "info")
        for i, url in enumerate(urls, 1):
            try:
                self._add_log(f"📥 [{i}/{len(urls)}] 正在下载节点源: {url}", "info")
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                content = response.text
                content_size = len(content)
                self._add_log(f"📊 下载完成，内容大小: {content_size} 字符", "info")
                if self._is_base64(content):
                    try:
                        content = base64.b64decode(content).decode('utf-8')
                        self._add_log(f"🔓 Base64解码成功，解码后大小: {len(content)} 字符", "info")
                    except:
                        self._add_log(f"⚠️ Base64解码失败，使用原始内容", "warning")
                node_links = self._extract_node_links(content)
                self._add_log(f"🔗 从 {url} 提取到 {len(node_links)} 个节点链接", "info")
                if node_links and len(node_links) > 0:
                    sample_url = node_links[0]
                    if '#' in sample_url:
                        fragment = sample_url.split('#')[1]
                        if len(fragment) > 0:
                            try:
                                decoded_name = urllib.parse.unquote(fragment, encoding='utf-8')
                                self._add_log(f"   示例节点名称: '{decoded_name}' (长度: {len(decoded_name)})", "info")
                            except:
                                pass
                if node_links:
                    type_count = {}
                    for link in node_links:
                        if link.startswith('ss://'):
                            type_count['SS'] = type_count.get('SS', 0) + 1
                        elif link.startswith('ssr://'):
                            type_count['SSR'] = type_count.get('SSR', 0) + 1
                        elif link.startswith('vmess://'):
                            type_count['VMess'] = type_count.get('VMess', 0) + 1
                        elif link.startswith('trojan://'):
                            type_count['Trojan'] = type_count.get('Trojan', 0) + 1
                        elif link.startswith('vless://'):
                            type_count['VLESS'] = type_count.get('VLESS', 0) + 1
                        elif link.startswith('hysteria2://') or link.startswith('hy2://'):
                            type_count['Hysteria2'] = type_count.get('Hysteria2', 0) + 1
                        elif link.startswith('tuic://'):
                            type_count['TUIC'] = type_count.get('TUIC', 0) + 1
                    if type_count:
                        type_info = ', '.join([f"{k}: {v}" for k, v in type_count.items()])
                        self._add_log(f"📈 节点类型统计: {type_info}", "info")
                for link in node_links:
                    nodes.append({
                        'url': link,
                        'source_index': i - 1,
                        'source_url': url,
                        'is_first_source': i == 1
                    })
                self._add_log(f"✅ [{i}/{len(urls)}] 从 {url} 成功获取 {len(node_links)} 个节点", "success")
            except Exception as e:
                self._add_log(f"❌ [{i}/{len(urls)}] 下载 {url} 失败: {str(e)}", "error")
        total_count = len(nodes)
        self._add_log(f"🎉 节点采集完成！总共获得 {total_count} 个节点", "success")
        return nodes
    
    def _is_base64(self, text: str) -> bool:
        try:
            clean_text = ''.join(text.split())
            if len(clean_text) % 4 != 0:
                return False
            base64.b64decode(clean_text)
            return True
        except:
            try:
                base64.b64decode(text)
                return True
            except:
                return False
    
    def _extract_node_links(self, content: str) -> List[str]:
        patterns = [
            r'vmess://[A-Za-z0-9+/=]+',
            r'vless://[A-Za-z0-9+/=@:?#%.-]+',
            r'ss://[A-Za-z0-9+/=@:?#%.-]+',
            r'ssr://[A-Za-z0-9+/=]+',
            r'trojan://[A-Za-z0-9-]+@[^:\s]+:\d+(?:[?&][^#\s]*)?(?:#[^\s]*)?',
            r'hysteria2://[A-Za-z0-9+/=@:?#%.-]+',
            r'hy2://[A-Za-z0-9+/=@:?#%.-]+',
            r'tuic://[A-Za-z0-9+/=@:?#%.-]+'
        ]
        links = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            links.extend(matches)
        return links
    
    def _filter_nodes(self, nodes: List[str], keywords: List[str]) -> List[str]:
        filtered = []
        for node in nodes:
            if not any(keyword in node for keyword in keywords):
                filtered.append(node)
        return filtered
    
    def _generate_v2ray_config(self, nodes: List[Dict[str, Any]], output_file: str, filter_keywords: List[str] = None):
        try:
            self._add_log(f"📋 开始生成V2Ray配置，节点数量: {len(nodes)}", "info")
            first_source_nodes = [node for node in nodes if node.get('is_first_source', False)]
            other_source_nodes = [node for node in nodes if not node.get('is_first_source', False)]
            ordered_nodes = first_source_nodes + other_source_nodes
            filtered_count = 0
            filtered_node_urls = []
            for node_info in ordered_nodes:
                node_url = node_info['url']
                if filter_keywords:
                    proxy = self._parse_node_without_rename(node_url)
                    if proxy:
                        node_name = proxy.get('name')
                        if not node_name:
                            node_name = f"{proxy.get('server', 'node')}:{proxy.get('port', '0')}"
                        if any(keyword in node_name for keyword in filter_keywords):
                            filtered_count += 1
                            continue
                filtered_node_urls.append(node_url)
            if filter_keywords and filtered_count > 0:
                self._add_log(f"🔍 根据节点名称过滤掉 {filtered_count} 个节点（V2Ray配置）", "info")
            content = '\n'.join(filtered_node_urls)
            content_size = len(content)
            self._add_log(f"📊 节点内容大小: {content_size} 字符", "info")
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            encoded_size = len(encoded_content)
            self._add_log(f"🔐 Base64编码完成，编码后大小: {encoded_size} 字符", "info")
            
            # 先保存到文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(encoded_content)
            file_size = os.path.getsize(output_file)
            self._add_log(f"💾 V2Ray配置文件已保存: {output_file} (大小: {file_size} 字节)", "info")
            
            # 立即同步到数据库（确保订阅服务能获取最新配置）
            self._save_v2ray_config_to_db(encoded_content)
            self._add_log(f"💾 V2Ray配置已同步到数据库", "info")
            
            self._add_log(f"✅ V2Ray配置生成完成！文件: {output_file}", "success")
        except Exception as e:
            self._add_log(f"❌ 生成V2Ray配置失败: {str(e)}", "error")
            raise
    
    def _generate_clash_config(self, nodes: List[Dict[str, Any]], output_file: str, filter_keywords: List[str] = None):
        try:
            self._add_log(f"📋 开始生成Clash配置，节点数量: {len(nodes)}", "info")
            proxies = []
            proxy_names = []
            node_type_count = {}
            failed_count = 0
            filtered_count = 0
            seen_nodes = set()  # 用于去重
            name_counter = {}  # 用于确保节点名称唯一
            self._add_log(f"🔍 开始解析 {len(nodes)} 个节点为Clash格式", "info")
            for i, node_info in enumerate(nodes, 1):
                try:
                    node_url = node_info['url']
                    if node_url.startswith('ss://'):
                        node_type = 'SS'
                    elif node_url.startswith('ssr://'):
                        node_type = 'SSR'
                    elif node_url.startswith('vmess://'):
                        node_type = 'VMess'
                    elif node_url.startswith('trojan://'):
                        node_type = 'Trojan'
                    elif node_url.startswith('vless://'):
                        node_type = 'VLESS'
                    elif node_url.startswith('hysteria2://') or node_url.startswith('hy2://'):
                        node_type = 'Hysteria2'
                    elif node_url.startswith('tuic://'):
                        node_type = 'TUIC'
                    else:
                        node_type = 'Unknown'
                    proxy = self._parse_node_without_rename(node_url)
                    if proxy:
                        if not proxy.get('name'):
                            proxy['name'] = f"{proxy.get('server', 'node')}:{proxy.get('port', '0')}"
                        node_name = proxy['name']
                        if i <= 3:
                            self._add_log(f"   节点 {i} 解析结果: 名称='{node_name}' (长度: {len(node_name)})", "info")
                        if filter_keywords and any(keyword in node_name for keyword in filter_keywords):
                            filtered_count += 1
                            continue
                        # 生成节点唯一标识用于去重
                        node_key = self._get_node_key(proxy)
                        if node_key in seen_nodes:
                            continue  # 跳过重复节点
                        seen_nodes.add(node_key)
                        # 确保节点名称唯一
                        original_name = node_name
                        if node_name in name_counter:
                            name_counter[node_name] += 1
                            node_name = f"{original_name}-{name_counter[node_name]}"
                            proxy['name'] = node_name
                        else:
                            name_counter[node_name] = 0
                        proxies.append(proxy)
                        proxy_names.append(node_name)
                        node_type_count[node_type] = node_type_count.get(node_type, 0) + 1
                    else:
                        failed_count += 1
                        if failed_count <= 5:
                            self._add_log(f"⚠️ 第 {i} 个节点解析失败: {node_type} 节点格式错误", "warning")
                    if i % 100 == 0:
                        self._add_log(f"📊 已处理 {i}/{len(nodes)} 个节点", "info")
                except Exception as e:
                    failed_count += 1
                    if failed_count <= 5:
                        self._add_log(f"⚠️ 处理第 {i} 个节点异常: {str(e)}", "warning")
            if filter_keywords and filtered_count > 0:
                self._add_log(f"🔍 根据节点名称过滤掉 {filtered_count} 个节点", "info")
            duplicate_count = len(nodes) - len(proxies) - failed_count - filtered_count
            if duplicate_count > 0:
                self._add_log(f"🔄 去重完成: 移除了 {duplicate_count} 个重复节点", "info")
            if node_type_count:
                type_info = ', '.join([f"{k}: {v}" for k, v in node_type_count.items()])
                self._add_log(f"📈 成功解析节点类型统计: {type_info}", "info")
            self._add_log(f"📊 解析完成: 成功 {len(proxies)} 个节点，失败 {failed_count} 个", "info")
            if not proxies:
                self._add_log("❌ 没有有效的节点可以生成Clash配置", "error")
                return
            self._add_log(f"🔧 开始生成Clash配置文件，使用 {len(proxies)} 个有效节点", "info")
            clash_config_content = self._generate_clash_with_legacy_template(proxies, proxy_names)
            config_size = len(clash_config_content)
            self._add_log(f"📊 Clash配置内容大小: {config_size} 字符", "info")
            
            # 先保存到文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(clash_config_content)
            file_size = os.path.getsize(output_file)
            self._add_log(f"💾 Clash配置文件已保存: {output_file} (大小: {file_size} 字节)", "info")
            
            # 立即同步到数据库（确保订阅服务能获取最新配置）
            self._save_clash_config_to_db(clash_config_content)
            self._add_log(f"💾 Clash配置已同步到数据库", "info")
            
            # 清除节点服务缓存
            try:
                from app.services.node_service import NodeService
                node_service = NodeService(self.db)
                node_service.clear_cache()
                node_service.close()
                self._add_log(f"🔄 节点服务缓存已清除", "info")
            except Exception as e:
                self._add_log(f"⚠️ 清除节点缓存失败: {str(e)}", "warning")
            
            self._add_log(f"✅ Clash配置生成完成！文件: {output_file}，共 {len(proxies)} 个节点", "success")
        except Exception as e:
            self._add_log(f"❌ 生成Clash配置失败: {str(e)}", "error")
            raise
    
    def _create_basic_clash_config_fallback(self, proxies: List[Dict[str, Any]], proxy_names: List[str]) -> str:
        config = {
            "port": 7890,
            "socks-port": 7891,
            "allow-lan": True,
            "mode": "Rule",
            "log-level": "info",
            "external-controller": ":9090",
            "dns": {
                "enable": True,
                "nameserver": ["119.29.29.29", "223.5.5.5"],
                "fallback": ["8.8.8.8", "8.8.4.4"]
            },
            "proxies": proxies,
            "proxy-groups": [
                {
                    "name": "🚀 节点选择",
                    "type": "select",
                    "proxies": ["♻️ 自动选择", "DIRECT"] + proxy_names
                },
                {
                    "name": "♻️ 自动选择",
                    "type": "url-test",
                    "url": "http://www.gstatic.com/generate_204",
                    "interval": 300,
                    "tolerance": 50,
                    "proxies": proxy_names
                },
                {
                    "name": "🎯 全球直连",
                    "type": "select",
                    "proxies": ["DIRECT", "🚀 节点选择", "♻️ 自动选择"]
                },
                {
                    "name": "🛑 全球拦截",
                    "type": "select",
                    "proxies": ["REJECT", "DIRECT"]
                },
                {
                    "name": "🐟 漏网之鱼",
                    "type": "select",
                    "proxies": ["🚀 节点选择", "🎯 全球直连", "♻️ 自动选择"] + proxy_names
                }
            ],
            "rules": [
                "DOMAIN-SUFFIX,{domain},🎯 全球直连",
                "IP-CIDR,127.0.0.0/8,🎯 全球直连,no-resolve",
                "IP-CIDR,172.16.0.0/12,🎯 全球直连,no-resolve",
                "IP-CIDR,192.168.0.0/16,🎯 全球直连,no-resolve",
                "GEOIP,CN,🎯 全球直连",
                "MATCH,🐟 漏网之鱼"
            ]
        }
        return yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    def _generate_clash_with_legacy_template(self, proxies: List[Dict[str, Any]], proxy_names: List[str]) -> str:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            app_dir = os.path.dirname(script_dir)
            head_file = os.path.join(app_dir, 'templates', 'clash_template_head.yaml')
            tail_file = os.path.join(app_dir, 'templates', 'clash_template_tail.yaml')
            head_file = os.path.normpath(head_file)
            tail_file = os.path.normpath(tail_file)
            if not os.path.exists(head_file) or not os.path.exists(tail_file):
                self._add_log(f"⚠️ 模板文件不存在，使用备用配置", "warning")
                if not os.path.exists(head_file):
                    self._add_log(f"   缺失文件: {head_file}", "warning")
                if not os.path.exists(tail_file):
                    self._add_log(f"   缺失文件: {tail_file}", "warning")
                return self._create_basic_clash_config_fallback(proxies, proxy_names)
            with open(head_file, encoding='utf-8') as f:
                head = f.read().rstrip() + '\n'
            with open(tail_file, encoding='utf-8') as f:
                tail = f.read().lstrip()
            proxies_yaml = yaml.dump({'proxies': proxies}, allow_unicode=True, sort_keys=False, indent=2)
            tail_lines = tail.split('\n')
            formatted_tail_lines = []
            i = 0
            while i < len(tail_lines):
                line = tail_lines[i]
                if line.strip():
                    if line.startswith('  - name:') or line.startswith('- name:'):
                        if line.startswith('- name:'):
                            formatted_tail_lines.append('  ' + line)
                        else:
                            formatted_tail_lines.append(line)
                        j = i + 1
                        while j < len(tail_lines):
                            next_line = tail_lines[j]
                            if 'proxies:' in next_line:
                                formatted_tail_lines.append(next_line)
                                k = j + 1
                                while k < len(tail_lines) and (tail_lines[k].startswith('      -') or not tail_lines[k].strip()):
                                    k += 1
                                for proxy_name in proxy_names:
                                    formatted_tail_lines.append(f'      - {proxy_name}')
                                i = k - 1
                                break
                            else:
                                formatted_tail_lines.append(next_line)
                                j += 1
                        if j >= len(tail_lines):
                            i = len(tail_lines)
                    else:
                        formatted_tail_lines.append(line)
                else:
                    formatted_tail_lines.append(line)
                i += 1
            formatted_tail = '\n'.join(formatted_tail_lines)
            # 检查 formatted_tail 是否已经包含 proxy-groups: 标签
            if formatted_tail.strip().startswith('proxy-groups:'):
                final_content = head + '\nproxies:\n' + proxies_yaml[9:] + '\n' + formatted_tail
            else:
                final_content = head + '\nproxies:\n' + proxies_yaml[9:] + '\nproxy-groups:\n' + formatted_tail
            return final_content
        except Exception as e:
            self._add_log(f"使用模板生成Clash配置失败: {str(e)}", "error")
            return self._create_basic_clash_config_fallback(proxies, proxy_names)
    
    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            if self.logs:
                return self.logs[-limit:] if len(self.logs) > limit else self.logs
            if self.db is not None:
                logs_record = self.db.query(SystemConfig).filter(SystemConfig.key == "config_update_logs").first()
                if logs_record:
                    logs_data = json.loads(logs_record.value)
                    return logs_data[-limit:] if logs_data else []
            return []
        except Exception as e:
            logger.error(f"获取日志失败: {str(e)}")
            return self.logs[-limit:] if self.logs else []
    
    def _add_log(self, message: str, level: str = "info"):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        }
        self.logs.append(log_entry)
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]

        try:
            if self.db is None:
                logger.warning("数据库连接无效，仅保存到内存")
                return
            logs_record = self.db.query(SystemConfig).filter(SystemConfig.key == "config_update_logs").first()
            if logs_record:
                logs_data = json.loads(logs_record.value)
            else:
                logs_data = []
            logs_data.append(log_entry)
            if len(logs_data) > self.max_logs:
                logs_data = logs_data[-self.max_logs:]
            if logs_record:
                logs_record.value = json.dumps(logs_data)
            else:
                logs_record = SystemConfig(
                    key="config_update_logs",
                    value=json.dumps(logs_data),
                    type="json",
                    category="general",
                    display_name="配置更新日志",
                    description="配置更新操作日志"
                )
                self.db.add(logs_record)
            self.db.commit()
            logger.info(f"日志已保存到数据库: {message}")
        except Exception as e:
            logger.error(f"保存日志到数据库失败: {str(e)}")

    def clear_old_logs(self, keep_recent: int = 50):
        """清理旧日志，只保留最近的N条"""
        if len(self.logs) > keep_recent:
            self.logs = self.logs[-keep_recent:]
    
    def get_config(self) -> Dict[str, Any]:
        try:
            config_record = self.db.query(SystemConfig).filter(SystemConfig.key == "config_update").first()
            if config_record:
                return json.loads(config_record.value)
            else:
                return self.default_config.copy()
        except Exception as e:
            logger.error(f"获取配置失败: {str(e)}")
            return self.default_config.copy()
    
    def get_node_sources(self) -> List[str]:
        try:
            config = self.get_config()
            return config.get("urls", [])
        except Exception as e:
            self._add_log(f"获取节点源配置失败: {str(e)}", "error")
            return []
    
    def update_node_sources(self, sources_data: dict) -> None:
        try:
            urls = sources_data.get("urls", [])
            if not isinstance(urls, list):
                raise ValueError("节点源URL必须是列表格式")
            filtered_urls = []
            for url in urls:
                url = url.strip() if isinstance(url, str) else str(url).strip()
                if url and url.startswith(('http://', 'https://')):
                    filtered_urls.append(url)
                elif url:
                    raise ValueError(f"无效的URL格式: {url}")
            if not filtered_urls:
                raise ValueError("至少需要配置一个有效的节点源URL")
            config = self.get_config()
            config["urls"] = filtered_urls
            self.update_config(config)
            self._add_log(f"节点源配置已更新，共 {len(filtered_urls)} 个源", "info")
        except Exception as e:
            self._add_log(f"更新节点源配置失败: {str(e)}", "error")
            raise
    
    def get_filter_keywords(self) -> List[str]:
        try:
            config = self.get_config()
            return config.get("filter_keywords", [])
        except Exception as e:
            self._add_log(f"获取过滤关键词配置失败: {str(e)}", "error")
            return []
    
    def get_node_name_suffix(self) -> str:
        try:
            config = self.get_config()
            return config.get("node_name_suffix", "")
        except Exception as e:
            self._add_log(f"获取节点名称后缀配置失败: {str(e)}", "error")
            return ""
    
    def update_node_name_suffix(self, suffix_data: dict) -> None:
        try:
            suffix = suffix_data.get("suffix", "")
            if not isinstance(suffix, str):
                raise ValueError("节点名称后缀必须是字符串格式")
            config = self.get_config()
            config["node_name_suffix"] = suffix
            self.update_config(config)
            self._add_log(f"节点名称后缀已更新: {suffix}", "info")
        except Exception as e:
            self._add_log(f"更新节点名称后缀失败: {str(e)}", "error")
            raise
    
    def update_filter_keywords(self, keywords_data: dict) -> None:
        try:
            keywords = keywords_data.get("keywords", [])
            if not isinstance(keywords, list):
                raise ValueError("过滤关键词必须是列表格式")
            config = self.get_config()
            config["filter_keywords"] = keywords
            self.update_config(config)
            self._add_log(f"过滤关键词配置已更新，共 {len(keywords)} 个关键词", "info")
        except Exception as e:
            self._add_log(f"更新过滤关键词配置失败: {str(e)}", "error")
            raise
    
    def update_config(self, config_data: Dict[str, Any]):
        try:
            validated_config = self._validate_config(config_data)
            config_record = self.db.query(SystemConfig).filter(SystemConfig.key == "config_update").first()
            if config_record:
                config_record.value = json.dumps(validated_config)
            else:
                config_record = SystemConfig(
                    key="config_update",
                    value=json.dumps(validated_config),
                    type="json",
                    category="general",
                    display_name="配置更新设置",
                    description="配置更新设置"
                )
                self.db.add(config_record)
            self.db.commit()
            self._add_log("配置已更新", "success")
        except Exception as e:
            self.db.rollback()
            self._add_log(f"更新配置失败: {str(e)}", "error")
            raise
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        validated = self.default_config.copy()
        if "urls" in config and isinstance(config["urls"], list):
            validated["urls"] = config["urls"]
        if "target_dir" in config and isinstance(config["target_dir"], str):
            validated["target_dir"] = config["target_dir"]
        if "v2ray_file" in config and isinstance(config["v2ray_file"], str):
            validated["v2ray_file"] = config["v2ray_file"]
        if "clash_file" in config and isinstance(config["clash_file"], str):
            validated["clash_file"] = config["clash_file"]
        if "update_interval" in config and isinstance(config["update_interval"], int):
            validated["update_interval"] = max(300, config["update_interval"])
        if "enable_schedule" in config and isinstance(config["enable_schedule"], bool):
            validated["enable_schedule"] = config["enable_schedule"]
        if "filter_keywords" in config and isinstance(config["filter_keywords"], list):
            validated["filter_keywords"] = config["filter_keywords"]
        return validated
    
    def get_generated_files(self) -> Dict[str, Any]:
        try:
            config = self.get_config()
            target_dir = config.get("target_dir", "./uploads/config")
            v2ray_file = os.path.join(target_dir, config.get("v2ray_file", "xr"))
            clash_file = os.path.join(target_dir, config.get("clash_file", "clash.yaml"))
            files_info = {}
            if os.path.exists(v2ray_file):
                stat = os.stat(v2ray_file)
                files_info["v2ray"] = {
                    "path": v2ray_file,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "exists": True
                }
            else:
                files_info["v2ray"] = {"exists": False}
            if os.path.exists(clash_file):
                stat = os.stat(clash_file)
                files_info["clash"] = {
                    "path": clash_file,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "exists": True
                }
            else:
                files_info["clash"] = {"exists": False}
            return files_info
        except Exception as e:
            logger.error(f"获取文件信息失败: {str(e)}")
            return {}
    
    def _check_config_files_exist(self) -> bool:
        try:
            config = self.get_config()
            target_dir = config.get("target_dir", "./uploads/config")
            v2ray_file = os.path.join(target_dir, config.get("v2ray_file", "xr"))
            clash_file = os.path.join(target_dir, config.get("clash_file", "clash.yaml"))
            return os.path.exists(v2ray_file) and os.path.exists(clash_file)
        except:
            return False
    
    def _get_last_update_time(self) -> Optional[str]:
        try:
            config_record = self.db.query(SystemConfig).filter(SystemConfig.key == "config_update_last_time").first()
            if config_record:
                return config_record.value
            return None
        except:
            return None
    
    def _update_last_update_time(self):
        try:
            current_time = datetime.now().isoformat()
            config_record = self.db.query(SystemConfig).filter(SystemConfig.key == "config_update_last_time").first()
            if config_record:
                config_record.value = current_time
            else:
                config_record = SystemConfig(
                    key="config_update_last_time",
                    value=current_time,
                    type="string",
                    category="general",
                    display_name="配置更新最后时间",
                    description="配置更新最后时间"
                )
                self.db.add(config_record)
            self.db.commit()
        except Exception as e:
            logger.error(f"更新最后更新时间失败: {str(e)}")
    
    def _get_next_update_time(self) -> Optional[str]:
        try:
            config = self.get_config()
            if not config.get("enable_schedule", False):
                return None
            last_update = self._get_last_update_time()
            if not last_update:
                return None
            last_time = datetime.fromisoformat(last_update)
            interval = config.get("update_interval", 3600)
            next_time = last_time + timedelta(seconds=interval)
            return next_time.isoformat()
        except:
            return None
    
    def get_schedule_config(self) -> Dict[str, Any]:
        return self.get_config()
    
    def update_schedule_config(self, schedule_data: Dict[str, Any]):
        self.update_config(schedule_data)
    
    def start_scheduled_task(self):
        try:
            config = self.get_config()
            if not config.get("enable_schedule", False):
                self._add_log("定时任务未启用", "warning")
                return
            if self.scheduled_task is not None:
                self._add_log("定时任务已在运行", "warning")
                return
            interval = config.get("update_interval", 3600)
            self.scheduled_task = threading.Timer(interval, self._scheduled_update)
            self.scheduled_task.start()
            self._add_log(f"定时任务已启动，间隔 {interval} 秒", "success")
        except Exception as e:
            self._add_log(f"启动定时任务失败: {str(e)}", "error")
            raise
    
    def stop_scheduled_task(self):
        try:
            if self.scheduled_task is not None:
                self.scheduled_task.cancel()
                self.scheduled_task = None
                self._add_log("定时任务已停止", "success")
            else:
                self._add_log("定时任务未在运行", "warning")
        except Exception as e:
            self._add_log(f"停止定时任务失败: {str(e)}", "error")
            raise
    
    def _scheduled_update(self):
        try:
            if not self.is_running_flag:
                self.run_update_task()
            config = self.get_config()
            if config.get("enable_schedule", False):
                interval = config.get("update_interval", 3600)
                self.scheduled_task = threading.Timer(interval, self._scheduled_update)
                self.scheduled_task.start()
        except Exception as e:
            self._add_log(f"定时更新失败: {str(e)}", "error")
            logger.error(f"定时更新失败: {str(e)}", exc_info=True)
    
    def _save_clash_config_to_db(self, config_content: str):
        """保存Clash配置到数据库 - 实时同步，确保订阅服务获取最新配置"""
        try:
            from sqlalchemy import text
            current_time = datetime.now()
            config_size = len(config_content)
            
            check_query = text('SELECT id FROM system_configs WHERE key = \'clash_config\' AND type = \'clash\'')
            existing = self.db.execute(check_query).first()
            
            if existing:
                update_query = text("""
                    UPDATE system_configs 
                    SET value = :value, updated_at = :updated_at
                    WHERE key = 'clash_config' AND type = 'clash'
                """)
                self.db.execute(update_query, {
                    "value": config_content,
                    "updated_at": current_time
                })
                self.db.commit()
                self._add_log(f"✅ Clash配置已实时同步到数据库 (大小: {config_size} 字符)", "success")
            else:
                insert_query = text("""
                    INSERT INTO system_configs ("key", value, type, category, display_name, description, is_public, sort_order, created_at, updated_at)
                    VALUES ('clash_config', :value, 'clash', 'proxy', 'Clash有效配置', 'Clash代理有效配置文件', 0, 1, :created_at, :updated_at)
                """)
                self.db.execute(insert_query, {
                    "value": config_content,
                    "created_at": current_time,
                    "updated_at": current_time
                })
                self.db.commit()
                self._add_log(f"✅ Clash配置已创建并保存到数据库 (大小: {config_size} 字符)", "success")
        except Exception as e:
            self.db.rollback()
            self._add_log(f"❌ 保存Clash配置到数据库失败: {str(e)}", "error")
            logger.error(f"保存Clash配置到数据库失败: {str(e)}", exc_info=True)
            raise
    
    def _save_v2ray_config_to_db(self, config_content: str):
        """保存V2Ray配置到数据库 - 实时同步，确保订阅服务获取最新配置"""
        try:
            from sqlalchemy import text
            current_time = datetime.now()
            config_size = len(config_content)
            
            check_query = text('SELECT id FROM system_configs WHERE key = \'v2ray_config\' AND type = \'v2ray\'')
            existing = self.db.execute(check_query).first()
            
            if existing:
                update_query = text("""
                    UPDATE system_configs 
                    SET value = :value, updated_at = :updated_at
                    WHERE key = 'v2ray_config' AND type = 'v2ray'
                """)
                self.db.execute(update_query, {
                    "value": config_content,
                    "updated_at": current_time
                })
                self.db.commit()
                self._add_log(f"✅ V2Ray配置已实时同步到数据库 (大小: {config_size} 字符)", "success")
            else:
                insert_query = text("""
                    INSERT INTO system_configs ("key", value, type, category, display_name, description, is_public, sort_order, created_at, updated_at)
                    VALUES ('v2ray_config', :value, 'v2ray', 'proxy', 'V2Ray有效配置', 'V2Ray代理有效配置文件', 0, 2, :created_at, :updated_at)
                """)
                self.db.execute(insert_query, {
                    "value": config_content,
                    "created_at": current_time,
                    "updated_at": current_time
                })
                self.db.commit()
                self._add_log(f"✅ V2Ray配置已创建并保存到数据库 (大小: {config_size} 字符)", "success")
        except Exception as e:
            self.db.rollback()
            self._add_log(f"❌ 保存V2Ray配置到数据库失败: {str(e)}", "error")
            logger.error(f"保存V2Ray配置到数据库失败: {str(e)}", exc_info=True)
            raise
    
    def _parse_node_without_rename(self, node_url: str) -> Optional[Dict[str, Any]]:
        try:
            if node_url.startswith('vmess://'):
                return self._parse_vmess_raw(node_url)
            elif node_url.startswith('ss://'):
                return self._parse_ss_raw(node_url)
            elif node_url.startswith('trojan://'):
                return self._parse_trojan_raw(node_url)
            elif node_url.startswith('vless://'):
                return self._parse_vless_raw(node_url)
            elif node_url.startswith('ssr://'):
                return self._parse_ssr_raw(node_url)
            elif node_url.startswith('hysteria2://') or node_url.startswith('hy2://'):
                return self._parse_hysteria2_raw(node_url)
            elif node_url.startswith('tuic://'):
                return self._parse_tuic_raw(node_url)
            else:
                return self._smart_parse_node(node_url)
        except Exception as e:
            return None
    
    def _smart_parse_node(self, node_url: str) -> Optional[Dict[str, Any]]:
        try:
            if '://' in node_url:
                protocol, content = node_url.split('://', 1)
                try:
                    if '#' in content:
                        b64_part = content.split('#')[0]
                    else:
                        b64_part = content
                    b64_part += '=' * (-len(b64_part) % 4)
                    decoded = base64.b64decode(b64_part).decode('utf-8')
                    if decoded.startswith('{') and '"add"' in decoded:
                        try:
                            data = json.loads(decoded)
                            if 'add' in data and 'port' in data and 'id' in data:
                                return self._parse_vmess_raw(node_url)
                        except:
                            pass
                    if ':' in decoded and '@' in decoded and not decoded.startswith('{'):
                        try:
                            parts = decoded.split('@')
                            if len(parts) == 2 and ':' in parts[0] and ':' in parts[1]:
                                return self._parse_ss_raw(node_url)
                        except:
                            pass
                    if '@' in decoded and ':' in decoded and not decoded.startswith('{'):
                        try:
                            password, server_part = decoded.split('@', 1)
                            if ':' in server_part:
                                return self._parse_trojan_raw(node_url)
                        except:
                            pass
                except:
                    pass
            return None
        except Exception as e:
            return None
    
    def _parse_vmess_raw(self, vmess_url: str) -> Optional[Dict[str, Any]]:
        try:
            try:
                b64 = vmess_url[8:]
                b64 += '=' * (-len(b64) % 4)
                raw = base64.b64decode(b64).decode('utf-8')
                if ':' in raw and '@' in raw and not raw.startswith('{'):
                    parts = raw.split('@')
                    if len(parts) == 2:
                        userinfo_part = parts[0]
                        server_part = parts[1]
                        if ':' in userinfo_part and ':' in server_part:
                            method, password = userinfo_part.split(':', 1)
                            server, port = server_part.split(':', 1)
                            return {
                                'name': None,
                                'type': 'ss',
                                'server': server,
                                'port': int(port),
                                'cipher': method,
                                'password': password,
                            }
                data = json.loads(raw)
                name = data.get('ps', '')
                if name:
                    name = urllib.parse.unquote(name)
                    try:
                        name = json.loads(f'"{name}"')
                    except:
                        pass
                if not name or name.strip() == '' or name == 'vmess':
                    name = None
                proxy = {
                    'name': name,
                    'type': 'vmess',
                    'server': data.get('add'),
                    'port': int(data.get('port', 443)),
                    'uuid': data.get('id'),
                    'alterId': int(data.get('aid', 0)),
                    'cipher': data.get('scy', 'auto'),
                    'udp': True,
                    'tls': data.get('tls', '') == 'tls',
                }
                network = data.get('net', 'tcp')
                if network == 'ws':
                    proxy['network'] = 'ws'
                    proxy['ws-opts'] = {
                        'path': data.get('path', '/'),
                        'headers': {
                            'Host': data.get('host', '')
                        } if data.get('host') else {}
                    }
                elif network == 'h2':
                    proxy['network'] = 'h2'
                    proxy['h2-opts'] = {
                        'path': data.get('path', '/'),
                        'host': [data.get('host', '')] if data.get('host') else []
                    }
                elif network == 'grpc':
                    proxy['network'] = 'grpc'
                    proxy['grpc-opts'] = {
                        'grpc-service-name': data.get('path', '')
                    }
                return proxy
            except Exception as e:
                try:
                    if vmess_url.startswith('vmess://'):
                        url_parts = urllib.parse.urlparse(vmess_url)
                        if url_parts.hostname and url_parts.port:
                            query_params = urllib.parse.parse_qs(url_parts.query)
                            name = None
                            if url_parts.fragment:
                                name = urllib.parse.unquote(url_parts.fragment, encoding='utf-8')
                            proxy = {
                                'name': name,
                                'type': 'vmess',
                                'server': url_parts.hostname,
                                'port': url_parts.port,
                                'uuid': url_parts.username or query_params.get('uuid', [''])[0],
                                'alterId': int(query_params.get('aid', ['0'])[0]),
                                'cipher': query_params.get('scy', ['auto'])[0],
                                'udp': True,
                                'tls': query_params.get('tls', [''])[0] == 'tls',
                            }
                            network = query_params.get('net', ['tcp'])[0]
                            if network == 'ws':
                                proxy['network'] = 'ws'
                                proxy['ws-opts'] = {
                                    'path': query_params.get('path', ['/'])[0],
                                    'headers': {
                                        'Host': query_params.get('host', [''])[0]
                                    } if query_params.get('host', [''])[0] else {}
                                }
                            return proxy
                except Exception as e2:
                    pass
            return None
        except Exception as e:
            return None
    
    def _parse_ss_raw(self, ss_url: str) -> Optional[Dict[str, Any]]:
        try:
            url_parts = urllib.parse.urlparse(ss_url)
            name = None
            if url_parts.fragment:
                name = urllib.parse.unquote(url_parts.fragment, encoding='utf-8')
            if ss_url.startswith('ss://') and len(ss_url) > 100:
                b64_part = ss_url[5:]
                if url_parts.fragment:
                    b64_part = b64_part.split('#')[0] if '#' in b64_part else b64_part
                try:
                    b64_part += '=' * (-len(b64_part) % 4)
                    raw = base64.b64decode(b64_part).decode('utf-8')
                    if raw.startswith('{') and raw.endswith('}'):
                        data = json.loads(raw)
                        if not name:
                            name = data.get('ps', '')
                            if name:
                                name = urllib.parse.unquote(name)
                                try:
                                    name = json.loads(f'"{name}"')
                                except:
                                    pass
                            if not name or name.strip() == '' or name == 'vmess':
                                name = None
                        proxy = {
                            'name': name,
                            'type': 'vmess',
                            'server': data.get('add'),
                            'port': int(data.get('port', 443)),
                            'uuid': data.get('id'),
                            'alterId': int(data.get('aid', 0)),
                            'cipher': data.get('scy', 'auto'),
                            'udp': True,
                            'tls': data.get('tls', '') == 'tls',
                        }
                        network = data.get('net', 'tcp')
                        if network == 'ws':
                            proxy['network'] = 'ws'
                            proxy['ws-opts'] = {
                                'path': data.get('path', '/'),
                                'headers': {
                                    'Host': data.get('host', '')
                                } if data.get('host') else {}
                            }
                        elif network == 'h2':
                            proxy['network'] = 'h2'
                            proxy['h2-opts'] = {
                                'path': data.get('path', '/'),
                                'host': [data.get('host', '')] if data.get('host') else []
                            }
                        elif network == 'grpc':
                            proxy['network'] = 'grpc'
                            proxy['grpc-opts'] = {
                                'grpc-service-name': data.get('path', '')
                            }
                        return proxy
                except:
                    pass
            m = re.match(r'ss://([A-Za-z0-9+/=%]+)@([^:]+):(\d+)(?:[?][^#]*)?(?:#(.+))?$', ss_url)
            if m:
                userinfo, server, port, name_from_regex = m.groups()
                try:
                    if name_from_regex:
                        name_from_regex_decoded = urllib.parse.unquote(name_from_regex, encoding='utf-8')
                        if not name or len(name_from_regex_decoded) > len(name):
                            name = name_from_regex_decoded
                    userinfo = urllib.parse.unquote(userinfo)
                    userinfo += '=' * (-len(userinfo) % 4)
                    method_pass = base64.b64decode(userinfo).decode('utf-8')
                    method, password = method_pass.split(':', 1)
                    return {
                        'name': name,
                        'type': 'ss',
                        'server': server,
                        'port': int(port),
                        'cipher': method,
                        'password': password,
                    }
                except Exception as e:
                    pass
            if ss_url.startswith('ss://') and '@' not in ss_url:
                try:
                    b64_part = url_parts.path or ss_url[5:]
                    if url_parts.fragment:
                        b64_part = b64_part.split('#')[0] if '#' in b64_part else b64_part
                    b64_part += '=' * (-len(b64_part) % 4)
                    decoded = base64.b64decode(b64_part).decode('utf-8')
                    if '@' in decoded and ':' in decoded:
                        userinfo, serverinfo = decoded.split('@', 1)
                        if ':' in userinfo and ':' in serverinfo:
                            method, password = userinfo.split(':', 1)
                            server, port = serverinfo.split(':', 1)
                            return {
                                'name': name,
                                'type': 'ss',
                                'server': server,
                                'port': int(port),
                                'cipher': method,
                                'password': password,
                            }
                except Exception as e:
                    pass
            if url_parts.hostname and url_parts.port:
                try:
                    query_params = urllib.parse.parse_qs(url_parts.query)
                    if 'password' in query_params and 'method' in query_params:
                        return {
                            'name': name,
                            'type': 'ss',
                            'server': url_parts.hostname,
                            'port': url_parts.port,
                            'cipher': query_params['method'][0],
                            'password': query_params['password'][0],
                        }
                except Exception as e:
                    pass
            m = re.match(r'^ss://([^@]+)@([^:]+):(\d+)(?:[?][^#]*)?(?:#(.+))?$', ss_url)
            if m:
                userinfo, server, port, name_from_regex = m.groups()
                try:
                    if name_from_regex:
                        name_from_regex_decoded = urllib.parse.unquote(name_from_regex, encoding='utf-8')
                        if not name or len(name_from_regex_decoded) > len(name):
                            name = name_from_regex_decoded
                    userinfo = urllib.parse.unquote(userinfo)
                    if ':' in userinfo:
                        method, password = userinfo.split(':', 1)
                        return {
                            'name': name,
                            'type': 'ss',
                            'server': server,
                            'port': int(port),
                            'cipher': method,
                            'password': password,
                        }
                    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                    if re.match(uuid_pattern, userinfo):
                        cipher = 'none'
                        if '?' in ss_url:
                            params_part = ss_url.split('?')[1].split('#')[0]
                            params = urllib.parse.parse_qs(params_part)
                            if 'encryption' in params:
                                cipher = params['encryption'][0]
                        return {
                            'name': name,
                            'type': 'ss',
                            'server': server,
                            'port': int(port),
                            'cipher': cipher,
                            'password': userinfo,
                        }
                    userinfo += '=' * (-len(userinfo) % 4)
                    method_pass = base64.b64decode(userinfo).decode('utf-8')
                    method, password = method_pass.split(':', 1)
                    return {
                        'name': name,
                        'type': 'ss',
                        'server': server,
                        'port': int(port),
                        'cipher': method,
                        'password': password,
                    }
                except:
                    pass
            return None
        except Exception as e:
            return None
    
    def _parse_trojan_raw(self, trojan_url: str) -> Optional[Dict[str, Any]]:
        try:
            try:
                url_parts = urllib.parse.urlparse(trojan_url)
                server = url_parts.hostname
                port = url_parts.port
                password = url_parts.username
                if not server or not port or not password:
                    raise ValueError("缺少必要参数")
                query_params = urllib.parse.parse_qs(url_parts.query)
                name = None
                if url_parts.fragment:
                    name = urllib.parse.unquote(url_parts.fragment, encoding='utf-8')
                proxy = {
                    'name': name,
                    'type': 'trojan',
                    'server': server,
                    'port': port,
                    'password': password,
                    'udp': True,
                    'tls': True
                }
                sni = query_params.get('sni', [''])[0]
                if sni:
                    proxy['sni'] = sni
                allow_insecure = query_params.get('allowInsecure', [''])[0]
                if allow_insecure == '1' or allow_insecure.lower() == 'true':
                    proxy['skip-cert-verify'] = True
                network_type = query_params.get('type', ['tcp'])[0]
                if network_type == 'ws':
                    proxy['network'] = 'ws'
                    ws_opts = {}
                    path = query_params.get('path', ['/'])[0]
                    ws_opts['path'] = path
                    host = query_params.get('host', [''])[0]
                    if host:
                        ws_opts['headers'] = {'Host': host}
                    proxy['ws-opts'] = ws_opts
                return proxy
            except Exception as e:
                if trojan_url.startswith('trojan://'):
                    try:
                        b64_part = trojan_url[9:]
                        if '#' in b64_part:
                            b64_part = b64_part.split('#')[0]
                        b64_part += '=' * (-len(b64_part) % 4)
                        decoded = base64.b64decode(b64_part).decode('utf-8')
                        if '@' in decoded:
                            password, server_part = decoded.split('@', 1)
                            if ':' in server_part:
                                server, port_part = server_part.split(':', 1)
                                if '?' in port_part:
                                    port, params = port_part.split('?', 1)
                                else:
                                    port = port_part
                                    params = ''
                                name = None
                                if '#' in trojan_url:
                                    name = urllib.parse.unquote(trojan_url.split('#')[1], encoding='utf-8')
                                proxy = {
                                    'name': name,
                                    'type': 'trojan',
                                    'server': server,
                                    'port': int(port),
                                    'password': password,
                                    'udp': True,
                                    'tls': True
                                }
                                if params:
                                    query_params = urllib.parse.parse_qs(params)
                                    sni = query_params.get('sni', [''])[0]
                                    if sni:
                                        proxy['sni'] = sni
                                    allow_insecure = query_params.get('allowInsecure', [''])[0]
                                    if allow_insecure == '1' or allow_insecure.lower() == 'true':
                                        proxy['skip-cert-verify'] = True
                                return proxy
                    except Exception as e2:
                        pass
            return None
        except Exception as e:
            return None
    
    def _parse_vless_raw(self, vless_url: str) -> Optional[Dict[str, Any]]:
        try:
            m = re.match(r'^vless://([^@]+)@([^:]+):(\d+)(?:[?]([^#]+))?(?:#(.+))?$', vless_url)
            if m:
                uuid, server, port, params, name = m.groups()
                if name:
                    name = urllib.parse.unquote(name, encoding='utf-8')
                proxy = {
                    'name': name,
                    'type': 'vless',
                    'server': server,
                    'port': int(port),
                    'uuid': uuid,
                    'udp': True,
                }
                if params:
                    for param in params.split('&'):
                        if '=' in param:
                            key, value = param.split('=', 1)
                            if key == 'encryption':
                                proxy['cipher'] = value
                            elif key == 'type':
                                if value == 'ws':
                                    proxy['network'] = 'ws'
                            elif key == 'path':
                                proxy['ws-opts'] = {'path': value}
                            elif key == 'host':
                                proxy['ws-opts'] = proxy.get('ws-opts', {})
                                proxy['ws-opts']['headers'] = {'Host': value}
                            elif key == 'security':
                                if value == 'tls':
                                    proxy['tls'] = True
                            elif key == 'sni':
                                proxy['sni'] = value
                return proxy
            return None
        except Exception as e:
            return None
    
    def _parse_ssr_raw(self, ssr_url: str) -> Optional[Dict[str, Any]]:
        try:
            b64 = ssr_url[6:]
            b64 += '=' * (-len(b64) % 4)
            raw = base64.b64decode(b64).decode('utf-8')
            parts = raw.split('/')
            main_part = parts[0]
            params_part = parts[1] if len(parts) > 1 else ''
            main_parts = main_part.split(':')
            if len(main_parts) < 6:
                if len(main_parts) >= 2:
                    server, port = main_parts[0], main_parts[1]
                    protocol = 'origin'
                    method = 'none'
                    obfs = 'plain'
                    password = ''
                else:
                    return None
            else:
                server, port, protocol, method, obfs, password_b64 = main_parts[:6]
                if password_b64:
                    password_b64 += '=' * (-len(password_b64) % 4)
                    try:
                        password = base64.b64decode(password_b64).decode('utf-8')
                    except:
                        password = ''
                else:
                    password = ''
            name = None
            if params_part:
                params = urllib.parse.parse_qs(params_part)
                if 'remarks' in params:
                    name_b64 = params['remarks'][0]
                    name_b64 += '=' * (-len(name_b64) % 4)
                    try:
                        name = base64.b64decode(name_b64).decode('utf-8')
                    except:
                        name = None
            return {
                'name': name,
                'type': 'ssr',
                'server': server,
                'port': int(port),
                'cipher': method,
                'password': password,
                'protocol': protocol,
                'obfs': obfs,
            }
        except Exception as e:
            return None
    
    def _parse_hysteria2_raw(self, hysteria2_url: str) -> Optional[Dict[str, Any]]:
        try:
            m = re.match(r'^(?:hysteria2|hy2)://([^@]+)@([^:]+):(\d+)(?:[?]([^#]+))?(?:#(.+))?$', hysteria2_url)
            if m:
                password, server, port, params, name = m.groups()
                if name:
                    name = urllib.parse.unquote(name, encoding='utf-8')
                proxy = {
                    'name': name,
                    'type': 'hysteria2',
                    'server': server,
                    'port': int(port),
                    'password': password,
                    'udp': True,
                }
                if params:
                    for param in params.split('&'):
                        if '=' in param:
                            key, value = param.split('=', 1)
                            if key == 'sni':
                                proxy['sni'] = value
                            elif key == 'insecure':
                                proxy['skip-cert-verify'] = value == '1'
                return proxy
            return None
        except Exception as e:
            return None
    
    def _get_node_key(self, proxy: Dict[str, Any]) -> str:
        """生成节点的唯一标识用于去重"""
        proxy_type = proxy.get('type', 'unknown')
        server = proxy.get('server', '')
        port = proxy.get('port', 0)
        
        if proxy_type == 'vmess':
            uuid = proxy.get('uuid', '')
            return f"{proxy_type}:{server}:{port}:{uuid}"
        elif proxy_type in ['ss', 'ssr']:
            password = proxy.get('password', '')
            cipher = proxy.get('cipher', '')
            return f"{proxy_type}:{server}:{port}:{cipher}:{password}"
        elif proxy_type == 'trojan':
            password = proxy.get('password', '')
            return f"{proxy_type}:{server}:{port}:{password}"
        elif proxy_type == 'vless':
            uuid = proxy.get('uuid', '')
            return f"{proxy_type}:{server}:{port}:{uuid}"
        elif proxy_type == 'hysteria2':
            password = proxy.get('password', '')
            return f"{proxy_type}:{server}:{port}:{password}"
        elif proxy_type == 'tuic':
            uuid = proxy.get('uuid', '')
            return f"{proxy_type}:{server}:{port}:{uuid}"
        else:
            return f"{proxy_type}:{server}:{port}"
    
    def _parse_tuic_raw(self, tuic_url: str) -> Optional[Dict[str, Any]]:
        try:
            m = re.match(r'^tuic://([^@]+)@([^:]+):(\d+)(?:[?]([^#]+))?(?:#(.+))?$', tuic_url)
            if m:
                uuid, server, port, params, name = m.groups()
                if name:
                    name = urllib.parse.unquote(name, encoding='utf-8')
                proxy = {
                    'name': name,
                    'type': 'tuic',
                    'server': server,
                    'port': int(port),
                    'uuid': uuid,
                    'udp': True,
                }
                if params:
                    for param in params.split('&'):
                        if '=' in param:
                            key, value = param.split('=', 1)
                            if key == 'sni':
                                proxy['sni'] = value
                            elif key == 'insecure':
                                proxy['skip-cert-verify'] = value == '1'
                return proxy
            return None
        except Exception as e:
            return None
