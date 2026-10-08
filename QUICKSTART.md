# PostgreSQL MCP 服务器 - 快速入门指南

5 分钟快速启动 PostgreSQL MCP 服务器。

## 前置条件

- Python 3.14+
- PostgreSQL 数据库（运行中且可访问）
- OpenAI API 密钥

## 安装步骤

### 步骤 1: 安装依赖

```bash
# 安装 UV 包管理器（推荐）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆仓库（或下载）
cd /path/to/pg-mcp

# 安装依赖
uv sync
```

### 步骤 2: 配置环境

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
vi .env
```

**最小必需配置**：

```bash
# 数据库配置
DATABASE_HOST=localhost
DATABASE_NAME=your_database
DATABASE_USER=your_user
DATABASE_PASSWORD=your_password

# OpenAI 配置
OPENAI_API_KEY=sk-your-api-key-here
```

### 步骤 3: 测试连接

```bash
# 验证数据库连接
psql -h localhost -U your_user -d your_database

# 如果成功，使用 \q 退出
```

## 运行服务器

### 方式 1: 独立运行

```bash
uv run python -m pg_mcp
```

### 方式 2: 配合 Claude Desktop 使用

**macOS**: 编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: 编辑 `%APPDATA%\Claude\claude_desktop_config.json`

添加以下配置：

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/pg-mcp",
        "run",
        "python",
        "-m",
        "pg_mcp"
      ],
      "env": {
        "DATABASE_HOST": "localhost",
        "DATABASE_NAME": "your_database",
        "DATABASE_USER": "your_user",
        "DATABASE_PASSWORD": "your_password",
        "OPENAI_API_KEY": "sk-your-api-key"
      }
    }
  }
}
```

**重启 Claude Desktop** 并尝试：

```
我的数据库中有多少张表？
```

### 方式 3: Docker

```bash
# 使用 Docker Compose 构建和运行
docker-compose up -d

# 查看日志
docker-compose logs -f pg-mcp
```

## 使用示例

### 简单查询

```
数据库中有多少个用户？
→ SELECT COUNT(*) FROM users

显示所有表名
→ SELECT tablename FROM pg_tables WHERE schemaname = 'public'
```

### 分析查询

```
最活跃的 10 个用户是谁？
→ SELECT user_id, COUNT(*) as activity_count
  FROM user_actions
  GROUP BY user_id
  ORDER BY activity_count DESC
  LIMIT 10
```

### 仅返回 SQL 模式

要求 Claude "仅生成 SQL" 或指定 `return_type="sql"`：

```
生成 SQL 查找上个月的所有订单
返回类型: sql
→ 只返回 SQL，不执行查询
```

## 故障排查

### "Connection refused" 连接被拒绝

- 检查 PostgreSQL 是否运行：`pg_isready`
- 验证 `.env` 中的凭据是否正确
- 检查防火墙规则

### "OpenAI API error" OpenAI API 错误

- 验证 API 密钥是否正确
- 检查 API 密钥是否有余额：https://platform.openai.com/usage
- 检查网络连接

### "Port already in use" 端口已被占用

- 指标端口 (9090) 已被占用
- 在 `.env` 中更改 `OBSERVABILITY_METRICS_PORT`
- 或禁用指标：`OBSERVABILITY_METRICS_ENABLED=false`

## 下一步

- 阅读完整文档：[README.md](README.md)
- 查看配置选项：[.env.example](.env.example)
- 探索示例：[CLAUDE_DESKTOP_SETUP.md](CLAUDE_DESKTOP_SETUP.md)
- 设置监控：参见 README.md 监控章节

## 安全提醒

生产环境使用时：

1. ✅ 使用只读数据库用户
2. ✅ 保持 `SECURITY_ALLOW_WRITE_OPERATIONS=false`
3. ✅ 安全存储凭据（生产环境不要使用 .env 文件）
4. ✅ 启用监控和日志记录
5. ✅ 查看 README.md 中的安全章节

## 支持

- 文档：README.md
- 配置说明：.env.example
- Claude Desktop 集成：CLAUDE_DESKTOP_SETUP.md
- 问题反馈：[GitHub Issues](repository-url/issues)

---

**准备就绪！** 开始用自然语言提问您的数据库吧。
