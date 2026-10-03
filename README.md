# LimeSlake-01 · 石灰熟化池作业板

厂区熟化池平面图作业基线（Flask + Jinja + Stimulus）。主界面是按厂区排布的池位瓦片，点选后在右侧抽屉登记峰值温度并改状态——不是侧栏双列表 CRUD。

## 技术栈

| 层 | 技术 |
| --- | --- |
| Web | Flask 3 · Blueprints · Flask-Login · Jinja2 · Stimulus CDN |
| 数据 | SQLAlchemy · PostgreSQL 15 |
| 部署 | Docker Compose · Gunicorn |

## 路径与端口

- **项目路径**：`d:\work\document\bytecode\claudeCodePro\LimeSlake\LimeSlake-01`
- **Web**：http://localhost:4730
- **PostgreSQL**：localhost:6130

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 操作工 |

登录页已预填 `admin` / `123456`。启动时 entrypoint 会建表并写入种子数据（示范厂区：**东湾石灰厂**）。

## 主界面

- **熟化池平面图**（`/board/`）：CSS 网格池位瓦片，按状态着色（注水中 / 熟化中 / 已出灰）
- 顶部厂区切换芯片（多厂时切换）
- 点击瓦片 → 右侧抽屉展示最近 `SlakeBatch`，可登记峰值温度并变更池状态
- 主导航不再挂「熟化池列表 / 批次列表」；旧 `/ponds/`、`/batches/` 路由仍保留但不作为作业入口

## 业务规则

熟化池状态不可设为「已出灰」（`drawn`），除非该池**最近一条** `SlakeBatch` 的 `peakTempC` 已记录且 **≥ 60℃**。

规则实现：`app/services/rules.py`

### 批次备注敏感词库

- 顶栏「敏感词库」（`/sensitive-words/`）可增、删、启用、停用敏感词（`SensitiveWord`）
- 批次备注命中任一**启用**词（子串匹配，大小写不敏感）即**整笔拒绝**：不新增批次、不改任何字段，无半插入
- 两条写入链路同口径校验（`app/services/filter.py`）：
  - 批次保存：`/batches/new`、`/batches/<id>/edit`
  - 平面图抽屉：`/board/ponds/<id>/ops`
- 备注相对原值**未改动**时不触发词库——出灰、改池态、登记峰值不受影响（含历史遗留的含词备注原样提交）
- 两个备注输入框有与后端同词库的实时提示；前端只作提示，拦截以后端事务为准
- 并发修改同一备注时，服务端先对批次行加 `FOR UPDATE` 锁、在锁内按库中最新备注判定：一笔命中、一笔合法时，只许合法那笔生效

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\LimeSlake\LimeSlake-01
docker compose up --build
```

浏览器打开 http://localhost:4730

停止：

```bash
docker compose down
```

## 目录结构

```
LimeSlake-01/
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh
├── wsgi.py
├── app/
│   ├── __init__.py          # 工厂 + seed
│   ├── models.py
│   ├── services/rules.py    # 出灰规则
│   ├── services/filter.py   # 备注敏感词校验（两条写入链路共用）
│   └── blueprints/{auth,board,ponds,batches,sensitive_words}
├── templates/
│   └── board/floor.html     # 平面图 + 抽屉
└── static/
```
