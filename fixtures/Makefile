# ============================================================================
# PostgreSQL MCP Test Databases Makefile
# ============================================================================
# This Makefile manages three test databases for the PostgreSQL MCP server:
# - blog_small: Small database with 7 tables (blog system)
# - ecommerce_medium: Medium database with 25 tables (e-commerce platform)
# - saas_crm_large: Large database with 55+ tables (enterprise CRM)
# ============================================================================

# PostgreSQL connection settings
PGHOST ?= localhost
PGPORT ?= 5432
PGUSER ?= postgres
PGPASSWORD ?=
PSQL = psql -h $(PGHOST) -p $(PGPORT) -U $(PGUSER)

# Database names
DB_SMALL = blog_small
DB_MEDIUM = ecommerce_medium
DB_LARGE = saas_crm_large

# SQL files
SQL_SMALL = 01_small_db.sql
SQL_MEDIUM = 02_medium_db.sql
SQL_LARGE = 03_large_db.sql

# Colors for output
COLOR_RESET = \033[0m
COLOR_BOLD = \033[1m
COLOR_GREEN = \033[32m
COLOR_YELLOW = \033[33m
COLOR_BLUE = \033[34m
COLOR_RED = \033[31m

.PHONY: all help clean create-all drop-all rebuild-all info \
        create-small create-medium create-large \
        drop-small drop-medium drop-large \
        rebuild-small rebuild-medium rebuild-large \
        connect-small connect-medium connect-large \
        test-small test-medium test-large

# ============================================================================
# Default target
# ============================================================================

all: create-all

# ============================================================================
# Help
# ============================================================================

help:
	@echo "$(COLOR_BOLD)PostgreSQL MCP Test Databases$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_BOLD)Available targets:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make create-all$(COLOR_RESET)      - Create all three test databases"
	@echo "  $(COLOR_GREEN)make drop-all$(COLOR_RESET)        - Drop all three test databases"
	@echo "  $(COLOR_GREEN)make rebuild-all$(COLOR_RESET)     - Drop and recreate all databases"
	@echo "  $(COLOR_GREEN)make clean$(COLOR_RESET)           - Same as drop-all"
	@echo ""
	@echo "$(COLOR_BOLD)Individual database targets:$(COLOR_RESET)"
	@echo "  $(COLOR_BLUE)Small database (blog_small):$(COLOR_RESET)"
	@echo "    make create-small      - Create small database"
	@echo "    make drop-small        - Drop small database"
	@echo "    make rebuild-small     - Rebuild small database"
	@echo "    make connect-small     - Connect to small database"
	@echo "    make test-small        - Show small database stats"
	@echo ""
	@echo "  $(COLOR_BLUE)Medium database (ecommerce_medium):$(COLOR_RESET)"
	@echo "    make create-medium     - Create medium database"
	@echo "    make drop-medium       - Drop medium database"
	@echo "    make rebuild-medium    - Rebuild medium database"
	@echo "    make connect-medium    - Connect to medium database"
	@echo "    make test-medium       - Show medium database stats"
	@echo ""
	@echo "  $(COLOR_BLUE)Large database (saas_crm_large):$(COLOR_RESET)"
	@echo "    make create-large      - Create large database"
	@echo "    make drop-large        - Drop large database"
	@echo "    make rebuild-large     - Rebuild large database"
	@echo "    make connect-large     - Connect to large database"
	@echo "    make test-large        - Show large database stats"
	@echo ""
	@echo "$(COLOR_BOLD)Information:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make info$(COLOR_RESET)            - Show database information"
	@echo "  $(COLOR_GREEN)make list$(COLOR_RESET)            - List all test databases"
	@echo ""
	@echo "$(COLOR_BOLD)Environment variables:$(COLOR_RESET)"
	@echo "  PGHOST     - PostgreSQL host (default: localhost)"
	@echo "  PGPORT     - PostgreSQL port (default: 5432)"
	@echo "  PGUSER     - PostgreSQL user (default: postgres)"
	@echo "  PGPASSWORD - PostgreSQL password"

# ============================================================================
# Create databases
# ============================================================================

create-all: create-small create-medium create-large
	@echo "$(COLOR_BOLD)$(COLOR_GREEN)✓ All test databases created successfully!$(COLOR_RESET)"

create-small:
	@echo "$(COLOR_BOLD)Creating small database ($(DB_SMALL))...$(COLOR_RESET)"
	@$(PSQL) -f $(SQL_SMALL) 2>&1 | grep -v "^DROP DATABASE" | grep -v "^CREATE DATABASE" || true
	@echo "$(COLOR_GREEN)✓ Small database created$(COLOR_RESET)"

create-medium:
	@echo "$(COLOR_BOLD)Creating medium database ($(DB_MEDIUM))...$(COLOR_RESET)"
	@$(PSQL) -f $(SQL_MEDIUM) 2>&1 | grep -v "^DROP DATABASE" | grep -v "^CREATE DATABASE" || true
	@echo "$(COLOR_GREEN)✓ Medium database created$(COLOR_RESET)"

create-large:
	@echo "$(COLOR_BOLD)Creating large database ($(DB_LARGE))...$(COLOR_RESET)"
	@$(PSQL) -f $(SQL_LARGE) 2>&1 | grep -v "^DROP DATABASE" | grep -v "^CREATE DATABASE" || true
	@echo "$(COLOR_GREEN)✓ Large database created$(COLOR_RESET)"

# ============================================================================
# Drop databases
# ============================================================================

drop-all: drop-small drop-medium drop-large
	@echo "$(COLOR_BOLD)$(COLOR_RED)✓ All test databases dropped$(COLOR_RESET)"

drop-small:
	@echo "$(COLOR_YELLOW)Dropping small database ($(DB_SMALL))...$(COLOR_RESET)"
	@$(PSQL) -c "DROP DATABASE IF EXISTS $(DB_SMALL);" 2>&1 | grep -v "^DROP DATABASE" || true
	@echo "$(COLOR_RED)✓ Small database dropped$(COLOR_RESET)"

drop-medium:
	@echo "$(COLOR_YELLOW)Dropping medium database ($(DB_MEDIUM))...$(COLOR_RESET)"
	@$(PSQL) -c "DROP DATABASE IF EXISTS $(DB_MEDIUM);" 2>&1 | grep -v "^DROP DATABASE" || true
	@echo "$(COLOR_RED)✓ Medium database dropped$(COLOR_RESET)"

drop-large:
	@echo "$(COLOR_YELLOW)Dropping large database ($(DB_LARGE))...$(COLOR_RESET)"
	@$(PSQL) -c "DROP DATABASE IF EXISTS $(DB_LARGE);" 2>&1 | grep -v "^DROP DATABASE" || true
	@echo "$(COLOR_RED)✓ Large database dropped$(COLOR_RESET)"

clean: drop-all

# ============================================================================
# Rebuild databases
# ============================================================================

rebuild-all: drop-all create-all
	@echo "$(COLOR_BOLD)$(COLOR_GREEN)✓ All test databases rebuilt successfully!$(COLOR_RESET)"

rebuild-small: drop-small create-small
	@echo "$(COLOR_GREEN)✓ Small database rebuilt$(COLOR_RESET)"

rebuild-medium: drop-medium create-medium
	@echo "$(COLOR_GREEN)✓ Medium database rebuilt$(COLOR_RESET)"

rebuild-large: drop-large create-large
	@echo "$(COLOR_GREEN)✓ Large database rebuilt$(COLOR_RESET)"

# ============================================================================
# Database information
# ============================================================================

info:
	@echo "$(COLOR_BOLD)PostgreSQL MCP Test Databases Information$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_BOLD)Connection Settings:$(COLOR_RESET)"
	@echo "  Host: $(PGHOST)"
	@echo "  Port: $(PGPORT)"
	@echo "  User: $(PGUSER)"
	@echo ""
	@echo "$(COLOR_BOLD)Test Databases:$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_BLUE)1. Small Database ($(DB_SMALL))$(COLOR_RESET)"
	@echo "   Description: Simple blog system"
	@echo "   Tables: 7 | Views: 3 | Types: 2"
	@echo "   File: $(SQL_SMALL)"
	@echo ""
	@echo "$(COLOR_BLUE)2. Medium Database ($(DB_MEDIUM))$(COLOR_RESET)"
	@echo "   Description: E-commerce platform"
	@echo "   Tables: 25 | Views: 6 | Types: 4"
	@echo "   File: $(SQL_MEDIUM)"
	@echo ""
	@echo "$(COLOR_BLUE)3. Large Database ($(DB_LARGE))$(COLOR_RESET)"
	@echo "   Description: Enterprise SaaS CRM"
	@echo "   Tables: 55+ | Views: 10 | Types: 6"
	@echo "   File: $(SQL_LARGE)"

list:
	@echo "$(COLOR_BOLD)Existing test databases:$(COLOR_RESET)"
	@$(PSQL) -t -c "SELECT datname FROM pg_database WHERE datname IN ('$(DB_SMALL)', '$(DB_MEDIUM)', '$(DB_LARGE)') ORDER BY datname;" | sed 's/^/ - /'

# ============================================================================
# Connect to databases
# ============================================================================

connect-small:
	@echo "$(COLOR_BOLD)Connecting to $(DB_SMALL)...$(COLOR_RESET)"
	@$(PSQL) -d $(DB_SMALL)

connect-medium:
	@echo "$(COLOR_BOLD)Connecting to $(DB_MEDIUM)...$(COLOR_RESET)"
	@$(PSQL) -d $(DB_MEDIUM)

connect-large:
	@echo "$(COLOR_BOLD)Connecting to $(DB_LARGE)...$(COLOR_RESET)"
	@$(PSQL) -d $(DB_LARGE)

# ============================================================================
# Test/Verify databases
# ============================================================================

test-small:
	@echo "$(COLOR_BOLD)Small Database ($(DB_SMALL)) Statistics:$(COLOR_RESET)"
	@$(PSQL) -d $(DB_SMALL) -c "\
		SELECT \
			(SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE') AS tables, \
			(SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'public') AS views, \
			(SELECT COUNT(*) FROM pg_type WHERE typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public') AND typtype = 'e') AS enum_types, \
			(SELECT SUM(n_live_tup) FROM pg_stat_user_tables) AS total_rows;"

test-medium:
	@echo "$(COLOR_BOLD)Medium Database ($(DB_MEDIUM)) Statistics:$(COLOR_RESET)"
	@$(PSQL) -d $(DB_MEDIUM) -c "\
		SELECT \
			(SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE') AS tables, \
			(SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'public') AS views, \
			(SELECT COUNT(*) FROM pg_type WHERE typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public') AND typtype = 'e') AS enum_types, \
			(SELECT SUM(n_live_tup) FROM pg_stat_user_tables) AS total_rows;"

test-large:
	@echo "$(COLOR_BOLD)Large Database ($(DB_LARGE)) Statistics:$(COLOR_RESET)"
	@$(PSQL) -d $(DB_LARGE) -c "\
		SELECT \
			(SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE') AS tables, \
			(SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'public') AS views, \
			(SELECT COUNT(*) FROM pg_type WHERE typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public') AND typtype = 'e') AS enum_types, \
			(SELECT SUM(n_live_tup) FROM pg_stat_user_tables) AS total_rows;"

test-all: test-small test-medium test-large

# ============================================================================
# Utility targets
# ============================================================================

# Check PostgreSQL connection
check-connection:
	@echo "$(COLOR_BOLD)Testing PostgreSQL connection...$(COLOR_RESET)"
	@$(PSQL) -c "SELECT version();" > /dev/null 2>&1 && \
		echo "$(COLOR_GREEN)✓ Connection successful$(COLOR_RESET)" || \
		(echo "$(COLOR_RED)✗ Connection failed$(COLOR_RESET)" && exit 1)

# Show table counts for each database
table-counts:
	@echo "$(COLOR_BOLD)Table counts in test databases:$(COLOR_RESET)"
	@for db in $(DB_SMALL) $(DB_MEDIUM) $(DB_LARGE); do \
		echo -n "  $$db: "; \
		$(PSQL) -d $$db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" 2>/dev/null | xargs || echo "not found"; \
	done

# Show database sizes
sizes:
	@echo "$(COLOR_BOLD)Database sizes:$(COLOR_RESET)"
	@$(PSQL) -c "\
		SELECT \
			datname AS database, \
			pg_size_pretty(pg_database_size(datname)) AS size \
		FROM pg_database \
		WHERE datname IN ('$(DB_SMALL)', '$(DB_MEDIUM)', '$(DB_LARGE)') \
		ORDER BY pg_database_size(datname) DESC;" 2>/dev/null || echo "Databases not found"

# Export database schemas (without data)
export-schemas:
	@echo "$(COLOR_BOLD)Exporting database schemas...$(COLOR_RESET)"
	@mkdir -p exports
	@pg_dump -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) --schema-only $(DB_SMALL) > exports/$(DB_SMALL)_schema.sql 2>/dev/null && \
		echo "$(COLOR_GREEN)✓ Exported $(DB_SMALL) schema$(COLOR_RESET)"
	@pg_dump -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) --schema-only $(DB_MEDIUM) > exports/$(DB_MEDIUM)_schema.sql 2>/dev/null && \
		echo "$(COLOR_GREEN)✓ Exported $(DB_MEDIUM) schema$(COLOR_RESET)"
	@pg_dump -h $(PGHOST) -p $(PGPORT) -U $(PGUSER) --schema-only $(DB_LARGE) > exports/$(DB_LARGE)_schema.sql 2>/dev/null && \
		echo "$(COLOR_GREEN)✓ Exported $(DB_LARGE) schema$(COLOR_RESET)"
