# Agent Skills Specification — TaskFlow AI Support Agent

**Project:** CRM Digital FTE Factory Final Hackathon 5  
**Product:** TaskFlow by TechCorp  
**Version:** 1.0  
**Date:** 2026-04-07

---

## Overview

This document defines the 5 core skills that the TaskFlow AI Support Agent must possess. Each skill includes a description, input/output specification, decision logic, and success criteria.

---

## Skill 1: Knowledge Retrieval

### Description
Search and retrieve relevant product documentation from the TaskFlow knowledge base based on customer query. Supports both topic-filtered and free-form keyword search with relevance scoring.

### Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Customer's question or issue description |
| `topic` | string | No | Topic filter: `password_reset`, `create_project`, `invite_team_members`, `kanban_board`, `pricing` |

### Outputs
| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `found` or `not_found` |
| `results_count` | int | Number of matching knowledge base entries |
| `results` | list | Sorted list of results with topic, relevance_score, and content |

### Decision Logic
```
1. Normalize query to lowercase
2. If topic filter provided:
   a. Search only that topic's keywords
   b. Return content if keyword match score > 0
3. If no topic filter:
   a. Search all 5 knowledge base topics
   b. Score each topic by keyword overlap count
   c. Return all topics with score > 0, sorted by score descending
4. If no matches: return not_found with escalation suggestion
```

### Knowledge Base Topics
| Topic | Keyword Count | Content Sections |
|-------|---------------|------------------|
| password_reset | 14 | overview, requirements, common_issues, security_notes, support_actions |
| create_project | 12 | overview, fields, tier_limits, common_issues |
| invite_team_members | 16 | overview, invitation_flow, tier_limits, bulk_import, common_issues |
| kanban_board | 16 | overview, customization, card_info, keyboard_shortcuts, common_issues |
| pricing | 16 | tiers, billing |

### Success Criteria
- Returns correct topic for 90%+ of queries from sample-tickets.json
- Relevance score correctly ranks results by keyword overlap
- Returns not_found with actionable suggestion when no match

### Edge Cases
- Query matches multiple topics → return all, sorted by score
- Query matches no topics → return not_found, suggest escalation
- Topic filter specified but no match → return not_found for that topic only

---

## Skill 2: Sentiment Analysis

### Description
Analyze customer message sentiment on a scale from -2 (very negative) to +2 (very positive) using rule-based lexical analysis. Detects emotional state, urgency indicators, and sentiment trends over time.

### Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message` | string | Yes | Customer's raw message text |

### Outputs
| Field | Type | Description |
|-------|------|-------------|
| `score` | int | Sentiment score: -2, -1, 0, +1, or +2 |
| `label` | string | One of: `very_negative`, `negative`, `neutral`, `positive`, `very_positive` |
| `indicators` | list[str] | Detected urgency/emotion flags |

### Lexicon

**Positive Words (+1 to +2):**
| Word | Score | Word | Score |
|------|-------|------|-------|
| love | +2 | great | +1 |
| awesome | +2 | excellent | +2 |
| happy | +1 | good | +1 |
| thanks/thank | +1 | appreciate | +1 |
| perfect | +2 | wonderful | +2 |
| fantastic | +2 | helpful | +1 |

**Negative Words (-0.3 to -2):**
| Word | Score | Word | Score |
|------|-------|------|-------|
| hate | -2 | terrible | -2 |
| awful | -2 | worst | -2 |
| horrible | -2 | frustrated | -1 |
| frustrating | -1 | annoying | -1 |
| angry | -2 | upset | -1 |
| disappointed | -1 | broken | -1 |
| useless | -2 | ridiculous | -2 |
| unacceptable | -2 | waste | -1 |
| not | -0.5 | never | -1 |
| no | -0.3 | still | -0.5 |

**Urgency Penalties (-0.5 each):**
`asap`, `urgent`, `critical`, `immediately`, `right now`

### Decision Logic
```
1. Tokenize message to lowercase words
2. Sum scores for all matched positive/negative words
3. Apply urgency penalties for matched phrases
4. Clamp result to range [-2, +2]
5. Map score to label:
   -2 → very_negative
   -1 → negative
    0 → neutral
   +1 → positive
   +2 → very_positive
```

### Trend Detection
When customer has prior history, compare current score to historical average:
- Current > historical average → "Improving"
- Current < historical average → "Declining"
- Current == historical average → "Stable"

### Success Criteria
- Correctly identifies positive/negative sentiment in 85%+ of sample tickets
- Detects urgency indicators in time-sensitive messages
- Sentiment trend accurately reflects direction of customer satisfaction

### Edge Cases
- Mixed sentiment (positive + negative words) → net score determines label
- Sarcasm not detected (rule-based limitation) → document as known constraint
- Non-English messages → return neutral (0) and flag for multilingual escalation

---

## Skill 3: Escalation Decision

