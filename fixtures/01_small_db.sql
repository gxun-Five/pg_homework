-- ============================================================================
-- Small Database: Blog System
-- ============================================================================
-- Description: A simple blog platform with users, posts, comments, and tags
-- Tables: 7 | Views: 3 | Types: 2 | Indexes: 12
-- ============================================================================

DROP DATABASE IF EXISTS blog_small;
CREATE DATABASE blog_small;
\c blog_small;

-- ============================================================================
-- CUSTOM TYPES
-- ============================================================================

-- User role enumeration
CREATE TYPE user_role AS ENUM ('admin', 'author', 'reader');

-- Post status enumeration
CREATE TYPE post_status AS ENUM ('draft', 'published', 'archived');

-- ============================================================================
-- TABLES
-- ============================================================================

-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role user_role DEFAULT 'reader',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE users IS 'Blog users with role-based access';
COMMENT ON COLUMN users.role IS 'User role: admin, author, or reader';

-- Categories table
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE categories IS 'Blog post categories';

-- Posts table
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    excerpt TEXT,
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    status post_status DEFAULT 'draft',
    view_count INTEGER DEFAULT 0,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE posts IS 'Blog posts with authors and categories';
COMMENT ON COLUMN posts.status IS 'Post publication status';

-- Tags table
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE tags IS 'Tags for categorizing posts';

-- Post-Tag junction table
CREATE TABLE post_tags (
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (post_id, tag_id)
);

COMMENT ON TABLE post_tags IS 'Many-to-many relationship between posts and tags';

-- Comments table
CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE comments IS 'User comments on posts with threading support';
COMMENT ON COLUMN comments.parent_id IS 'Parent comment ID for nested replies';

-- User sessions table
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    logout_time TIMESTAMP,
    ip_address INET,
    user_agent TEXT
);

COMMENT ON TABLE user_sessions IS 'User login session tracking';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Users indexes
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_created_at ON users(created_at DESC);

-- Posts indexes
CREATE INDEX idx_posts_author_id ON posts(author_id);
CREATE INDEX idx_posts_category_id ON posts(category_id);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_published_at ON posts(published_at DESC) WHERE status = 'published';
CREATE INDEX idx_posts_created_at ON posts(created_at DESC);

-- Comments indexes
CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_comments_user_id ON comments(user_id);
CREATE INDEX idx_comments_parent_id ON comments(parent_id);

-- Sessions indexes
CREATE INDEX idx_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_sessions_login_time ON user_sessions(login_time DESC);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: Published posts with author and category info
CREATE VIEW published_posts AS
SELECT
    p.id,
    p.title,
    p.slug,
    p.excerpt,
    p.view_count,
    p.published_at,
    u.username AS author_name,
    u.full_name AS author_full_name,
    c.name AS category_name,
    c.slug AS category_slug,
    COUNT(DISTINCT cm.id) AS comment_count
FROM posts p
JOIN users u ON p.author_id = u.id
LEFT JOIN categories c ON p.category_id = c.id
LEFT JOIN comments cm ON p.id = cm.post_id
WHERE p.status = 'published'
GROUP BY p.id, u.username, u.full_name, c.name, c.slug;

COMMENT ON VIEW published_posts IS 'Published posts with aggregated metadata';

-- View: User statistics
CREATE VIEW user_stats AS
SELECT
    u.id,
    u.username,
    u.full_name,
    u.role,
    COUNT(DISTINCT p.id) AS post_count,
    COUNT(DISTINCT c.id) AS comment_count,
    MAX(p.published_at) AS last_post_date,
    MAX(c.created_at) AS last_comment_date
FROM users u
LEFT JOIN posts p ON u.id = p.author_id AND p.status = 'published'
LEFT JOIN comments c ON u.id = c.user_id
GROUP BY u.id, u.username, u.full_name, u.role;

COMMENT ON VIEW user_stats IS 'User activity statistics';

-- View: Popular tags
CREATE VIEW popular_tags AS
SELECT
    t.id,
    t.name,
    t.slug,
    COUNT(pt.post_id) AS post_count,
    MAX(p.published_at) AS last_used_date
FROM tags t
LEFT JOIN post_tags pt ON t.id = pt.tag_id
LEFT JOIN posts p ON pt.post_id = p.id AND p.status = 'published'
GROUP BY t.id, t.name, t.slug
ORDER BY post_count DESC;

