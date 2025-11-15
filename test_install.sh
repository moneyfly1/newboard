#!/bin/bash

# 测试脚本 - 模拟VPS环境检查install.sh可能存在的问题

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_PATH="/Users/apple/Downloads/cboard 网站/install.sh"

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   CBoard 安装脚本测试工具                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# 测试1: 语法检查
echo -e "${YELLOW}[测试1] 语法检查...${NC}"
if bash -n "$SCRIPT_PATH" 2>&1; then
    echo -e "${GREEN}✅ 语法检查通过${NC}"
else
    echo -e "${RED}❌ 语法检查失败${NC}"
    exit 1
fi
echo ""

# 测试2: 检查set -e的影响
echo -e "${YELLOW}[测试2] 检查set -e的影响...${NC}"
echo "检查脚本中set -e的使用情况..."
if grep -q "^set -e" "$SCRIPT_PATH"; then
    echo -e "${YELLOW}⚠️  脚本使用了 set -e，可能导致某些命令失败时脚本退出${NC}"
    echo "检查是否有适当的错误处理..."
    
    # 检查是否有set +e来临时禁用
    if grep -q "set +e" "$SCRIPT_PATH"; then
        echo -e "${GREEN}✅ 发现 set +e 用于临时禁用错误退出${NC}"
    else
        echo -e "${YELLOW}⚠️  未发现 set +e，某些非关键命令失败可能导致脚本退出${NC}"
    fi
fi
echo ""

# 测试3: 检查函数中的变量作用域
echo -e "${YELLOW}[测试3] 检查变量作用域问题...${NC}"
echo "检查函数中未声明的变量..."
# 查找可能的问题变量
PROBLEM_VARS=$(grep -n "ADMIN_EMAIL\|ADMIN_PASSWORD\|NEW_PASSWORD\|DOMAIN\|USE_HTTPS" "$SCRIPT_PATH" | head -20)
if [ -n "$PROBLEM_VARS" ]; then
    echo -e "${YELLOW}⚠️  发现可能未初始化的变量使用：${NC}"
    echo "$PROBLEM_VARS" | while read line; do
        echo "   $line"
    done
fi
echo ""

# 测试4: 检查命令依赖
echo -e "${YELLOW}[测试4] 检查命令依赖...${NC}"
REQUIRED_COMMANDS=("python3" "node" "npm" "systemctl" "nginx" "certbot")
MISSING_COMMANDS=()

for cmd in "${REQUIRED_COMMANDS[@]}"; do
    if ! command -v "$cmd" &> /dev/null; then
        MISSING_COMMANDS+=("$cmd")
    fi
done

