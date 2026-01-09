#!/bin/bash
# QuantAgent 自动部署脚本
# 用法: ./deploy.sh

set -e

PROJECT_DIR="/root/data/9gggggv2x5z8qm6n1p8r3b"
BACKUP_DIR="/var/www/quant-deploy/backups"
LOG_FILE="/var/www/quant-deploy/logs/deploy.log"
MAX_BACKUPS=5

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 备份当前版本
backup() {
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="$BACKUP_DIR/$TIMESTAMP"
    mkdir -p "$BACKUP_PATH"

    # 备份前端构建产物
    if [ -d "$PROJECT_DIR/frontend/dist" ]; then
        cp -r "$PROJECT_DIR/frontend/dist" "$BACKUP_PATH/"
        log "备份已创建: $BACKUP_PATH"
    fi

    # 清理旧备份，保留最近 MAX_BACKUPS 个
    if [ -d "$BACKUP_DIR" ]; then
        ls -t "$BACKUP_DIR" 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -I {} rm -rf "$BACKUP_DIR/{}" 2>/dev/null || true
    fi
}

# 回滚到上一个版本
rollback() {
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR" 2>/dev/null | head -1)
    if [ -n "$LATEST_BACKUP" ] && [ -d "$BACKUP_DIR/$LATEST_BACKUP/dist" ]; then
        log "部署失败，正在回滚到 $LATEST_BACKUP"
        rm -rf "$PROJECT_DIR/frontend/dist"
        cp -r "$BACKUP_DIR/$LATEST_BACKUP/dist" "$PROJECT_DIR/frontend/"
        log "回滚完成"
    else
        log "没有可用的备份，无法回滚"
    fi
    exit 1
}

# 捕获错误并回滚
trap rollback ERR

# 创建必要目录
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

log "=========================================="
log "开始部署"
log "=========================================="

cd "$PROJECT_DIR"

# 备份当前版本
log "备份当前版本..."
backup

# 拉取最新代码
log "拉取最新代码..."
git pull origin main

# 构建前端
log "构建前端（生产模式）..."
cd "$PROJECT_DIR/frontend"
npm install
npm run build

log "前端构建完成"
log "构建产物: $PROJECT_DIR/frontend/dist"

# 如果后端服务存在，则重启
if systemctl is-active --quiet quant-backend; then
    log "重启后端服务..."
    systemctl restart quant-backend
else
    log "后端服务未运行，跳过重启"
fi

# 重载 Nginx
log "重载 Nginx..."
systemctl reload nginx

log "=========================================="
log "部署成功！"
log "=========================================="
log "访问地址: https://fenxi.caomao.xyz/"
