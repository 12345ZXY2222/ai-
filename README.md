# AI 模拟平台 - 精简版

这是一个清理后的 AI 模拟平台备份，仅包含前后端核心逻辑和两个示例模拟，如果部署不了或者因为版本问题，可以下载下来让openclaw或者copilot等完成修复

## 项目结构

```
ai-sim-platform-empty/
├── backend/              # Python/FastAPI 后端
│   ├── app/
│   │   ├── api/         # API 端点
│   │   ├── core/        # 核心逻辑（Adapter/Generator）
│   │   ├── models/      # 数据模型
│   │   └── main.py      # FastAPI 入口
│   └── requirements.txt # Python 依赖
│
├── frontend/             # React/Vite 前端
│   ├── src/
│   │   ├── pages/       # 页面组件
│   │   ├── api/         # API 客户端
│   │   └── App.tsx      # 主应用
│   └── package.json     # Node 依赖
│
├── scripts/              # 研究/实验脚本
└── README.md             # 本文档
```

## 快速开始

### 1. 后端启动

```bash
cd backend

# 创建虚拟环境（可选）
python -m venv .venv
.venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
copy .env.example .env
# 编辑 .env 填入你的 API Key

# 启动服务
uvicorn app.main:app --reload --port 8001
```

### 2. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 `http://localhost:5173` 查看前端界面。

## 功能模块

### 1. Agent 管理
- 创建/编辑/删除 AI Agent
- 支持 DeepSeek、智谱 AI 及自定义模型
- **核心特性**：AI 自动生成适配器代码

### 2. Simulation 设计器
- 可视化设计模拟流程
- 支持 Agent/Code/Loop/Dialogue 四种步骤
- AI 辅助生成模拟流程

### 3. World 地图系统
- 绘制地图（墙/语义区域）
- 定义 POI（兴趣点）
- 身份系统 + 日程驱动行为
- 自动漫游 + 相遇对话

## 示例模拟

平台预置了两个示例模拟：

### 示例 1：辩论模拟
- **场景**：AI 安全辩论
- **角色**：Proponent（支持方）、Opponent（反对方）、Judge（裁判）
- **流程**：开场陈述 → 3 轮辩论 → 裁判判定

### 示例 2：牛鞭效应模拟
- **场景**：供应链库存管理
- **角色**：零售商、批发商、分销商、制造商
- **学习点**：需求信息放大效应

## API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/agents` | 获取所有 Agent |
| POST | `/api/agents` | 创建新 Agent |
| POST | `/api/generate-adapter` | 生成适配器代码 |
| POST | `/api/chat` | 与 Agent 对话 |
| POST | `/api/simulations` | 创建 Simulation |
| POST | `/api/simulations/generate` | AI 生成 Simulation |
| POST | `/api/simulations/run` | 执行 Simulation |

## 部署说明

### 生产环境部署

#### 后端（systemd 服务）

```bash
# 创建服务文件
sudo nano /etc/systemd/system/aisim-backend.service
```

内容：
```ini
[Unit]
Description=AI Simulation Platform Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/aisim/backend
Environment="PATH=/var/www/aisim/backend/.venv/bin"
ExecStart=/var/www/aisim/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
Restart=always

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl enable aisim-backend
sudo systemctl start aisim-backend
```

#### 前端（Nginx）

```bash
# 构建前端
cd frontend
npm run build

# 复制到 Nginx 目录
sudo rsync -a dist/ /var/www/aisim/frontend/
```

Nginx 配置：
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    root /var/www/aisim/frontend;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Docker 部署（可选）

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
  
  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
```

## 环境变量

创建 `.env` 文件：
```env
# AI API Keys
DEEPSEEK_API_KEY=your_deepseek_key
ZHIPU_API_KEY=your_zhipu_key

# 可选配置
DEBUG=true
LOG_LEVEL=info
```

## 开发指南

### 添加新的 Agent 提供商

1. 在 `backend/app/core/adapter.py` 中添加新的适配函数
2. 或使用平台的"Generate Adapter"功能自动生成

### 添加新的 Simulation 步骤类型

1. 在 `backend/app/models/simulation.py` 中扩展 `SimulationStep` 模型
2. 在 `backend/app/api/endpoints.py` 中实现执行逻辑
3. 在前端 `src/pages/SimulationDesigner.tsx` 中添加 UI 支持

## 技术栈

- **后端**：Python 3.10+、FastAPI、Pydantic、Uvicorn
- **前端**：React 18、TypeScript、Vite、Ant Design
- **AI 集成**：阿里云百炼、DeepSeek、智谱 AI

## 许可证

MIT License

## 联系方式

- GitHub Issues: 提交问题和建议
- 文档：查看项目 Wiki
