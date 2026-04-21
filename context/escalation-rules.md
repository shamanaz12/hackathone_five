# Escalation Rules - When to Escalate to Human Agent

## Overview
This document defines the criteria for escalating customer support tickets from the AI agent to a human support representative. The goal is to ensure critical issues are resolved quickly while allowing the AI to handle routine inquiries autonomously.

---

## Escalation Triggers

### 🔴 P1 - Critical (Immediate Escalation)
**Escalate immediately, no AI resolution attempt required.**

| Trigger | Reason | Action |
|---------|--------|--------|
| Account locked / compromised | Security risk, user cannot access account | Escalate to Security Team within 30 minutes |
| Data breach or suspected unauthorized access | Legal and compliance implications | Escalate to Security + Legal team immediately |
| System-wide outage affecting customer | Revenue-impacting issue | Escalate to Engineering + Support Lead |
| Billing error > $500 or duplicate enterprise charge | High financial impact | Escalate to Billing Team within 1 hour |
| Threat of legal action or churn | Customer retention risk | Escalate to Customer Success Manager |

### 🟠 P2 - High (Escalate After 1 AI Attempt)
**AI attempts resolution once. If unresolved, escalate.**

| Trigger | Reason | Action |
|---------|--------|--------|
| Password reset email not received after 10+ minutes | Possible email delivery issue | Escalate to Support if resend fails |
| Feature not working (bug report) | Requires engineering investigation | Escalate to Engineering with bug details |
| Kanban board performance issues (>10 sec load) | Possible backend issue | Escalate to Engineering with account details |
| Billing dispute or unexpected charge | Customer dissatisfaction | Escalate to Billing Team |
| Enterprise sales inquiry (SSO, on-premise, 100+ users) | Requires sales engagement | Escalate to Sales Team within 2 hours |
| Customer requests human agent | Customer preference | Escalate immediately to available agent |

### 🟡 P3 - Medium (Escalate After 2 AI Attempts)
**AI attempts resolution up to twice. If still unresolved, escalate.**

| Trigger | Reason | Action |
|---------|--------|--------|
| Invitation emails not received | Possible email configuration issue | Escalate if resend fails twice |
| Project creation errors | Possible account/data issue | Escalate if standard troubleshooting fails |
| Role change not reflecting | Possible permission sync issue | Escalate if UI steps don't resolve |
| Export/download not working | Possible file generation issue | Escalate if retry fails |
| Integration setup failure | Third-party dependency | Escalate with integration logs |

### 🟢 P4 - Low (AI Handles Fully)
**AI resolves autonomously. No escalation required unless customer insists.**

| Trigger | Reason | Action |
|---------|--------|--------|
| General how-to questions | Documentation available | AI provides step-by-step guidance |
| Feature requests | Product feedback | AI acknowledges + logs feedback |
| Pricing inquiries | Pricing docs available | AI provides pricing info |
| Keyboard shortcuts / tips | Documentation available | AI provides reference |
| Non-urgent account questions | Standard procedures | AI resolves with docs |

---

## Escalation Procedures

### Step-by-Step Escalation Flow
1. **Identify trigger** from the tables above
2. **Classify priority** (P1-P4)
3. **Attempt AI resolution** (if applicable per priority)
4. **If unresolved**, gather:
   - Customer name, email, account ID
   - Ticket ID and channel
   - Summary of issue and steps already taken
   - Relevant screenshots/logs (if available)
5. **Route to correct team:**
   - **Security Team:** security@techcorp.com (P1 only)
   - **Engineering Team:** eng-support@techcorp.internal
   - **Billing Team:** billing@techcorp.com
   - **Sales Team:** sales@techcorp.com
   - **Customer Success:** csm@techcorp.com
   - **General Support Queue:** support-queue@techcorp.internal
6. **Notify customer:** "I've escalated your issue to our [Team Name]. You can expect a response within [SLA time]."

---

## SLA Response Times by Priority

| Priority | Response Time | Resolution Target |
|----------|---------------|-------------------|
| P1 - Critical | 30 minutes | 4 hours |
| P2 - High | 1 hour | 8 hours |
| P3 - Medium | 4 hours | 24 hours |
| P4 - Low | 24 hours | 72 hours |

---

## Special Escalation Scenarios

### VIP / Enterprise Customers
- Any P2 or above ticket from **Enterprise** tier customers → **Immediate escalation**
- Enterprise customers have dedicated CSM → Route to CSM directly

### Repeat Offenders
- If the same customer submits **3+ tickets on the same issue** within 48 hours → Escalate regardless of priority

### Language Barriers
- If customer communicates in a language the AI cannot confidently handle → Escalate to multilingual support team

### Sensitive Situations
- Customer mentions **harassment, discrimination, or legal concerns** → Escalate to Legal + Support Lead immediately
- Customer expresses **emotional distress** → Escalate with empathy note to Customer Success

---

## Escalation Decision Tree

```
Customer Ticket Received
         │
         ▼
  Is it P1 (Critical)? ──YES──► Immediate Escalation
         │
         NO
         ▼
  Does customer request human? ──YES──► Immediate Escalation
         │
         NO
         ▼
  Is it P2 (High)? ──YES──► AI attempts once → Still unresolved? ──YES──► Escalate
         │                                              │
         NO                                             NO
         │                                              ▼
  Is it P3 (Medium)? ──YES──► AI attempts twice → Still unresolved? ──YES──► Escalate
         │                                              │
         NO                                             NO
         │                                              ▼
  P4 (Low) ──────────────────────────────────────► AI resolves autonomously
                                                          │
                                                          ▼
                                                    Log & close ticket
```

---

## Notes for AI Agent
- **Always be transparent:** Tell the customer when you're escalating and why
- **Never promise resolution times** outside the SLA table
- **Always summarize** what steps you've already taken before escalating
- **Preserve context:** Include full conversation history in escalation handoff
- **Follow up:** If escalation is made, set a reminder to check status before SLA expires