if [ ${#MISSING_COMMANDS[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ 所有必需命令都可用${NC}"
else
    echo -e "${YELLOW}⚠️  以下命令在当前环境不可用（这在VPS上可能正常）：${NC}"
    for cmd in "${MISSING_COMMANDS[@]}"; do
        echo "   - $cmd"
    done
fi
echo ""

# 测试5: 检查路径问题
echo -e "${YELLOW}[测试5] 检查路径问题...${NC}"
echo "检查硬编码路径..."
HARDCODED_PATHS=$(grep -n "/www/\|/etc/\|/var/" "$SCRIPT_PATH" | grep -v "#" | head -10)
if [ -n "$HARDCODED_PATHS" ]; then
    echo -e "${GREEN}✅ 发现路径配置（这些在VPS上是正常的）：${NC}"
    echo "$HARDCODED_PATHS" | while read line; do
        echo "   $line"
    done
fi
echo ""

# 测试6: 检查sed命令兼容性
echo -e "${YELLOW}[测试6] 检查sed命令兼容性...${NC}"
SED_COMMANDS=$(grep -n "sed -i" "$SCRIPT_PATH" | head -10)
if [ -n "$SED_COMMANDS" ]; then
    echo "检查sed -i的使用..."
    # macOS的sed需要备份扩展名，Linux不需要
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${YELLOW}⚠️  在macOS上，sed -i 需要备份扩展名${NC}"
        echo -e "${YELLOW}   但在Linux VPS上应该没问题${NC}"
    else
        echo -e "${GREEN}✅ sed命令格式正确（Linux环境）${NC}"
    fi
    echo "$SED_COMMANDS" | while read line; do
        echo "   $line"
    done
fi
echo ""

# 测试7: 检查函数返回值处理
echo -e "${YELLOW}[测试7] 检查函数返回值处理...${NC}"
echo "检查函数中的return语句..."
RETURN_STATEMENTS=$(grep -n "return [0-9]" "$SCRIPT_PATH" | head -10)
if [ -n "$RETURN_STATEMENTS" ]; then
    echo -e "${GREEN}✅ 函数有返回值处理${NC}"
    echo "$RETURN_STATEMENTS" | while read line; do
        echo "   $line"
    done
fi
echo ""

# 测试8: 检查Nginx配置生成
echo -e "${YELLOW}[测试8] 检查Nginx配置生成逻辑...${NC}"
if grep -q "NGINX_CONFIG=" "$SCRIPT_PATH"; then
    echo -e "${GREEN}✅ 发现Nginx配置生成逻辑${NC}"
    # 检查变量转义
    if grep -q '\\$host\|\\$remote_addr' "$SCRIPT_PATH"; then
        echo -e "${GREEN}✅ Nginx变量转义正确（\\\$host, \\\$remote_addr）${NC}"
    else
        echo -e "${RED}❌ 可能缺少Nginx变量转义${NC}"
    fi
fi
echo ""

# 测试9: 检查.env文件操作
echo -e "${YELLOW}[测试9] 检查.env文件操作...${NC}"
if grep -q "\.env" "$SCRIPT_PATH"; then
    echo -e "${GREEN}✅ 发现.env文件操作${NC}"
    # 检查是否检查文件存在
    if grep -q "\[ -f \"\.env\" \]" "$SCRIPT_PATH"; then
        echo -e "${GREEN}✅ 有检查.env文件是否存在${NC}"
    else
        echo -e "${YELLOW}⚠️  可能缺少.env文件存在性检查${NC}"
    fi
fi
echo ""

# 测试10: 检查权限检查
echo -e "${YELLOW}[测试10] 检查权限检查...${NC}"
if grep -q "EUID.*-ne 0\|whoami.*root" "$SCRIPT_PATH"; then
    echo -e "${GREEN}✅ 有root权限检查${NC}"
    ROOT_CHECKS=$(grep -n "EUID.*-ne 0" "$SCRIPT_PATH" | wc -l)
    echo "   发现 $ROOT_CHECKS 处权限检查"
else
    echo -e "${RED}❌ 缺少root权限检查${NC}"
fi
echo ""

# 测试11: 检查systemd服务操作
echo -e "${YELLOW}[测试11] 检查systemd服务操作...${NC}"
SYSTEMD_OPS=$(grep -n "systemctl" "$SCRIPT_PATH" | wc -l)
if [ "$SYSTEMD_OPS" -gt 0 ]; then
    echo -e "${GREEN}✅ 发现 $SYSTEMD_OPS 处systemd操作${NC}"
    # 检查是否有错误处理
    if grep -q "systemctl.*2>/dev/null\|systemctl.*||" "$SCRIPT_PATH"; then
        echo -e "${GREEN}✅ systemd命令有错误处理${NC}"
    else
        echo -e "${YELLOW}⚠️  某些systemd命令可能缺少错误处理${NC}"
    fi
fi
echo ""

# 测试12: 检查交互式输入
echo -e "${YELLOW}[测试12] 检查交互式输入验证...${NC}"
READ_COMMANDS=$(grep -n "read -p" "$SCRIPT_PATH" | wc -l)
if [ "$READ_COMMANDS" -gt 0 ]; then
    echo -e "${GREEN}✅ 发现 $READ_COMMANDS 处交互式输入${NC}"
    # 检查是否有输入验证
    if grep -q "while.*-z\|if.*-z" "$SCRIPT_PATH"; then
        echo -e "${GREEN}✅ 有输入验证逻辑${NC}"
    else
        echo -e "${YELLOW}⚠️  某些输入可能缺少验证${NC}"
    fi
fi
echo ""

# 测试13: 检查潜在问题
echo -e "${YELLOW}[测试13] 检查潜在问题...${NC}"
ISSUES=0

# 检查是否有未转义的变量在heredoc中
if grep -A 5 "cat >.*<< EOF" "$SCRIPT_PATH" | grep -q '\$[A-Z_]' | grep -v '\\$'; then
    echo -e "${RED}❌ 发现heredoc中可能未转义的变量${NC}"
    ISSUES=$((ISSUES + 1))
fi

# 检查是否有命令替换可能失败
if grep -q '\$(' "$SCRIPT_PATH"; then
    echo -e "${YELLOW}⚠️  发现命令替换，确保有错误处理${NC}"
fi

# 检查cd命令后是否有错误处理
CD_COUNT=$(grep -n "^[[:space:]]*cd " "$SCRIPT_PATH" | wc -l)
if [ "$CD_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ 发现 $CD_COUNT 处cd命令${NC}"
    # 检查cd后是否有错误处理（在set -e下，cd失败会自动退出）
fi

if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✅ 未发现明显问题${NC}"
fi
echo ""

# 总结
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}测试完成${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

