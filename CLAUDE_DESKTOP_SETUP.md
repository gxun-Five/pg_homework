# Claude Desktop Configuration Guide

This guide explains how to configure the PostgreSQL MCP Server to work with Claude Desktop.

## Quick Setup

### 1. Locate Configuration File

The Claude Desktop configuration file location depends on your operating system:

**macOS**:
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows**:
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux**:
```
~/.config/Claude/claude_desktop_config.json
```

### 2. Edit Configuration File

Open the configuration file in your text editor and add the PostgreSQL MCP server configuration.

#### Using UV (Recommended)

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
        "main.py"
      ],
      "env": {
        "DATABASE_HOST": "localhost",
        "DATABASE_NAME": "mydb",
        "DATABASE_USER": "postgres",
        "DATABASE_PASSWORD": "your-password",
        "OPENAI_API_KEY": "sk-your-api-key-here"
      }
    }
  }
}
```

#### Using Python Virtualenv

```json
{
  "mcpServers": {
    "postgres": {
      "command": "/absolute/path/to/pg-mcp/.venv/bin/python",
      "args": ["main.py"],
      "cwd": "/absolute/path/to/pg-mcp",
      "env": {
        "DATABASE_HOST": "localhost",
        "DATABASE_NAME": "mydb",
        "DATABASE_USER": "postgres",
        "DATABASE_PASSWORD": "your-password",
        "OPENAI_API_KEY": "sk-your-api-key-here"
      }
    }
  }
}
```

#### Using System Python

```json
{
  "mcpServers": {
    "postgres": {
      "command": "python3",
      "args": ["main.py"],
      "cwd": "/absolute/path/to/pg-mcp",
      "env": {
        "DATABASE_HOST": "localhost",
        "DATABASE_NAME": "mydb",
        "DATABASE_USER": "postgres",
        "DATABASE_PASSWORD": "your-password",
        "OPENAI_API_KEY": "sk-your-api-key-here"
      }
    }
  }
}
```

### 3. Configuration Parameters

#### Required Parameters

These parameters are required for the server to function:

- `DATABASE_HOST`: PostgreSQL server hostname or IP
- `DATABASE_NAME`: Database name to connect to
- `DATABASE_USER`: Database username
- `DATABASE_PASSWORD`: Database password
- `OPENAI_API_KEY`: OpenAI API key for SQL generation

#### Optional Parameters

You can add any of these optional parameters to customize behavior:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": ["--directory", "/path/to/pg-mcp", "run", "python", "main.py"],
      "env": {
        "DATABASE_HOST": "localhost",
        "DATABASE_PORT": "5432",
        "DATABASE_NAME": "mydb",
        "DATABASE_USER": "postgres",
        "DATABASE_PASSWORD": "password",

        "DATABASE_MIN_POOL_SIZE": "5",
        "DATABASE_MAX_POOL_SIZE": "20",
        "DATABASE_COMMAND_TIMEOUT": "30",

        "OPENAI_API_KEY": "sk-...",
        "OPENAI_MODEL": "gpt-5.2-mini",
        "OPENAI_MAX_TOKENS": "32000",
        "OPENAI_TEMPERATURE": "0.0",

        "SECURITY_ALLOW_WRITE_OPERATIONS": "false",
        "SECURITY_MAX_ROWS": "10000",
        "SECURITY_MAX_EXECUTION_TIME": "30",

        "CACHE_ENABLED": "true",
        "CACHE_SCHEMA_TTL": "3600",

        "OBSERVABILITY_LOG_LEVEL": "INFO",
        "OBSERVABILITY_METRICS_ENABLED": "true"
      }
    }
  }
}
```

### 4. Restart Claude Desktop

After editing the configuration:

1. **Quit Claude Desktop** completely (not just close the window)
2. **Restart Claude Desktop**
3. The PostgreSQL MCP server should now be available

## Verification

To verify the server is working:

1. Open Claude Desktop
2. Start a new conversation
3. Try asking a database question like:
   - "How many tables are in my database?"
   - "Show me the structure of the users table"
   - "Count all records in the orders table"

If configured correctly, Claude will use the PostgreSQL MCP server to answer these questions.

## Platform-Specific Examples

### macOS Example

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/yourname/projects/pg-mcp",
        "run",
        "python",
        "main.py"
      ],
      "env": {
        "DATABASE_HOST": "localhost",
        "DATABASE_NAME": "myapp",
        "DATABASE_USER": "myuser",
        "DATABASE_PASSWORD": "mypassword",
        "OPENAI_API_KEY": "sk-proj-..."
      }
    }
  }
}
```

**Configuration File Location**: `~/Library/Application Support/Claude/claude_desktop_config.json`

### Windows Example

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Users\\YourName\\projects\\pg-mcp",
        "run",
        "python",
        "main.py"
      ],
      "env": {
        "DATABASE_HOST": "localhost",
        "DATABASE_NAME": "myapp",
        "DATABASE_USER": "myuser",
        "DATABASE_PASSWORD": "mypassword",
        "OPENAI_API_KEY": "sk-proj-..."
      }
    }
  }
}
```

**Configuration File Location**: `%APPDATA%\Claude\claude_desktop_config.json`

