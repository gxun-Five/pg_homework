# PostgreSQL MCP Test Databases

This directory contains three comprehensive test databases designed for the PostgreSQL MCP server. Each database represents a different scale and complexity level, allowing you to test the MCP server's performance and capabilities across various scenarios.

## Overview

| Database | Size | Tables | Views | Types | Indexes | Description |
|----------|------|--------|-------|-------|---------|-------------|
| **blog_small** | Small | 7 | 3 | 2 | 12 | Simple blog platform with users, posts, comments, and tags |
| **ecommerce_medium** | Medium | 25 | 6 | 4 | 45+ | E-commerce platform with products, orders, payments, and reviews |
| **saas_crm_large** | Large | 55+ | 10 | 6 | 100+ | Enterprise SaaS CRM with multi-tenant architecture |

## Prerequisites

- PostgreSQL 12.0+ (recommended: 14.0+)
- `psql` command-line tool
- `make` utility (for using Makefile commands)
- Appropriate PostgreSQL user permissions to create databases

## Quick Start

### 1. Create All Databases

```bash
cd w5/pg-mcp/fixtures
make create-all
```

### 2. Verify Creation

```bash
make list          # List all test databases
make test-all      # Show statistics for all databases
make sizes         # Show database sizes
```

### 3. Connect to a Database

```bash
make connect-small    # Connect to blog_small
make connect-medium   # Connect to ecommerce_medium
make connect-large    # Connect to saas_crm_large
```

## Database Details

### 1. Small Database: `blog_small`

**File:** `01_small_db.sql`

A simple blog system with basic features:

#### Schema
- **Tables:** users, posts, comments, categories, tags, post_tags, user_sessions
- **Views:** published_posts, user_stats, popular_tags
- **Types:** user_role, post_status

#### Sample Data
- 8 users (admin, authors, readers)
- 5 categories
- 8 tags
- 10 blog posts (various statuses)
- 17 comments (including nested replies)
- 9 user sessions

#### Use Cases
- Testing basic SELECT queries
- Testing JOIN operations (posts + users + categories)
- Testing aggregations (comment counts, view counts)
- Testing date/time queries (recent posts, user activity)

#### Example Queries

```sql
-- Get all published posts with author info
SELECT * FROM published_posts ORDER BY published_at DESC;

-- Find most active users
SELECT * FROM user_stats ORDER BY post_count DESC;

-- Get posts from last 7 days
SELECT title, published_at, view_count
FROM posts
WHERE published_at >= CURRENT_DATE - INTERVAL '7 days'
  AND status = 'published'
ORDER BY published_at DESC;
```

### 2. Medium Database: `ecommerce_medium`

**File:** `02_medium_db.sql`

A comprehensive e-commerce platform:

#### Schema
- **Tables:** 25 tables including users, products, orders, payments, inventory, reviews, carts, coupons, shipments
- **Views:** 6 views including active_products_inventory, customer_order_summary, daily_sales
- **Types:** user_status, order_status, payment_status, payment_method

#### Sample Data
- 10 users with addresses
- 10 product categories (hierarchical)
- 5 brands
- 15 products with images and variants
- 3 warehouses with inventory
- 7 orders with order items
- Payment and shipment records
- Product reviews and ratings
- Shopping carts
- Discount coupons

#### Use Cases
- Testing complex JOIN queries (orders + items + products + customers)
- Testing inventory management queries
- Testing aggregations (revenue calculations, order statistics)
- Testing hierarchical data (category tree)
- Testing JSONB queries (product attributes, user preferences)

#### Example Queries

```sql
-- Get products with available stock
SELECT * FROM active_products_inventory
WHERE available_stock > 0
ORDER BY total_stock DESC;

-- Calculate total revenue
SELECT SUM(total_amount) AS total_revenue
FROM orders
WHERE status NOT IN ('cancelled', 'refunded');

-- Find top customers by spending
SELECT * FROM customer_order_summary
ORDER BY total_spent DESC
LIMIT 10;

-- Get low stock alerts
SELECT * FROM low_stock_products;
```

### 3. Large Database: `saas_crm_large`

**File:** `03_large_db.sql`

An enterprise-grade SaaS CRM platform with multi-tenant architecture:

