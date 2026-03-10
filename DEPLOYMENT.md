# GitHub 发布指南

## 发布到 GitHub

### 1. 创建 GitHub 仓库

1. 访问 https://github.com/new
2. 仓库名：`ai-sim-platform`
3. 描述：AI 模拟平台 - 基于 LLM 的社会经济模拟系统
4. 设为公开仓库
5. **不要**勾选"Add a README"（我们已经有 README.md）

### 2. 初始化 Git 仓库

```bash
cd C:\Users\21307\Desktop\ai-sim-platform-empty

# 初始化 Git
git init

# 添加所有文件
git add .

# 首次提交
git commit -m "Initial commit: AI 模拟平台核心逻辑"

# 添加远程仓库（替换为你的 GitHub 用户名）
git remote add origin https://github.com/YOUR_USERNAME/ai-sim-platform.git

# 推送到 GitHub
git push -u origin main
```

### 3. 配置环境变量

在 GitHub 仓库设置中添加 Secrets：

1. 进入仓库 → Settings → Secrets and variables → Actions
2. 添加以下 Secrets：
   - `DEEPSEEK_API_KEY`: 你的 DeepSeek API 密钥
   - `ZHIPU_API_KEY`: 你的智谱 AI 密钥
   - `ALIYUN_API_KEY`: 阿里云百炼 API 密钥（可选）

### 4. 添加 GitHub Actions（可选）

创建 `.github/workflows/ci.yml`：

```yaml
name: CI/CD

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      
      - name: Lint with flake8
        run: |
          pip install flake8
          cd backend
          flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      
      - name: Build
        run: |
          cd frontend
          npm run build
```

## 部署到服务器

### 方案 1：VPS 部署（推荐）

#### 准备工作

- 一台 Linux 服务器（Ubuntu 20.04+）
- 域名（可选）
- SSH 访问权限

#### 步骤

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/ai-sim-platform.git
cd ai-sim-platform

# 2. 创建虚拟环境
cd backend
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
nano .env  # 填入你的 API Keys

# 5. 使用 systemd 运行后端
sudo nano /etc/systemd/system/aisim-backend.service
```

服务文件内容：
```ini
[Unit]
Description=AI Simulation Platform Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/ai-sim-platform/backend
Environment="PATH=/home/ubuntu/ai-sim-platform/backend/.venv/bin"
ExecStart=/home/ubuntu/ai-sim-platform/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# 6. 启动服务
sudo systemctl daemon-reload
sudo systemctl enable aisim-backend
sudo systemctl start aisim-backend
sudo systemctl status aisim-backend

# 7. 构建前端
cd ../frontend
npm install
npm run build

# 8. 配置 Nginx
sudo apt install nginx
sudo nano /etc/nginx/sites-available/aisim
```

Nginx 配置：
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    root /home/ubuntu/ai-sim-platform/frontend/dist;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# 9. 启用 Nginx 配置
sudo ln -s /etc/nginx/sites-available/aisim /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 10. 配置防火墙
sudo ufw allow 'Nginx Full'
sudo ufw allow 'OpenSSH'
sudo ufw enable
```

### 方案 2：Docker 部署

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8001:8001"
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - ZHIPU_API_KEY=${ZHIPU_API_KEY}
    volumes:
      - ./backend/data:/app/data
    restart: unless-stopped
  
  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  backend_data:
```

创建 `backend/Dockerfile`：
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

创建 `frontend/Dockerfile`：
```dockerfile
FROM node:18-alpine as build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

运行：
```bash
docker-compose up -d
```

### 方案 3：云平台部署

#### Vercel（前端）+ Railway（后端）

**前端（Vercel）**：
1. 访问 https://vercel.com/new
2. 导入 GitHub 仓库
3. 设置构建命令：`cd frontend && npm install && npm run build`
4. 设置输出目录：`frontend/dist`
5. 添加环境变量：`VITE_API_URL=https://your-backend.railway.app/api`

**后端（Railway）**：
1. 访问 https://railway.app
2. 新建项目 → Deploy from GitHub repo
3. 选择你的仓库
4. 设置环境变量（API Keys）
5. 设置启动命令：`cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## 维护指南

### 更新代码

```bash
# 拉取最新代码
git pull origin main

# 重启服务
sudo systemctl restart aisim-backend
```

### 查看日志

```bash
# 后端日志
sudo journalctl -u aisim-backend -f

# Nginx 日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 备份数据

```bash
# 备份数据目录
tar -czf backup-$(date +%Y%m%d).tar.gz backend/data/

# 上传到云存储（可选）
aws s3 cp backup-$(date +%Y%m%d).tar.gz s3://your-bucket/backups/
```

## 故障排除

### 后端无法启动

```bash
# 检查服务状态
sudo systemctl status aisim-backend

# 查看详细错误
sudo journalctl -u aisim-backend -n 50

# 检查端口占用
sudo lsof -i :8001
```

### 前端无法访问后端

1. 检查 CORS 配置
2. 确认 API URL 正确
3. 查看浏览器控制台错误

### 数据库损坏

```bash
# 恢复备份
tar -xzf backup-20260310.tar.gz

# 或重置数据
cd backend/data
rm *.json
# 重新初始化（启动后端会自动创建）
```

## 安全建议

1. **使用 HTTPS**：通过 Let's Encrypt 获取免费 SSL 证书
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```

2. **限制 API 访问**：添加 API 认证中间件

3. **定期更新依赖**：
   ```bash
   pip list --outdated
   npm outdated
   ```

4. **监控服务**：使用 Uptime Kuma 或 Uptime Robot

## 联系支持

- GitHub Issues: 提交 Bug 和功能请求
- 邮件：your-email@example.com
