#!/bin/bash
# QuantAgent 一键停止脚本

echo "=========================================="
echo "正在停止所有服务..."
echo "=========================================="

# 停止后端服务
if systemctl is-active --quiet quant-backend; then
    echo "停止后端服务..."
    systemctl stop quant-backend
    echo "✓ 后端服务已停止"
else
    echo "○ 后端服务未运行"
fi

# 停止 PDF 工具
if systemctl is-active --quiet quant-pdf; then
    echo "停止 PDF 工具..."
    systemctl stop quant-pdf
    echo "✓ PDF 工具已停止"
else
    echo "○ PDF 工具未运行"
fi

# 停止 Nginx（可选）
read -p "是否停止 Nginx？(y/N): " stop_nginx
if [[ $stop_nginx =~ ^[Yy]$ ]]; then
    if systemctl is-active --quiet nginx; then
        echo "停止 Nginx..."
        systemctl stop nginx
        echo "✓ Nginx 已停止"
    else
        echo "○ Nginx 未运行"
    fi
else
    echo "○ 保持 Nginx 运行"
fi

echo "=========================================="
echo "服务已停止"
echo "=========================================="
echo ""
echo "重新启动请运行: ./start.sh"
