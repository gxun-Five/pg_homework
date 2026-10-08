# CLAUDE.md - PostgreSQL MCP Server 开发指南

## 项目概述

PostgreSQL MCP Server 是一个基于 Model Context Protocol 的智能数据库查询服务，允许用户通过自然语言与 PostgreSQL 数据库交互。详细需求见 `specs/w5/0001-pg-mcp-prd.md`。

## 技术栈

- **Python**: 3.12+
- **MCP SDK**: FastMCP
- **PostgreSQL Driver**: asyncpg (异步) 或 psycopg3
- **SQL Parser**: pglast (PostgreSQL 专用解析器)
- **LLM**: OpenAI SDK (gpt-5.2-mini)
- **配置管理**: pydantic-settings
- **测试**: pytest + pytest-asyncio + pytest-cov

## 核心开发原则

### Python Best Practices

```python
# 1. 使用类型注解 (Type Hints)
from typing import Protocol, TypeVar, Generic
from collections.abc import Sequence, Mapping

def query_database(sql: str, params: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    ...

# 2. 使用 dataclasses 或 Pydantic 定义数据模型
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=10000)
    database: str | None = None
    return_type: Literal["sql", "result"] = "result"

# 3. 使用 Enum 而非魔法字符串
from enum import StrEnum, auto

class ErrorCode(StrEnum):
    SUCCESS = auto()
    SECURITY_VIOLATION = auto()
    SQL_PARSE_ERROR = auto()

# 4. 使用 contextlib 管理资源
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db_connection():
    conn = await asyncpg.connect(...)
    try:
        yield conn
    finally:
        await conn.close()

# 5. 使用 __slots__ 优化内存 (高频对象)
class SchemaColumn:
    __slots__ = ("name", "type", "nullable", "default", "comment")
    ...
```

### SOLID 原则应用

#### Single Responsibility (单一职责)

```
src/
├── core/
│   ├── schema_cache.py      # 仅负责 Schema 缓存管理
│   ├── sql_generator.py     # 仅负责 SQL 生成 (LLM 调用)
│   ├── sql_validator.py     # 仅负责 SQL 安全验证
│   ├── sql_executor.py      # 仅负责 SQL 执行
│   └── result_validator.py  # 仅负责结果验证
├── models/
│   ├── schema.py            # Schema 相关数据模型
│   ├── query.py             # 查询请求/响应模型
│   └── errors.py            # 错误定义
├── services/
│   └── query_service.py     # 编排各个组件的服务层
└── config/
    └── settings.py          # 配置管理
```

#### Open/Closed (开闭原则)

```python
# 使用 Protocol 定义接口，便于扩展
from typing import Protocol

class SQLGenerator(Protocol):
    async def generate(self, question: str, schema: DatabaseSchema) -> str:
        """Generate SQL from natural language."""
        ...

class OpenAISQLGenerator:
    """OpenAI 实现"""
    async def generate(self, question: str, schema: DatabaseSchema) -> str:
        ...

class AnthropicSQLGenerator:
    """未来可扩展: Anthropic 实现"""
    async def generate(self, question: str, schema: DatabaseSchema) -> str:
        ...
```

#### Liskov Substitution (里氏替换)

```python
# 子类必须完全兼容父类接口
class BaseValidator(ABC):
    @abstractmethod
    def validate(self, sql: str) -> ValidationResult:
        ...

class ReadOnlyValidator(BaseValidator):
    def validate(self, sql: str) -> ValidationResult:
        # 返回类型和行为与父类一致
        ...
```

#### Interface Segregation (接口隔离)

```python
# 细粒度接口，客户端只依赖需要的方法
class Readable(Protocol):
    async def read(self, key: str) -> Any: ...

class Writable(Protocol):
    async def write(self, key: str, value: Any) -> None: ...

class SchemaCache(Readable):  # 只读缓存只实现 Readable
    async def read(self, key: str) -> Any: ...
```

#### Dependency Inversion (依赖反转)

```python
# 高层模块依赖抽象，而非具体实现
class QueryService:
    def __init__(
        self,
        generator: SQLGenerator,      # 依赖抽象
        validator: SQLValidator,       # 依赖抽象
        executor: SQLExecutor,         # 依赖抽象
    ):
        self._generator = generator
        self._validator = validator
        self._executor = executor
```

### DRY 原则