### Description
Determine whether a ticket should be escalated to a human agent based on priority, topic, AI attempt count, sentiment, and special conditions. Routes to the correct team with appropriate SLA.

### Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `priority` | string | Yes | P1, P2, P3, or P4 |
| `topic` | string | Yes | Classified topic of the ticket |
| `ai_attempt` | int | Yes | Number of AI resolution attempts (1, 2, ...) |
| `urgency` | list[str] | Yes | Urgency indicators from normalizer |
| `sentiment_score` | int | Yes | Current sentiment score (-2 to +2) |
| `sentiment_trend` | string | Yes | "Improving", "Declining", or "Stable" |

### Outputs
| Field | Type | Description |
|-------|------|-------------|
| `escalate` | bool | Whether to escalate |
| `team` | string | Target team name |
| `sla` | string | Response SLA timeframe |
| `reason` | string | Human-readable escalation reason |

### Escalation Rules Matrix

| Priority | Condition | Action | Target Team | SLA |
|----------|-----------|--------|-------------|-----|
| P1 | Any trigger | Immediate escalation | Security Team | 30 minutes |
| P2 | AI attempt >= 1 | Escalate | Engineering/Billing/Sales/Support | 1-2 hours |
| P3 | AI attempt >= 2 | Escalate | Support Team | 4 hours |
| P4 | Always | No escalation | N/A | N/A |
| Any | Human requested | Immediate escalation | Support Team | 1 hour |
| Any | Score <= -2 AND Declining | Immediate escalation | Customer Success | 1 hour |

### Team Routing for P2
| Topic | Target Team |
|-------|-------------|
| kanban_board | Engineering Team |
| pricing (enterprise/SSO/on-premise) | Sales Team |
| pricing (billing/refund) | Billing Team |
| password_reset | Support Team |
| create_project | Support Team |
| invite_team_members | Support Team |

### Decision Logic
```
1. If priority == P1 → escalate immediately to Security Team
2. If "human_request" in urgency → escalate immediately to Support Team
3. If sentiment_score <= -2 AND trend == "Declining" → escalate to Customer Success
4. If priority == P2 AND ai_attempt >= 1 → escalate to topic-specific team
5. If priority == P3 AND ai_attempt >= 2 → escalate to Support Team
6. If priority == P4 → no escalation (AI resolves autonomously)
7. Otherwise → no escalation yet
```

### Success Criteria
- P1 tickets always escalated immediately (100%)
- P2 tickets escalated after exactly 1 AI attempt
- P3 tickets escalated after exactly 2 AI attempts
- P4 tickets never escalated unless human requested
- Correct team routing for all topic/team combinations

### Edge Cases
- Customer requests human at any priority → immediate escalation
- Sentiment critically negative + declining → proactive escalation even at P3
- Repeat offender (3+ tickets same issue in 48h) → escalate regardless of priority
- Enterprise customer P2+ → immediate escalation to CSM

---

## Skill 4: Channel Adaptation

### Description
Adapt response tone, format, length, and style to match the communication channel (email, WhatsApp, web_form) per TechCorp brand voice guidelines.

### Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `channel` | string | Yes | One of: `email`, `whatsapp`, `web_form` |
| `response_text` | string | Yes | Base response content |
| `customer_name` | string | Yes | Customer's first name for greeting |
| `use_emojis` | bool | No | Override emoji usage (default: per channel) |

### Outputs
| Field | Type | Description |
|-------|------|-------------|
| `formatted_text` | string | Channel-formatted response |
| `channel` | string | Channel the response was formatted for |

### Channel Specifications

#### Email
| Attribute | Specification |
|-----------|---------------|
| Tone | Professional, thorough, warm |
| Length | Medium to long (3-8 paragraphs) |
| Formality | Semi-formal |
| Greeting | "Hi {name}," |
| Sign-off | "Best regards,\nThe TaskFlow Support Team" |
| Emojis | Never |
| Structure | Full paragraphs + bullet points |
| Links | Full URLs or hyperlinks |
| Response SLA | < 2 hours |

#### WhatsApp
| Attribute | Specification |
|-----------|---------------|
| Tone | Friendly, concise, conversational |
| Length | Short (1-3 short messages) |
| Formality | Casual but professional |
| Greeting | "Hey {name}! [wave emoji]" |
| Sign-off | "Hope that helps! [smile emoji]" |
| Emojis | Yes, 1-2 per message max |
| Structure | Short lines + numbered steps with emoji numbers |
| Links | Shortened URLs |
| Response SLA | < 15 minutes |
| Max length | 1000 characters (truncate with note if exceeded) |

#### Web Form
| Attribute | Specification |
|-----------|---------------|
| Tone | Professional, structured, helpful |
| Length | Medium (2-5 paragraphs) |
| Formality | Semi-formal |
| Greeting | "Hello {name}," |
| Sign-off | "Thank you for contacting TaskFlow Support.\nBest regards,\nThe TaskFlow Team" |
| Emojis | Never |
| Structure | Paragraphs + bullet points |
| Links | Full URLs |
| Response SLA | < 4 hours |
| Auto-acknowledgment | Sent immediately upon receipt |

