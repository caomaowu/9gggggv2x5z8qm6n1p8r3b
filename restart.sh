#!/bin/bash
# QuantAgent 一键重启脚本

echo "=========================================="
echo "正在重启所有服务..."
echo "=========================================="

# 重启后端服务
echo "重启后端服务..."
systemctl restart quant-backend
echo "✓ 后端服务已重启"

# 重启 PDF 工具
echo "重启 PDF 工具..."
systemctl restart quant-pdf
echo "✓ PDF 工具已重启"

# 重启 Nginx
echo "重载 Nginx..."
systemctl reload nginx
echo "✓ Nginx 已重载"

echo "=========================================="
echo "服务已重启"
echo "=========================================="
echo ""
echo "访问地址: https://fenxi.caomao.xyz/"
