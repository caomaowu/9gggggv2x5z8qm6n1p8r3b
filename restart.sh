#!/bin/bash
# QuantAgent 一键重启脚本

echo "=========================================="
echo "正在重启所有服务..."
echo "=========================================="

# 重启后端服务
echo "重启后端服务..."
systemctl restart quant-backend
echo "✓ 后端服务已重启"

# PDF 自动转换工具已停用：缺少 Playwright，且此前陷入自动重启循环。
# 如需恢复，请先安装依赖并重新启用 quant-pdf.service。

# 重启 Nginx
echo "重载 Nginx..."
systemctl reload nginx
echo "✓ Nginx 已重载"

echo "=========================================="
echo "服务已重启"
echo "=========================================="
echo ""
echo "访问地址: https://fenxi.caomaowu.lol/"
