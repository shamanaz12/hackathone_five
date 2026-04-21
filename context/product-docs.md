# TaskFlow Product Documentation

## Table of Contents
1. [Password Reset](#password-reset)
2. [Create Project](#create-project)
3. [Invite Team Members](#invite-team-members)
4. [Kanban Board](#kanban-board)
5. [Pricing Tiers](#pricing-tiers)

---

## Password Reset

### How It Works
Users can reset their password through the following flow:

1. Navigate to **login page** → Click **"Forgot Password?"**
2. Enter registered email address
3. System sends a **password reset email** with a unique link (valid for 1 hour)
4. User clicks link → enters new password (min 8 chars, 1 uppercase, 1 number, 1 special char)
5. Password updated successfully → user redirected to login

### Common Issues & Solutions
| Issue | Solution |
|-------|----------|
| Reset email not received | Check spam folder; verify email is correct; wait up to 5 minutes; resend option available |
| Reset link expired | Link expires after 1 hour; request a new reset link |
| "Email not found" error | Verify the email matches the one used during registration; check for typos |
| Password doesn't meet requirements | Must be 8+ characters, include uppercase, number, and special character |

### Support Actions
- **Verify account status** in admin dashboard
- **Manually trigger** reset email if system delay > 10 minutes
- **Escalate** if user suspects account compromise

### Security Notes
- Failed reset attempts are logged (max 5 attempts per hour)
- Account temporarily locked after 10 failed attempts
- All password changes trigger a notification email to the account holder

---

## Create Project

### Steps to Create a Project
1. Log in to TaskFlow
2. Click **"+ New Project"** button (top right of dashboard)
3. Fill in project details:
   - **Project Name** (required, max 100 chars)
   - **Description** (optional, max 5000 chars)
   - **Template** (optional: Blank, Agile Sprint, Marketing Campaign, Bug Tracker)
   - **Visibility** (Private / Team / Public)
   - **Start Date & End Date** (optional)
4. Click **"Create Project"**

### Project Limits by Tier
| Tier | Max Projects | Max Members per Project |
|------|--------------|-------------------------|
| Free | 3 | 5 |
| Starter | Unlimited | 50 |
| Professional | Unlimited | 200 |
| Enterprise | Unlimited | Unlimited |

### Common Issues & Solutions
| Issue | Solution |
|-------|----------|
| "Project limit reached" error | Upgrade tier or delete/archive old projects |
| Can't add members | Check tier limits; ensure invitees have TaskFlow accounts |
| Template not loading | Refresh page; try creating blank project; clear browser cache |
| Project not visible after creation | Check visibility settings; verify you're in correct workspace |

### Features Available in Every Project
- Kanban board (default view)
- Task assignments & due dates
- File attachments (up to 100 MB/file)
- Comments & @mentions
- Activity log
- Export (CSV, PDF)

---

## Invite Team Members

### How to Invite Members
1. Open the target project
2. Click **"Team"** tab → **"Invite Members"**
3. Enter email address(es) (comma-separated for bulk invites)
4. Select role:
   - **Admin** – Full project control, billing access
   - **Member** – Create/edit tasks, comment, upload files
   - **Viewer** – Read-only access
5. Optional: Add a personal message
6. Click **"Send Invites"**

### Invitation Flow
1. Invitee receives email with **"Join Project"** button
2. If they have a TaskFlow account → added immediately
3. If no account → prompted to sign up (free) → then added
4. Invitation expires after **7 days**

### Common Issues & Solutions
| Issue | Solution |
|-------|----------|
| Invitee didn't receive email | Check spam; verify email; resend invite; check if email is already registered |
| "Invite limit reached" | Check tier member limits; upgrade if needed |
| Wrong role assigned | Admin can change role in Team settings |
| Can't find "Invite Members" button | Only Admins and Members can invite; Viewers cannot |

### Bulk Import
- Available for **Professional** and **Enterprise** tiers
- Upload CSV with columns: `email, name, role`
- Max 500 invites per upload

---

## Kanban Board

### Overview
The Kanban board is the default project view, designed for visual task management.

### Default Columns
| Column | Purpose |
|--------|---------|
| **Backlog** | Tasks not yet started |
| **To Do** | Tasks ready to be worked on |
| **In Progress** | Currently being worked on |
| **In Review** | Awaiting approval/feedback |
| **Done** | Completed tasks |

### Customization
- **Add/Remove Columns:** Click "⚙️ Settings" → "Manage Columns"
- **Rename Columns:** Double-click column header
- **Reorder Columns:** Drag and drop column headers
- **WIP Limits:** Set Work-In-Progress limits per column (Professional+ tier)

### Task Cards
Each card displays:
- Task title
- Assignee avatar(s)
- Due date (color-coded: green = on track, yellow = due soon, red = overdue)
- Priority flag (Low, Medium, High, Urgent)
- Labels/tags
- Attachment count
- Comment count

### Drag & Drop
- Move cards between columns by dragging
- Reorder cards within a column
- Assign tasks by dragging to a team member's swimlane (if enabled)

### Filters & Search
- **Filter by:** Assignee, Label, Priority, Due Date, Status
- **Search:** Keyword search across task titles and descriptions
- **Save Filters:** Professional+ tier can save and share filter presets

### Common Issues & Solutions
| Issue | Solution |
|-------|----------|
| Cards not draggable | Check browser compatibility; disable browser extensions; refresh page |
| Column not showing new cards | Check WIP limits; verify task status matches column |
| Slow loading | Large boards may take time; use filters to reduce visible cards |
| Missing cards | Check filters; verify task wasn't archived or deleted |

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `N` | Create new task |
| `F` | Open filter menu |
| `/` | Focus search bar |
| `←` / `→` | Move selected card between columns |
| `Delete` | Archive selected card |

---

## Pricing Tiers

### Comparison Table

| Feature | Free | Starter ($12/user/mo) | Professional ($25/user/mo) | Enterprise (Custom) |
|---------|------|------------------------|----------------------------|---------------------|
| **Max Members** | 5 | 50 | 200 | Unlimited |
| **Max Projects** | 3 | Unlimited | Unlimited | Unlimited |
| **Storage** | 1 GB | 50 GB | 200 GB | Unlimited |
| **Kanban Board** | ✅ | ✅ | ✅ | ✅ |
| **Timeline View** | ❌ | ✅ | ✅ | ✅ |
| **Time Tracking** | ❌ | ✅ | ✅ | ✅ |
| **Custom Workflows** | ❌ | ❌ | ✅ | ✅ |
| **API Access** | ❌ | ❌ | ✅ | ✅ |
| **Advanced Reporting** | ❌ | ❌ | ✅ | ✅ |
| **SSO / SAML** | ❌ | ❌ | ❌ | ✅ |
| **Dedicated Support** | ❌ | ❌ | ❌ | ✅ |
| **SLA Guarantee** | ❌ | ❌ | ❌ | 99.99% |
| **On-Premise Option** | ❌ | ❌ | ❌ | ✅ |
| **Bulk Import** | ❌ | ❌ | ✅ | ✅ |
| **Priority Support** | ❌ | ✅ | ✅ | ✅ |

### Billing Details
- **Billing Cycle:** Monthly or Annual (save 20% on annual)
- **Payment Methods:** Visa, Mastercard, Amex, PayPal, Wire Transfer (Enterprise)
- **Free Trial:** 14-day trial for Starter and Professional (no credit card required)
- **Refund Policy:** 30-day money-back guarantee
- **Upgrade/Downgrade:** Anytime; prorated billing applied

### Common Pricing Questions
| Question | Answer |
|----------|--------|
| Can I switch tiers mid-cycle? | Yes; prorated credit applied |
| What happens when I downgrade? | Features revert at next billing cycle; data preserved |
| Is there a discount for nonprofits? | Yes, 50% off all paid tiers (contact sales) |
| Can I cancel anytime? | Yes; no cancellation fees; data exportable for 30 days |

---

## Appendix: Quick Reference

### Support Triage Priority
| Issue Type | Priority | SLA Response |
|------------|----------|--------------|
| Account locked / Security breach | P1 – Critical | 30 minutes |
| Billing / Payment failure | P2 – High | 1 hour |
| Feature not working / Bug | P2 – High | 2 hours |
| How-to / General question | P3 – Medium | 4 hours |
| Feature request / Feedback | P4 – Low | 24 hours |

### Internal Resources
- **Admin Dashboard:** admin.techcorp.internal
- **User Lookup:** admin.techcorp.internal/users
- **Ticket System:** zendesk.techcorp.internal
- **Status Page:** status.techcorp.com
