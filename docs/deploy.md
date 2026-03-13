# PAVAgent 部署指南

## 服务器信息

| 项目 | 值 |
|------|------|
| 服务器 IP | `8.134.210.147` |
| 域名 | `www.xintda.cn/pav/` |
| 部署目录 | `/opt/PAVAgent` |
| 容器名 | `pavagent` |
| 端口 | `8001` |
| 镜像 | `pavagent:latest`（服务器本地构建） |
| GitHub | `https://github.com/tda1017/PAVAgent` |

## Nginx 代理配置

服务通过 Nginx 反向代理挂在 `/pav/` 子路径下：

```nginx
location ^~ /pav/ {
    proxy_pass http://127.0.0.1:8001/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_set_header Connection "";
    chunked_transfer_encoding on;
    client_max_body_size 50m;
}
```

> **⚠️ 关键：** Nginx 会把 `/pav/xxx` 转发为 `/xxx` 到后端，因此前端构建时
> 必须设置 `base: '/pav/'`，否则 JS/CSS 资源路径不匹配会导致页面白屏。

## 部署流程

### 1. 前端构建（如有前端改动）

```bash
cd frontend
VITE_BASE=/pav/ npm run build
```

> **⚠️ 踩坑记录：** 必须带 `VITE_BASE=/pav/`，不能直接 `npm run build`。
> 直接构建会生成 `/assets/...` 绝对路径，经 Nginx `/pav/` 代理后浏览器
> 请求 `/assets/xxx` 不会命中 `/pav/` location，导致 JS/CSS 全部 404 白屏。

### 2. 同步代码到服务器

```bash
rsync -avz \
  --exclude='.venv' \
  --exclude='node_modules' \
  --exclude='.DS_Store' \
  --exclude='__pycache__' \
  --exclude='results' \
  --exclude='.git' \
  --exclude='src/video' \
  /Users/cjx/Documents/work/PAVAgent/ \
  root@8.134.210.147:/opt/PAVAgent/
```

> **注意排除项：**
> - `.git` — git 历史不需要上传到服务器
> - `src/video` — 原始视频文件 763MB+，服务器不需要

### 3. 服务器上重建镜像并重启

```bash
ssh root@8.134.210.147 'cd /opt/PAVAgent \
  && docker stop pavagent \
  && docker rm pavagent \
  && docker build -t pavagent:latest . \
  && docker run -d --name pavagent -p 8001:8001 --restart unless-stopped pavagent:latest \
  && docker ps | grep pavagent'
```

### 4. 验证

```bash
# 检查容器状态
ssh root@8.134.210.147 'docker ps | grep pavagent'

# 检查服务是否响应
ssh root@8.134.210.147 'curl -s http://localhost:8001/ | head -5'

# 浏览器访问
# http://www.xintda.cn/pav/
```

## 一键部署（本地执行）

```bash
# 1. 先构建前端（如有改动）
cd /Users/cjx/Documents/work/PAVAgent/frontend && VITE_BASE=/pav/ npm run build && cd ..

# 2. 同步 + 重建 + 重启
rsync -avz \
  --exclude='.venv' --exclude='node_modules' --exclude='.DS_Store' \
  --exclude='__pycache__' --exclude='results' --exclude='.git' --exclude='src/video' \
  /Users/cjx/Documents/work/PAVAgent/ root@8.134.210.147:/opt/PAVAgent/ \
&& ssh root@8.134.210.147 'cd /opt/PAVAgent \
  && docker stop pavagent && docker rm pavagent \
  && docker build -t pavagent:latest . \
  && docker run -d --name pavagent -p 8001:8001 --restart unless-stopped pavagent:latest \
  && docker ps | grep pavagent'
```

## 推送 GitHub

```bash
# tests/data/ 下的图片和视频已在 .gitignore 中排除
# src/video/ 下的大文件也已排除
git add -A && git commit -m "描述" && git push origin main
```

> **⚠️ GitHub 文件大小限制：** 单文件不能超过 100MB。
> `src/video/` 下有 763MB 视频，已通过 `.gitignore` 排除。
> 如果不慎提交了大文件，需要 `git filter-branch` 从历史中清除后才能推送。

## 查看日志

```bash
ssh root@8.134.210.147 'docker logs -f --tail 100 pavagent'
```

## 注意事项

- Dockerfile 使用阿里云镜像源（apt + pip），适配国内服务器网络
- `.env` 文件包含 API 密钥，会一并同步到服务器，注意保密（已在 `.gitignore` 排除，不会推到 GitHub）
- 容器内已安装 `ffmpeg`，用于视频压缩和 GPT 抽帧
- `--restart unless-stopped` 确保服务器重启后容器自动恢复
- Docker 构建依赖层有缓存，只改代码时重建很快（几秒）
