-- ============================================================================
-- Medium Database: E-Commerce Platform
-- ============================================================================
-- Description: An online shopping platform with products, orders, and payments
-- Tables: 25 | Views: 6 | Types: 4 | Indexes: 45+
-- ============================================================================

DROP DATABASE IF EXISTS ecommerce_medium;
CREATE DATABASE ecommerce_medium;
\c ecommerce_medium;

-- ============================================================================
-- CUSTOM TYPES
-- ============================================================================

CREATE TYPE user_status AS ENUM ('active', 'inactive', 'suspended', 'deleted');
CREATE TYPE order_status AS ENUM ('pending', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded');
CREATE TYPE payment_status AS ENUM ('pending', 'completed', 'failed', 'refunded');
CREATE TYPE payment_method AS ENUM ('credit_card', 'debit_card', 'paypal', 'bank_transfer', 'cash_on_delivery');

-- ============================================================================
-- CORE TABLES - USERS & AUTHENTICATION
-- ============================================================================

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    status user_status DEFAULT 'active',
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

COMMENT ON TABLE users IS 'Customer accounts';

CREATE TABLE user_addresses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    address_type VARCHAR(20) DEFAULT 'shipping',
    street_address VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100),
    postal_code VARCHAR(20) NOT NULL,
    country VARCHAR(100) NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE user_addresses IS 'User shipping and billing addresses';

CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    avatar_url VARCHAR(500),
    date_of_birth DATE,
    gender VARCHAR(20),
    bio TEXT,
    preferences JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE user_profiles IS 'Extended user profile information';

-- ============================================================================
-- PRODUCT CATALOG
-- ============================================================================

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    parent_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    description TEXT,
    image_url VARCHAR(500),
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE categories IS 'Product categories with hierarchical structure';

CREATE TABLE brands (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    logo_url VARCHAR(500),
    website VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE brands IS 'Product brands/manufacturers';

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    sku VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    brand_id INTEGER REFERENCES brands(id) ON DELETE SET NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    price DECIMAL(10, 2) NOT NULL,
    compare_at_price DECIMAL(10, 2),
    cost_price DECIMAL(10, 2),
    is_active BOOLEAN DEFAULT TRUE,
    is_featured BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE products IS 'Product catalog';

CREATE TABLE product_images (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    image_url VARCHAR(500) NOT NULL,
    alt_text VARCHAR(255),
    display_order INTEGER DEFAULT 0,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE product_images IS 'Product image gallery';

CREATE TABLE product_variants (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    sku VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2),
    attributes JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE product_variants IS 'Product variants (size, color, etc.)';

-- ============================================================================
-- INVENTORY MANAGEMENT
-- ============================================================================

CREATE TABLE warehouses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    address VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE warehouses IS 'Warehouse locations';

CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 0,
    reserved_quantity INTEGER NOT NULL DEFAULT 0,
    reorder_point INTEGER DEFAULT 10,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, warehouse_id)
);

COMMENT ON TABLE inventory IS 'Product inventory levels by warehouse';

