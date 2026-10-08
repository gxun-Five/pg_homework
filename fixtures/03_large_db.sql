-- ============================================================================
-- Large Database: Enterprise SaaS CRM Platform
-- ============================================================================
-- Description: Multi-tenant CRM with sales, marketing, support, and billing
-- Tables: 55+ | Views: 10 | Types: 6 | Indexes: 100+
-- ============================================================================

DROP DATABASE IF EXISTS saas_crm_large;
CREATE DATABASE saas_crm_large;
\c saas_crm_large;

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- ============================================================================
-- CUSTOM TYPES
-- ============================================================================

CREATE TYPE user_role AS ENUM ('owner', 'admin', 'manager', 'sales_rep', 'support_agent', 'viewer');
CREATE TYPE account_status AS ENUM ('trial', 'active', 'suspended', 'cancelled', 'expired');
CREATE TYPE subscription_status AS ENUM ('active', 'cancelled', 'past_due', 'unpaid', 'trialing');
CREATE TYPE lead_status AS ENUM ('new', 'contacted', 'qualified', 'unqualified', 'lost');
CREATE TYPE deal_stage AS ENUM ('prospecting', 'qualification', 'proposal', 'negotiation', 'closed_won', 'closed_lost');
CREATE TYPE ticket_status AS ENUM ('open', 'pending', 'in_progress', 'waiting_customer', 'resolved', 'closed');
CREATE TYPE ticket_priority AS ENUM ('low', 'medium', 'high', 'urgent');
CREATE TYPE task_priority AS ENUM ('low', 'medium', 'high', 'urgent');
CREATE TYPE invoice_status AS ENUM ('draft', 'sent', 'paid', 'overdue', 'void', 'refunded');
CREATE TYPE payment_status AS ENUM ('pending', 'completed', 'failed', 'refunded');
CREATE TYPE activity_type AS ENUM ('call', 'email', 'meeting', 'note', 'task');
CREATE TYPE campaign_status AS ENUM ('draft', 'scheduled', 'active', 'paused', 'completed');

-- ============================================================================
-- MULTI-TENANT FOUNDATION
-- ============================================================================

CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    domain VARCHAR(255),
    account_status account_status DEFAULT 'trial',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trial_ends_at TIMESTAMP,
    suspended_at TIMESTAMP,
    cancelled_at TIMESTAMP
);

COMMENT ON TABLE organizations IS 'Tenant organizations in multi-tenant system';

CREATE TABLE organization_settings (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER UNIQUE NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    timezone VARCHAR(100) DEFAULT 'UTC',
    currency VARCHAR(3) DEFAULT 'USD',
    date_format VARCHAR(50) DEFAULT 'YYYY-MM-DD',
    time_format VARCHAR(50) DEFAULT 'HH:mm:ss',
    language VARCHAR(10) DEFAULT 'en',
    business_hours JSONB,
    features JSONB DEFAULT '{}',
    limits JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE organization_settings IS 'Organization-specific configuration';

-- ============================================================================
-- USERS & AUTHENTICATION
-- ============================================================================

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    avatar_url VARCHAR(500),
    role user_role DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    two_factor_enabled BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, email)
);

COMMENT ON TABLE users IS 'Users with organization membership';

CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE user_sessions IS 'Active user sessions';

CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    manager_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, name)
);

COMMENT ON TABLE teams IS 'Teams within organizations';

CREATE TABLE team_members (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, user_id)
);

COMMENT ON TABLE team_members IS 'Team membership';

-- ============================================================================
-- CRM - CONTACTS & ACCOUNTS
-- ============================================================================

CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    website VARCHAR(255),
    industry VARCHAR(100),
    employee_count INTEGER,
    annual_revenue DECIMAL(15, 2),
    description TEXT,
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    parent_account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    billing_street VARCHAR(255),
    billing_city VARCHAR(100),
    billing_state VARCHAR(100),
    billing_postal_code VARCHAR(20),
    billing_country VARCHAR(100),
    shipping_street VARCHAR(255),
    shipping_city VARCHAR(100),
    shipping_state VARCHAR(100),
    shipping_postal_code VARCHAR(20),
    shipping_country VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE accounts IS 'Customer and prospect companies';

CREATE TABLE contacts (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    mobile VARCHAR(20),
    title VARCHAR(100),
    department VARCHAR(100),
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    mailing_street VARCHAR(255),
    mailing_city VARCHAR(100),
    mailing_state VARCHAR(100),
    mailing_postal_code VARCHAR(20),
    mailing_country VARCHAR(100),
    description TEXT,
    linkedin_url VARCHAR(500),
    twitter_handle VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE contacts IS 'Individual contact persons';

CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    company VARCHAR(255),
    title VARCHAR(100),
    status lead_status DEFAULT 'new',
    source VARCHAR(100),
    industry VARCHAR(100),
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    description TEXT,
    converted_at TIMESTAMP,
    converted_account_id INTEGER REFERENCES accounts(id),
    converted_contact_id INTEGER REFERENCES contacts(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE leads IS 'Sales leads before conversion';

-- ============================================================================
-- CRM - OPPORTUNITIES & PIPELINE
-- ============================================================================

CREATE TABLE pipelines (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, name)
);

COMMENT ON TABLE pipelines IS 'Sales pipelines';

CREATE TABLE pipeline_stages (
    id SERIAL PRIMARY KEY,
    pipeline_id INTEGER NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    stage_type deal_stage NOT NULL,
    probability INTEGER DEFAULT 0 CHECK (probability >= 0 AND probability <= 100),
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE pipeline_stages IS 'Stages within sales pipelines';

CREATE TABLE deals (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    pipeline_id INTEGER NOT NULL REFERENCES pipelines(id) ON DELETE RESTRICT,
    stage_id INTEGER NOT NULL REFERENCES pipeline_stages(id) ON DELETE RESTRICT,
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    amount DECIMAL(15, 2),
    probability INTEGER DEFAULT 0 CHECK (probability >= 0 AND probability <= 100),
    expected_close_date DATE,
    actual_close_date DATE,
    description TEXT,
    next_step TEXT,
    lead_source VARCHAR(100),
    competitors TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE deals IS 'Sales opportunities';

-- ============================================================================
-- PRODUCTS & PRICING
-- ============================================================================

CREATE TABLE product_categories (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES product_categories(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, name)
);

COMMENT ON TABLE product_categories IS 'Product categorization';

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(100),
    category_id INTEGER REFERENCES product_categories(id),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_recurring BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, sku)
);

COMMENT ON TABLE products IS 'Products and services catalog';

CREATE TABLE price_books (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, name)
);

