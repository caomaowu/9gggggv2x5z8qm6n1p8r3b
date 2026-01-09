#!/bin/bash
# QuantAgent 自动部署脚本 (精简版 - 无备份)
# 用法: ./deploy.sh

set -e

PROJECT_DIR="/root/data/9gggggv2x5z8qm6n1p8r3b"
LOG_FILE="/var/www/quant-deploy/logs/deploy.log"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 错误处理函数
handle_error() {
    log "!!! 部署过程中发生错误 !!!"
    log "请检查上方日志以定位问题。"
    exit 1
}

# 捕获错误
trap handle_error ERR

# 创建日志目录
mkdir -p "$(dirname "$LOG_FILE")"

log "=========================================="
log "开始部署 (快速模式)"
log "=========================================="

cd "$PROJECT_DIR"

# 1. 拉取最新代码
log "拉取最新代码..."
git pull origin main

# 2. 更新后端依赖
if [ -f "requirements.txt" ]; then
    log "检测到 requirements.txt，正在更新后端依赖..."
    # 假设 python 环境已配置好，直接安装
    pip install -r requirements.txt
fi

# 3. 构建前端
log "构建前端（生产模式）..."
cd "$PROJECT_DIR/frontend"

# 优先使用 npm ci 以保证依赖一致性
if [ -f "package-lock.json" ]; then
    npm ci
else
    npm install
fi

npm run build

log "前端构建完成"

# 4. 重启后端服务
if systemctl is-active --quiet quant-backend; then
    log "重启后端服务..."
    systemctl restart quant-backend
else
    log "后端服务未运行，跳过重启"
fi

# 5. 重载 Nginx
log "检查 Nginx 配置..."
if command -v nginx >/dev/null 2>&1; then
    if nginx -t; then
        log "Nginx 配置检查通过，重载 Nginx..."
        systemctl reload nginx
    else
        log "!!! 错误: Nginx 配置检查失败，跳过重载操作，请手动检查 !!!"
        # 即使 Nginx 重载失败，前面的部署（代码+后端）也已经生效，所以不强制退出
    fi
else
    log "未找到 Nginx 命令，跳过重载"
fi

log "=========================================="
log "部署成功！"
log "=========================================="
log "访问地址: https://fenxi.caomao.xyz/"
