# Discovery Log — CRM Digital FTE Factory Final Hackathon 5

**Analysis Date:** 2026-04-07  
**Analyst:** AI Agent  
**Source Files Analyzed:**
- `context/company-profile.md`
- `context/product-docs.md`
- `context/sample-tickets.json` (18 tickets)
- `context/escalation-rules.md`
- `context/brand-voice.md`

---

## 1. Ticket Volume & Channel Distribution

| Channel | Count | Percentage |
|---------|-------|------------|
| **Email** | 6 | 33.3% |
| **WhatsApp** | 6 | 33.3% |
| **Web Form** | 6 | 33.3% |

**Discovery:** The sample set is evenly distributed across all 3 channels. In production, actual distribution may skew — the AI agent must be prepared to handle any channel with equal competence but adapt its response style per `brand-voice.md`.

---

## 2. Topic Distribution Across All Tickets

| Topic | Count | Percentage | Channels Observed |
|-------|-------|------------|-------------------|
| **Kanban Board** | 4 | 22.2% | email, whatsapp, web_form |
| **Pricing** | 4 | 22.2% | whatsapp, web_form, email |
| **Password Reset** | 3 | 16.7% | email, web_form, whatsapp |
| **Invite Team Members** | 3 | 16.7% | web_form, whatsapp, email |
| **Create Project** | 2 | 11.1% | whatsapp, email |
| **Billing** | 1 | 5.6% | web_form |
| **Other (trial expiry, role change, bulk import)** | 1 | 5.6% | email, whatsapp, web_form |

**Discovery:** Kanban Board and Pricing are the dominant topics (combined 44.4%). Password Reset and Invite Team Members are tied at 16.7% each. These 4 topics account for **77.8%** of all tickets.

**Hidden Requirement:** The AI agent should have **fast-path resolution flows** for these top 4 topics, with pre-built troubleshooting trees that minimize back-and-forth.

---

## 3. Priority Distribution

| Priority | Count | Percentage | Escalation Rule |
|----------|-------|------------|-----------------|
| **P1 – Critical** | 1 | 5.6% | Immediate escalation |
| **P2 – High** | 6 | 33.3% | AI attempts once, then escalate |
| **P3 – Medium** | 9 | 50.0% | AI attempts twice, then escalate |
| **P4 – Low** | 2 | 11.1% | AI resolves autonomously |

**Discovery:** 83.3% of tickets (P2 + P3) require the AI to attempt resolution before escalating. Only 5.6% are immediate escalations (P1), and 11.1% are fully AI-handled (P4).

**Hidden Requirement:** The AI agent's **core competency** is handling P2 and P3 tickets — it needs robust troubleshooting logic, not just FAQ retrieval. It must track attempt counts per ticket to know when to escalate.

---

## 4. Channel-Specific Patterns

### 4.1 Email (6 tickets)

| Ticket | Topic | Priority | Key Characteristics |
|--------|-------|----------|---------------------|
| TKT-001 | Password Reset | P2 | Urgent tone, time-sensitive (client presentation) |
| TKT-004 | Kanban Board | P2 | Team impact described, asks about known issues |
| TKT-007 | Kanban Board | P3 | Positive sentiment ("Love the product"), how-to question |
| TKT-010 | Create Project | P3 | Confusion about account state, asks for account check |
| TKT-013 | Invite Members | P3 | How-to question, UI confusion |
| TKT-016 | Pricing | P3 | Downgrade inquiry, data retention concern |

**Email Patterns:**
- Customers write **detailed, structured messages** with context
- Often include **background information** (team size, usage history)
- More likely to express **positive or negative sentiment** explicitly
- Average message length: **longest** among all channels
- Common themes: account state verification, feature how-to, billing concerns

**Hidden Requirements for Email:**
- AI must parse **multi-paragraph messages** and extract key issue + context
- Should acknowledge sentiment (positive or negative) in response
- Should reference account-specific data when customer asks ("Can you check my account?")
- Must handle **compound questions** (e.g., TKT-016 asks about data retention AND billing adjustment)

---

### 4.2 WhatsApp (6 tickets)

