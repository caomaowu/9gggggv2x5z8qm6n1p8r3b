#!/bin/bash
# QuantAgent 一键启动脚本

echo "=========================================="
echo "正在启动所有服务..."
echo "=========================================="

# 启动 Nginx
if ! systemctl is-active --quiet nginx; then
    echo "启动 Nginx..."
    systemctl start nginx
    echo "✓ Nginx 已启动"
else
    echo "○ Nginx 已在运行"
fi

# 启动后端服务
if ! systemctl is-active --quiet quant-backend; then
    echo "启动后端服务..."
    systemctl start quant-backend
    echo "✓ 后端服务已启动"
else
    echo "○ 后端服务已在运行"
fi

# 启动 PDF 工具
if ! systemctl is-active --quiet quant-pdf; then
    echo "启动 PDF 自动转换工具..."
    systemctl start quant-pdf
    echo "✓ PDF 工具已启动"
else
    echo "○ PDF 工具已在运行"
fi

echo "=========================================="
echo "所有服务已启动"
echo "=========================================="
echo ""
echo "访问地址: https://fenxi.caomao.xyz/"
echo ""
echo "查看服务状态:"
echo "  systemctl status quant-backend"
echo "  systemctl status quant-pdf"
echo "  systemctl status nginx"
echo ""
echo "查看日志:"
echo "  journalctl -u quant-backend -f"
echo "  journalctl -u quant-pdf -f"
