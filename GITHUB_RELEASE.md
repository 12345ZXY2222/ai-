# 🚀 GitHub 发布指南

## ✅ 已完成的工作

1. **代码已整理完毕** - 位于 `C:\Users\21307\Desktop\ai-sim-platform-empty`
2. **Git 仓库已初始化** - 已完成首次提交（203 个文件）
3. **数据已清理** - 所有用户数据、聊天记录、论文文件已移除
4. **示例已保留** - 包含 2 个示例模拟（辩论模拟 + 牛鞭效应）

## 📋 下一步操作

### 1. 创建 GitHub 仓库

访问 https://github.com/new

- **Repository name**: `ai-sim-platform`
- **Description**: `AI 模拟平台 - 基于 LLM 的社会经济模拟系统 | AI Simulation Platform for Socio-Economic Research`
- **Public** (公开仓库)
- **不要**勾选 "Add a README file"

点击 **Create repository**

### 2. 推送到 GitHub

在 GitHub 仓库页面复制你的仓库 URL，然后执行：

```bash
cd C:\Users\21307\Desktop\ai-sim-platform-empty

# 替换为你的 GitHub 用户名
git remote add origin https://github.com/YOUR_USERNAME/ai-sim-platform.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

### 3. 配置环境变量（重要！）

在 GitHub 仓库设置中添加 Secrets：

1. 进入仓库 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. 添加以下 Secrets：

| Name | Value |
|------|-------|
| `DEEPSEEK_API_KEY` | 你的 DeepSeek API 密钥 |
| `ZHIPU_API_KEY` | 你的智谱 AI 密钥 |
| `ALIYUN_API_KEY` | 阿里云百炼 API 密钥（可选） |

### 4. 更新 README.md

编辑 `README.md` 文件，将以下内容替换为你的信息：

```markdown
## 联系方式

- GitHub: [@YOUR_USERNAME](https://github.com/YOUR_USERNAME)
- Email: your-email@example.com
```

## 📦 仓库内容

### 核心功能
- ✅ **Agent 管理系统** - 支持多模型接入，AI 自动生成适配器代码
- ✅ **Simulation 设计器** - 可视化设计模拟流程
- ✅ **World 地图系统** - 可运行的虚拟世界，支持自动漫游
- ✅ **论文复现功能** - AI 辅助论文分析和代码生成

### 预置示例
- 📝 **AI 安全辩论模拟** - 三方辩论流程示例
- 📊 **牛鞭效应模拟** - 供应链库存管理示例

### 技术栈
- **后端**: Python 3.10+, FastAPI, Pydantic
- **前端**: React 18, TypeScript, Vite, Ant Design
- **AI 集成**: DeepSeek, 智谱 AI, 阿里云百炼

## 🔧 快速开始

### 本地开发

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/ai-sim-platform.git
cd ai-sim-platform

# 后端
cd backend
pip install -r requirements.txt
cp .env.example .env  # 编辑填入 API Keys
uvicorn app.main:app --reload --port 8001

# 前端（新终端）
cd frontend
npm install
npm run dev
```

### 生产部署

详见 [`DEPLOYMENT.md`](DEPLOYMENT.md) 文档，支持：
- VPS 部署（systemd + Nginx）
- Docker 部署
- 云平台部署（Vercel + Railway）

## 📄 许可证

MIT License

---

**创建时间**: 2026 年 3 月 10 日  
**版本**: 1.0.0 (精简发布版)