| Ticket | Topic | Priority | Key Characteristics |
|--------|-------|----------|---------------------|
| TKT-002 | Create Project | P3 | New user, confused, casual tone |
| TKT-005 | Pricing | P4 | Pre-sales question, team size mentioned, nonprofit discount |
| TKT-008 | Invite Members | P3 | Tier limit hit, upgrade inquiry, cost question |
| TKT-011 | Kanban Board | P3 | Export feature question, stakeholder sharing use case |
| TKT-014 | Password Reset | P2 | Email delivery issue, provides email address |
| TKT-017 | Invite Members | P3 | Bulk import question, tier-appropriate (Professional) |

**WhatsApp Patterns:**
- Messages are **short, conversational, direct**
- Often start with casual greetings ("Hey", "Hi!")
- Frequently include **specific numbers** (team of 8, 50 people, 45 people)
- More likely to be **pre-sales or quick how-to** questions
- Customers provide **phone numbers** instead of emails (some also provide email in message body)
- One non-English greeting (TKT-008: "Hola!")

**Hidden Requirements for WhatsApp:**
- AI must respond in **short, scannable messages** (per brand-voice.md)
- Should use **emojis sparingly** (1-2 max)
- Must extract **numeric details** (team size, counts) to give tier-appropriate answers
- Should be prepared for **multilingual greetings** and respond appropriately
- Must handle **pre-sales questions** (pricing comparisons, discount inquiries) without account lookup
- Response time expectation is **< 15 minutes** (vs. 2 hours for email)

---

### 4.3 Web Form (6 tickets)

| Ticket | Topic | Priority | Key Characteristics |
|--------|-------|----------|---------------------|
| TKT-003 | Invite Members | P3 | Multiple people affected, already tried spam check |
| TKT-006 | Password Reset | P1 | Account locked, admin role, urgent business impact |
| TKT-009 | Billing | P2 | Duplicate charge, specific amounts and dates |
| TKT-012 | Pricing | P2 | Enterprise inquiry, 800 employees, compliance requirements |
| TKT-015 | Kanban Board | P2 | Bug report, reproducible (3x), environment details provided |
| TKT-018 | Pricing | P3 | Trial expiry, data access request, read-only workaround ask |

**Web Form Patterns:**
- Messages are **structured with subjects** (like email but more formal)
- Customers provide **specific technical details** (dates, amounts, browser/OS, reproduction steps)
- More likely to be **bug reports or escalated issues** (highest P1/P2 ratio)
- Often include **business context** (admin role, compliance requirements, team size)
- Customers have **already tried basic troubleshooting** before submitting

**Hidden Requirements for Web Form:**
- AI must parse **subject lines** as primary issue indicators
- Should acknowledge **troubleshooting already attempted** by customer
- Must handle **high-priority tickets** (P1, P2) with appropriate urgency
- Should extract **environment details** (browser, OS) for bug reports
- Must identify **enterprise/compliance keywords** (SSO, on-premise, 800 employees) for sales escalation
- Auto-acknowledgment is sent immediately per company-profile.md — AI should reference this

---

## 5. Cross-Channel Comparison

| Dimension | Email | WhatsApp | Web Form |
|-----------|-------|----------|----------|
| **Avg. Urgency** | Medium-High | Low-Medium | High |
| **Detail Level** | High | Low | Very High |
| **Sentiment Expressed** | Explicit (positive & negative) | Neutral-Positive | Neutral-Negative |
| **Pre-Sales vs. Post-Sales** | Mostly post-sales | Mixed | Mostly post-sales |
| **Bug Reports** | 17% (1/6) | 0% (0/6) | 33% (2/6) |
| **How-To Questions** | 50% (3/6) | 67% (4/6) | 17% (1/6) |
| **Billing/Pricing** | 33% (2/6) | 33% (2/6) | 50% (3/6) |
| **Account Issues** | 33% (2/6) | 17% (1/6) | 33% (2/6) |

**Key Discovery:** Web Form has the highest concentration of **bugs and billing issues** (83% combined). WhatsApp is dominated by **how-to and pre-sales questions** (67%). Email is the most **balanced** channel.

---

## 6. Hidden Requirements Discovered

### 6.1 Account Context Awareness
- **TKT-001, TKT-006, TKT-010, TKT-014** all require the AI to look up account state (locked status, project count, email delivery status)
- **Requirement:** AI must integrate with admin dashboard (`admin.techcorp.internal/users`) to verify account details before responding

