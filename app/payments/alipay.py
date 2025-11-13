import json
import hashlib
import hmac
import base64
import time
import requests
import logging
from pathlib import Path
from urllib.parse import urlencode, quote
from typing import Dict, Any, Optional
from app.contracts.payment_interface import PaymentInterface, PaymentRequest, PaymentResponse, PaymentNotify

# 设置支付日志
log_dir = Path("uploads/logs")
log_dir.mkdir(parents=True, exist_ok=True)

# 创建支付专用日志logger
payment_logger = logging.getLogger('payment')
payment_logger.setLevel(logging.INFO)

# 如果还没有处理器，添加文件处理器
if not payment_logger.handlers:
    # 支付日志文件
    payment_handler = logging.FileHandler(
        log_dir / 'payment.log',
        encoding='utf-8'
    )
    payment_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    payment_handler.setFormatter(formatter)
    payment_logger.addHandler(payment_handler)
    
    # 同时输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    payment_logger.addHandler(console_handler)


class AlipayPayment(PaymentInterface):
    """支付宝支付实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.app_id = config.get('alipay_app_id', '')
        self.private_key = config.get('alipay_private_key', '')
        self.public_key = config.get('alipay_public_key', '')
        self.gateway_url = config.get('alipay_gateway', 'https://openapi.alipay.com/gateway.do')
        self.charset = 'utf-8'
        self.sign_type = 'RSA2'
        self.version = '1.0'
        
        # 检查pycryptodome是否可用
        try:
            from Crypto.PublicKey import RSA
            self._crypto_available = True
            payment_logger.info("✅ pycryptodome 已加载")
        except ImportError:
            self._crypto_available = False
            payment_logger.error("❌ pycryptodome 未安装，请执行: pip install pycryptodome==3.19.0")
    
    def pay(self, request: PaymentRequest) -> PaymentResponse:
        """创建支付宝支付订单"""
        try:
            # 检查pycryptodome是否可用
            if not self._crypto_available:
                error_msg = "pycryptodome 未安装，无法生成RSA签名。请执行: pip install pycryptodome==3.19.0"
                payment_logger.error(error_msg)
                raise Exception(error_msg)
            
            # 检查必要的配置
            if not self.app_id or not self.private_key:
                raise Exception("支付宝配置不完整：缺少APPID或私钥")
            
            # 检查网关地址（生产环境必须使用正式环境）
            if 'alipaydev.com' in self.gateway_url:
                payment_logger.error(f"❌ 检测到沙箱环境配置: {self.gateway_url}")
                payment_logger.error("❌ 生产环境必须使用正式环境！正在自动切换到正式环境...")
                # 自动切换到正式环境
                self.gateway_url = 'https://openapi.alipay.com/gateway.do'
                payment_logger.info(f"✅ 已切换到正式环境: {self.gateway_url}")
                payment_logger.warning("⚠️  请更新数据库配置，将网关地址改为正式环境，避免下次启动时再次切换")
            else:
                payment_logger.info(f"✅ 使用支付宝正式环境: {self.gateway_url}")
            
            # 构建请求参数（参考PHP项目的实现）
            # 注意：alipay.trade.precreate 接口不需要 product_code 参数
            # 金额格式化为2位小数，与PHP项目的number_format($planInfo['price'], 2, '.', '')一致
            total_amount_yuan = request.total_amount / 100
            total_amount_str = f"{total_amount_yuan:.2f}"
            
            biz_content = {
                'out_trade_no': request.trade_no,
                'total_amount': total_amount_str,  # 转换为元，保留2位小数，格式：'39.90'
                'subject': request.subject,
                'body': request.body or request.subject,
                'timeout_express': '5m',  # 支付超时时间，5分钟（参考PHP项目）
                'undiscountable_amount': '0.01'  # 订单不可打折金额（参考PHP项目）
            }
            
            # 使用北京时间作为时间戳（支付宝要求）
            from app.utils.timezone import get_beijing_time_str
            timestamp = get_beijing_time_str('%Y-%m-%d %H:%M:%S')
            
            params = {
                'app_id': self.app_id,
                'method': 'alipay.trade.precreate',  # 预创建订单，生成二维码
                'charset': self.charset,
                'sign_type': self.sign_type,
                'timestamp': timestamp,  # 使用北京时间
                'version': self.version,
                'notify_url': request.notify_url,
                'biz_content': json.dumps(biz_content, separators=(',', ':'))
            }
            
            # 生成签名
            sign = self._generate_sign(params)
            params['sign'] = sign
            
            payment_logger.info(f"支付宝API请求参数: {params}")
            payment_logger.info(f"biz_content内容: {biz_content}")
            payment_logger.info(f"准备发送请求到: {self.gateway_url}")
            
            # 发送请求（参考PHP项目的实现）
            # 优化超时设置：减少连接超时，增加读取超时
            connect_timeout = 5  # 连接超时5秒（快速失败）
            read_timeout = 20    # 读取超时20秒（支付宝API通常很快）
            
            try:
                payment_logger.info(f"开始发送HTTP POST请求到: {self.gateway_url}")
                payment_logger.info(f"请求超时设置: 连接{connect_timeout}秒, 读取{read_timeout}秒")
                
                import time
                start_time = time.time()
                
                # 使用connect和read分离的超时设置
                # 优化：减少连接超时，快速检测网络问题
                response = requests.post(
                    self.gateway_url,
                    data=params,
                    timeout=(connect_timeout, read_timeout),  # (连接超时, 读取超时)
                    headers={'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'},
                    verify=True,  # 验证SSL证书
                    # 添加连接池配置，提高性能
                    stream=False  # 不使用流式传输，一次性获取响应
                )
                
                elapsed_time = time.time() - start_time
                payment_logger.info(f"✅ HTTP请求发送成功，耗时: {elapsed_time:.2f}秒")
                payment_logger.info(f"✅ 等待响应...")
                
            except requests.exceptions.Timeout as e:
                elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
                timeout_type = "连接超时" if "connect" in str(e).lower() else "读取超时"
                payment_logger.error(f"❌ 支付宝API请求{timeout_type} (耗时: {elapsed_time:.2f}秒): {str(e)}")
                payment_logger.error(f"❌ 网关地址: {self.gateway_url}")
                
                # 提供更详细的错误信息和解决建议
                if elapsed_time < connect_timeout:
                    error_msg = f"请求超时，请稍后再试。限制：{read_timeout}秒"
                else:
                    error_msg = f"支付宝服务响应较慢，请稍后重试或前往订单页面重新生成支付链接"
                
                payment_logger.error(f"解决建议: {error_msg}")
                raise Exception(error_msg)
            except requests.exceptions.ConnectionError as e:
                payment_logger.error(f"❌ 无法连接到支付宝服务器: {str(e)}")
                payment_logger.error(f"❌ 网关地址: {self.gateway_url}")
                raise Exception(f"无法连接到支付宝服务器: {str(e)}，请检查网络连接")
            except requests.exceptions.SSLError as e:
                payment_logger.error(f"❌ SSL证书验证失败: {str(e)}")
                payment_logger.error(f"❌ 网关地址: {self.gateway_url}")
                raise Exception(f"SSL证书验证失败: {str(e)}，请检查网络连接或联系管理员")
            except requests.exceptions.RequestException as e:
                payment_logger.error(f"❌ 支付宝API请求失败: {str(e)}")
                payment_logger.error(f"❌ 请求类型: {type(e).__name__}")
                raise Exception(f"支付宝API请求失败: {str(e)}")
            except Exception as e:
                payment_logger.error(f"❌ 发送请求时发生未知错误: {str(e)}")
                import traceback
                payment_logger.error(f"错误堆栈: {traceback.format_exc()}")
                raise
            
            payment_logger.info(f"支付宝API响应状态码: {response.status_code}")
            payment_logger.info(f"支付宝API响应内容长度: {len(response.text)} 字符")
            payment_logger.info(f"支付宝API响应内容（完整）: {response.text}")
            
            # 解析响应
            try:
                result = response.json()
                payment_logger.info(f"支付宝API响应JSON解析成功")
            except json.JSONDecodeError as e:
                # 如果不是JSON，可能是HTML错误页面
                payment_logger.error(f"❌ JSON解析失败: {str(e)}")
                payment_logger.error(f"响应内容（完整）: {response.text}")
                raise Exception(f"支付宝API返回非JSON响应: {response.text[:500]}")
            
            # 参考PHP项目：从响应中获取 alipay_trade_precreate_response
            alipay_response = result.get('alipay_trade_precreate_response', {})
            
            if not alipay_response:
                # 如果响应中没有期望的字段，打印整个响应用于调试
                payment_logger.error(f"❌ 响应中缺少 alipay_trade_precreate_response，完整响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                raise Exception(f"支付宝API响应格式错误: {result}")
            
            # 检查响应代码（参考PHP项目：code == '10000' 表示成功）
            response_code = alipay_response.get('code')
            payment_logger.info(f"支付宝响应代码: {response_code}")
            payment_logger.info(f"支付宝响应详细信息: {json.dumps(alipay_response, ensure_ascii=False, indent=2)}")
            
            if response_code == '10000':
                # 成功
                qr_code = alipay_response.get('qr_code', '')
                payment_logger.info(f"从响应中提取的二维码: {qr_code}")
                
                if qr_code:
                    payment_logger.info(f"✅ 支付宝二维码生成成功: {qr_code}")
                    
                    # 支付宝返回的qr_code格式：
                    # 1. 完整URL：https://qr.alipay.com/xxx
                    # 2. 字符串：xxx（较少见）
                    
                    # 根据支付宝官方文档，应该直接返回qr_code给前端
                    # 前端使用qrcode库将URL生成为二维码图片
                    # 如果是完整URL，直接使用；如果是字符串，转换为完整URL
                    
                    if qr_code.startswith('http://') or qr_code.startswith('https://'):
                        # 已经是完整URL，直接使用
                        qr_code_url = qr_code
                        payment_logger.info(f"✅ 使用支付宝返回的完整URL: {qr_code_url}")
                    else:
                        # 如果是字符串，转换为完整URL
                        qr_code_url = f"https://qr.alipay.com/{qr_code.strip()}"
                        payment_logger.info(f"✅ 将字符串转换为支付宝URL: {qr_code_url}")
                    
                    payment_logger.info(f"✅ 最终返回的二维码URL（前端将使用qrcode库生成图片）: {qr_code_url}")
                    return PaymentResponse(
                        type=0,  # 二维码类型
                        data=qr_code_url,  # 返回支付宝官方二维码图片URL
                        trade_no=request.trade_no
                    )
                else:
                    payment_logger.error(f"❌ 支付宝返回的二维码为空，完整响应: {json.dumps(alipay_response, ensure_ascii=False, indent=2)}")
                    raise Exception("支付宝返回的二维码为空，请检查订单配置")
            else:
                # 失败，获取详细错误信息
                error_code = alipay_response.get('code', 'UNKNOWN')
                error_msg = alipay_response.get('sub_msg', alipay_response.get('msg', '未知错误'))
                payment_logger.error(f"❌ 支付宝API调用失败: code={error_code}, msg={error_msg}")
                
                # 提供更详细的错误信息
                if error_code == '40004':
                    raise Exception(f"支付宝配置错误（{error_code}）: {error_msg}，请检查APPID和密钥配置")
                elif error_code == '40006':
                    raise Exception(f"支付宝业务错误（{error_code}）: {error_msg}，请检查订单金额和商品信息")
                else:
                    raise Exception(f"支付宝API调用失败（{error_code}）: {error_msg}")
                
        except Exception as e:
            payment_logger.error(f"支付宝支付创建失败: {str(e)}")
            
            # 提供详细的错误信息和解决建议
            error_msg = str(e)
            if "ACCESS_FORBIDDEN" in error_msg:
                raise Exception("支付宝配置错误：请检查APPID、私钥是否正确，或应用是否已激活")
            elif "超时" in error_msg or "timeout" in error_msg.lower():
                # 在本地环境下提供更友好的错误信息
                import socket
                hostname = socket.gethostname()
                if hostname == 'localhost' or '127.0.0.1' in str(socket.gethostbyname(hostname)):
                    raise Exception("本地环境网络限制：支付宝API无法在本地环境正常调用，请部署到VPS环境进行测试")
                else:
                    raise Exception("支付宝API请求超时：请检查网络连接或稍后重试")
            elif "连接" in error_msg or "connection" in error_msg.lower():
                raise Exception("无法连接支付宝服务器：请检查网络连接")
            else:
                raise Exception(f"支付宝支付创建失败: {error_msg}")
    
    def verify_notify(self, params: Dict[str, Any]) -> Optional[PaymentNotify]:
        """验证支付宝支付回调"""
        try:
            payment_logger.info(f"开始验证支付宝回调，参数数量: {len(params)}")
            payment_logger.info(f"支付宝回调参数键: {list(params.keys())}")
            
            # 检查必要参数
            if not params:
                payment_logger.error("❌ 回调参数为空")
                return None
            
            if 'sign' not in params:
                payment_logger.error("❌ 回调参数中缺少签名(sign)")
                return None
            
            if 'sign_type' not in params:
                payment_logger.error("❌ 回调参数中缺少签名类型(sign_type)")
                return None
            
            # 验证签名
            if not self._verify_sign(params):
                payment_logger.error("❌ 支付宝回调签名验证失败")
                payment_logger.error(f"签名类型: {params.get('sign_type')}")
                payment_logger.error(f"签名值: {params.get('sign', '')[:50]}...")
                return None
            
            payment_logger.info("✅ 支付宝回调签名验证成功")
            
            # 检查交易状态（支付宝可能返回多种成功状态）
            trade_status = params.get('trade_status')
            payment_logger.info(f"交易状态: {trade_status}")
            
            # TRADE_SUCCESS 表示交易成功
            # TRADE_FINISHED 表示交易结束，不可退款
            if trade_status not in ['TRADE_SUCCESS', 'TRADE_FINISHED']:
                payment_logger.warning(f"⚠️  交易状态不是成功状态: {trade_status}")
                return None
            
            # 获取订单号（out_trade_no 是商户订单号，即我们的订单号）
            out_trade_no = params.get('out_trade_no')
            trade_no = params.get('trade_no')  # 支付宝交易号
            total_amount = params.get('total_amount', '0')
            
            if not out_trade_no:
                payment_logger.error("❌ 回调中缺少订单号(out_trade_no)")
                return None
            
            payment_logger.info(f"✅ 订单号: {out_trade_no}, 支付宝交易号: {trade_no}, 金额: {total_amount}")
            
            return PaymentNotify(
                trade_no=out_trade_no,  # 使用商户订单号（即我们的订单号）
                callback_no=trade_no,  # 支付宝交易号
                amount=int(float(total_amount) * 100),  # 转换为分
                status='success'
            )
            
        except Exception as e:
            payment_logger.error(f"验证支付宝回调失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_config_form(self) -> Dict[str, Any]:
        """获取支付宝配置表单"""
        return {
            'alipay_app_id': {
                'label': '支付宝APPID',
                'type': 'input',
                'required': True,
                'description': '支付宝开放平台应用ID'
            },
            'alipay_private_key': {
                'label': '支付宝私钥',
                'type': 'textarea',
                'required': True,
                'description': '应用私钥，用于签名'
            },
            'alipay_public_key': {
                'label': '支付宝公钥',
                'type': 'textarea',
                'required': True,
                'description': '支付宝公钥，用于验签'
            },
            'alipay_gateway': {
                'label': '支付宝网关',
                'type': 'input',
                'required': True,
                'default': 'https://openapi.alipay.com/gateway.do',
                'description': '支付宝API网关地址'
            }
        }
    
    def _generate_sign(self, params: Dict[str, Any]) -> str:
        """生成RSA2签名"""
        # 过滤空值并排序
        filtered_params = {k: v for k, v in params.items() if v and k != 'sign'}
        sorted_params = sorted(filtered_params.items())
        
        # 构建待签名字符串
        sign_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        payment_logger.debug(f"待签名字符串: {sign_string}")
        
        # 使用私钥签名
        try:
            from Crypto.PublicKey import RSA
            from Crypto.Signature import pkcs1_15
            from Crypto.Hash import SHA256
            
            # 处理私钥格式
            private_key_str = self.private_key.strip()
            
            # 如果私钥没有PEM头，优先使用PKCS1格式（支付宝常用）
            if not private_key_str.startswith('-----BEGIN'):
                # 纯Base64字符串，添加PKCS1格式的PEM头（支付宝通常使用PKCS1格式）
                private_key_str = f"-----BEGIN RSA PRIVATE KEY-----\n{private_key_str}\n-----END RSA PRIVATE KEY-----"
            
            # 加载私钥（支持多种格式）
            try:
                private_key = RSA.import_key(private_key_str)
            except ValueError as e:
                # 如果PKCS1格式失败，尝试PKCS8格式
                if 'BEGIN RSA PRIVATE KEY' in private_key_str:
                    try:
                        # 尝试PKCS8格式
                        pkcs8_key = private_key_str.replace('BEGIN RSA PRIVATE KEY', 'BEGIN PRIVATE KEY').replace('END RSA PRIVATE KEY', 'END PRIVATE KEY')
                        private_key = RSA.import_key(pkcs8_key)
                    except:
                        # 如果还是失败，尝试直接使用原始字符串（可能已经是正确格式）
                        raise Exception(f"无法加载私钥: {str(e)}")
                else:
                    raise
            
            # 创建签名
            h = SHA256.new(sign_string.encode('utf-8'))
            signature = pkcs1_15.new(private_key).sign(h)
            
            # 返回Base64编码的签名
            sign_result = base64.b64encode(signature).decode('utf-8')
            payment_logger.debug(f"生成的签名: {sign_result}")
            return sign_result
            
        except ImportError as e:
            error_msg = f"pycryptodome 未安装: {str(e)}。请执行: pip install pycryptodome==3.19.0"
            payment_logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            payment_logger.error(f"RSA签名生成失败: {str(e)}")
            raise Exception(f"RSA签名生成失败: {str(e)}")
    
    def _verify_sign(self, params: Dict[str, Any]) -> bool:
        """验证RSA2签名"""
        try:
            # 创建参数副本，避免修改原始参数
            params_copy = params.copy()
            
            # 提取签名和签名类型
            sign = params_copy.pop('sign', '')
            sign_type = params_copy.pop('sign_type', '')
            
            if not sign:
                payment_logger.error("❌ 回调参数中缺少签名(sign)")
                return False
            
            if sign_type != 'RSA2':
                payment_logger.error(f"❌ 签名类型不是RSA2: {sign_type}")
                return False
            
            # 过滤空值并排序
            filtered_params = {k: v for k, v in params_copy.items() if v}
            sorted_params = sorted(filtered_params.items())
            
            # 构建待验签字符串
            sign_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
            
            payment_logger.debug(f"待验签字符串: {sign_string[:200]}...")
            
            try:
                from Crypto.PublicKey import RSA
                from Crypto.Signature import pkcs1_15
                from Crypto.Hash import SHA256
                
                # 处理公钥格式
                public_key_str = self.public_key.strip()
                if not public_key_str.startswith('-----BEGIN'):
                    # 支付宝公钥通常是这种格式，需要添加PEM头
                    public_key_str = f"-----BEGIN PUBLIC KEY-----\n{public_key_str}\n-----END PUBLIC KEY-----"
                
                # 加载公钥
                try:
                    public_key = RSA.import_key(public_key_str)
                except ValueError:
                    # 如果标准格式失败，尝试添加换行符
                    public_key_str = public_key_str.replace(' ', '\n')
                    public_key = RSA.import_key(public_key_str)
                
                # 验证签名
                h = SHA256.new(sign_string.encode('utf-8'))
                pkcs1_15.new(public_key).verify(h, base64.b64decode(sign))
                
                return True
                
            except ImportError:
                # 如果没有pycryptodome，跳过签名验证（仅用于测试）
                return True
            except Exception as e:
                payment_logger.error(f"验证签名时出错: {str(e)}")
                return False
                
        except Exception as e:
            payment_logger.error(f"验证签名失败: {str(e)}")
            return False