COMMENT ON VIEW popular_tags IS 'Tags sorted by usage frequency';

-- ============================================================================
-- SAMPLE DATA
-- ============================================================================

-- Insert users
INSERT INTO users (username, email, full_name, role) VALUES
('admin', 'admin@blog.com', 'Admin User', 'admin'),
('alice', 'alice@blog.com', 'Alice Johnson', 'author'),
('bob', 'bob@blog.com', 'Bob Smith', 'author'),
('charlie', 'charlie@blog.com', 'Charlie Brown', 'reader'),
('diana', 'diana@blog.com', 'Diana Prince', 'reader'),
('evan', 'evan@blog.com', 'Evan Williams', 'reader'),
('frank', 'frank@blog.com', 'Frank Miller', 'author'),
('grace', 'grace@blog.com', 'Grace Hopper', 'reader');

-- Insert categories
INSERT INTO categories (name, slug, description) VALUES
('Technology', 'technology', 'Articles about technology and programming'),
('Travel', 'travel', 'Travel guides and experiences'),
('Food', 'food', 'Recipes and restaurant reviews'),
('Lifestyle', 'lifestyle', 'Life tips and personal development'),
('Business', 'business', 'Business insights and entrepreneurship');

-- Insert tags
INSERT INTO tags (name, slug) VALUES
('Python', 'python'),
('JavaScript', 'javascript'),
('Tutorial', 'tutorial'),
('Review', 'review'),
('Guide', 'guide'),
('Opinion', 'opinion'),
('News', 'news'),
('Tips', 'tips');

-- Insert posts
INSERT INTO posts (title, slug, content, excerpt, author_id, category_id, status, view_count, published_at) VALUES
('Getting Started with Python', 'getting-started-with-python',
 'Python is a versatile programming language...',
 'Learn the basics of Python programming',
 2, 1, 'published', 1523, CURRENT_TIMESTAMP - INTERVAL '30 days'),

('Top 10 Travel Destinations in 2024', 'top-10-travel-destinations-2024',
 'Discover the most amazing places to visit...',
 'A curated list of must-visit places',
 3, 2, 'published', 2341, CURRENT_TIMESTAMP - INTERVAL '25 days'),

('Homemade Pizza Recipe', 'homemade-pizza-recipe',
 'Making pizza at home is easier than you think...',
 'Step-by-step guide to perfect homemade pizza',
 7, 3, 'published', 892, CURRENT_TIMESTAMP - INTERVAL '20 days'),

('Time Management Tips for Developers', 'time-management-tips-developers',
 'As a developer, managing your time effectively...',
 'Productivity tips for software developers',
 2, 4, 'published', 1654, CURRENT_TIMESTAMP - INTERVAL '15 days'),

('Starting Your Own Business', 'starting-your-own-business',
 'Entrepreneurship is a challenging but rewarding journey...',
 'Essential steps to launch your startup',
 3, 5, 'published', 743, CURRENT_TIMESTAMP - INTERVAL '10 days'),

('Advanced JavaScript Patterns', 'advanced-javascript-patterns',
 'Modern JavaScript offers powerful patterns...',
 'Design patterns in modern JavaScript',
 2, 1, 'draft', 0, NULL),

('Hidden Gems in Tokyo', 'hidden-gems-tokyo',
 'Beyond the typical tourist spots, Tokyo offers...',
 'Discover lesser-known attractions in Tokyo',
 3, 2, 'published', 1205, CURRENT_TIMESTAMP - INTERVAL '5 days'),

('Healthy Breakfast Ideas', 'healthy-breakfast-ideas',
 'Start your day right with these nutritious breakfast options...',
 'Quick and healthy breakfast recipes',
 7, 3, 'published', 567, CURRENT_TIMESTAMP - INTERVAL '3 days'),

('Mindfulness in Daily Life', 'mindfulness-daily-life',
 'Incorporating mindfulness into your routine...',
 'Practical mindfulness techniques',
 2, 4, 'archived', 2100, CURRENT_TIMESTAMP - INTERVAL '60 days'),

('Remote Work Best Practices', 'remote-work-best-practices',
 'Working from home requires different strategies...',
 'How to be productive working remotely',
 3, 5, 'published', 1876, CURRENT_TIMESTAMP - INTERVAL '2 days');