```python
# 提取公共逻辑到工具函数
# utils/sql.py
def sanitize_identifier(name: str) -> str:
    """安全处理 SQL 标识符"""
    ...

# 使用装饰器消除重复的横切关注点
from functools import wraps

def with_timeout(seconds: float):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with asyncio.timeout(seconds):
                return await func(*args, **kwargs)
        return wrapper
    return decorator

# 使用泛型减少重复代码
T = TypeVar("T")

class Result(Generic[T]):
    def __init__(self, value: T | None, error: ErrorCode | None):
        self.value = value
        self.error = error
```

## 代码质量要求

### 必须遵循

1. **类型完整**: 所有公开 API 必须有完整类型注解
2. **文档字符串**: 公开类和函数必须有 docstring (Google style)
3. **错误处理**: 使用自定义异常，不要裸露 `except`
4. **日志脱敏**: 绝不在日志中记录密钥、密码、PII 数据
5. **资源管理**: 使用 context manager 管理连接、文件等资源

### 代码风格

```bash
# 使用 ruff 进行 lint 和格式化
ruff check --fix .
ruff format .

# pyproject.toml 配置
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = [
    "E", "F", "W",   # pyflakes, pycodestyle
    "I",              # isort
    "B", "C4",        # bugbear, comprehensions
    "UP",             # pyupgrade
    "SIM",            # simplify
    "TCH",            # type-checking imports
    "RUF",            # ruff-specific
    "S",              # security (bandit)
    "ASYNC",          # async best practices
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # allow assert in tests
```

### 安全编码

```python
# 1. 永远不要拼接 SQL
# BAD
sql = f"SELECT * FROM {table_name}"

# GOOD - 使用参数化查询
sql = "SELECT * FROM $1"
await conn.fetch(sql, table_name)

# 2. 验证所有外部输入
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=10000)

    @field_validator("question")
    @classmethod
    def sanitize_question(cls, v: str) -> str:
        # 移除潜在的 prompt injection
        return sanitize_user_input(v)

# 3. 使用 pglast 解析和验证 SQL
from pglast import parse_sql, Node

def validate_sql(sql: str) -> bool:
    try:
        stmts = parse_sql(sql)
        for stmt in stmts:
            if not isinstance(stmt.stmt, SelectStmt):
                raise SecurityViolationError("Only SELECT allowed")
        return True
    except ParseError:
        raise SQLParseError("Invalid SQL syntax")
```

## 测试要求

### 测试结构

```
tests/
├── conftest.py              # 共享 fixtures
├── unit/
│   ├── test_sql_validator.py
│   ├── test_sql_generator.py
│   └── test_schema_cache.py
├── integration/
│   ├── test_query_flow.py
│   └── test_db_connection.py
└── security/
    ├── test_sql_injection.py
    └── test_blocked_operations.py
```

### 测试覆盖率要求

- **总体覆盖率**: >= 80%
- **核心安全模块**: >= 95% (sql_validator, security checks)
- **分支覆盖**: 必须覆盖所有安全相关分支

### 测试示例

```python
# tests/unit/test_sql_validator.py
import pytest
from src.core.sql_validator import SQLValidator, SecurityViolationError

class TestSQLValidator:
    @pytest.fixture
    def validator(self) -> SQLValidator:
        return SQLValidator(blocked_functions=["pg_sleep"])

    @pytest.mark.parametrize("sql", [
        "SELECT * FROM users",
        "SELECT COUNT(*) FROM orders WHERE date > '2024-01-01'",
        "WITH cte AS (SELECT 1) SELECT * FROM cte",
    ])
    def test_valid_select_queries(self, validator: SQLValidator, sql: str):
        assert validator.validate(sql).is_valid

    @pytest.mark.parametrize("sql,expected_error", [
        ("DELETE FROM users", "DELETE statement not allowed"),
        ("DROP TABLE users", "DROP statement not allowed"),
        ("SELECT pg_sleep(100)", "Function pg_sleep is blocked"),
        ("INSERT INTO logs VALUES (1)", "INSERT statement not allowed"),
    ])
    def test_blocked_operations(
        self, validator: SQLValidator, sql: str, expected_error: str
    ):
        with pytest.raises(SecurityViolationError, match=expected_error):
            validator.validate(sql)

    def test_sql_injection_attempts(self, validator: SQLValidator):
        # 测试各种 SQL 注入变体
        injection_attempts = [
            "SELECT * FROM users; DROP TABLE users;--",
            "SELECT * FROM users WHERE id = 1 OR 1=1",
            "SELECT * FROM users UNION SELECT * FROM passwords",
        ]
        for sql in injection_attempts:
            result = validator.validate(sql)
            assert not result.allows_data_modification

# tests/integration/test_query_flow.py
@pytest.mark.asyncio
async def test_end_to_end_query(
    query_service: QueryService,
    mock_openai: MockOpenAI,
    test_db: AsyncConnection,
):
    # Arrange
    mock_openai.set_response("SELECT COUNT(*) FROM users")

    # Act
    result = await query_service.query(
        question="How many users are there?",
        return_type="result",
    )

    # Assert
    assert result.success
    assert result.data.row_count == 1
    assert result.confidence >= 70
```