### 6.2 Tier-Aware Responses
- **TKT-005** (team of 8, Starter vs. Professional comparison)
- **TKT-008** (Starter plan, 50-member limit hit)
- **TKT-017** (Professional plan, bulk import question)
- **TKT-016** (downgrade from Professional to Starter)
- **Requirement:** AI must know the customer's current tier and tailor answers accordingly (e.g., bulk import is only available on Professional+)

### 6.3 Multi-Question Handling
- **TKT-005:** "What's the difference between Starter and Professional?" + "Do you offer nonprofit discounts?"
- **TKT-016:** "What happens to our data?" + "How does billing adjustment work?"
- **TKT-018:** "Can't access projects" + "Is there read-only access?"
- **Requirement:** AI must identify and answer **all sub-questions** in a single ticket, not just the primary one

### 6.4 Escalation Timing Logic
- **TKT-006** (P1): Account locked → immediate escalation per escalation-rules.md
- **TKT-012** (P2): Enterprise sales inquiry → escalate to Sales within 2 hours
- **TKT-009** (P2): Billing dispute → escalate to Billing Team
- **TKT-015** (P2): Bug report → AI attempts once, then escalate to Engineering
- **Requirement:** AI must track escalation timers and route to correct teams per escalation-rules.md

### 6.5 Emotional Intelligence
- **TKT-001:** Urgent ("client presentation tomorrow")
- **TKT-006:** Urgent ("critical sprint starting", "ASAP")
- **TKT-007:** Positive ("Love the product")
- **TKT-018:** Understanding but requesting exception ("I understand the trial ended but...")
- **Requirement:** AI must detect emotional cues and adjust tone — urgency for time-sensitive issues, warmth for positive sentiment, empathy for frustrated customers

### 6.6 Environment & Reproduction Details
- **TKT-015:** "Using Chrome on Windows", "happened 3 times today"
- **TKT-004:** "team of 30", "200 active tasks", "15-20 seconds to load"
- **Requirement:** AI must extract and preserve technical details for bug reports and escalate them to Engineering with full context

### 6.7 Non-English Support
- **TKT-008:** "Hola!" (Spanish greeting)
- **Escalation-rules.md** mentions: "Language Barriers → Escalate to multilingual support team"
- **Requirement:** AI should detect non-English messages and either respond in that language (if supported) or escalate per escalation rules

### 6.8 Proactive Upsell/Downsell Guidance
- **TKT-005:** Team of 8 considering Starter vs. Professional → AI should recommend based on feature needs
- **TKT-008:** Starter plan, needs 50 members → AI should suggest Professional tier
- **TKT-016:** Wants to downgrade → AI should explain implications without being pushy
- **Requirement:** AI must provide **tier-appropriate recommendations** that balance customer needs with revenue considerations

### 6.9 Data Retention Concerns
- **TKT-016:** "Will we lose anything?" (downgrade)
- **TKT-018:** "Can't access my projects" (trial expiry)
- **Requirement:** AI must clearly explain data preservation policies — data is preserved on downgrade and accessible for 30 days post-cancellation per product-docs.md

### 6.10 Auto-Acknowledgment for Web Form
- **company-profile.md:** Web Form has "auto-acknowledgment"
- **brand-voice.md:** "We've received your request and will respond within [SLA time]"
- **Requirement:** AI must send immediate acknowledgment for web form tickets, then follow up with detailed response

---

## 7. Priority-to-Topic Mapping

| Topic | P1 | P2 | P3 | P4 | Total |
|-------|----|----|----|----|-------|
| Password Reset | 1 (TKT-006) | 2 (TKT-001, TKT-014) | 0 | 0 | 3 |
| Kanban Board | 0 | 2 (TKT-004, TKT-015) | 2 (TKT-007, TKT-011) | 0 | 4 |
| Invite Members | 0 | 0 | 3 (TKT-003, TKT-008, TKT-017) | 0 | 3 |
| Pricing | 0 | 1 (TKT-012) | 2 (TKT-016, TKT-018) | 1 (TKT-005) | 4 |
| Create Project | 0 | 0 | 2 (TKT-002, TKT-010) | 0 | 2 |
| Billing | 0 | 1 (TKT-009) | 0 | 0 | 1 |

**Discovery:** Password Reset is the only topic with a P1 ticket (account lockout). Kanban Board has the most P2 tickets (bugs/performance). Invite Members is exclusively P3 (how-to). Pricing spans all priority levels.

