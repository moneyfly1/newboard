import json
import base64
import time
import requests
import logging
from pathlib import Path
from urllib.parse import urlencode
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


class YipayPayment(PaymentInterface):
    """易支付实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.pid = config.get('yipay_pid', '')  # 商户ID
        self.private_key = config.get('yipay_private_key', '')  # 商户私钥
        self.public_key = config.get('yipay_public_key', '')  # 平台公钥
        # 支付类型：alipay（支付宝）或 wxpay（微信支付）
        self.payment_type = config.get('yipay_type', 'alipay')  # 默认为支付宝
        # 网关地址（基础URL），如果包含完整路径则直接使用，否则拼接 /api/pay/create
        gateway_base = config.get('yipay_gateway', 'https://pay.yi-zhifu.cn/').rstrip('/')
        if gateway_base.endswith('/api/pay/create'):
            # 如果已经包含完整路径，直接使用
            self.gateway_url = gateway_base
        else:
            # 如果只是基础URL，拼接接口路径
            self.gateway_url = f"{gateway_base}/api/pay/create"
        self.sign_type = 'RSA'
        
        # 检查pycryptodome是否可用
        try:
            from Crypto.PublicKey import RSA
            from Crypto.Signature import pkcs1_15
            from Crypto.Hash import SHA256
            self._crypto_available = True
            payment_logger.info("✅ pycryptodome 已加载")
        except ImportError:
            self._crypto_available = False
            payment_logger.error("❌ pycryptodome 未安装，请执行: pip install pycryptodome==3.19.0")
    
    def pay(self, request: PaymentRequest) -> PaymentResponse:
        """创建易支付订单"""
        try:
            # 检查pycryptodome是否可用
            if not self._crypto_available:
                error_msg = "pycryptodome 未安装，无法生成RSA签名。请执行: pip install pycryptodome==3.19.0"
                payment_logger.error(error_msg)
                raise Exception(error_msg)
            
            # 检查必要的配置
            if not self.pid or not self.private_key:
                raise Exception("易支付配置不完整：缺少商户ID或私钥")
            
            # 金额转换为元，保留2位小数
            total_amount_yuan = request.total_amount / 100
            total_amount_str = f"{total_amount_yuan:.2f}"
            
            # 获取当前时间戳（10位整数，单位秒）
            timestamp = str(int(time.time()))
            
            # 构建请求参数（V2接口）
            params = {
                'pid': self.pid,
                'method': 'web',  # 接口类型：web（通用网页支付，会根据device自动返回跳转url/二维码等）
                'type': self.payment_type,  # 支付方式：alipay（支付宝）或 wxpay（微信支付）
                'out_trade_no': request.trade_no,
                'notify_url': request.notify_url,
                'return_url': request.return_url,
                'name': request.subject,
                'money': total_amount_str,
                'clientip': self._get_client_ip(request),  # 用户IP地址（必填）
                'device': 'pc',  # 设备类型：pc（电脑浏览器），可选值：pc/mobile/qq/wechat/alipay
                'timestamp': timestamp,  # 当前时间戳（10位整数，单位秒，必填）
                'sign_type': self.sign_type  # 签名类型：RSA（V2接口使用RSA签名）
            }
            
            # 生成签名
            sign = self._generate_sign(params)
            params['sign'] = sign
            
            payment_logger.info(f"易支付API请求参数: {params}")
            payment_logger.info(f"准备发送请求到: {self.gateway_url}")
            
            # 发送请求
            try:
                response = requests.post(
                    self.gateway_url,
                    data=params,
                    timeout=30,
                    headers={'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'},
                    verify=True
                )
                payment_logger.info(f"易支付API响应状态码: {response.status_code}")
                payment_logger.info(f"易支付API响应内容: {response.text}")
            except Exception as e:
                payment_logger.error(f"❌ 易支付API请求失败: {str(e)}")
                raise Exception(f"易支付API请求失败: {str(e)}")
            
            # 解析响应
            try:
                result = response.json()
                payment_logger.info(f"易支付API响应JSON解析成功")
            except json.JSONDecodeError as e:
                payment_logger.error(f"❌ JSON解析失败: {str(e)}")
                raise Exception(f"易支付API返回非JSON响应: {response.text[:500]}")
            
            # 检查响应代码
            code = result.get('code')
            if code == 0:
                # 成功
                pay_type = result.get('pay_type', 'jump')  # 发起支付类型
                pay_info = result.get('pay_info', '')
                trade_no = result.get('trade_no', '')
                
                payment_logger.info(f"✅ 易支付订单创建成功: trade_no={trade_no}, pay_type={pay_type}")
                
                # 根据pay_type返回不同的响应（V2接口支持多种支付类型）
                if pay_type == 'qrcode':
                    # 二维码支付
                    return PaymentResponse(
                        type=0,  # 二维码类型
                        data=pay_info,  # 二维码内容
                        trade_no=request.trade_no
                    )
                elif pay_type in ['jump', 'html', 'urlscheme']:
                    # 跳转支付（jump: 支付跳转url, html: html代码, urlscheme: 小程序跳转url）
                    return PaymentResponse(
                        type=1,  # 跳转URL类型
                        data=pay_info,  # 跳转URL或HTML代码
                        trade_no=request.trade_no
                    )
                elif pay_type in ['jsapi', 'app', 'wxplugin', 'wxapp']:
                    # JSAPI/APP/小程序支付参数（需要前端特殊处理）
                    # 这里也返回跳转类型，由前端根据pay_type和pay_info处理
                    return PaymentResponse(
                        type=1,
                        data=pay_info,  # JSON格式的支付参数
                        trade_no=request.trade_no
                    )
                elif pay_type == 'scan':
                    # 付款码支付成功，返回订单信息
                    return PaymentResponse(
                        type=1,
                        data=pay_info,  # 订单信息（JSON格式）
                        trade_no=request.trade_no
                    )
                else:
                    # 其他类型，默认返回跳转URL
                    return PaymentResponse(
                        type=1,
                        data=pay_info,
                        trade_no=request.trade_no
                    )
            else:
                # 失败
                error_msg = result.get('msg', '未知错误')
                payment_logger.error(f"❌ 易支付API调用失败: code={code}, msg={error_msg}")
                raise Exception(f"易支付API调用失败（{code}）: {error_msg}")
                
        except Exception as e:
            payment_logger.error(f"易支付订单创建失败: {str(e)}")
            raise Exception(f"易支付订单创建失败: {str(e)}")
    
    def verify_notify(self, params: Dict[str, Any]) -> Optional[PaymentNotify]:
        """验证易支付回调"""
        try:
            payment_logger.info(f"易支付回调参数: {params}")
            
            # 验证签名
            if not self._verify_sign(params):
                payment_logger.error("❌ 易支付回调签名验证失败")
                return None
            
            payment_logger.info("✅ 易支付回调签名验证成功")
            
            # 检查交易状态
            trade_status = params.get('trade_status')
            if trade_status != 'TRADE_SUCCESS':
                payment_logger.warning(f"⚠️  交易状态不是成功状态: {trade_status}")
                return None
            
            # 获取订单信息
            out_trade_no = params.get('out_trade_no')  # 商户订单号
            trade_no = params.get('trade_no')  # 平台订单号
            api_trade_no = params.get('api_trade_no', '')  # 接口订单号
            money = params.get('money', '0')  # 金额（元）
            
            if not out_trade_no:
                payment_logger.error("❌ 回调中缺少订单号(out_trade_no)")
                return None
            
            payment_logger.info(f"✅ 订单号: {out_trade_no}, 平台订单号: {trade_no}, 金额: {money}")
            
            return PaymentNotify(
                trade_no=out_trade_no,  # 使用商户订单号
                callback_no=api_trade_no or trade_no,  # 使用接口订单号或平台订单号
                amount=int(float(money) * 100),  # 转换为分
                status='success'
            )
            
        except Exception as e:
            payment_logger.error(f"验证易支付回调失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_config_form(self) -> Dict[str, Any]:
        """获取易支付配置表单（V2接口）"""
        return {
            'yipay_type': {
                'label': '支付类型',
                'type': 'select',
                'required': True,
                'options': [
                    {'value': 'alipay', 'label': '支付宝'},
                    {'value': 'wxpay', 'label': '微信支付'}
                ],
                'default': 'alipay',
                'description': '选择易支付的支付类型：支付宝或微信支付（易支付-支付宝和易支付-微信使用相同的商户ID、私钥、公钥，仅此参数不同）'
            },
            'yipay_pid': {
                'label': '商户ID',
                'type': 'input',
                'required': True,
                'description': '易支付商户ID（在商户后台->个人资料->API信息中查看）'
            },
            'yipay_private_key': {
                'label': '商户私钥',
                'type': 'textarea',
                'required': True,
                'description': '商户私钥（在商户后台->个人资料->API信息中点击"生成商户RSA密钥对"生成，V2接口使用RSA签名）'
            },
            'yipay_public_key': {
                'label': '平台公钥',
                'type': 'textarea',
                'required': True,
                'description': '平台公钥（在商户后台->个人资料->API信息中查看，用于验签）'
            },
            'yipay_gateway': {
                'label': '网关地址',
                'type': 'input',
                'required': True,
                'default': 'https://pay.yi-zhifu.cn/',
                'description': '易支付API网关地址（基础URL，例如：https://pay.yi-zhifu.cn/）。系统会自动拼接V2接口路径 /api/pay/create。如果填写完整URL（包含 /api/pay/create），则直接使用。'
            }
        }
    
    def _generate_sign(self, params: Dict[str, Any]) -> str:
        """生成RSA签名（SHA256WithRSA）"""
        try:
            from Crypto.PublicKey import RSA
            from Crypto.Signature import pkcs1_15
            from Crypto.Hash import SHA256
            
            # 1. 获取所有非空参数，排除sign和sign_type
            filtered_params = {k: v for k, v in params.items() if v and k not in ['sign', 'sign_type']}
            
            # 2. 按照键的ASCII码递增排序
            sorted_params = sorted(filtered_params.items())
            
            # 3. 构建待签名字符串：参数=参数值&参数=参数值
            sign_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
            
            payment_logger.debug(f"待签名字符串: {sign_string}")
            
            # 4. 处理私钥格式
            private_key_str = self.private_key.strip()
            
            # 如果私钥已经是完整的PEM格式，直接使用
            if private_key_str.startswith('-----BEGIN'):
                # 已经是PEM格式，确保换行符正确
                private_key_str = private_key_str.replace('\r\n', '\n').replace('\r', '\n')
            else:
                # 如果没有PEM头，添加PKCS1格式的PEM头
                # 移除所有换行符和空格，然后每64个字符换行
                clean_key = ''.join(private_key_str.split())
                formatted_key = '\n'.join([clean_key[i:i+64] for i in range(0, len(clean_key), 64)])
                private_key_str = f"-----BEGIN RSA PRIVATE KEY-----\n{formatted_key}\n-----END RSA PRIVATE KEY-----"
            
            # 5. 加载私钥（尝试多种格式）
            private_key = None
            last_error = None
            
            # 尝试1: 直接导入（可能是PKCS1或PKCS8）
            try:
                private_key = RSA.import_key(private_key_str)
            except ValueError as e:
                last_error = e
                # 尝试2: 如果是PKCS1格式，尝试转换为PKCS8
                if 'BEGIN RSA PRIVATE KEY' in private_key_str:
                    try:
                        pkcs8_key = private_key_str.replace('BEGIN RSA PRIVATE KEY', 'BEGIN PRIVATE KEY').replace('END RSA PRIVATE KEY', 'END PRIVATE KEY')
                        private_key = RSA.import_key(pkcs8_key)
                    except ValueError as e2:
                        last_error = e2
                        # 尝试3: 如果是PKCS8格式，尝试转换为PKCS1
                        if 'BEGIN PRIVATE KEY' in private_key_str:
                            try:
                                pkcs1_key = private_key_str.replace('BEGIN PRIVATE KEY', 'BEGIN RSA PRIVATE KEY').replace('END PRIVATE KEY', 'END RSA PRIVATE KEY')
                                private_key = RSA.import_key(pkcs1_key)
                            except ValueError as e3:
                                last_error = e3
            
            if private_key is None:
                raise Exception(f"无法加载私钥: {str(last_error)}")
            
            # 6. 使用SHA256WithRSA签名
            h = SHA256.new(sign_string.encode('utf-8'))
            signature = pkcs1_15.new(private_key).sign(h)
            
            # 7. 返回Base64编码的签名
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
        """验证RSA签名（SHA256WithRSA）"""
        try:
            # 获取签名和签名类型
            sign = params.get('sign', '')
            sign_type = params.get('sign_type', 'RSA')
            
            if sign_type != 'RSA':
                payment_logger.warning(f"签名类型不匹配: {sign_type}")
                return False
            
            if not sign:
                payment_logger.error("缺少签名字段")
                return False
            
            try:
                from Crypto.PublicKey import RSA
                from Crypto.Signature import pkcs1_15
                from Crypto.Hash import SHA256
                
                # 1. 获取所有非空参数，排除sign和sign_type
                filtered_params = {k: v for k, v in params.items() if v and k not in ['sign', 'sign_type']}
                
                # 2. 按照键的ASCII码递增排序
                sorted_params = sorted(filtered_params.items())
                
                # 3. 构建待验签字符串
                sign_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
                
                # 4. 处理公钥格式
                public_key_str = self.public_key.strip()
                if not public_key_str.startswith('-----BEGIN'):
                    # 如果没有PEM头，添加PUBLIC KEY格式的PEM头
                    public_key_str = f"-----BEGIN PUBLIC KEY-----\n{public_key_str}\n-----END PUBLIC KEY-----"
                
                # 5. 加载公钥
                try:
                    public_key = RSA.import_key(public_key_str)
                except ValueError:
                    # 如果标准格式失败，尝试添加换行符
                    public_key_str = public_key_str.replace(' ', '\n')
                    public_key = RSA.import_key(public_key_str)
                
                # 6. 验证签名
                h = SHA256.new(sign_string.encode('utf-8'))
                pkcs1_15.new(public_key).verify(h, base64.b64decode(sign))
                
                payment_logger.info("✅ 签名验证成功")
                return True
                
            except ImportError:
                payment_logger.warning("pycryptodome未安装，跳过签名验证")
                return True
            except Exception as e:
                payment_logger.error(f"验证签名时出错: {str(e)}")
                return False
                
        except Exception as e:
            payment_logger.error(f"验证签名失败: {str(e)}")
            return False
    
    def _get_client_ip(self, request: PaymentRequest = None) -> str:
        """获取客户端IP地址（用于支付请求）"""
        # 从配置中获取客户端IP，如果没有则使用默认值
        # 在实际使用时，应该从HTTP请求中获取真实IP
        return self.config.get('clientip', '127.0.0.1')