### 测试运行

```bash
# 运行所有测试
pytest

# 运行并生成覆盖率报告
pytest --cov=src --cov-report=html --cov-fail-under=80

# 只运行安全测试
pytest tests/security/ -v

# 运行集成测试 (需要 PostgreSQL)
pytest tests/integration/ --db-url="postgresql://test@localhost/test"
```

## 性能要求

### 异步优先

```python
# 使用 asyncpg 进行异步数据库操作
import asyncpg

async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=5,
        max_size=20,
        command_timeout=30,
    )

# 并发执行独立操作
async def load_all_schemas(databases: list[str]) -> dict[str, Schema]:
    tasks = [load_schema(db) for db in databases]
    results = await asyncio.gather(*tasks)
    return dict(zip(databases, results))
```

### 缓存策略

```python
from functools import lru_cache
from cachetools import TTLCache

# 内存缓存 Schema
class SchemaCache:
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: TTLCache[str, DatabaseSchema] = TTLCache(
            maxsize=100, ttl=ttl_seconds
        )

    async def get_schema(self, database: str) -> DatabaseSchema:
        if database not in self._cache:
            self._cache[database] = await self._load_schema(database)
        return self._cache[database]
```

### 连接池管理

```python
# 使用连接池避免频繁建立连接
class DatabaseManager:
    def __init__(self):
        self._pools: dict[str, asyncpg.Pool] = {}

    async def get_connection(self, database: str) -> asyncpg.Connection:
        if database not in self._pools:
            self._pools[database] = await asyncpg.create_pool(...)
        return await self._pools[database].acquire()
```

## 项目配置

### pyproject.toml 完整配置

```toml
[project]
name = "pg-mcp"
version = "0.1.0"
description = "PostgreSQL MCP Server for natural language queries"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=2.14.1",
    "asyncpg>=0.29.0",
    "pglast>=6.0",
    "openai>=1.0.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "structlog>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
    "ruff>=0.4",
    "mypy>=1.10",
    "pre-commit>=3.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --tb=short"

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.coverage.run]
source = ["src"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "@abstractmethod",
]
```

## 常用命令

```bash
# 安装依赖
uv sync

# 运行服务
uv run python main.py

# 运行测试
uv run pytest

# 类型检查
uv run mypy src

# Lint 和格式化
uv run ruff check --fix .
uv run ruff format .

# 生成覆盖率报告
uv run pytest --cov=src --cov-report=html
```

## 错误处理模式

```python
# 定义项目异常层次
class PgMcpError(Exception):
    """Base exception for pg-mcp"""
    def __init__(self, message: str, code: ErrorCode):
        super().__init__(message)
        self.code = code

class SecurityViolationError(PgMcpError):
    def __init__(self, message: str):
        super().__init__(message, ErrorCode.SECURITY_VIOLATION)

class SQLParseError(PgMcpError):
    def __init__(self, message: str):
        super().__init__(message, ErrorCode.SQL_PARSE_ERROR)

# 统一错误处理
async def handle_query(request: QueryRequest) -> QueryResponse:
    try:
        return await _process_query(request)
    except SecurityViolationError as e:
        return QueryResponse(
            success=False,
            error=ErrorInfo(code=e.code, message=str(e)),
        )
    except PgMcpError as e:
        logger.warning("Query failed", error=str(e), code=e.code)
        return QueryResponse(success=False, error=ErrorInfo(code=e.code, message=str(e)))
    except Exception:
        logger.exception("Unexpected error")
        return QueryResponse(
            success=False,
            error=ErrorInfo(code=ErrorCode.INTERNAL_ERROR, message="Internal error"),
        )
```

## Git 提交规范

```
feat: 新功能
fix: Bug 修复
docs: 文档更新
refactor: 重构 (不改变功能)
test: 测试相关
perf: 性能优化
security: 安全相关修复
```

## 检查清单

在提交 PR 前确保:

- [ ] 所有测试通过 (`pytest`)
- [ ] 类型检查通过 (`mypy src`)
- [ ] Lint 检查通过 (`ruff check .`)
- [ ] 安全测试覆盖新增代码路径
- [ ] 敏感信息未暴露在日志中
- [ ] 文档已更新 (如适用)
