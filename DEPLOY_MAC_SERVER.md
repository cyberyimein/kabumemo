# 使用 Apple Container 部署 Kabumemo

本项目在 macOS 上使用 Apple Container CLI 部署。`Dockerfile.server` 采用标准 OCI/Dockerfile 格式，Apple Container 可以直接构建；不需要 Docker Desktop、Docker Engine、Compose 或 Colima。

## 一、准备运行时和数据目录

```bash
container system start
mkdir -p /Users/mithridates/data/kabumemo
```

正式数据保存在宿主机 `/Users/mithridates/data/kabumemo`，并挂载为容器内 `/data`。重建镜像或删除容器不会删除该目录。

## 二、构建镜像

在仓库根目录执行：

```bash
container build \
  --tag local/kabumemo-backend:latest \
  --file Dockerfile.server \
  .
```

构建过程会完成前端编译和后端依赖安装，最终生成同时提供 UI 与 API 的单一 OCI 镜像。

## 三、首次部署或升级

先停止并删除旧容器，再从新镜像启动：

```bash
container stop kabumemo-backend 2>/dev/null || true
container delete kabumemo-backend 2>/dev/null || true

container run --detach \
  --name kabumemo-backend \
  --cpus 4 \
  --memory 1G \
  --publish 0.0.0.0:9527:8000 \
  --env KABUCOUNT_DATA_DIR=/data \
  --env KABUMEMO_DIST_DIR=/frontend_dist \
  --volume /Users/mithridates/data/kabumemo:/data \
  local/kabumemo-backend:latest
```

访问地址：

- 本机：`http://localhost:9527/`
- 局域网：`http://服务器IP:9527/`
- 健康检查：`http://服务器IP:9527/api/health`

## 四、检查部署

```bash
container list --all
container logs kabumemo-backend
curl http://127.0.0.1:9527/api/health
```

健康接口应返回 `{"status":"ok"}`。

## 五、数据维护

查看数据同步状态：

```bash
container exec kabumemo-backend \
  python /app/backend/scripts/check_data_sync.py --data-dir /data
```

需要从 JSON 强制重建 SQLite 时：

```bash
container exec kabumemo-backend \
  python /app/backend/scripts/import_json_to_sqlite.py --data-dir /data --force
```

## 六、备份与恢复

备份前建议先停止容器，确保 JSON 与 SQLite 快照一致：

```bash
container stop kabumemo-backend
tar czf /Users/mithridates/data/kabumemo-backup-$(date +%Y%m%d-%H%M%S).tar.gz \
  -C /Users/mithridates/data kabumemo
container start kabumemo-backend
```

恢复时停止容器、还原 `/Users/mithridates/data/kabumemo`，再启动容器即可。

## 七、常用命令

```bash
container start kabumemo-backend
container stop kabumemo-backend
container logs kabumemo-backend
container inspect kabumemo-backend
container list --all
```

仓库中的 `docker-compose.yml` 仅保留作跨平台兼容文件，不是本机正式部署入口。