### Formatting Rules
```
1. Apply channel-specific greeting
2. Format numbered steps:
   - Email/Web Form: "1. Step text"
   - WhatsApp: "[1] Step text" (emoji number placeholders)
3. Format bullet points:
   - Email/Web Form: "- Point text"
   - WhatsApp: "• Point text"
4. Apply channel-specific sign-off
5. For WhatsApp: truncate if > 1000 chars, add "[Message truncated -- full details sent via email]"
6. Strip emoji placeholders for email/web_form channels
7. Render emoji placeholders for WhatsApp channel
```

### Success Criteria
- Email responses use semi-formal tone with full paragraphs
- WhatsApp responses are concise with emoji, under 1000 chars
- Web Form responses are structured with acknowledgment and sign-off
- No emoji leakage into email or web_form responses
- Greeting and sign-off match channel specification exactly

### Edge Cases
- Very long knowledge base answer → summarize for WhatsApp, full for email
- Customer switches channels mid-conversation → acknowledge previous channel in response
- Non-English customer message → maintain channel format, flag for multilingual team

---

## Skill 5: Customer Identification

### Description
Resolve incoming tickets to existing customer profiles using email and/or phone number matching. Create new profiles for unknown customers. Enable cross-channel continuity by linking identities across communication channels.

### Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | string | No | Customer's email address |
| `phone` | string | No | Customer's phone number |
| `customer_id` | string | No | Direct customer ID override |
| `customer_name` | string | Yes | Customer's full name |

### Outputs
| Field | Type | Description |
|-------|------|-------------|
| `customer_id` | string | Resolved or created customer ID (e.g., CUST-0001) |
| `is_new` | bool | Whether this is a new customer |
| `profile` | dict | Full customer profile |
| `channels_seen` | list[str] | All channels this customer has used |
| `total_tickets` | int | Total tickets from this customer |

### Identity Resolution Logic
```
1. If email provided:
   a. Search identity_map for email (case-insensitive)
   b. If found → return existing customer_id
2. If phone provided:
   a. Search identity_map for phone (exact match)
   b. If found → return existing customer_id
3. If neither found:
   a. Create new customer_id (CUST-NNNN format)
   b. Create new profile with name, email, phone
   c. Add email and phone to identity_map
   d. Return new customer_id
4. Update profile with any new contact info from ticket
```

### Profile Structure
```json
{
  "customer_id": "CUST-0001",
  "name": "Alice Johnson",
  "email": "alice.j@startupco.com",
  "phone": "+1 555 123 4567",
  "tier": "unknown",
  "channels_seen": ["email", "whatsapp"],
  "total_tickets": 2,
  "resolved_tickets": 0,
  "escalated_tickets": 2,
  "sentiment_history": [
    ["2026-04-07T09:00:00Z", 0],
    ["2026-04-07T09:20:00Z", 0]
  ],
  "topic_history": [
    ["2026-04-07T09:00:00Z", "password_reset"],
    ["2026-04-07T09:20:00Z", "password_reset"]
  ],
  "last_contact": "2026-04-07T09:20:00Z",
  "created_at": "2026-04-07T09:00:00Z"
}
```

### Cross-Channel Continuity
When a customer contacts via a different channel than before:
1. Detect channel switch by comparing current channel to last recorded channel
2. Retrieve full conversation history from all channels
3. Include conversation summary in agent response context
4. Update profile's channels_seen list

### Success Criteria
- 100% accurate email-based customer matching (case-insensitive)
- 100% accurate phone-based customer matching (exact match)
- New customers created with complete profile
- Cross-channel history correctly merged for same customer
- Profile updated with new contact info when provided

### Edge Cases
- Customer provides email on first contact, phone on second → merge profiles
- Customer uses different email addresses → treated as separate customers (limitation)
- Customer uses different phone numbers → treated as separate customers (limitation)
- No email or phone provided → create new profile with name only

---

## Skill Interdependency Map

```
                    ┌─────────────────────┐
                    │  Customer Identify   │ ← Skill 5
                    │  (resolve profile)   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Knowledge Retrieve  │ ← Skill 1
                    │  (find answer)       │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Sentiment Analyze   │ ← Skill 2
                    │  (detect emotion)    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Escalation Decide   │ ← Skill 3
                    │  (route or resolve)  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Channel Adapt       │ ← Skill 4
                    │  (format response)   │
                    └─────────────────────┘
```

### Execution Order
1. **Customer Identification** — Who is this?
2. **Knowledge Retrieval** — What do they need?
3. **Sentiment Analysis** — How do they feel?
4. **Escalation Decision** — Can AI handle this or escalate?
5. **Channel Adaptation** — How should we respond?

---

*End of Agent Skills Specification*
