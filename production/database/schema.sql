-- ============================================================
-- TaskFlow AI Support Agent — PostgreSQL Database Schema
-- CRM Digital FTE Factory Final Hackathon 5
--
-- Database: PostgreSQL 15+
-- Schema: taskflow_support
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- ENUM TYPES
-- ============================================================

DO $$ BEGIN
    CREATE TYPE channel_type AS ENUM ('email', 'whatsapp', 'web_form');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE ticket_priority AS ENUM ('P1', 'P2', 'P3', 'P4');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE ticket_status AS ENUM ('open', 'in_progress', 'responded', 'escalated', 'resolved', 'closed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE resolution_status AS ENUM ('new', 'in_progress', 'resolved', 'escalated', 'closed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE escalation_team_type AS ENUM (
        'security', 'engineering', 'billing', 'sales',
        'support', 'customer_success', 'legal', 'product'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE escalation_status AS ENUM ('pending', 'assigned', 'in_progress', 'resolved', 'closed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE message_role AS ENUM ('customer', 'agent', 'system');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE customer_tier AS ENUM ('free', 'starter', 'professional', 'enterprise', 'unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE kb_topic AS ENUM (
        'password_reset', 'create_project', 'invite_team_members',
        'kanban_board', 'pricing'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ============================================================
-- SEQUENCES (must be created before tables that use them)
-- ============================================================

CREATE SEQUENCE IF NOT EXISTS customer_seq START 1;
CREATE SEQUENCE IF NOT EXISTS ticket_seq START 1;
CREATE SEQUENCE IF NOT EXISTS escalation_seq START 1;
CREATE SEQUENCE IF NOT EXISTS message_seq START 1;
CREATE SEQUENCE IF NOT EXISTS conversation_seq START 1;
CREATE SEQUENCE IF NOT EXISTS audit_seq START 1;


-- ============================================================
-- 1. CUSTOMERS
-- ============================================================

CREATE TABLE IF NOT EXISTS customers (
    customer_id       VARCHAR(20)     PRIMARY KEY DEFAULT 'CUST-' || LPAD(NEXTVAL('customer_seq')::TEXT, 4, '0'),
    name              VARCHAR(200)    NOT NULL,
    email             VARCHAR(320)    UNIQUE,
    phone             VARCHAR(30)     UNIQUE,
    tier              customer_tier   NOT NULL DEFAULT 'unknown',
    channels_seen     channel_type[]  NOT NULL DEFAULT '{}',
    total_tickets     INTEGER         NOT NULL DEFAULT 0,
    resolved_tickets  INTEGER         NOT NULL DEFAULT 0,
    escalated_tickets INTEGER         NOT NULL DEFAULT 0,
    sentiment_history JSONB           NOT NULL DEFAULT '[]'::JSONB,
    topic_history     JSONB           NOT NULL DEFAULT '[]'::JSONB,
    last_contact      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_email_or_phone CHECK (email IS NOT NULL OR phone IS NOT NULL)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone) WHERE phone IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_customers_tier ON customers(tier);
CREATE INDEX IF NOT EXISTS idx_customers_last_contact ON customers(last_contact);
CREATE INDEX IF NOT EXISTS idx_customers_created_at ON customers(created_at);

-- Comments
COMMENT ON TABLE customers IS 'Customer profiles with cross-channel identity resolution.';
COMMENT ON COLUMN customers.channels_seen IS 'Array of distinct channels the customer has used.';
COMMENT ON COLUMN customers.sentiment_history IS 'JSON array of [timestamp, score] pairs.';
COMMENT ON COLUMN customers.topic_history IS 'JSON array of [timestamp, topic] pairs.';


-- ============================================================
-- 2. TICKETS
-- ============================================================

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id       VARCHAR(20)       PRIMARY KEY DEFAULT 'TICKET-' || LPAD(NEXTVAL('ticket_seq')::TEXT, 4, '0'),
    customer_id     VARCHAR(20)       NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    channel         channel_type      NOT NULL,
    subject         VARCHAR(500),
    message         TEXT              NOT NULL,
    status          ticket_status     NOT NULL DEFAULT 'open',
    priority        ticket_priority   NOT NULL DEFAULT 'P3',
    topic           VARCHAR(50),
    sentiment_score INTEGER           DEFAULT 0,
    sentiment_label VARCHAR(20),
    ai_attempts     INTEGER           NOT NULL DEFAULT 0,
    is_follow_up    BOOLEAN           NOT NULL DEFAULT FALSE,
    channel_switch  BOOLEAN           NOT NULL DEFAULT FALSE,
    previous_channel channel_type,
    created_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ,

    CONSTRAINT chk_sentiment_score CHECK (sentiment_score BETWEEN -2 AND 2)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tickets_customer ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_channel ON tickets(channel);
CREATE INDEX IF NOT EXISTS idx_tickets_topic ON tickets(topic);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at);
CREATE INDEX IF NOT EXISTS idx_tickets_updated_at ON tickets(updated_at);
CREATE INDEX IF NOT EXISTS idx_tickets_customer_status ON tickets(customer_id, status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority_status ON tickets(priority, status) WHERE status IN ('open', 'escalated');

-- Comments
COMMENT ON TABLE tickets IS 'Support tickets from all channels with AI classification and tracking.';
COMMENT ON COLUMN tickets.topic IS 'Classified topic: password_reset, create_project, etc.';
COMMENT ON COLUMN tickets.ai_attempts IS 'Number of AI resolution attempts.';
COMMENT ON COLUMN tickets.is_follow_up IS 'True if customer has prior ticket on same topic.';
COMMENT ON COLUMN tickets.channel_switch IS 'True if customer used a different channel than before.';


-- ============================================================
-- 3. CONVERSATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id   UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id       VARCHAR(20)       NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    ticket_id         VARCHAR(20)       REFERENCES tickets(ticket_id) ON DELETE SET NULL,
    turn_number       INTEGER           NOT NULL,
    channel           channel_type      NOT NULL,
    topic             VARCHAR(50),
    sentiment_score   INTEGER           DEFAULT 0,
    sentiment_label   VARCHAR(20),
    resolution_status resolution_status NOT NULL DEFAULT 'new',
    created_at        TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_conv_sentiment CHECK (sentiment_score BETWEEN -2 AND 2),
    CONSTRAINT chk_turn_number CHECK (turn_number > 0),
    UNIQUE (customer_id, turn_number)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_conversations_customer ON conversations(customer_id);
CREATE INDEX IF NOT EXISTS idx_conversations_ticket ON conversations(ticket_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(resolution_status);
CREATE INDEX IF NOT EXISTS idx_conversations_customer_turn ON conversations(customer_id, turn_number);

-- Comments
COMMENT ON TABLE conversations IS 'Individual conversation turns with sentiment and resolution tracking.';
COMMENT ON COLUMN conversations.turn_number IS 'Sequential turn number per customer.';


-- ============================================================
-- 4. MESSAGES
-- ============================================================

CREATE TABLE IF NOT EXISTS messages (
    message_id        UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id   UUID              NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    ticket_id         VARCHAR(20)       REFERENCES tickets(ticket_id) ON DELETE SET NULL,
    role              message_role      NOT NULL,
    content           TEXT              NOT NULL,
    formatted_content TEXT,
    channel           channel_type      NOT NULL,
    agent_name        VARCHAR(200),
    metadata          JSONB             NOT NULL DEFAULT '{}'::JSONB,
    created_at        TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_content_length CHECK (LENGTH(content) > 0 AND LENGTH(content) <= 50000)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_ticket ON messages(ticket_id);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created ON messages(conversation_id, created_at);

-- Comments
COMMENT ON TABLE messages IS 'Individual messages within conversations (customer or agent side).';
COMMENT ON COLUMN messages.formatted_content IS 'Channel-formatted version of the content.';
COMMENT ON COLUMN messages.metadata IS 'Extra data: escalation info, KB references, etc.';


-- ============================================================
-- 5. ESCALATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS escalations (
    escalation_id   VARCHAR(20)           PRIMARY KEY DEFAULT 'ESC-' || LPAD(NEXTVAL('escalation_seq')::TEXT, 4, '0'),
    ticket_id       VARCHAR(20)           NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    customer_id     VARCHAR(20)           NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    team            escalation_team_type  NOT NULL,
    team_email      VARCHAR(320),
    reason          TEXT                  NOT NULL,
    summary         TEXT,
    priority        ticket_priority       NOT NULL DEFAULT 'P2',
    sla             VARCHAR(50)           NOT NULL,
    status          escalation_status     NOT NULL DEFAULT 'pending',
    assigned_to     VARCHAR(200),
    notes           TEXT,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ           NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ           NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_reason_length CHECK (LENGTH(reason) <= 2000),
    CONSTRAINT chk_summary_length CHECK (summary IS NULL OR LENGTH(summary) <= 10000)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_escalations_ticket ON escalations(ticket_id);
CREATE INDEX IF NOT EXISTS idx_escalations_customer ON escalations(customer_id);
CREATE INDEX IF NOT EXISTS idx_escalations_team ON escalations(team);
CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);
CREATE INDEX IF NOT EXISTS idx_escalations_priority ON escalations(priority);
CREATE INDEX IF NOT EXISTS idx_escalations_created_at ON escalations(created_at);
CREATE INDEX IF NOT EXISTS idx_escalations_team_status ON escalations(team, status) WHERE status = 'pending';

-- Comments
COMMENT ON TABLE escalations IS 'Tickets escalated to human support teams with routing and SLA tracking.';
COMMENT ON COLUMN escalations.sla IS 'Response SLA timeframe (e.g., "30 minutes", "1 hour").';
COMMENT ON COLUMN escalations.assigned_to IS 'Human agent who took ownership of the escalation.';


-- ============================================================
-- 6. KNOWLEDGE BASE
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_base (
    kb_id           UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic           kb_topic          NOT NULL UNIQUE,
    title           VARCHAR(200)      NOT NULL,
    overview        TEXT              NOT NULL,
    content         JSONB             NOT NULL DEFAULT '{}'::JSONB,
    keywords        TEXT[]            NOT NULL DEFAULT '{}',
    version         INTEGER           NOT NULL DEFAULT 1,
    is_active       BOOLEAN           NOT NULL DEFAULT TRUE,
    created_by      VARCHAR(200)      NOT NULL DEFAULT 'system',
    updated_by      VARCHAR(200)      NOT NULL DEFAULT 'system',
    created_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_keywords_not_empty CHECK (array_length(keywords, 1) > 0)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_kb_topic ON knowledge_base(topic);
CREATE INDEX IF NOT EXISTS idx_kb_active ON knowledge_base(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_kb_keywords ON knowledge_base USING GIN(keywords);
CREATE INDEX IF NOT EXISTS idx_kb_content ON knowledge_base USING GIN(content);

-- Comments
COMMENT ON TABLE knowledge_base IS 'Product documentation organized by topic with keyword search.';
COMMENT ON COLUMN knowledge_base.content IS 'Structured JSON with sections: common_issues, troubleshooting, support_actions, etc.';
COMMENT ON COLUMN knowledge_base.keywords IS 'Array of keywords for full-text matching.';
COMMENT ON COLUMN knowledge_base.version IS 'Incremented on each content update.';


-- ============================================================
-- 7. KNOWLEDGE BASE VERSION HISTORY
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_base_history (
    history_id      UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
    kb_id           UUID              NOT NULL REFERENCES knowledge_base(kb_id) ON DELETE CASCADE,
    topic           kb_topic          NOT NULL,
    version         INTEGER           NOT NULL,
    content_snapshot JSONB            NOT NULL,
    keywords_snapshot TEXT[]          NOT NULL,
    changed_by      VARCHAR(200)      NOT NULL,
    change_reason   VARCHAR(500),
    changed_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_kb_history_kb ON knowledge_base_history(kb_id);
CREATE INDEX IF NOT EXISTS idx_kb_history_topic_version ON knowledge_base_history(topic, version);

-- Comments
COMMENT ON TABLE knowledge_base_history IS 'Version history for knowledge base content changes.';


-- ============================================================
-- 8. IDENTITY MAP (email/phone -> customer_id)
-- ============================================================

CREATE TABLE IF NOT EXISTS identity_map (
    identity_id     UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id     VARCHAR(20)       NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    identifier_type VARCHAR(10)       NOT NULL CHECK (identifier_type IN ('email', 'phone')),
    identifier_value VARCHAR(320)     NOT NULL,
    is_primary      BOOLEAN           NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    UNIQUE (identifier_type, identifier_value)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_identity_customer ON identity_map(customer_id);
CREATE INDEX IF NOT EXISTS idx_identity_value ON identity_map(identifier_value);
CREATE INDEX IF NOT EXISTS idx_identity_type_value ON identity_map(identifier_type, identifier_value);

-- Comments
COMMENT ON TABLE identity_map IS 'Maps email addresses and phone numbers to customer IDs for cross-channel resolution.';


-- ============================================================
-- 9. AUDIT LOG
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id        UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type     VARCHAR(50)       NOT NULL,
    entity_id       VARCHAR(50)       NOT NULL,
    action          VARCHAR(50)       NOT NULL,
    old_values      JSONB,
    new_values      JSONB,
    performed_by    VARCHAR(200)      NOT NULL DEFAULT 'system',
    ip_address      INET,
    user_agent      VARCHAR(500),
    created_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_performed_by ON audit_log(performed_by);

-- Comments
COMMENT ON TABLE audit_log IS 'Audit trail for all data modifications.';


-- ============================================================
-- 10. SYSTEM CONFIG
-- ============================================================

CREATE TABLE IF NOT EXISTS system_config (
    config_key      VARCHAR(100)      PRIMARY KEY,
    config_value    JSONB             NOT NULL,
    description     TEXT,
    updated_by      VARCHAR(200),
    updated_at      TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

-- Comments
COMMENT ON TABLE system_config IS 'Runtime configuration (SLA times, escalation rules, feature flags).';

-- Seed default config
INSERT INTO system_config (config_key, config_value, description) VALUES
    ('sla_p1', '"30 minutes"', 'P1 response SLA'),
    ('sla_p2', '"1 hour"', 'P2 response SLA'),
    ('sla_p3', '"4 hours"', 'P3 response SLA'),
    ('sla_p4', '"24 hours"', 'P4 response SLA'),
    ('escalation_p1_attempts', '0', 'AI attempts before P1 escalation'),
    ('escalation_p2_attempts', '1', 'AI attempts before P2 escalation'),
    ('escalation_p3_attempts', '2', 'AI attempts before P3 escalation'),
    ('sentiment_escalation_threshold', '-2', 'Sentiment score triggering proactive escalation'),
    ('repeat_offender_threshold', '3', 'Tickets on same issue before auto-escalation'),
    ('repeat_offender_window_hours', '48', 'Time window for repeat offender detection'),
    ('whatsapp_max_response_length', '1000', 'Max characters for WhatsApp responses'),
    ('nonprofit_discount_percent', '50', 'Nonprofit discount percentage')
ON CONFLICT (config_key) DO NOTHING;


-- ============================================================
-- TRIGGERS: Auto-update updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_tickets_updated_at
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_escalations_updated_at
    BEFORE UPDATE ON escalations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_knowledge_base_updated_at
    BEFORE UPDATE ON knowledge_base
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_system_config_updated_at
    BEFORE UPDATE ON system_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- TRIGGER: Auto-increment customer ticket counts
-- ============================================================

CREATE OR REPLACE FUNCTION increment_customer_ticket_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE customers
    SET total_tickets = total_tickets + 1,
        last_contact = NEW.created_at
    WHERE customer_id = NEW.customer_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tickets_customer_count
    AFTER INSERT ON tickets
    FOR EACH ROW EXECUTE FUNCTION increment_customer_ticket_count();


-- ============================================================
-- TRIGGER: Auto-increment conversation turn number
-- ============================================================

CREATE OR REPLACE FUNCTION set_conversation_turn_number()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.turn_number IS NULL THEN
        SELECT COALESCE(MAX(turn_number), 0) + 1
        INTO NEW.turn_number
        FROM conversations
        WHERE customer_id = NEW.customer_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_conversations_turn_number
    BEFORE INSERT ON conversations
    FOR EACH ROW EXECUTE FUNCTION set_conversation_turn_number();


-- ============================================================
-- FULL-TEXT SEARCH: Knowledge Base
-- ============================================================

-- Add tsvector column for full-text search
ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS search_vector TSVECTOR
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', title), 'A') ||
        setweight(to_tsvector('english', overview), 'B') ||
        setweight(to_tsvector('english', array_to_string(keywords, ' ')), 'C') ||
        setweight(to_tsvector('english', content::text), 'D')
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_kb_search_vector ON knowledge_base USING GIN(search_vector);


-- ============================================================
-- VIEWS
-- ============================================================

-- Active tickets by priority
CREATE OR REPLACE VIEW v_active_tickets AS
SELECT
    t.ticket_id,
    t.customer_id,
    c.name AS customer_name,
    c.email AS customer_email,
    c.tier AS customer_tier,
    t.channel,
    t.subject,
    t.priority,
    t.status,
    t.topic,
    t.sentiment_score,
    t.ai_attempts,
    t.is_follow_up,
    t.channel_switch,
    t.created_at,
    t.updated_at,
    e.escalation_id,
    e.team AS escalation_team,
    e.sla AS escalation_sla,
    e.status AS escalation_status
FROM tickets t
JOIN customers c ON t.customer_id = c.customer_id
LEFT JOIN escalations e ON t.ticket_id = e.ticket_id AND e.status IN ('pending', 'assigned')
WHERE t.status IN ('open', 'in_progress', 'escalated')
ORDER BY
    CASE t.priority
        WHEN 'P1' THEN 1
        WHEN 'P2' THEN 2
        WHEN 'P3' THEN 3
        WHEN 'P4' THEN 4
    END,
    t.created_at ASC;

-- Customer 360 view
CREATE OR REPLACE VIEW v_customer_360 AS
SELECT
    c.customer_id,
    c.name,
    c.email,
    c.phone,
    c.tier,
    c.channels_seen,
    c.total_tickets,
    c.resolved_tickets,
    c.escalated_tickets,
    c.last_contact,
    c.created_at,
    COALESCE(AVG(t.sentiment_score), 0) AS avg_sentiment,
    COUNT(t.ticket_id) FILTER (WHERE t.status = 'open') AS open_tickets,
    COUNT(t.ticket_id) FILTER (WHERE t.status = 'escalated') AS escalated_tickets,
    MAX(t.created_at) AS last_ticket_at,
    COUNT(DISTINCT t.channel) AS channels_used
FROM customers c
LEFT JOIN tickets t ON c.customer_id = t.customer_id
GROUP BY c.customer_id, c.name, c.email, c.phone, c.tier, c.channels_seen,
         c.total_tickets, c.resolved_tickets, c.escalated_tickets, c.last_contact, c.created_at;

-- Escalation SLA compliance
CREATE OR REPLACE VIEW v_escalation_sla_compliance AS
SELECT
    e.escalation_id,
    e.ticket_id,
    e.team,
    e.priority,
    e.sla,
    e.status,
    e.created_at,
    e.resolved_at,
    EXTRACT(EPOCH FROM (COALESCE(e.resolved_at, NOW()) - e.created_at)) / 60 AS minutes_elapsed,
    CASE
        WHEN e.sla = '30 minutes' AND EXTRACT(EPOCH FROM (COALESCE(e.resolved_at, NOW()) - e.created_at)) / 60 <= 30 THEN TRUE
        WHEN e.sla = '1 hour' AND EXTRACT(EPOCH FROM (COALESCE(e.resolved_at, NOW()) - e.created_at)) / 60 <= 60 THEN TRUE
        WHEN e.sla = '2 hours' AND EXTRACT(EPOCH FROM (COALESCE(e.resolved_at, NOW()) - e.created_at)) / 60 <= 120 THEN TRUE
        WHEN e.sla = '4 hours' AND EXTRACT(EPOCH FROM (COALESCE(e.resolved_at, NOW()) - e.created_at)) / 60 <= 240 THEN TRUE
        ELSE FALSE
    END AS sla_met
FROM escalations e;


-- ============================================================
-- SEED DATA: Knowledge Base
-- ============================================================

INSERT INTO knowledge_base (topic, title, overview, content, keywords) VALUES
    ('password_reset', 'Password Reset',
     'Users reset passwords via the login page -> Forgot Password? -> enter email -> receive reset link (valid 1 hour) -> set new password.',
     '{
        "requirements": "8+ characters, 1 uppercase, 1 number, 1 special character",
        "common_issues": [
            "Reset email not received: check spam, verify email, wait 5 min, resend available",
            "Reset link expired: link valid for 1 hour, request a new one",
            "Email not found: verify email matches registration, check typos",
            "Password does not meet requirements: must satisfy all complexity rules"
        ],
        "security_notes": [
            "Max 5 failed reset attempts per hour",
            "Account locked after 10 failed attempts",
            "All password changes trigger a notification email"
        ],
        "support_actions": [
            "Verify account status in admin dashboard",
            "Manually trigger reset email if delay > 10 minutes",
            "Escalate if user suspects account compromise"
        ]
     }'::JSONB,
     ARRAY['password', 'reset', 'forgot password', 'login', 'sign in', 'can''t log in', 'cannot log in', 'locked out', 'access my account', 'reset link', 'expired', 'not received', 'didn''t receive']),

    ('create_project', 'Create Project',
     'Log in -> click + New Project (top right) -> fill details -> Create Project.',
     '{
        "fields": "Project Name (required, 100 chars), Description (optional, 5000 chars), Template, Visibility, Dates",
        "tier_limits": {
            "Free": "3 projects, 5 members",
            "Starter": "Unlimited projects, 50 members",
            "Professional": "Unlimited projects, 200 members",
            "Enterprise": "Unlimited projects, unlimited members"
        },
        "common_issues": [
            "Project limit reached: upgrade tier or archive old projects",
            "Can''t add members: check tier limits, ensure invitees have accounts",
            "Template not loading: refresh, try blank project, clear cache",
            "Project not visible: check visibility settings, verify workspace"
        ]
     }'::JSONB,
     ARRAY['create project', 'new project', 'add project', '+ new project', 'can''t create', 'project limit', 'can''t find', 'where is', 'start a project', 'make a project']),

    ('invite_team_members', 'Invite Team Members',
     'Open project -> Team tab -> Invite Members -> enter emails -> select role (Admin/Member/Viewer) -> Send Invites.',
     '{
        "invitation_flow": "Invitee receives email -> if has account, added immediately; if not, prompted to sign up (free) -> then added. Invitation expires after 7 days.",
        "tier_limits": {
            "Free": "5 members",
            "Starter": "50 members",
            "Professional": "200 members",
            "Enterprise": "unlimited members"
        },
        "bulk_import": "Professional+ only. CSV with columns: email, name, role. Max 500 per upload.",
        "common_issues": [
            "Invitee didn''t receive: check spam, verify email, resend, check if already registered",
            "Invite limit reached: check tier limits, upgrade if needed",
            "Wrong role: Admin can change role in Team settings",
            "Can''t find Invite button: only Admins and Members can invite; Viewers cannot"
        ]
     }'::JSONB,
     ARRAY['invite', 'team member', 'add member', 'add user', 'send invite', 'invitation', 'didn''t receive', 'not received', 'bulk import', 'role', 'admin', 'member', 'viewer', 'change role', 'invite limit', 'member limit']),

    ('kanban_board', 'Kanban Board',
     'Default project view. Columns: Backlog, To Do, In Progress, In Review, Done.',
     '{
        "customization": [
            "Add/Remove/Rename columns: Settings -> Manage Columns",
            "Reorder columns: drag and drop headers",
            "WIP limits per column: Professional+ tier"
        ],
        "card_info": "Title, assignee avatar, due date (color-coded), priority, labels, attachments, comments",
        "keyboard_shortcuts": {
            "N": "Create new task",
            "F": "Open filter menu",
            "/": "Focus search bar",
            "Left/Right": "Move card between columns",
            "Delete": "Archive selected card"
        },
        "common_issues": [
            "Cards not draggable: check browser, disable extensions, refresh",
            "Column not showing cards: check WIP limits, verify task status",
            "Slow loading: large boards take time, use filters",
            "Missing cards: check filters, verify not archived/deleted"
        ]
     }'::JSONB,
     ARRAY['kanban', 'board', 'drag', 'drop', 'column', 'card', 'slow', 'loading', 'not visible', 'disappeared', 'missing', 'export', 'pdf', 'custom column', 'add column', 'WIP limit', 'filter', 'shortcut']),

    ('pricing', 'Pricing Tiers',
     'Four tiers: Free ($0), Starter ($12/user/mo), Professional ($25/user/mo), Enterprise (custom).',
     '{
        "tiers": {
            "Free": "$0/mo -- 5 members, 3 projects, basic Kanban, 1 GB storage",
            "Starter": "$12/user/mo -- unlimited projects, 50 members, time tracking, integrations, 50 GB, priority support",
            "Professional": "$25/user/mo -- 200 members, custom workflows, API, advanced reporting, bulk import, 200 GB",
            "Enterprise": "Custom pricing -- unlimited, SSO/SAML, on-premise, dedicated support, 99.99% SLA"
        },
        "billing": [
            "Monthly or annual (save 20% on annual)",
            "14-day free trial for Starter/Professional (no credit card)",
            "30-day money-back guarantee",
            "Upgrade/downgrade anytime, prorated billing",
            "Nonprofit discount: 50% off all paid tiers",
            "Cancel anytime, no fees, data exportable for 30 days",
            "Downgrade: data preserved, features revert at next billing cycle"
        ]
     }'::JSONB,
     ARRAY['pricing', 'plan', 'tier', 'upgrade', 'downgrade', 'cost', 'billing', 'charge', 'refund', 'subscription', 'free trial', 'trial expired', 'enterprise', 'SSO', 'on-premise', 'nonprofit', 'discount', 'switch', 'cancel'])
ON CONFLICT (topic) DO NOTHING;