COMMENT ON TABLE price_books IS 'Price books for different markets/segments';

CREATE TABLE price_book_entries (
    id SERIAL PRIMARY KEY,
    price_book_id INTEGER NOT NULL REFERENCES price_books(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    unit_price DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(price_book_id, product_id)
);

COMMENT ON TABLE price_book_entries IS 'Product prices in price books';

CREATE TABLE deal_products (
    id SERIAL PRIMARY KEY,
    deal_id INTEGER NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER DEFAULT 1,
    unit_price DECIMAL(10, 2) NOT NULL,
    discount_percent DECIMAL(5, 2) DEFAULT 0,
    total_price DECIMAL(15, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE deal_products IS 'Products associated with deals';

-- ============================================================================
-- SUBSCRIPTIONS & BILLING
-- ============================================================================

CREATE TABLE subscription_plans (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    billing_interval VARCHAR(20) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    trial_days INTEGER DEFAULT 0,
    features JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE subscription_plans IS 'Recurring subscription plans';

CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    plan_id INTEGER NOT NULL REFERENCES subscription_plans(id),
    status subscription_status DEFAULT 'trialing',
    current_period_start DATE NOT NULL,
    current_period_end DATE NOT NULL,
    trial_end DATE,
    cancel_at DATE,
    cancelled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE subscriptions IS 'Customer subscriptions';

CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    subscription_id INTEGER REFERENCES subscriptions(id),
    status invoice_status DEFAULT 'draft',
    subtotal DECIMAL(15, 2) NOT NULL,
    tax_amount DECIMAL(15, 2) DEFAULT 0,
    discount_amount DECIMAL(15, 2) DEFAULT 0,
    total_amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL,
    paid_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE invoices IS 'Customer invoices';

CREATE TABLE invoice_line_items (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id),
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    total_price DECIMAL(15, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE invoice_line_items IS 'Invoice line items';

CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    payment_method VARCHAR(50),
    status payment_status DEFAULT 'pending',
    transaction_id VARCHAR(255),
    payment_gateway VARCHAR(100),
    payment_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE payments IS 'Payment transactions';

-- ============================================================================
-- SUPPORT TICKETS
-- ============================================================================

CREATE TABLE ticket_categories (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES ticket_categories(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, name)
);

COMMENT ON TABLE ticket_categories IS 'Support ticket categories';

CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    ticket_number VARCHAR(50) UNIQUE NOT NULL,
    account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    category_id INTEGER REFERENCES ticket_categories(id),
    subject VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    status ticket_status DEFAULT 'open',
    priority ticket_priority DEFAULT 'medium',
    assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
    team_id INTEGER REFERENCES teams(id),
    source VARCHAR(50),
    created_by INTEGER REFERENCES users(id),
    resolved_at TIMESTAMP,
    closed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE tickets IS 'Customer support tickets';

CREATE TABLE ticket_comments (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    comment TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE ticket_comments IS 'Ticket conversation threads';

CREATE TABLE ticket_attachments (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    comment_id INTEGER REFERENCES ticket_comments(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    uploaded_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE ticket_attachments IS 'Files attached to tickets';

-- ============================================================================
-- ACTIVITIES & TASKS
-- ============================================================================

CREATE TABLE activities (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    activity_type activity_type NOT NULL,
    subject VARCHAR(255) NOT NULL,
    description TEXT,
    related_to_type VARCHAR(50),
    related_to_id INTEGER,
    account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    deal_id INTEGER REFERENCES deals(id) ON DELETE SET NULL,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scheduled_at TIMESTAMP,
    duration_minutes INTEGER,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE activities IS 'Sales and support activities (calls, meetings, etc)';

CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    subject VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'not_started',
    priority task_priority DEFAULT 'medium',
    assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
    related_to_type VARCHAR(50),
    related_to_id INTEGER,
    due_date DATE,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE tasks IS 'Action items and to-dos';

-- ============================================================================
-- MARKETING CAMPAIGNS
-- ============================================================================

CREATE TABLE campaigns (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    campaign_type VARCHAR(50),
    status campaign_status DEFAULT 'draft',
    start_date DATE,
    end_date DATE,
    budget DECIMAL(15, 2),
    expected_revenue DECIMAL(15, 2),
    actual_cost DECIMAL(15, 2),
    owner_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE campaigns IS 'Marketing campaigns';

CREATE TABLE campaign_members (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'sent',
    responded BOOLEAN DEFAULT FALSE,
    responded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (contact_id IS NOT NULL AND lead_id IS NULL) OR
        (contact_id IS NULL AND lead_id IS NOT NULL)
    )
);

COMMENT ON TABLE campaign_members IS 'Campaign recipients and responses';

-- ============================================================================
-- EMAILS & COMMUNICATIONS
-- ============================================================================

CREATE TABLE email_templates (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    body_html TEXT NOT NULL,
    body_text TEXT,
    category VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, name)
);

COMMENT ON TABLE email_templates IS 'Email templates for campaigns and workflows';

CREATE TABLE emails (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    from_address VARCHAR(255) NOT NULL,
    to_address VARCHAR(255) NOT NULL,
    cc_address TEXT,
    bcc_address TEXT,
    subject VARCHAR(255) NOT NULL,
    body_html TEXT,
    body_text TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    sent_at TIMESTAMP,
    opened_at TIMESTAMP,
    clicked_at TIMESTAMP,
    bounced_at TIMESTAMP,
    related_to_type VARCHAR(50),
    related_to_id INTEGER,
    campaign_id INTEGER REFERENCES campaigns(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE emails IS 'Email communication log';

-- ============================================================================
-- DOCUMENTS & FILES
-- ============================================================================

CREATE TABLE folders (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    parent_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    is_public BOOLEAN DEFAULT FALSE,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE folders IS 'Document folder structure';

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    file_url VARCHAR(500) NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    uploaded_by INTEGER REFERENCES users(id),
    related_to_type VARCHAR(50),
    related_to_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE documents IS 'Document management';

-- ============================================================================
-- REPORTS & DASHBOARDS
-- ============================================================================

CREATE TABLE dashboards (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    owner_id INTEGER REFERENCES users(id),
    is_public BOOLEAN DEFAULT FALSE,
    layout JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE dashboards IS 'Custom dashboards';

CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    report_type VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    filters JSONB DEFAULT '{}',
    columns JSONB DEFAULT '[]',
    owner_id INTEGER REFERENCES users(id),
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE reports IS 'Custom reports';

-- ============================================================================
-- AUDIT & LOGGING
-- ============================================================================

CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE audit_logs IS 'Audit trail for all changes';

CREATE TABLE system_logs (
    id SERIAL PRIMARY KEY,
    log_level VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    context JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE system_logs IS 'System event logs';

-- ============================================================================
-- NOTIFICATIONS
-- ============================================================================

CREATE TABLE notification_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email_enabled BOOLEAN DEFAULT TRUE,
    push_enabled BOOLEAN DEFAULT TRUE,
    sms_enabled BOOLEAN DEFAULT FALSE,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE notification_preferences IS 'User notification settings';

CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    related_to_type VARCHAR(50),
    related_to_id INTEGER,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE notifications IS 'In-app notifications';

-- ============================================================================
-- INTEGRATIONS
-- ============================================================================

CREATE TABLE integrations (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    integration_type VARCHAR(50) NOT NULL,
    config JSONB DEFAULT '{}',
    credentials JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, name)
);

COMMENT ON TABLE integrations IS 'Third-party integrations';

CREATE TABLE webhooks (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    url VARCHAR(500) NOT NULL,
    event_types TEXT[] NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    secret VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE webhooks IS 'Webhook subscriptions';

CREATE TABLE webhook_deliveries (
    id SERIAL PRIMARY KEY,
    webhook_id INTEGER NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    response_status INTEGER,
    response_body TEXT,
    delivered_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE webhook_deliveries IS 'Webhook delivery log';

-- ============================================================================
-- CUSTOM FIELDS (EAV Pattern)
-- ============================================================================

CREATE TABLE custom_field_definitions (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    field_type VARCHAR(20) NOT NULL,
    is_required BOOLEAN DEFAULT FALSE,
    default_value TEXT,
    options JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, entity_type, field_name)
);

COMMENT ON TABLE custom_field_definitions IS 'Custom field definitions';

CREATE TABLE custom_field_values (
    id SERIAL PRIMARY KEY,
    field_definition_id INTEGER NOT NULL REFERENCES custom_field_definitions(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL,
    value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(field_definition_id, entity_id)
);

COMMENT ON TABLE custom_field_values IS 'Custom field values';

-- ============================================================================
-- COMPREHENSIVE INDEXES
-- ============================================================================

-- Organizations
CREATE INDEX idx_orgs_slug ON organizations(slug);
CREATE INDEX idx_orgs_status ON organizations(account_status);
CREATE INDEX idx_orgs_created_at ON organizations(created_at DESC);

-- Users
CREATE INDEX idx_users_org_id ON users(organization_id);
CREATE INDEX idx_users_email ON users(organization_id, email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

-- Teams
CREATE INDEX idx_teams_org_id ON teams(organization_id);
CREATE INDEX idx_team_members_team_id ON team_members(team_id);
CREATE INDEX idx_team_members_user_id ON team_members(user_id);

-- Accounts
CREATE INDEX idx_accounts_org_id ON accounts(organization_id);
CREATE INDEX idx_accounts_owner_id ON accounts(owner_id);
CREATE INDEX idx_accounts_name_trgm ON accounts USING gin (name gin_trgm_ops);
CREATE INDEX idx_accounts_created_at ON accounts(created_at DESC);

-- Contacts
CREATE INDEX idx_contacts_org_id ON contacts(organization_id);
CREATE INDEX idx_contacts_account_id ON contacts(account_id);
CREATE INDEX idx_contacts_owner_id ON contacts(owner_id);
CREATE INDEX idx_contacts_email ON contacts(email);
CREATE INDEX idx_contacts_name ON contacts(organization_id, last_name, first_name);

-- Leads
CREATE INDEX idx_leads_org_id ON leads(organization_id);
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_owner_id ON leads(owner_id);
CREATE INDEX idx_leads_created_at ON leads(created_at DESC);
CREATE INDEX idx_leads_converted ON leads(converted_at) WHERE converted_at IS NOT NULL;

-- Pipelines & Stages
CREATE INDEX idx_pipelines_org_id ON pipelines(organization_id);
CREATE INDEX idx_pipeline_stages_pipeline_id ON pipeline_stages(pipeline_id);

-- Deals
CREATE INDEX idx_deals_org_id ON deals(organization_id);
CREATE INDEX idx_deals_account_id ON deals(account_id);
CREATE INDEX idx_deals_contact_id ON deals(contact_id);
CREATE INDEX idx_deals_pipeline_id ON deals(pipeline_id);
CREATE INDEX idx_deals_stage_id ON deals(stage_id);
CREATE INDEX idx_deals_owner_id ON deals(owner_id);
CREATE INDEX idx_deals_close_date ON deals(expected_close_date);
CREATE INDEX idx_deals_created_at ON deals(created_at DESC);

-- Products
CREATE INDEX idx_products_org_id ON products(organization_id);
CREATE INDEX idx_products_category_id ON products(category_id);
CREATE INDEX idx_products_is_active ON products(is_active);

-- Price Books
CREATE INDEX idx_price_books_org_id ON price_books(organization_id);
CREATE INDEX idx_price_book_entries_book_id ON price_book_entries(price_book_id);
CREATE INDEX idx_price_book_entries_product_id ON price_book_entries(product_id);

-- Subscriptions
CREATE INDEX idx_subscriptions_org_id ON subscriptions(organization_id);
CREATE INDEX idx_subscriptions_account_id ON subscriptions(account_id);
CREATE INDEX idx_subscriptions_plan_id ON subscriptions(plan_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);

-- Invoices
CREATE INDEX idx_invoices_org_id ON invoices(organization_id);
CREATE INDEX idx_invoices_account_id ON invoices(account_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_due_date ON invoices(due_date);
CREATE INDEX idx_invoices_created_at ON invoices(created_at DESC);

-- Payments
CREATE INDEX idx_payments_org_id ON payments(organization_id);
CREATE INDEX idx_payments_invoice_id ON payments(invoice_id);
CREATE INDEX idx_payments_account_id ON payments(account_id);
CREATE INDEX idx_payments_status ON payments(status);

-- Tickets
CREATE INDEX idx_tickets_org_id ON tickets(organization_id);
CREATE INDEX idx_tickets_account_id ON tickets(account_id);
CREATE INDEX idx_tickets_contact_id ON tickets(contact_id);
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_priority ON tickets(priority);
CREATE INDEX idx_tickets_assigned_to ON tickets(assigned_to);
CREATE INDEX idx_tickets_team_id ON tickets(team_id);
CREATE INDEX idx_tickets_created_at ON tickets(created_at DESC);

-- Ticket Comments
CREATE INDEX idx_ticket_comments_ticket_id ON ticket_comments(ticket_id);
CREATE INDEX idx_ticket_comments_user_id ON ticket_comments(user_id);

-- Activities
CREATE INDEX idx_activities_org_id ON activities(organization_id);
CREATE INDEX idx_activities_type ON activities(activity_type);
CREATE INDEX idx_activities_owner_id ON activities(owner_id);
CREATE INDEX idx_activities_account_id ON activities(account_id);
CREATE INDEX idx_activities_contact_id ON activities(contact_id);
CREATE INDEX idx_activities_deal_id ON activities(deal_id);
CREATE INDEX idx_activities_scheduled_at ON activities(scheduled_at);

-- Tasks
CREATE INDEX idx_tasks_org_id ON tasks(organization_id);
CREATE INDEX idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);

-- Campaigns
CREATE INDEX idx_campaigns_org_id ON campaigns(organization_id);
CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaign_members_campaign_id ON campaign_members(campaign_id);
CREATE INDEX idx_campaign_members_contact_id ON campaign_members(contact_id);
CREATE INDEX idx_campaign_members_lead_id ON campaign_members(lead_id);

-- Emails
CREATE INDEX idx_emails_org_id ON emails(organization_id);
CREATE INDEX idx_emails_status ON emails(status);
CREATE INDEX idx_emails_sent_at ON emails(sent_at DESC);

-- Documents
CREATE INDEX idx_documents_org_id ON documents(organization_id);
CREATE INDEX idx_documents_folder_id ON documents(folder_id);
CREATE INDEX idx_folders_org_id ON folders(organization_id);
CREATE INDEX idx_folders_parent_id ON folders(parent_id);

-- Audit Logs
CREATE INDEX idx_audit_logs_org_id ON audit_logs(organization_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- Notifications
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_is_read ON notifications(user_id, is_read);
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);

-- Integrations
CREATE INDEX idx_integrations_org_id ON integrations(organization_id);
CREATE INDEX idx_webhooks_org_id ON webhooks(organization_id);
CREATE INDEX idx_webhook_deliveries_webhook_id ON webhook_deliveries(webhook_id);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Sales Pipeline Overview
CREATE VIEW sales_pipeline_summary AS
SELECT
    p.organization_id,
    p.id AS pipeline_id,
    p.name AS pipeline_name,
    ps.id AS stage_id,
    ps.name AS stage_name,
    ps.stage_type,
    COUNT(d.id) AS deal_count,
    SUM(d.amount) AS total_value,
    AVG(d.probability)::NUMERIC(5,2) AS avg_probability,
    SUM(d.amount * d.probability / 100.0)::NUMERIC(15,2) AS weighted_value
FROM pipelines p
JOIN pipeline_stages ps ON p.id = ps.pipeline_id
LEFT JOIN deals d ON ps.id = d.stage_id
GROUP BY p.organization_id, p.id, p.name, ps.id, ps.name, ps.stage_type
ORDER BY p.id, ps.display_order;

COMMENT ON VIEW sales_pipeline_summary IS 'Sales pipeline metrics by stage';

-- Account Revenue Summary
CREATE VIEW account_revenue AS
SELECT
    a.id AS account_id,
    a.organization_id,
    a.name AS account_name,
    COUNT(DISTINCT i.id) AS invoice_count,
    SUM(CASE WHEN i.status = 'paid' THEN i.total_amount ELSE 0 END) AS total_paid,
    SUM(CASE WHEN i.status = 'overdue' THEN i.total_amount ELSE 0 END) AS total_overdue,
    MAX(i.paid_date) AS last_payment_date
FROM accounts a
LEFT JOIN invoices i ON a.id = i.account_id
GROUP BY a.id, a.organization_id, a.name;

COMMENT ON VIEW account_revenue IS 'Revenue metrics by account';

-- Active Subscriptions View
CREATE VIEW active_subscriptions AS
SELECT
    s.id,
    s.organization_id,
    a.name AS account_name,
    sp.name AS plan_name,
    sp.price AS monthly_price,
    s.status,
    s.current_period_start,
    s.current_period_end,
    (s.current_period_end - CURRENT_DATE) AS days_until_renewal
FROM subscriptions s
JOIN accounts a ON s.account_id = a.id
JOIN subscription_plans sp ON s.plan_id = sp.id
WHERE s.status IN ('active', 'trialing');

COMMENT ON VIEW active_subscriptions IS 'Currently active subscriptions';

-- Support Ticket Metrics
CREATE VIEW ticket_metrics AS
SELECT
    t.organization_id,
    t.status,
    t.priority,
    COUNT(*) AS ticket_count,
    AVG(EXTRACT(EPOCH FROM (COALESCE(t.resolved_at, CURRENT_TIMESTAMP) - t.created_at)) / 3600)::NUMERIC(10,2) AS avg_resolution_hours,
    COUNT(CASE WHEN t.resolved_at IS NOT NULL THEN 1 END) AS resolved_count,
    COUNT(CASE WHEN t.resolved_at IS NULL THEN 1 END) AS open_count
FROM tickets t
GROUP BY t.organization_id, t.status, t.priority;

COMMENT ON VIEW ticket_metrics IS 'Support ticket statistics';

-- User Activity Summary
CREATE VIEW user_activity_summary AS
SELECT
    u.id AS user_id,
    u.organization_id,
    u.first_name || ' ' || u.last_name AS user_name,
    u.role,
    COUNT(DISTINCT a.id) AS activity_count,
    COUNT(DISTINCT t.id) AS task_count,
    COUNT(DISTINCT CASE WHEN d.owner_id = u.id THEN d.id END) AS deals_owned,
    SUM(CASE WHEN d.owner_id = u.id THEN d.amount ELSE 0 END) AS total_deal_value
FROM users u
LEFT JOIN activities a ON u.id = a.owner_id
LEFT JOIN tasks t ON u.id = t.assigned_to
LEFT JOIN deals d ON u.id = d.owner_id
GROUP BY u.id, u.organization_id, u.first_name, u.last_name, u.role;

COMMENT ON VIEW user_activity_summary IS 'User performance metrics';

-- Lead Conversion Funnel
CREATE VIEW lead_conversion_funnel AS
SELECT
    l.organization_id,
    l.source,
    COUNT(*) AS total_leads,
    COUNT(CASE WHEN l.status = 'qualified' THEN 1 END) AS qualified_leads,
    COUNT(CASE WHEN l.converted_at IS NOT NULL THEN 1 END) AS converted_leads,
    (COUNT(CASE WHEN l.converted_at IS NOT NULL THEN 1 END)::FLOAT / NULLIF(COUNT(*), 0) * 100)::NUMERIC(5,2) AS conversion_rate
FROM leads l
GROUP BY l.organization_id, l.source;

COMMENT ON VIEW lead_conversion_funnel IS 'Lead conversion metrics by source';

-- Monthly Revenue Trends
CREATE VIEW monthly_revenue AS
SELECT
    i.organization_id,
    DATE_TRUNC('month', i.paid_date)::DATE AS month,
    COUNT(*) AS invoice_count,
    SUM(i.total_amount) AS total_revenue,
    AVG(i.total_amount)::NUMERIC(10,2) AS avg_invoice_value
FROM invoices i
WHERE i.status = 'paid' AND i.paid_date IS NOT NULL
GROUP BY i.organization_id, DATE_TRUNC('month', i.paid_date)
ORDER BY month DESC;

COMMENT ON VIEW monthly_revenue IS 'Monthly revenue trends';

-- Overdue Invoices
CREATE VIEW overdue_invoices AS
SELECT
    i.id,
    i.organization_id,
    i.invoice_number,
    a.name AS account_name,
    i.total_amount,
    i.due_date,
    CURRENT_DATE - i.due_date AS days_overdue,
    i.created_at
FROM invoices i
JOIN accounts a ON i.account_id = a.id
WHERE i.status = 'overdue'
ORDER BY i.due_date;

COMMENT ON VIEW overdue_invoices IS 'Invoices past due date';

-- Top Performing Products
CREATE VIEW top_products AS
SELECT
    p.id,
    p.organization_id,
    p.name AS product_name,
    COUNT(DISTINCT dp.deal_id) AS times_sold,
    SUM(dp.quantity) AS total_quantity_sold,
    SUM(dp.total_price) AS total_revenue
FROM products p
LEFT JOIN deal_products dp ON p.id = dp.product_id
GROUP BY p.id, p.organization_id, p.name
ORDER BY total_revenue DESC;

COMMENT ON VIEW top_products IS 'Product sales performance from deals';

-- Campaign Performance
CREATE VIEW campaign_performance AS
SELECT
    c.id,
    c.organization_id,
    c.name AS campaign_name,
    c.campaign_type,
    c.status,
    COUNT(DISTINCT cm.id) AS total_recipients,
    COUNT(CASE WHEN cm.responded = TRUE THEN 1 END) AS responded_count,
    (COUNT(CASE WHEN cm.responded = TRUE THEN 1 END)::FLOAT / NULLIF(COUNT(DISTINCT cm.id), 0) * 100)::NUMERIC(5,2) AS response_rate,
    c.budget,
    c.actual_cost,
    c.expected_revenue
FROM campaigns c
LEFT JOIN campaign_members cm ON c.id = cm.campaign_id
GROUP BY c.id, c.organization_id, c.name, c.campaign_type, c.status, c.budget, c.actual_cost, c.expected_revenue;

COMMENT ON VIEW campaign_performance IS 'Marketing campaign metrics';

-- ============================================================================
-- SAMPLE DATA
-- ============================================================================

-- Insert organizations
INSERT INTO organizations (name, slug, domain, account_status, trial_ends_at) VALUES
('Acme Corporation', 'acme-corp', 'acme.com', 'active', NULL),
('TechStart Inc', 'techstart', 'techstart.io', 'active', NULL),
('Global Solutions', 'global-solutions', 'globalsolutions.com', 'trial', CURRENT_TIMESTAMP + INTERVAL '14 days'),
('Enterprise Systems', 'enterprise-sys', 'enterprisesys.com', 'active', NULL);

-- Insert users
INSERT INTO users (organization_id, email, password_hash, first_name, last_name, role, is_active, email_verified) VALUES
(1, 'john@acme.com', '$2b$10$hash1', 'John', 'Doe', 'owner', TRUE, TRUE),
(1, 'sarah@acme.com', '$2b$10$hash2', 'Sarah', 'Johnson', 'admin', TRUE, TRUE),
(1, 'mike@acme.com', '$2b$10$hash3', 'Mike', 'Chen', 'sales_rep', TRUE, TRUE),
(1, 'lisa@acme.com', '$2b$10$hash4', 'Lisa', 'Wang', 'sales_rep', TRUE, TRUE),
(1, 'david@acme.com', '$2b$10$hash5', 'David', 'Miller', 'support_agent', TRUE, TRUE),
(2, 'alice@techstart.io', '$2b$10$hash6', 'Alice', 'Smith', 'owner', TRUE, TRUE),
(2, 'bob@techstart.io', '$2b$10$hash7', 'Bob', 'Brown', 'sales_rep', TRUE, TRUE),
(3, 'emma@globalsolutions.com', '$2b$10$hash8', 'Emma', 'Davis', 'owner', TRUE, TRUE),
(4, 'james@enterprisesys.com', '$2b$10$hash9', 'James', 'Wilson', 'owner', TRUE, TRUE);

-- Insert teams
INSERT INTO teams (organization_id, name, description, manager_id) VALUES
(1, 'Sales Team', 'Main sales team', 2),
(1, 'Support Team', 'Customer support', 2),
(2, 'Revenue Team', 'Sales and revenue operations', 6);

-- Insert team members
INSERT INTO team_members (team_id, user_id) VALUES
(1, 3), (1, 4),
(2, 5),
(3, 7);

-- Insert accounts (customers/prospects)
INSERT INTO accounts (organization_id, name, website, industry, employee_count, annual_revenue, owner_id, billing_city, billing_state, billing_country) VALUES
(1, 'ABC Manufacturing', 'www.abcmfg.com', 'Manufacturing', 250, 5000000.00, 3, 'Detroit', 'MI', 'USA'),
(1, 'XYZ Retail', 'www.xyzretail.com', 'Retail', 150, 3000000.00, 3, 'New York', 'NY', 'USA'),
(1, 'CloudFirst Technologies', 'www.cloudfirst.io', 'Technology', 50, 2000000.00, 4, 'San Francisco', 'CA', 'USA'),
(1, 'GreenEnergy Corp', 'www.greenenergy.com', 'Energy', 400, 15000000.00, 4, 'Houston', 'TX', 'USA'),
(2, 'StartupX', 'www.startupx.com', 'Technology', 10, 500000.00, 7, 'Austin', 'TX', 'USA'),
(2, 'FinTech Solutions', 'www.fintechsol.com', 'Financial Services', 75, 4000000.00, 7, 'Boston', 'MA', 'USA');

-- Insert contacts
INSERT INTO contacts (organization_id, account_id, first_name, last_name, email, phone, title, department, owner_id, is_primary) VALUES
(1, 1, 'Robert', 'Johnson', 'rjohnson@abcmfg.com', '+1-313-555-0001', 'CEO', 'Executive', 3, TRUE),
(1, 1, 'Mary', 'Williams', 'mwilliams@abcmfg.com', '+1-313-555-0002', 'CFO', 'Finance', 3, FALSE),
(1, 2, 'Patricia', 'Brown', 'pbrown@xyzretail.com', '+1-212-555-0001', 'VP Operations', 'Operations', 3, TRUE),
(1, 3, 'Michael', 'Davis', 'mdavis@cloudfirst.io', '+1-415-555-0001', 'CTO', 'Engineering', 4, TRUE),
(1, 4, 'Jennifer', 'Garcia', 'jgarcia@greenenergy.com', '+1-713-555-0001', 'Director of IT', 'IT', 4, TRUE),
(2, 5, 'William', 'Martinez', 'wmartinez@startupx.com', '+1-512-555-0001', 'Founder', 'Executive', 7, TRUE),
(2, 6, 'Linda', 'Rodriguez', 'lrodriguez@fintechsol.com', '+1-617-555-0001', 'VP Sales', 'Sales', 7, TRUE);

-- Insert leads
INSERT INTO leads (organization_id, first_name, last_name, email, phone, company, title, status, source, owner_id, rating) VALUES
(1, 'Daniel', 'Anderson', 'danderson@newcompany.com', '+1-555-0101', 'NewCompany LLC', 'Manager', 'new', 'Website', 3, 3),
(1, 'Jessica', 'Thomas', 'jthomas@futuretech.com', '+1-555-0102', 'FutureTech', 'Director', 'contacted', 'Referral', 3, 4),
(1, 'Christopher', 'Jackson', 'cjackson@innovate.io', '+1-555-0103', 'Innovate Systems', 'VP', 'qualified', 'Trade Show', 4, 5),
(2, 'Sarah', 'White', 'swhite@rapidgrowth.com', '+1-555-0104', 'RapidGrowth Inc', 'CEO', 'new', 'LinkedIn', 7, 3);

-- Insert pipelines
INSERT INTO pipelines (organization_id, name, description, is_default) VALUES
(1, 'Standard Sales Pipeline', 'Default sales process', TRUE),
(2, 'Enterprise Sales', 'Enterprise deal process', TRUE);

-- Insert pipeline stages
INSERT INTO pipeline_stages (pipeline_id, name, stage_type, probability, display_order) VALUES
(1, 'Prospecting', 'prospecting', 10, 1),
(1, 'Qualification', 'qualification', 25, 2),
(1, 'Proposal', 'proposal', 50, 3),
(1, 'Negotiation', 'negotiation', 75, 4),
(1, 'Closed Won', 'closed_won', 100, 5),
(1, 'Closed Lost', 'closed_lost', 0, 6),
(2, 'Discovery', 'prospecting', 10, 1),
(2, 'Proof of Concept', 'qualification', 30, 2),
(2, 'Proposal', 'proposal', 60, 3),
(2, 'Contract Review', 'negotiation', 85, 4),
(2, 'Won', 'closed_won', 100, 5),
(2, 'Lost', 'closed_lost', 0, 6);

-- Insert product categories
INSERT INTO product_categories (organization_id, name, description) VALUES
(1, 'Software Licenses', 'Software licensing products'),
(1, 'Professional Services', 'Consulting and implementation'),
(1, 'Support Plans', 'Technical support subscriptions'),
(2, 'SaaS Products', 'Cloud software subscriptions');

-- Insert products
INSERT INTO products (organization_id, name, sku, category_id, description, is_active, is_recurring) VALUES
(1, 'Enterprise CRM License', 'CRM-ENT-001', 1, 'Enterprise CRM platform annual license', TRUE, TRUE),
(1, 'Professional CRM License', 'CRM-PRO-001', 1, 'Professional CRM platform annual license', TRUE, TRUE),
(1, 'Implementation Services', 'SVC-IMPL-001', 2, 'CRM implementation and setup', TRUE, FALSE),
(1, 'Training Package', 'SVC-TRAIN-001', 2, 'User training program', TRUE, FALSE),
(1, 'Premium Support', 'SUP-PREM-001', 3, '24/7 premium support plan', TRUE, TRUE),
(2, 'Starter Plan', 'SAAS-START-001', 4, 'Starter subscription plan', TRUE, TRUE),
(2, 'Growth Plan', 'SAAS-GROW-001', 4, 'Growth subscription plan', TRUE, TRUE),
(2, 'Enterprise Plan', 'SAAS-ENT-001', 4, 'Enterprise subscription plan', TRUE, TRUE);

-- Insert price books
INSERT INTO price_books (organization_id, name, description, is_active, is_default) VALUES
(1, 'Standard Price Book', 'Default pricing', TRUE, TRUE),
(2, 'Standard Pricing', 'Default pricing', TRUE, TRUE);

-- Insert price book entries
INSERT INTO price_book_entries (price_book_id, product_id, unit_price) VALUES
(1, 1, 999.00), (1, 2, 499.00), (1, 3, 5000.00), (1, 4, 2000.00), (1, 5, 299.00),
(2, 6, 49.00), (2, 7, 199.00), (2, 8, 999.00);

-- Insert deals
INSERT INTO deals (organization_id, name, account_id, contact_id, pipeline_id, stage_id, owner_id, amount, probability, expected_close_date) VALUES
(1, 'ABC Manufacturing - Enterprise CRM', 1, 1, 1, 3, 3, 15000.00, 50, CURRENT_DATE + INTERVAL '30 days'),
(1, 'XYZ Retail - Professional CRM', 2, 3, 1, 2, 3, 7500.00, 25, CURRENT_DATE + INTERVAL '45 days'),
(1, 'CloudFirst - Implementation', 3, 4, 1, 4, 4, 25000.00, 75, CURRENT_DATE + INTERVAL '15 days'),
(1, 'GreenEnergy - Enterprise Deal', 4, 5, 1, 1, 4, 50000.00, 10, CURRENT_DATE + INTERVAL '90 days'),
(2, 'StartupX - Growth Plan', 5, 6, 2, 3, 7, 2400.00, 60, CURRENT_DATE + INTERVAL '20 days');

-- Insert subscription plans
INSERT INTO subscription_plans (organization_id, name, billing_interval, price, trial_days, is_active) VALUES
(1, 'Monthly Professional', 'month', 499.00, 14, TRUE),
(1, 'Annual Professional', 'year', 4990.00, 14, TRUE),
(1, 'Monthly Enterprise', 'month', 999.00, 30, TRUE),
(2, 'Starter Monthly', 'month', 49.00, 7, TRUE),
(2, 'Growth Monthly', 'month', 199.00, 14, TRUE);

-- Insert subscriptions
INSERT INTO subscriptions (organization_id, account_id, plan_id, status, current_period_start, current_period_end) VALUES
(1, 1, 2, 'active', CURRENT_DATE - INTERVAL '30 days', CURRENT_DATE + INTERVAL '335 days'),
(1, 3, 3, 'active', CURRENT_DATE - INTERVAL '15 days', CURRENT_DATE + INTERVAL '15 days'),
(2, 5, 4, 'trialing', CURRENT_DATE - INTERVAL '3 days', CURRENT_DATE + INTERVAL '27 days');

-- Insert invoices
INSERT INTO invoices (organization_id, invoice_number, account_id, subscription_id, status, subtotal, tax_amount, total_amount, issue_date, due_date, paid_date) VALUES
(1, 'INV-2024-0001', 1, 1, 'paid', 4990.00, 399.20, 5389.20, CURRENT_DATE - INTERVAL '30 days', CURRENT_DATE - INTERVAL '15 days', CURRENT_DATE - INTERVAL '20 days'),
(1, 'INV-2024-0002', 3, 2, 'paid', 999.00, 79.92, 1078.92, CURRENT_DATE - INTERVAL '15 days', CURRENT_DATE, CURRENT_DATE - INTERVAL '5 days'),
(1, 'INV-2024-0003', 2, NULL, 'sent', 7500.00, 600.00, 8100.00, CURRENT_DATE - INTERVAL '10 days', CURRENT_DATE + INTERVAL '20 days', NULL),
(2, 'INV-2024-T001', 5, 3, 'draft', 0.00, 0.00, 0.00, CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', NULL);

-- Insert invoice line items
INSERT INTO invoice_line_items (invoice_id, product_id, description, quantity, unit_price, total_price) VALUES
(1, 2, 'Professional CRM Annual License', 1, 4990.00, 4990.00),
(2, 1, 'Enterprise CRM Monthly License', 1, 999.00, 999.00),
(3, 3, 'CRM Implementation Services', 1, 5000.00, 5000.00),
(3, 4, 'Training Package - 10 users', 1, 2000.00, 2000.00),
(3, 5, 'Premium Support - 6 months', 1, 500.00, 500.00);

-- Insert payments
INSERT INTO payments (organization_id, invoice_id, account_id, amount, payment_method, status, transaction_id, payment_date) VALUES
(1, 1, 1, 5389.20, 'credit_card', 'completed', 'txn_abc123', CURRENT_DATE - INTERVAL '20 days'),
(1, 2, 3, 1078.92, 'bank_transfer', 'completed', 'txn_def456', CURRENT_DATE - INTERVAL '5 days');

-- Insert ticket categories
INSERT INTO ticket_categories (organization_id, name, description) VALUES
(1, 'Technical Support', 'Technical issues and bugs'),
(1, 'Billing', 'Billing and payment questions'),
(1, 'Feature Request', 'New feature suggestions'),
(2, 'General Support', 'General customer support');

-- Insert tickets
INSERT INTO tickets (organization_id, ticket_number, account_id, contact_id, category_id, subject, description, status, priority, assigned_to) VALUES
(1, 'TKT-001', 1, 1, 1, 'Cannot login to dashboard', 'User reports unable to access dashboard after password reset', 'in_progress', 'high', 5),
(1, 'TKT-002', 2, 3, 2, 'Invoice payment question', 'Customer asking about payment terms', 'resolved', 'low', 5),
(1, 'TKT-003', 3, 4, 3, 'Request API integration', 'Customer wants to integrate with external system', 'open', 'medium', 5),
(2, 'TKT-T001', 5, 6, 4, 'Help with onboarding', 'New customer needs setup assistance', 'pending', 'medium', NULL);

-- Insert ticket comments
INSERT INTO ticket_comments (ticket_id, user_id, comment, is_internal) VALUES
(1, 5, 'Looking into the issue. Can you confirm your email address?', FALSE),
(1, 3, 'My email is rjohnson@abcmfg.com', FALSE),
(1, 5, 'Found the issue - password reset email went to spam. Resending now.', FALSE),
(2, 5, 'Payment terms are Net 30 as per your contract.', FALSE),
(3, 5, 'Our API documentation is available at api.acme.com/docs', FALSE);

-- Insert activities
INSERT INTO activities (organization_id, activity_type, subject, description, account_id, contact_id, deal_id, owner_id, scheduled_at, duration_minutes) VALUES
(1, 'call', 'Discovery Call - ABC Manufacturing', 'Initial discovery call to understand requirements', 1, 1, 1, 3, CURRENT_TIMESTAMP - INTERVAL '2 days', 60),
(1, 'meeting', 'Demo Session - XYZ Retail', 'Product demonstration', 2, 3, 2, 3, CURRENT_TIMESTAMP + INTERVAL '3 days', 90),
(1, 'email', 'Proposal Follow-up', 'Following up on sent proposal', 3, 4, 3, 4, CURRENT_TIMESTAMP - INTERVAL '1 day', NULL),
(1, 'call', 'Contract Negotiation', 'Discussing contract terms', 4, 5, 4, 4, CURRENT_TIMESTAMP + INTERVAL '5 days', 45);

-- Insert tasks
INSERT INTO tasks (organization_id, subject, description, status, priority, assigned_to, due_date) VALUES
(1, 'Prepare proposal for ABC Manufacturing', 'Create detailed proposal including pricing', 'in_progress', 'high', 3, CURRENT_DATE + INTERVAL '2 days'),
(1, 'Follow up with XYZ Retail', 'Send follow-up email after demo', 'not_started', 'medium', 3, CURRENT_DATE + INTERVAL '1 day'),
(1, 'Schedule implementation kickoff', 'Set up kickoff meeting with CloudFirst', 'not_started', 'high', 4, CURRENT_DATE + INTERVAL '3 days');

-- Insert campaigns
INSERT INTO campaigns (organization_id, name, description, campaign_type, status, start_date, end_date, budget, owner_id) VALUES
(1, 'Summer 2024 Promotion', 'Q3 product promotion campaign', 'email', 'completed', CURRENT_DATE - INTERVAL '60 days', CURRENT_DATE - INTERVAL '30 days', 5000.00, 2),
(1, 'Webinar Series - Fall 2024', 'Educational webinar series', 'webinar', 'active', CURRENT_DATE - INTERVAL '15 days', CURRENT_DATE + INTERVAL '45 days', 3000.00, 2);

-- Insert campaign members
INSERT INTO campaign_members (campaign_id, contact_id, status, responded, responded_at) VALUES
(1, 1, 'sent', TRUE, CURRENT_TIMESTAMP - INTERVAL '50 days'),
(1, 2, 'sent', FALSE, NULL),
(1, 3, 'sent', TRUE, CURRENT_TIMESTAMP - INTERVAL '45 days'),
(2, 4, 'sent', TRUE, CURRENT_TIMESTAMP - INTERVAL '10 days'),
(2, 5, 'sent', FALSE, NULL);

-- Insert email templates
INSERT INTO email_templates (organization_id, name, subject, body_html, category, is_active) VALUES
(1, 'Welcome Email', 'Welcome to Acme CRM', '<h1>Welcome!</h1><p>Thank you for choosing Acme CRM...</p>', 'onboarding', TRUE),
(1, 'Invoice Reminder', 'Invoice Payment Reminder', '<p>This is a friendly reminder about invoice #{invoice_number}...</p>', 'billing', TRUE);

-- Insert notifications
INSERT INTO notifications (user_id, title, message, notification_type, is_read) VALUES
(3, 'New lead assigned', 'A new lead "Daniel Anderson" has been assigned to you', 'lead', FALSE),
(3, 'Deal moved to Proposal stage', 'Deal "ABC Manufacturing - Enterprise CRM" moved to Proposal stage', 'deal', TRUE),
(5, 'New ticket assigned', 'Ticket TKT-003 has been assigned to you', 'ticket', FALSE);

-- Insert audit logs (sample)
INSERT INTO audit_logs (organization_id, user_id, action, entity_type, entity_id, new_values, ip_address) VALUES
(1, 3, 'create', 'deal', 1, '{"name": "ABC Manufacturing - Enterprise CRM", "amount": 15000.00}'::jsonb, '192.168.1.100'),
(1, 3, 'update', 'deal', 1, '{"stage_id": 3}'::jsonb, '192.168.1.100'),
(1, 5, 'update', 'ticket', 1, '{"status": "in_progress"}'::jsonb, '192.168.1.101');

-- ============================================================================
-- TRIGGER FUNCTION FOR UPDATED_AT
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to all tables with updated_at column
DO $$
DECLARE
    t text;
BEGIN
    FOR t IN
        SELECT table_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name = 'updated_at'
          AND table_name NOT LIKE 'pg_%'
    LOOP
        EXECUTE format('
            CREATE TRIGGER update_%I_updated_at
            BEFORE UPDATE ON %I
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        ', t, t);
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DATABASE STATISTICS
-- ============================================================================

VACUUM ANALYZE;

SELECT
    'Database' AS object_type,
    current_database() AS name,
    'Enterprise SaaS CRM with 55+ tables, 10 views, 6 types' AS description
UNION ALL
SELECT
    'Tables' AS object_type,
    COUNT(*)::text AS name,
    'User-defined tables' AS description
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
UNION ALL
SELECT
    'Views' AS object_type,
    COUNT(*)::text AS name,
    'User-defined views' AS description
FROM information_schema.views
WHERE table_schema = 'public'
UNION ALL
SELECT
    'Indexes' AS object_type,
    COUNT(*)::text AS name,
    'User-defined indexes' AS description
FROM pg_indexes
WHERE schemaname = 'public';