#### Schema
- **Tables:** 55+ tables including organizations, users, accounts, contacts, leads, deals, tickets, campaigns, invoices, subscriptions
- **Views:** 10 comprehensive views for analytics and reporting
- **Types:** 6 enum types for various entity states
- **Extensions:** uuid-ossp, pg_trgm (for fuzzy search)

#### Key Features
- Multi-tenant architecture with organization isolation
- Complete CRM functionality (sales, marketing, support)
- Subscription and billing management
- Document management
- Audit logging
- Notification system
- Webhook integrations
- Custom fields (EAV pattern)

#### Sample Data
- 4 organizations (tenants)
- 9 users across organizations
- 6 customer accounts
- 7 contacts
- 4 leads
- 5 deals in sales pipeline
- Multiple invoices and payments
- Support tickets with comments
- Marketing campaigns
- Activities and tasks

#### Use Cases
- Testing multi-tenant queries (organization-scoped data)
- Testing complex business logic (sales pipelines, subscriptions)
- Testing audit trails and change tracking
- Testing full-text search (pg_trgm)
- Testing UUID-based queries
- Testing JSONB for flexible schemas

#### Example Queries

```sql
-- Get sales pipeline overview
SELECT * FROM sales_pipeline_summary
WHERE organization_id = 1;

-- Find accounts with overdue invoices
SELECT * FROM overdue_invoices
WHERE organization_id = 1;

-- Calculate monthly recurring revenue (MRR)
SELECT
    organization_id,
    SUM(sp.price) AS mrr
FROM subscriptions s
JOIN subscription_plans sp ON s.plan_id = sp.id
WHERE s.status = 'active'
GROUP BY organization_id;

-- Get user activity metrics
SELECT * FROM user_activity_summary
WHERE organization_id = 1
ORDER BY total_deal_value DESC;

-- Find all open tickets assigned to a user
SELECT t.ticket_number, t.subject, t.priority, t.status, a.name AS account_name
FROM tickets t
LEFT JOIN accounts a ON t.account_id = a.id
WHERE t.assigned_to = 5
  AND t.status IN ('open', 'in_progress')
ORDER BY t.priority DESC, t.created_at;
```

## Makefile Commands

### Database Creation

```bash
make create-all         # Create all three databases
make create-small       # Create only small database
make create-medium      # Create only medium database
make create-large       # Create only large database
```

### Database Deletion

```bash
make drop-all           # Drop all three databases
make drop-small         # Drop only small database
make drop-medium        # Drop only medium database
make drop-large         # Drop only large database
make clean              # Same as drop-all
```

### Database Rebuild

```bash
make rebuild-all        # Drop and recreate all databases
make rebuild-small      # Rebuild small database
make rebuild-medium     # Rebuild medium database
make rebuild-large      # Rebuild large database
```

### Database Connection

```bash
make connect-small      # Connect to small database with psql
make connect-medium     # Connect to medium database with psql
make connect-large      # Connect to large database with psql
```

### Database Information

```bash
make info               # Show information about all databases
make list               # List existing test databases
make test-all           # Show statistics for all databases
make test-small         # Show statistics for small database
make test-medium        # Show statistics for medium database
make test-large         # Show statistics for large database
make sizes              # Show database sizes
make table-counts       # Show table counts for each database
```

### Utility Commands

```bash
make help               # Show all available commands
make check-connection   # Test PostgreSQL connection
make export-schemas     # Export database schemas (without data)
```

## Environment Variables

You can customize the PostgreSQL connection by setting these environment variables:

```bash
export PGHOST=localhost      # PostgreSQL host (default: localhost)
export PGPORT=5432          # PostgreSQL port (default: 5432)
export PGUSER=postgres      # PostgreSQL user (default: postgres)
export PGPASSWORD=yourpass  # PostgreSQL password

# Then run make commands
make create-all
```

## Testing the MCP Server

### 1. Test with Small Database

Good for initial testing and development:

```bash
# Natural language query examples:
"Show me all published posts from the last month"
"Who are the most active commenters?"
"List all posts in the Technology category"
```

### 2. Test with Medium Database

Good for testing complex queries and performance:

