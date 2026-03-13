# PAVAgent 部署指南

## 服务器信息

| 项目 | 值 |
|------|------|
| 服务器 IP | `8.134.210.147` |
| 部署目录 | `/opt/PAVAgent` |
| 容器名 | `pavagent` |
| 端口 | `8001` |
| 镜像 | `pavagent:latest`（本地构建） |

## 部署流程

### 1. 同步代码到服务器

```bash
rsync -avz \
  --exclude='.venv' \
  --exclude='node_modules' \
  --exclude='.DS_Store' \
  --exclude='__pycache__' \
  --exclude='results' \
  /Users/cjx/Documents/work/PAVAgent/ \
  root@8.134.210.147:/opt/PAVAgent/
```

### 2. 服务器上重建镜像并重启

```bash
ssh root@8.134.210.147

cd /opt/PAVAgent
docker stop pavagent
docker rm pavagent
docker build -t pavagent:latest .
docker run -d --name pavagent -p 8001:8001 --restart unless-stopped pavagent:latest
```

### 3. 验证

```bash
docker ps | grep pavagent
# 确认 STATUS 为 Up
```

## 一键部署（本地执行）

```bash
# 同步 + 重建 + 重启，一条命令搞定
rsync -avz --exclude='.venv' --exclude='node_modules' --exclude='.DS_Store' --exclude='__pycache__' --exclude='results' \
  /Users/cjx/Documents/work/PAVAgent/ root@8.134.210.147:/opt/PAVAgent/ \
&& ssh root@8.134.210.147 'cd /opt/PAVAgent && docker stop pavagent && docker rm pavagent && docker build -t pavagent:latest . && docker run -d --name pavagent -p 8001:8001 --restart unless-stopped pavagent:latest && docker ps | grep pavagent'
```

## 查看日志

```bash
ssh root@8.134.210.147 'docker logs -f --tail 100 pavagent'
```

## 前端构建（如有前端改动）

部署前需要先在本地构建前端：

```bash
cd frontend
npm run build
# 构建产物在 frontend/dist/，会被 rsync 同步到服务器
```

## 注意事项

- Dockerfile 使用阿里云镜像源（apt + pip），适配国内服务器网络
- `.env` 文件包含 API 密钥，会一并同步，注意保密
- 容器内已安装 `ffmpeg`，用于视频压缩和 GPT 抽帧
- `--restart unless-stopped` 确保服务器重启后容器自动恢复