### Linux Example

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": [
        "--directory",
        "/home/yourname/projects/pg-mcp",
        "run",
        "python",
        "main.py"
      ],
      "env": {
        "DATABASE_HOST": "localhost",
        "DATABASE_NAME": "myapp",
        "DATABASE_USER": "myuser",
        "DATABASE_PASSWORD": "mypassword",
        "OPENAI_API_KEY": "sk-proj-..."
      }
    }
  }
}
```

**Configuration File Location**: `~/.config/Claude/claude_desktop_config.json`

## Multiple Databases

You can configure multiple database connections by adding additional MCP server entries:

```json
{
  "mcpServers": {
    "postgres-production": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/pg-mcp",
        "run",
        "python",
        "main.py"
      ],
      "env": {
        "DATABASE_HOST": "prod-db.example.com",
        "DATABASE_NAME": "production",
        "DATABASE_USER": "readonly",
        "DATABASE_PASSWORD": "prod-password",
        "OPENAI_API_KEY": "sk-...",
        "SECURITY_ALLOW_WRITE_OPERATIONS": "false"
      }
    },
    "postgres-development": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/pg-mcp",
        "run",
        "python",
        "main.py"
      ],
      "env": {
        "DATABASE_HOST": "localhost",
        "DATABASE_NAME": "development",
        "DATABASE_USER": "dev",
        "DATABASE_PASSWORD": "dev-password",
        "OPENAI_API_KEY": "sk-...",
        "SECURITY_ALLOW_WRITE_OPERATIONS": "false"
      }
    }
  }
}
```

## Troubleshooting

### Server Not Starting

**Symptoms**: Claude Desktop doesn't show the PostgreSQL tool, or shows errors

**Solutions**:

1. **Check Logs**: Claude Desktop logs server output. Check:
   - macOS: `~/Library/Logs/Claude/mcp*.log`
   - Windows: `%APPDATA%\Claude\logs\mcp*.log`

2. **Verify Paths**: Ensure all paths are absolute, not relative
   - ❌ Wrong: `"--directory", "pg-mcp"`
   - ✅ Correct: `"--directory", "/Users/yourname/projects/pg-mcp"`

3. **Test Manually**: Run the server manually to check for errors:
   ```bash
   cd /path/to/pg-mcp
   uv run python main.py
   ```

### Database Connection Fails

**Symptoms**: Server starts but can't connect to database

**Solutions**:

1. **Test Database Connection**:
   ```bash
   psql -h localhost -U postgres -d mydb
   ```

2. **Check Credentials**: Verify DATABASE_HOST, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD

3. **Check Network**: Ensure PostgreSQL is accessible from Claude Desktop
   - Is PostgreSQL running?
   - Is it listening on the correct port?
   - Are there firewall rules blocking connections?

### OpenAI API Errors

**Symptoms**: Database connects but SQL generation fails

**Solutions**:

1. **Verify API Key**: Check OPENAI_API_KEY is correct and has credits

2. **Test API Key**:
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

3. **Check Model**: Ensure OPENAI_MODEL is valid (e.g., gpt-5.2-mini, gpt-4o)

### Permission Issues

**Symptoms**: Server starts but queries fail with permission errors

**Solutions**:

1. **Check Database Permissions**:
   ```sql
   -- Connect as superuser
   GRANT CONNECT ON DATABASE mydb TO myuser;
   GRANT USAGE ON SCHEMA public TO myuser;
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO myuser;
   ```

2. **Use Read-Only User**: Create dedicated read-only user:
   ```sql
   CREATE USER pg_mcp_readonly WITH PASSWORD 'secure-password';
   GRANT CONNECT ON DATABASE mydb TO pg_mcp_readonly;
   GRANT USAGE ON SCHEMA public TO pg_mcp_readonly;
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO pg_mcp_readonly;
   ```

## Security Best Practices

1. **Read-Only User**: Always use a read-only database user
2. **Secure Passwords**: Use strong, unique passwords
3. **Network Isolation**: Restrict database access by IP/network
4. **Write Operations**: Keep `SECURITY_ALLOW_WRITE_OPERATIONS=false`
5. **Monitor Usage**: Enable metrics and monitor for unusual activity

## Advanced Configuration

### Using .env File

Instead of putting all configuration in `claude_desktop_config.json`, you can use a .env file:

**claude_desktop_config.json**:
```json
{
  "mcpServers": {
    "postgres": {
      "command": "bash",
      "args": [
        "-c",
        "cd /path/to/pg-mcp && source .env && uv run python main.py"
      ]
    }
  }
}
```

**.env** (in pg-mcp directory):
```bash
DATABASE_HOST=localhost
DATABASE_NAME=mydb
DATABASE_USER=postgres
DATABASE_PASSWORD=password
OPENAI_API_KEY=sk-...
```

### Custom Port Configuration

If PostgreSQL is running on a non-standard port:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": ["--directory", "/path/to/pg-mcp", "run", "python", "main.py"],
      "env": {
        "DATABASE_HOST": "localhost",
        "DATABASE_PORT": "5433",
        "DATABASE_NAME": "mydb",
        ...
      }
    }
  }
}
```

### Remote Database Connection

To connect to a remote PostgreSQL server:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": ["--directory", "/path/to/pg-mcp", "run", "python", "main.py"],
      "env": {
        "DATABASE_HOST": "db.example.com",
        "DATABASE_PORT": "5432",
        "DATABASE_NAME": "production",
        "DATABASE_USER": "readonly_user",
        "DATABASE_PASSWORD": "secure_password",
        "OPENAI_API_KEY": "sk-...",
        "SECURITY_ALLOW_WRITE_OPERATIONS": "false"
      }
    }
  }
}
```

## Support

For issues or questions:
- Check the main README.md for detailed documentation
- Review server logs in Claude Desktop log directory
- Test the server manually outside of Claude Desktop
- Verify all paths are absolute
- Ensure environment variables are properly set