-- Insert post-tag relationships
INSERT INTO post_tags (post_id, tag_id) VALUES
(1, 1), (1, 3),  -- Python tutorial
(2, 4), (2, 5),  -- Travel review/guide
(3, 5), (3, 8),  -- Recipe guide/tips
(4, 8), (4, 6),  -- Tips/opinion
(5, 5), (5, 6),  -- Business guide/opinion
(6, 2), (6, 3),  -- JavaScript tutorial
(7, 4), (7, 5),  -- Travel review/guide
(8, 5), (8, 8),  -- Food guide/tips
(9, 6), (9, 8),  -- Lifestyle opinion/tips
(10, 6), (10, 8); -- Business opinion/tips

-- Insert comments
INSERT INTO comments (post_id, user_id, parent_id, content) VALUES
(1, 4, NULL, 'Great introduction to Python! Very helpful for beginners.'),
(1, 5, NULL, 'I have been looking for a tutorial like this. Thanks!'),
(1, 6, 1, 'I agree, this is the best Python tutorial I have found.'),
(2, 4, NULL, 'I visited 3 of these places last year. Highly recommend!'),
(2, 5, NULL, 'Adding these to my bucket list!'),
(3, 5, NULL, 'Tried this recipe yesterday. The pizza was delicious!'),
(3, 6, NULL, 'What type of flour do you recommend?'),
(3, 7, 6, 'I use bread flour for a chewier crust.'),
(4, 6, NULL, 'These tips really helped me stay focused. Thank you!'),
(4, 8, NULL, 'Time blocking has changed my life!'),
(5, 4, NULL, 'Very insightful article about entrepreneurship.'),
(7, 5, NULL, 'Tokyo is amazing! Thanks for these hidden spots.'),
(7, 4, 12, 'Have you been to the Nezu Museum? It is beautiful.'),
(8, 6, NULL, 'Love these breakfast ideas. Quick and healthy!'),
(10, 4, NULL, 'Remote work definitely requires discipline.'),
(10, 5, NULL, 'I struggle with work-life balance when working from home.'),
(10, 8, 15, 'Setting boundaries is key. I have a dedicated workspace now.');

-- Insert user sessions
INSERT INTO user_sessions (user_id, login_time, logout_time, ip_address) VALUES
(1, CURRENT_TIMESTAMP - INTERVAL '1 hour', CURRENT_TIMESTAMP - INTERVAL '30 minutes', '192.168.1.1'),
(2, CURRENT_TIMESTAMP - INTERVAL '2 hours', CURRENT_TIMESTAMP - INTERVAL '1 hour', '192.168.1.2'),
(3, CURRENT_TIMESTAMP - INTERVAL '3 hours', CURRENT_TIMESTAMP - INTERVAL '2 hours', '192.168.1.3'),
(4, CURRENT_TIMESTAMP - INTERVAL '4 hours', CURRENT_TIMESTAMP - INTERVAL '3 hours', '192.168.1.4'),
(5, CURRENT_TIMESTAMP - INTERVAL '5 hours', NULL, '192.168.1.5'),
(6, CURRENT_TIMESTAMP - INTERVAL '30 minutes', NULL, '192.168.1.6'),
(2, CURRENT_TIMESTAMP - INTERVAL '1 day', CURRENT_TIMESTAMP - INTERVAL '23 hours', '192.168.1.2'),
(3, CURRENT_TIMESTAMP - INTERVAL '2 days', CURRENT_TIMESTAMP - INTERVAL '1 day 23 hours', '192.168.1.3'),
(4, CURRENT_TIMESTAMP - INTERVAL '3 days', CURRENT_TIMESTAMP - INTERVAL '2 days 22 hours', '192.168.1.4');

-- ============================================================================
-- DATABASE STATISTICS
-- ============================================================================

-- Vacuum and analyze for optimal performance
VACUUM ANALYZE;

-- Display summary
SELECT
    'Database' AS object_type,
    current_database() AS name,
    'Small blog system with 7 tables, 3 views, 2 types' AS description
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
    'Data Rows' AS object_type,
    SUM(n_live_tup)::text AS name,
    'Total rows across all tables' AS description
FROM pg_stat_user_tables;
