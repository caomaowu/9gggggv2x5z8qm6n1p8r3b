# VPS 部署问题排查与修复指南

## 1. 核心问题分析

您遇到的 `net::ERR_CONNECTION_REFUSED` (localhost:8000) 和 WebSocket 连接失败，根本原因是**混用了开发模式与生产模式**。

### 错误现象
1.  **API 请求指向 Localhost**：前端代码试图连接用户本地电脑的 8000 端口，而不是 VPS 服务器。
2.  **WebSocket 错误**：Vite 开发服务器 (`npm run dev`) 试图建立热更新 (HMR) 连接，但这在生产环境是不需要的，且会被防火墙拦截。

### 原因总结
*   **构建配置未生效**：前端构建时没有正确加载 `.env.production`，导致 `VITE_API_URL` 默认为 localhost。
*   **运行方式错误**：在 VPS 上运行了 `npm run dev`（开发服务器），而不是使用 Nginx 托管静态文件 (`dist`)。

---

## 2. 正确部署流程（请严格按此执行）

### 第一步：本地构建 (Windows)

在您的开发机上执行，生成纯静态文件。

1.  **清理旧文件**：
    ```powershell
    Remove-Item -Recurse -Force frontend/dist
    ```
2.  **强制生产环境构建**：
    ```powershell
    cd frontend
    npm run build -- --mode production
    ```
    > **原理**：这会强制加载 `.env.production`，将 API 地址设置为 `/api/v1`（相对路径），从而自动适配任何域名。

### 第二步：文件上传

将本地生成的 `frontend/dist` 文件夹上传到 VPS。
*   **源路径**：`frontend/dist`
*   **目标路径**：`/var/www/fenxi.caomao.xyz/html` (示例路径，可自定义)

### 第三步：VPS 服务配置

#### 1. 停止错误服务
在 VPS 上终止所有 `npm run dev` 或 `vite` 进程。

#### 2. Nginx 配置 (关键)
修改或创建 `/etc/nginx/sites-available/fenxi.caomao.xyz`：

```nginx
server {
    listen 80;
    server_name fenxi.caomao.xyz;  # 您的域名

    # 1. 前端静态托管
    location / {
        root /var/www/fenxi.caomao.xyz/html;  # 指向上传的 dist 目录
        index index.html;
        try_files $uri $uri/ /index.html;  # 处理 React 路由
    }

    # 2. 后端 API 反向代理
    location /api/v1/ {
        proxy_pass http://127.0.0.1:8000;  # 转发给本地 Python 服务
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
*完成后重启 Nginx：`sudo systemctl restart nginx`*

#### 3. 后端服务 (Systemd)
确保 Python 后端在后台稳定运行。创建 `/etc/systemd/system/quant-backend.service`：

```ini
[Unit]
Description=QuantAgent Backend
After=network.target

[Service]
User=root
WorkingDirectory=/path/to/your/backend  # 修改为实际路径
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```
*启动命令：*
```bash
sudo systemctl daemon-reload
sudo systemctl start quant-backend
sudo systemctl enable quant-backend
```

---

## 3. 验证清单

1.  打开浏览器访问 `http://fenxi.caomao.xyz`。
2.  打开 F12 -> Network。
3.  点击“分析”按钮。
4.  **检查 Request URL**：应该是 `http://fenxi.caomao.xyz/api/v1/analyze` (正确)，而不是 `localhost:8000`。