CREATE TABLE inventory_transactions (
    id SERIAL PRIMARY KEY,
    inventory_id INTEGER NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
    transaction_type VARCHAR(50) NOT NULL,
    quantity INTEGER NOT NULL,
    reference_type VARCHAR(50),
    reference_id INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE inventory_transactions IS 'Inventory movement history';

-- ============================================================================
-- SHOPPING CART
-- ============================================================================

CREATE TABLE carts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

COMMENT ON TABLE carts IS 'Shopping carts for registered and guest users';

CREATE TABLE cart_items (
    id SERIAL PRIMARY KEY,
    cart_id INTEGER NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    variant_id INTEGER REFERENCES product_variants(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1,
    price DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE cart_items IS 'Items in shopping carts';

-- ============================================================================
-- ORDERS & PAYMENTS
-- ============================================================================

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status order_status DEFAULT 'pending',
    subtotal DECIMAL(10, 2) NOT NULL,
    tax_amount DECIMAL(10, 2) DEFAULT 0,
    shipping_amount DECIMAL(10, 2) DEFAULT 0,
    discount_amount DECIMAL(10, 2) DEFAULT 0,
    total_amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    shipping_address_id INTEGER REFERENCES user_addresses(id),
    billing_address_id INTEGER REFERENCES user_addresses(id),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

COMMENT ON TABLE orders IS 'Customer orders';

CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    variant_id INTEGER REFERENCES product_variants(id),
    product_name VARCHAR(255) NOT NULL,
    sku VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    total_price DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE order_items IS 'Line items in orders';

CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    payment_method payment_method NOT NULL,
    status payment_status DEFAULT 'pending',
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    transaction_id VARCHAR(255),
    payment_gateway VARCHAR(100),
    payment_details JSONB,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE payments IS 'Payment transactions';

-- ============================================================================
-- SHIPPING & FULFILLMENT
-- ============================================================================

CREATE TABLE shipping_carriers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    website VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE shipping_carriers IS 'Shipping carrier companies';

CREATE TABLE shipments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    carrier_id INTEGER REFERENCES shipping_carriers(id),
    tracking_number VARCHAR(255),
    warehouse_id INTEGER REFERENCES warehouses(id),
    status VARCHAR(50) DEFAULT 'pending',
    shipped_at TIMESTAMP,
    estimated_delivery TIMESTAMP,
    delivered_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE shipments IS 'Order shipment tracking';

-- ============================================================================
-- PROMOTIONS & DISCOUNTS
-- ============================================================================

CREATE TABLE coupons (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    discount_type VARCHAR(20) NOT NULL,
    discount_value DECIMAL(10, 2) NOT NULL,
    min_order_amount DECIMAL(10, 2),
    max_discount_amount DECIMAL(10, 2),
    usage_limit INTEGER,
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    starts_at TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE coupons IS 'Discount coupons and promo codes';

CREATE TABLE coupon_usage (
    id SERIAL PRIMARY KEY,
    coupon_id INTEGER NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    discount_amount DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(coupon_id, order_id)
);

COMMENT ON TABLE coupon_usage IS 'Coupon redemption history';

-- ============================================================================
-- REVIEWS & RATINGS
-- ============================================================================

CREATE TABLE product_reviews (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(255),
    comment TEXT,
    is_verified_purchase BOOLEAN DEFAULT FALSE,
    is_approved BOOLEAN DEFAULT FALSE,
    helpful_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, user_id, order_id)
);

COMMENT ON TABLE product_reviews IS 'Customer product reviews and ratings';

CREATE TABLE review_votes (
    id SERIAL PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES product_reviews(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_helpful BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(review_id, user_id)
);

COMMENT ON TABLE review_votes IS 'User votes on review helpfulness';

-- ============================================================================
-- WISHLISTS
-- ============================================================================

CREATE TABLE wishlists (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) DEFAULT 'My Wishlist',
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE wishlists IS 'User wishlists';

CREATE TABLE wishlist_items (
    id SERIAL PRIMARY KEY,
    wishlist_id INTEGER NOT NULL REFERENCES wishlists(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(wishlist_id, product_id)
);

COMMENT ON TABLE wishlist_items IS 'Products in wishlists';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Users indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_created_at ON users(created_at DESC);

-- Addresses indexes
CREATE INDEX idx_addresses_user_id ON user_addresses(user_id);
CREATE INDEX idx_addresses_is_default ON user_addresses(user_id, is_default);

-- Categories indexes
CREATE INDEX idx_categories_parent_id ON categories(parent_id);
CREATE INDEX idx_categories_is_active ON categories(is_active);

-- Products indexes
CREATE INDEX idx_products_category_id ON products(category_id);
CREATE INDEX idx_products_brand_id ON products(brand_id);
CREATE INDEX idx_products_is_active ON products(is_active);
CREATE INDEX idx_products_is_featured ON products(is_featured) WHERE is_featured = TRUE;
CREATE INDEX idx_products_price ON products(price);
CREATE INDEX idx_products_created_at ON products(created_at DESC);

-- Product images indexes
CREATE INDEX idx_product_images_product_id ON product_images(product_id);

-- Product variants indexes
CREATE INDEX idx_product_variants_product_id ON product_variants(product_id);

-- Inventory indexes
CREATE INDEX idx_inventory_product_id ON inventory(product_id);
CREATE INDEX idx_inventory_warehouse_id ON inventory(warehouse_id);
CREATE INDEX idx_inventory_low_stock ON inventory(product_id) WHERE quantity <= reorder_point;

-- Inventory transactions indexes
CREATE INDEX idx_inventory_txn_inventory_id ON inventory_transactions(inventory_id);
CREATE INDEX idx_inventory_txn_created_at ON inventory_transactions(created_at DESC);

-- Cart indexes
CREATE INDEX idx_carts_user_id ON carts(user_id);
CREATE INDEX idx_carts_session_id ON carts(session_id);

-- Cart items indexes
CREATE INDEX idx_cart_items_cart_id ON cart_items(cart_id);
CREATE INDEX idx_cart_items_product_id ON cart_items(product_id);

-- Orders indexes
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX idx_orders_order_number ON orders(order_number);

-- Order items indexes
CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);

-- Payments indexes
CREATE INDEX idx_payments_order_id ON payments(order_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_created_at ON payments(created_at DESC);

-- Shipments indexes
CREATE INDEX idx_shipments_order_id ON shipments(order_id);
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_tracking_number ON shipments(tracking_number);

-- Coupons indexes
CREATE INDEX idx_coupons_code ON coupons(code);
CREATE INDEX idx_coupons_is_active ON coupons(is_active) WHERE is_active = TRUE;

-- Reviews indexes
CREATE INDEX idx_reviews_product_id ON product_reviews(product_id);
CREATE INDEX idx_reviews_user_id ON product_reviews(user_id);
CREATE INDEX idx_reviews_is_approved ON product_reviews(is_approved) WHERE is_approved = TRUE;
CREATE INDEX idx_reviews_rating ON product_reviews(rating);

-- Wishlist indexes
CREATE INDEX idx_wishlists_user_id ON wishlists(user_id);
CREATE INDEX idx_wishlist_items_wishlist_id ON wishlist_items(wishlist_id);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Active products with inventory
CREATE VIEW active_products_inventory AS
SELECT
    p.id,
    p.name,
    p.sku,
    p.price,
    p.compare_at_price,
    c.name AS category_name,
    b.name AS brand_name,
    COALESCE(SUM(i.quantity), 0) AS total_stock,
    COALESCE(SUM(i.reserved_quantity), 0) AS reserved_stock,
    COALESCE(SUM(i.quantity - i.reserved_quantity), 0) AS available_stock
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
LEFT JOIN brands b ON p.brand_id = b.id
LEFT JOIN inventory i ON p.id = i.product_id
WHERE p.is_active = TRUE
GROUP BY p.id, p.name, p.sku, p.price, p.compare_at_price, c.name, b.name;

COMMENT ON VIEW active_products_inventory IS 'Active products with aggregated inventory';

-- Product ratings summary
CREATE VIEW product_ratings AS
SELECT
    p.id AS product_id,
    p.name AS product_name,
    COUNT(r.id) AS review_count,
    AVG(r.rating)::NUMERIC(3,2) AS average_rating,
    COUNT(CASE WHEN r.rating = 5 THEN 1 END) AS five_star_count,
    COUNT(CASE WHEN r.rating = 4 THEN 1 END) AS four_star_count,
    COUNT(CASE WHEN r.rating = 3 THEN 1 END) AS three_star_count,
    COUNT(CASE WHEN r.rating = 2 THEN 1 END) AS two_star_count,
    COUNT(CASE WHEN r.rating = 1 THEN 1 END) AS one_star_count
FROM products p
LEFT JOIN product_reviews r ON p.id = r.product_id AND r.is_approved = TRUE
GROUP BY p.id, p.name;

COMMENT ON VIEW product_ratings IS 'Product review statistics';

-- Customer order history
CREATE VIEW customer_order_summary AS
SELECT
    u.id AS user_id,
    u.email,
    u.first_name,
    u.last_name,
    COUNT(o.id) AS total_orders,
    SUM(CASE WHEN o.status = 'delivered' THEN o.total_amount ELSE 0 END) AS total_spent,
    MAX(o.created_at) AS last_order_date,
    AVG(o.total_amount)::NUMERIC(10,2) AS average_order_value
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.email, u.first_name, u.last_name;

COMMENT ON VIEW customer_order_summary IS 'Customer purchase statistics';

-- Order details with items
CREATE VIEW order_details AS
SELECT
    o.id AS order_id,
    o.order_number,
    o.status,
    o.total_amount,
    o.created_at,
    u.email AS customer_email,
    u.first_name || ' ' || u.last_name AS customer_name,
    COUNT(oi.id) AS item_count,
    STRING_AGG(oi.product_name, ', ') AS products
FROM orders o
JOIN users u ON o.user_id = u.id
LEFT JOIN order_items oi ON o.id = oi.order_id
GROUP BY o.id, o.order_number, o.status, o.total_amount, o.created_at, u.email, u.first_name, u.last_name;

COMMENT ON VIEW order_details IS 'Order summary with customer info';

-- Low stock products
CREATE VIEW low_stock_products AS
SELECT
    p.id,
    p.name,
    p.sku,
    w.name AS warehouse_name,
    i.quantity AS current_stock,
    i.reserved_quantity,
    i.reorder_point,
    (i.quantity - i.reserved_quantity) AS available_stock
FROM inventory i
JOIN products p ON i.product_id = p.id
JOIN warehouses w ON i.warehouse_id = w.id
WHERE i.quantity <= i.reorder_point
ORDER BY (i.quantity - i.reorder_point);

COMMENT ON VIEW low_stock_products IS 'Products below reorder point';

-- Daily sales summary
CREATE VIEW daily_sales AS
SELECT
    DATE(created_at) AS sale_date,
    COUNT(*) AS order_count,
    SUM(total_amount) AS total_revenue,
    AVG(total_amount)::NUMERIC(10,2) AS average_order_value,
    COUNT(DISTINCT user_id) AS unique_customers
FROM orders
WHERE status NOT IN ('cancelled', 'refunded')
GROUP BY DATE(created_at)
ORDER BY sale_date DESC;

COMMENT ON VIEW daily_sales IS 'Daily sales metrics';

-- ============================================================================
-- SAMPLE DATA
-- ============================================================================

-- Insert users
INSERT INTO users (email, password_hash, first_name, last_name, phone, status, email_verified) VALUES
('john.doe@email.com', '$2b$10$hash1', 'John', 'Doe', '+1234567890', 'active', TRUE),
('jane.smith@email.com', '$2b$10$hash2', 'Jane', 'Smith', '+1234567891', 'active', TRUE),
('bob.johnson@email.com', '$2b$10$hash3', 'Bob', 'Johnson', '+1234567892', 'active', TRUE),
('alice.williams@email.com', '$2b$10$hash4', 'Alice', 'Williams', '+1234567893', 'active', TRUE),
('charlie.brown@email.com', '$2b$10$hash5', 'Charlie', 'Brown', '+1234567894', 'active', FALSE),
('diana.prince@email.com', '$2b$10$hash6', 'Diana', 'Prince', '+1234567895', 'active', TRUE),
('evan.hansen@email.com', '$2b$10$hash7', 'Evan', 'Hansen', '+1234567896', 'inactive', TRUE),
('frank.miller@email.com', '$2b$10$hash8', 'Frank', 'Miller', '+1234567897', 'active', TRUE),
('grace.hopper@email.com', '$2b$10$hash9', 'Grace', 'Hopper', '+1234567898', 'active', TRUE),
('henry.ford@email.com', '$2b$10$hash10', 'Henry', 'Ford', '+1234567899', 'active', TRUE);

-- Insert addresses
INSERT INTO user_addresses (user_id, address_type, street_address, city, state, postal_code, country, is_default) VALUES
(1, 'shipping', '123 Main St', 'New York', 'NY', '10001', 'USA', TRUE),
(1, 'billing', '123 Main St', 'New York', 'NY', '10001', 'USA', FALSE),
(2, 'shipping', '456 Oak Ave', 'Los Angeles', 'CA', '90001', 'USA', TRUE),
(3, 'shipping', '789 Pine Rd', 'Chicago', 'IL', '60601', 'USA', TRUE),
(4, 'shipping', '321 Elm St', 'Houston', 'TX', '77001', 'USA', TRUE),
(5, 'shipping', '654 Maple Dr', 'Phoenix', 'AZ', '85001', 'USA', TRUE),
(6, 'shipping', '987 Cedar Ln', 'Philadelphia', 'PA', '19101', 'USA', TRUE);

-- Insert categories
INSERT INTO categories (name, slug, parent_id, description, display_order, is_active) VALUES
('Electronics', 'electronics', NULL, 'Electronic devices and accessories', 1, TRUE),
('Computers', 'computers', 1, 'Laptops, desktops, and accessories', 1, TRUE),
('Smartphones', 'smartphones', 1, 'Mobile phones and accessories', 2, TRUE),
('Home & Garden', 'home-garden', NULL, 'Home improvement and garden supplies', 2, TRUE),
('Furniture', 'furniture', 4, 'Home and office furniture', 1, TRUE),
('Clothing', 'clothing', NULL, 'Apparel and fashion', 3, TRUE),
('Men', 'men', 6, 'Mens clothing', 1, TRUE),
('Women', 'women', 6, 'Womens clothing', 2, TRUE),
('Sports', 'sports', NULL, 'Sports and outdoor equipment', 4, TRUE),
('Books', 'books', NULL, 'Books and media', 5, TRUE);

-- Insert brands
INSERT INTO brands (name, slug, description, website) VALUES
('TechPro', 'techpro', 'Premium electronics brand', 'https://techpro.example.com'),
('HomeComfort', 'homecomfort', 'Quality home furnishings', 'https://homecomfort.example.com'),
('StyleWear', 'stylewear', 'Modern fashion brand', 'https://stylewear.example.com'),
('ActiveLife', 'activelife', 'Sports and fitness gear', 'https://activelife.example.com'),
('BookHaven', 'bookhaven', 'Publisher and book distributor', 'https://bookhaven.example.com');

-- Insert warehouses
INSERT INTO warehouses (name, code, address, city, state, country) VALUES
('East Coast Warehouse', 'EC-WH-01', '100 Industrial Pkwy', 'Newark', 'NJ', 'USA'),
('West Coast Warehouse', 'WC-WH-01', '200 Logistics Blvd', 'San Diego', 'CA', 'USA'),
('Central Warehouse', 'CT-WH-01', '300 Distribution Dr', 'Dallas', 'TX', 'USA');

-- Insert products
INSERT INTO products (name, slug, sku, description, brand_id, category_id, price, compare_at_price, cost_price, is_active, is_featured) VALUES
('Laptop Pro 15', 'laptop-pro-15', 'TECH-LP-001', 'High-performance laptop for professionals', 1, 2, 1299.99, 1499.99, 800.00, TRUE, TRUE),
('Smartphone X', 'smartphone-x', 'TECH-SP-001', 'Latest flagship smartphone', 1, 3, 899.99, 999.99, 600.00, TRUE, TRUE),
('Wireless Mouse', 'wireless-mouse', 'TECH-MS-001', 'Ergonomic wireless mouse', 1, 2, 29.99, 39.99, 15.00, TRUE, FALSE),
('Office Chair Deluxe', 'office-chair-deluxe', 'HOME-CH-001', 'Comfortable ergonomic office chair', 2, 5, 299.99, 349.99, 150.00, TRUE, TRUE),
('Desk Lamp LED', 'desk-lamp-led', 'HOME-LM-001', 'Modern LED desk lamp', 2, 5, 49.99, 59.99, 25.00, TRUE, FALSE),
('Running Shoes Pro', 'running-shoes-pro', 'SPORT-SH-001', 'Professional running shoes', 4, 9, 129.99, 149.99, 60.00, TRUE, TRUE),
('Yoga Mat Premium', 'yoga-mat-premium', 'SPORT-YM-001', 'Non-slip premium yoga mat', 4, 9, 39.99, 49.99, 20.00, TRUE, FALSE),
('Mens T-Shirt Classic', 'mens-tshirt-classic', 'STYLE-MT-001', 'Classic cotton t-shirt', 3, 7, 24.99, 29.99, 10.00, TRUE, FALSE),
('Womens Jeans', 'womens-jeans', 'STYLE-WJ-001', 'Comfortable slim-fit jeans', 3, 8, 79.99, 89.99, 35.00, TRUE, FALSE),
('Programming Guide', 'programming-guide', 'BOOK-PG-001', 'Complete programming reference', 5, 10, 49.99, NULL, 20.00, TRUE, FALSE),
('Tablet 10 inch', 'tablet-10-inch', 'TECH-TB-001', 'Portable tablet device', 1, 1, 399.99, 449.99, 250.00, TRUE, FALSE),
('USB-C Cable', 'usb-c-cable', 'TECH-CB-001', 'Fast charging USB-C cable', 1, 1, 14.99, 19.99, 5.00, TRUE, FALSE),
('Coffee Table Oak', 'coffee-table-oak', 'HOME-CT-001', 'Solid oak coffee table', 2, 5, 249.99, 299.99, 120.00, TRUE, FALSE),
('Garden Tools Set', 'garden-tools-set', 'HOME-GT-001', 'Complete garden tool kit', 2, 4, 89.99, 99.99, 40.00, TRUE, FALSE),
('Backpack Hiking', 'backpack-hiking', 'SPORT-BP-001', 'Durable hiking backpack', 4, 9, 69.99, 79.99, 30.00, TRUE, FALSE);

-- Insert product images
INSERT INTO product_images (product_id, image_url, alt_text, display_order, is_primary) VALUES
(1, 'https://images.example.com/laptop-pro-15-1.jpg', 'Laptop Pro 15 Front View', 1, TRUE),
(1, 'https://images.example.com/laptop-pro-15-2.jpg', 'Laptop Pro 15 Side View', 2, FALSE),
(2, 'https://images.example.com/smartphone-x-1.jpg', 'Smartphone X Front', 1, TRUE),
(3, 'https://images.example.com/wireless-mouse-1.jpg', 'Wireless Mouse', 1, TRUE),
(4, 'https://images.example.com/office-chair-1.jpg', 'Office Chair Deluxe', 1, TRUE);

-- Insert inventory
INSERT INTO inventory (product_id, warehouse_id, quantity, reserved_quantity, reorder_point) VALUES
(1, 1, 50, 5, 10),
(1, 2, 45, 3, 10),
(2, 1, 100, 10, 20),
(2, 2, 95, 8, 20),
(3, 1, 200, 15, 30),
(4, 1, 30, 2, 5),
(4, 3, 25, 1, 5),
(5, 1, 80, 5, 15),
(6, 2, 120, 10, 25),
(7, 1, 150, 12, 30),
(8, 1, 300, 20, 50),
(9, 1, 180, 15, 40),
(10, 1, 75, 5, 15),
(11, 2, 60, 4, 10),
(12, 1, 500, 30, 100),
(13, 3, 20, 1, 5),
(14, 1, 40, 3, 10),
(15, 2, 70, 5, 15);

-- Insert shipping carriers
INSERT INTO shipping_carriers (name, code, website) VALUES
('FedEx', 'FEDEX', 'https://www.fedex.com'),
('UPS', 'UPS', 'https://www.ups.com'),
('USPS', 'USPS', 'https://www.usps.com'),
('DHL', 'DHL', 'https://www.dhl.com');

-- Insert coupons
INSERT INTO coupons (code, description, discount_type, discount_value, min_order_amount, usage_limit, is_active, starts_at, expires_at) VALUES
('WELCOME10', '10% off first order', 'percentage', 10.00, 50.00, 1000, TRUE, CURRENT_TIMESTAMP - INTERVAL '30 days', CURRENT_TIMESTAMP + INTERVAL '30 days'),
('SAVE20', '$20 off orders over $100', 'fixed', 20.00, 100.00, 500, TRUE, CURRENT_TIMESTAMP - INTERVAL '15 days', CURRENT_TIMESTAMP + INTERVAL '45 days'),
('FREESHIP', 'Free shipping', 'fixed', 10.00, 75.00, NULL, TRUE, CURRENT_TIMESTAMP - INTERVAL '10 days', CURRENT_TIMESTAMP + INTERVAL '60 days');

-- Insert orders
INSERT INTO orders (order_number, user_id, status, subtotal, tax_amount, shipping_amount, discount_amount, total_amount, shipping_address_id, billing_address_id, created_at, completed_at) VALUES
('ORD-2024-0001', 1, 'delivered', 1329.98, 106.40, 10.00, 0.00, 1446.38, 1, 2, CURRENT_TIMESTAMP - INTERVAL '30 days', CURRENT_TIMESTAMP - INTERVAL '25 days'),
('ORD-2024-0002', 2, 'delivered', 899.99, 72.00, 10.00, 89.90, 892.09, 3, 3, CURRENT_TIMESTAMP - INTERVAL '28 days', CURRENT_TIMESTAMP - INTERVAL '23 days'),
('ORD-2024-0003', 3, 'delivered', 329.98, 26.40, 10.00, 0.00, 366.38, 4, 4, CURRENT_TIMESTAMP - INTERVAL '25 days', CURRENT_TIMESTAMP - INTERVAL '20 days'),
('ORD-2024-0004', 1, 'shipped', 179.97, 14.40, 10.00, 0.00, 204.37, 1, 2, CURRENT_TIMESTAMP - INTERVAL '5 days', NULL),
('ORD-2024-0005', 4, 'processing', 549.98, 44.00, 10.00, 20.00, 583.98, 5, 5, CURRENT_TIMESTAMP - INTERVAL '3 days', NULL),
('ORD-2024-0006', 5, 'pending', 129.99, 10.40, 10.00, 12.99, 137.40, 6, 6, CURRENT_TIMESTAMP - INTERVAL '1 day', NULL),
('ORD-2024-0007', 6, 'cancelled', 299.99, 24.00, 10.00, 0.00, 333.99, 7, 7, CURRENT_TIMESTAMP - INTERVAL '10 days', NULL);

-- Insert order items
INSERT INTO order_items (order_id, product_id, product_name, sku, quantity, unit_price, total_price) VALUES
(1, 1, 'Laptop Pro 15', 'TECH-LP-001', 1, 1299.99, 1299.99),
(1, 3, 'Wireless Mouse', 'TECH-MS-001', 1, 29.99, 29.99),
(2, 2, 'Smartphone X', 'TECH-SP-001', 1, 899.99, 899.99),
(3, 4, 'Office Chair Deluxe', 'HOME-CH-001', 1, 299.99, 299.99),
(3, 3, 'Wireless Mouse', 'TECH-MS-001', 1, 29.99, 29.99),
(4, 6, 'Running Shoes Pro', 'SPORT-SH-001', 1, 129.99, 129.99),
(4, 7, 'Yoga Mat Premium', 'SPORT-YM-001', 1, 39.99, 39.99),
(4, 12, 'USB-C Cable', 'TECH-CB-001', 1, 14.99, 14.99),
(5, 4, 'Office Chair Deluxe', 'HOME-CH-001', 1, 299.99, 299.99),
(5, 13, 'Coffee Table Oak', 'HOME-CT-001', 1, 249.99, 249.99),
(6, 6, 'Running Shoes Pro', 'SPORT-SH-001', 1, 129.99, 129.99),
(7, 4, 'Office Chair Deluxe', 'HOME-CH-001', 1, 299.99, 299.99);

-- Insert payments
INSERT INTO payments (order_id, payment_method, status, amount, transaction_id, payment_gateway, processed_at) VALUES
(1, 'credit_card', 'completed', 1446.38, 'txn_001', 'Stripe', CURRENT_TIMESTAMP - INTERVAL '30 days'),
(2, 'paypal', 'completed', 892.09, 'txn_002', 'PayPal', CURRENT_TIMESTAMP - INTERVAL '28 days'),
(3, 'credit_card', 'completed', 366.38, 'txn_003', 'Stripe', CURRENT_TIMESTAMP - INTERVAL '25 days'),
(4, 'credit_card', 'completed', 204.37, 'txn_004', 'Stripe', CURRENT_TIMESTAMP - INTERVAL '5 days'),
(5, 'debit_card', 'completed', 583.98, 'txn_005', 'Stripe', CURRENT_TIMESTAMP - INTERVAL '3 days'),
(6, 'credit_card', 'pending', 137.40, NULL, 'Stripe', NULL),
(7, 'credit_card', 'refunded', 333.99, 'txn_007', 'Stripe', CURRENT_TIMESTAMP - INTERVAL '10 days');

-- Insert shipments
INSERT INTO shipments (order_id, carrier_id, tracking_number, warehouse_id, status, shipped_at, estimated_delivery, delivered_at) VALUES
(1, 1, 'FDX123456789', 1, 'delivered', CURRENT_TIMESTAMP - INTERVAL '29 days', CURRENT_TIMESTAMP - INTERVAL '25 days', CURRENT_TIMESTAMP - INTERVAL '25 days'),
(2, 2, 'UPS987654321', 1, 'delivered', CURRENT_TIMESTAMP - INTERVAL '27 days', CURRENT_TIMESTAMP - INTERVAL '23 days', CURRENT_TIMESTAMP - INTERVAL '23 days'),
(3, 1, 'FDX111222333', 1, 'delivered', CURRENT_TIMESTAMP - INTERVAL '24 days', CURRENT_TIMESTAMP - INTERVAL '20 days', CURRENT_TIMESTAMP - INTERVAL '20 days'),
(4, 3, 'USPS444555666', 1, 'in_transit', CURRENT_TIMESTAMP - INTERVAL '4 days', CURRENT_TIMESTAMP + INTERVAL '1 day', NULL);

-- Insert product reviews
INSERT INTO product_reviews (product_id, user_id, order_id, rating, title, comment, is_verified_purchase, is_approved, helpful_count) VALUES
(1, 1, 1, 5, 'Excellent laptop!', 'This laptop exceeded my expectations. Fast, reliable, and great build quality.', TRUE, TRUE, 15),
(3, 1, 1, 4, 'Good mouse', 'Comfortable and responsive. Battery life could be better.', TRUE, TRUE, 8),
(2, 2, 2, 5, 'Best phone ever', 'Amazing camera quality and battery life. Highly recommend!', TRUE, TRUE, 23),
(4, 3, 3, 5, 'Super comfortable', 'My back pain is gone after using this chair. Worth every penny.', TRUE, TRUE, 12),
(3, 3, 3, 3, 'Average mouse', 'Works fine but nothing special. Expected more for the price.', TRUE, TRUE, 5),
(6, 1, 4, 5, 'Perfect running shoes', 'Great cushioning and support. My new favorite running shoes.', TRUE, TRUE, 9),
(7, 1, 4, 4, 'Good yoga mat', 'Non-slip surface works well. A bit thin for my preference.', TRUE, TRUE, 4);

-- Insert wishlists
INSERT INTO wishlists (user_id, name, is_public) VALUES
(1, 'My Wishlist', FALSE),
(2, 'Tech Wishlist', TRUE),
(3, 'Home Office Setup', FALSE);

-- Insert wishlist items
INSERT INTO wishlist_items (wishlist_id, product_id) VALUES
(1, 11), (1, 13), (1, 15),
(2, 1), (2, 2),
(3, 4), (3, 5), (3, 13);

-- ============================================================================
-- DATABASE STATISTICS
-- ============================================================================

VACUUM ANALYZE;

SELECT
    'Database' AS object_type,
    current_database() AS name,
    'E-commerce platform with 25 tables, 6 views, 4 types' AS description
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
WHERE table_schema = 'public';