```bash
# Natural language query examples:
"What are the top 10 best-selling products?"
"Show me all orders from the last week"
"Which customers have spent more than $1000?"
"What products are low on stock?"
```

### 3. Test with Large Database

Good for testing scalability and enterprise features:

```bash
# Natural language query examples:
"Show me all deals in the negotiation stage for Acme Corporation"
"What's our monthly recurring revenue by organization?"
"List all open support tickets assigned to David Miller"
"Which campaigns have the highest response rate?"
"Show me overdue invoices for all customers"
```

## Database Schema Exploration

### Viewing Table Structure

```sql
-- List all tables
\dt

-- Describe a specific table
\d table_name

-- List all views
\dv

-- List all types
\dT

-- List all indexes
\di
```

### Exploring Relationships

```sql
-- Find foreign key relationships
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name;
```

## Performance Testing

### Test Query Performance

```sql
-- Enable timing
\timing on

-- Run a complex query and measure time
EXPLAIN ANALYZE
SELECT p.name, SUM(oi.total_price) AS revenue
FROM products p
JOIN order_items oi ON p.id = oi.product_id
GROUP BY p.id, p.name
ORDER BY revenue DESC
LIMIT 10;
```

### Test with Different Data Volumes

The three databases provide different data volumes:
- **Small:** ~100 rows total - fast queries, simple testing
- **Medium:** ~500+ rows total - moderate complexity
- **Large:** ~1000+ rows total - complex queries, performance testing

## Troubleshooting

### Connection Issues

```bash
# Test connection
make check-connection

# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# Verify credentials
psql -h localhost -U postgres -l
```

### Database Already Exists

```bash
# Drop and recreate
make rebuild-all

# Or drop specific database first
make drop-small
make create-small
```

### Permission Denied

Ensure your PostgreSQL user has `CREATEDB` privilege:

```sql
-- As superuser
ALTER USER your_username CREATEDB;
```

### Import Errors

If you encounter errors during import:

```bash
# Check SQL file syntax
psql -h localhost -U postgres --set ON_ERROR_STOP=on -f 01_small_db.sql

# View detailed error messages
psql -h localhost -U postgres -f 01_small_db.sql 2>&1 | grep ERROR
```

## Data Reset

To reset databases to their original state:

```bash
make rebuild-all
```

This will:
1. Drop all three test databases
2. Recreate them from the SQL files
3. Load all sample data

## Customization

### Adding More Sample Data

Edit the SQL files in the `-- SAMPLE DATA` sections:

- `01_small_db.sql` - Lines 235-334
- `02_medium_db.sql` - Lines 595-785
- `03_large_db.sql` - Lines 1185-1505

Then rebuild the database:

```bash
make rebuild-small  # or rebuild-medium, rebuild-large
```

### Modifying Schema

Edit the SQL files in the schema definition sections, then rebuild:

```bash
make rebuild-all
```

## Integration with MCP Server

Configure your MCP server to connect to these databases:

```yaml
databases:
  - name: blog_db
    host: localhost
    port: 5432
    database: blog_small
    user: postgres
    password: ${DB_PASSWORD}

  - name: ecommerce_db
    host: localhost
    port: 5432
    database: ecommerce_medium
    user: postgres
    password: ${DB_PASSWORD}

  - name: crm_db
    host: localhost
    port: 5432
    database: saas_crm_large
    user: postgres
    password: ${DB_PASSWORD}
```

## Best Practices

1. **Start Small:** Begin testing with `blog_small` before moving to larger databases
2. **Use Transactions:** When testing, wrap queries in transactions to avoid data changes
3. **Regular Resets:** Rebuild databases regularly to maintain clean test data
4. **Monitor Performance:** Use `EXPLAIN ANALYZE` to understand query performance
5. **Test Security:** Verify that the MCP server correctly blocks non-SELECT queries

## Contributing

To add new test databases or improve existing ones:

1. Create a new SQL file following the naming convention: `0X_name_db.sql`
2. Update the Makefile with new targets
3. Update this README with database details
4. Test thoroughly before committing

## License

These test databases are part of the PostgreSQL MCP server project and follow the same license.

## Support

For issues or questions:
- Check the main project README
- Review the troubleshooting section above
- Open an issue in the project repository