---

## 8. Response Time Requirements by Channel

| Channel | SLA Expectation | Tickets at Risk |
|---------|-----------------|-----------------|
| **WhatsApp** | < 15 minutes | TKT-014 (P2, password reset) — customer waiting 20+ minutes already |
| **Email** | < 2 hours | TKT-001 (P2, urgent presentation tomorrow) |
| **Web Form** | < 4 hours | TKT-006 (P1, account locked — should be 30 min per escalation rules) |

**Hidden Requirement:** WhatsApp has the **shortest expected response time** but the AI may not be optimized for real-time. The system should prioritize WhatsApp tickets for immediate AI processing.

---

## 9. Escalation Readiness Assessment

Based on escalation-rules.md, here's how the 18 tickets should be handled:

| Ticket | Priority | AI Attempts Allowed | Escalation Required? | Target Team |
|--------|----------|---------------------|----------------------|-------------|
| TKT-001 | P2 | 1 | If unresolved | Support |
| TKT-002 | P3 | 2 | If unresolved | Support |
| TKT-003 | P3 | 2 | If unresolved | Support |
| TKT-004 | P2 | 1 | If unresolved | Engineering |
| TKT-005 | P4 | ∞ | No | AI resolves |
| TKT-006 | P1 | 0 | **Immediate** | Security Team |
| TKT-007 | P3 | 2 | If unresolved | Support |
| TKT-008 | P3 | 2 | If unresolved | Support/Sales |
| TKT-009 | P2 | 1 | If unresolved | Billing Team |
| TKT-010 | P3 | 2 | If unresolved | Support |
| TKT-011 | P3 | 2 | If unresolved | Support |
| TKT-012 | P2 | 1 | If unresolved | Sales Team |
| TKT-013 | P3 | 2 | If unresolved | Support |
| TKT-014 | P2 | 1 | If unresolved | Support |
| TKT-015 | P2 | 1 | If unresolved | Engineering |
| TKT-016 | P3 | 2 | If unresolved | Support/Billing |
| TKT-017 | P3 | 2 | If unresolved | Support |
| TKT-018 | P3 | 2 | If unresolved | Support |

**Summary:**
- **1 ticket** (5.6%) → Immediate escalation (TKT-006)
- **6 tickets** (33.3%) → Escalate after 1 AI attempt
- **10 tickets** (55.6%) → Escalate after 2 AI attempts
- **1 ticket** (5.6%) → Fully AI-resolved (TKT-005)

---

## 10. AI Agent Capability Requirements

Based on all discoveries, the AI agent must support:

| Capability | Priority | Justification |
|------------|----------|---------------|
| **Account lookup** | Critical | 4+ tickets require account state verification |
| **Tier-aware responses** | Critical | 4+ tickets are tier-dependent |
| **Multi-question parsing** | High | 3+ tickets have compound questions |
| **Escalation routing** | Critical | 17/18 tickets may require escalation |
| **Emotion detection** | High | Urgency and sentiment vary widely |
| **Channel-specific formatting** | Critical | 3 channels with distinct voice requirements |
| **Bug report extraction** | High | Engineering escalations need technical details |
| **SLA timer tracking** | High | Different priorities have different response windows |
| **Multilingual detection** | Medium | Spanish greeting detected in sample |
| **Proactive recommendations** | Medium | Upsell/downsell guidance needed |
| **Attempt counter** | Critical | P2/P3 escalation rules require tracking |
| **Auto-acknowledgment** | Medium | Web form requires immediate acknowledgment |

---

## 11. Recommendations for Implementation

1. **Build a ticket classifier** that identifies topic + priority from message content
2. **Implement a context retriever** that fetches account data, tier, and history
3. **Create resolution playbooks** for top 4 topics (Kanban, Pricing, Password Reset, Invites)
4. **Design an escalation router** that maps priority → team → SLA timer
5. **Build channel-specific response formatters** (Email: long/formal, WhatsApp: short/casual, Web Form: medium/structured)
6. **Add an emotion detector** to adjust tone and prioritize urgent tickets
7. **Implement an attempt tracker** to count AI resolution attempts per ticket
8. **Create a feedback loop** to log unresolved tickets for continuous improvement

---

*End of Discovery Log*
