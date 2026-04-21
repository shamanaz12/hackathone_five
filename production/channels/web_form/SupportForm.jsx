
import React, { useState, useCallback, useMemo } from "react";
import PropTypes from "prop-types";

// ============================================================
// CONSTANTS
// ============================================================

const SUPPORT_CATEGORIES = [
  { value: "password_reset", label: "Password Reset", icon: "🔑" },
  { value: "create_project", label: "Create Project", icon: "📁" },
  { value: "invite_team_members", label: "Invite Team Members", icon: "👥" },
  { value: "kanban_board", label: "Kanban Board Issue", icon: "📋" },
  { value: "pricing", label: "Pricing / Billing", icon: "💳" },
  { value: "bug_report", label: "Bug Report", icon: "🐛" },
  { value: "feature_request", label: "Feature Request", icon: "💡" },
  { value: "other", label: "Other", icon: "❓" },
];

const PRIORITY_LABELS = {
  password_reset: "P2",
  create_project: "P3",
  invite_team_members: "P3",
  kanban_board: "P2",
  pricing: "P3",
  bug_report: "P2",
  feature_request: "P4",
  other: "P3",
};

const MAX_MESSAGE_LENGTH = 5000;
const MIN_MESSAGE_LENGTH = 10;
const MAX_SUBJECT_LENGTH = 200;

// ============================================================
// VALIDATION HELPERS
// ============================================================

const validators = {
  name: (value) => {
    if (!value.trim()) return "Name is required.";
    if (value.trim().length < 2) return "Name must be at least 2 characters.";
    if (value.length > 200) return "Name must be under 200 characters.";
    return "";
  },
  email: (value) => {
    if (!value.trim()) return "Email is required.";
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(value.trim())) return "Please enter a valid email address.";
    return "";
  },
  category: (value) => {
    if (!value) return "Please select a category.";
    return "";
  },
  subject: (value) => {
    if (!value.trim()) return "Subject is required.";
    if (value.length > MAX_SUBJECT_LENGTH) return `Subject must be under ${MAX_SUBJECT_LENGTH} characters.`;
    return "";
  },
  message: (value) => {
    if (!value.trim()) return "Message is required.";
    if (value.length < MIN_MESSAGE_LENGTH) return `Please provide at least ${MIN_MESSAGE_LENGTH} characters so we can help you better.`;
    if (value.length > MAX_MESSAGE_LENGTH) return `Message must be under ${MAX_MESSAGE_LENGTH} characters.`;
    return "";
  },
};

function validateField(name, value) {
  return validators[name] ? validators[name](value) : "";
}

function validateAll(fields) {
  const errors = {};
  let isValid = true;
  for (const [key, value] of Object.entries(fields)) {
    const error = validateField(key, value);
    if (error) {
      errors[key] = error;
      isValid = false;
    }
  }
  return { isValid, errors };
}

// ============================================================
// STYLES
// ============================================================

const styles = {
  container: {
    maxWidth: "680px",
    margin: "0 auto",
    padding: "32px 24px",
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    color: "#1a1a2e",
  },
  header: {
    textAlign: "center",
    marginBottom: "32px",
  },
  logo: {
    fontSize: "28px",
    fontWeight: "700",
    color: "#4361ee",
    marginBottom: "4px",
  },
  title: {
    fontSize: "22px",
    fontWeight: "600",
    color: "#1a1a2e",
    marginBottom: "8px",
  },
  subtitle: {
    fontSize: "14px",
    color: "#6c757d",
    lineHeight: "1.5",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  fieldGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  label: {
    fontSize: "14px",
    fontWeight: "600",
    color: "#344054",
  },
  required: {
    color: "#e53e3e",
    marginLeft: "2px",
  },
  input: {
    padding: "10px 14px",
    fontSize: "15px",
    border: "1px solid #d0d5dd",
    borderRadius: "8px",
    outline: "none",
    transition: "border-color 0.2s, box-shadow 0.2s",
    backgroundColor: "#fff",
  },
  inputError: {
    borderColor: "#e53e3e",
    boxShadow: "0 0 0 3px rgba(229, 62, 62, 0.1)",
  },
  inputFocused: {
    borderColor: "#4361ee",
    boxShadow: "0 0 0 3px rgba(67, 97, 238, 0.15)",
  },
  textarea: {
    padding: "10px 14px",
    fontSize: "15px",
    border: "1px solid #d0d5dd",
    borderRadius: "8px",
    outline: "none",
    resize: "vertical",
    minHeight: "120px",
    fontFamily: "inherit",
    transition: "border-color 0.2s, box-shadow 0.2s",
  },
  errorText: {
    fontSize: "12px",
    color: "#e53e3e",
    marginTop: "2px",
  },
  charCount: {
    fontSize: "12px",
    color: "#6c757d",
    textAlign: "right",
    marginTop: "2px",
  },
  charCountWarning: {
    color: "#e53e3e",
    fontWeight: "600",
  },
  categoryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
    gap: "8px",
  },
  categoryCard: (selected) => ({
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "10px 12px",
    fontSize: "13px",
    fontWeight: selected ? "600" : "400",
    border: selected ? "2px solid #4361ee" : "1px solid #d0d5dd",
    borderRadius: "8px",
    backgroundColor: selected ? "#eef2ff" : "#fff",
    cursor: "pointer",
    transition: "all 0.15s",
    color: selected ? "#4361ee" : "#344054",
  }),
  categoryIcon: {
    fontSize: "16px",
  },
  submitButton: (disabled) => ({
    padding: "12px 24px",
    fontSize: "16px",
    fontWeight: "600",
    color: "#fff",
    backgroundColor: disabled ? "#a0aec0" : "#4361ee",
    border: "none",
    borderRadius: "8px",
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "background-color 0.2s",
    marginTop: "8px",
  }),
  spinner: {
    display: "inline-block",
    width: "18px",
    height: "18px",
    border: "2px solid rgba(255,255,255,0.3)",
    borderTop: "2px solid #fff",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
    marginRight: "8px",
    verticalAlign: "middle",
  },
  successContainer: {
    textAlign: "center",
    padding: "48px 24px",
  },
  successIcon: {
    fontSize: "64px",
    marginBottom: "16px",
  },
  successTitle: {
    fontSize: "22px",
    fontWeight: "700",
    color: "#1a1a2e",
    marginBottom: "8px",
  },
  successMessage: {
    fontSize: "15px",
    color: "#6c757d",
    lineHeight: "1.6",
    marginBottom: "24px",
  },
  ticketBadge: {
    display: "inline-block",
    padding: "6px 16px",
    fontSize: "14px",
    fontWeight: "600",
    backgroundColor: "#eef2ff",
    color: "#4361ee",
    borderRadius: "20px",
    marginBottom: "16px",
  },
  slaInfo: {
    fontSize: "13px",
    color: "#6c757d",
    backgroundColor: "#f8f9fa",
    padding: "12px 16px",
    borderRadius: "8px",
    marginBottom: "24px",
  },
  newTicketButton: {
    padding: "10px 24px",
    fontSize: "15px",
    fontWeight: "600",
    color: "#4361ee",
    backgroundColor: "transparent",
    border: "1px solid #4361ee",
    borderRadius: "8px",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  formFooter: {
    marginTop: "24px",
    padding: "16px",
    backgroundColor: "#f8f9fa",
    borderRadius: "8px",
    fontSize: "13px",
    color: "#6c757d",
    textAlign: "center",
    lineHeight: "1.5",
  },
  formFooterLink: {
    color: "#4361ee",
    textDecoration: "none",
    fontWeight: "500",
  },
  globalError: {
    padding: "12px 16px",
    fontSize: "14px",
    color: "#e53e3e",
    backgroundColor: "#fff5f5",
    border: "1px solid #fed7d7",
    borderRadius: "8px",
    marginBottom: "8px",
  },
};

// ============================================================
// SUPPORT FORM COMPONENT
// ============================================================

function SupportForm({ onSubmit, apiEndpoint = "/api/tickets" }) {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    category: "",
    subject: "",
    message: "",
  });

  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [focusedField, setFocusedField] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [isSuccess, setIsSuccess] = useState(false);
  const [ticketId, setTicketId] = useState("");
  const [estimatedResponse, setEstimatedResponse] = useState("");

  // ── Handlers ──

  const handleChange = useCallback((field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setSubmitError("");

    // Live validation for touched fields
    setTouched((prev) => {
      if (prev[field]) {
        const error = validateField(field, value);
        setErrors((prevErrors) => ({ ...prevErrors, [field]: error }));
      }
      return prev;
    });
  }, []);

  const handleBlur = useCallback((field) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
    const error = validateField(field, formData[field]);
    setErrors((prev) => ({ ...prev, [field]: error }));
    setFocusedField(null);
  }, [formData]);

  const handleFocus = useCallback((field) => {
    setFocusedField(field);
  }, []);

  const handleCategorySelect = useCallback((category) => {
    handleChange("category", category);
  }, [handleChange]);

  const handleSubmit = useCallback(
    async (e) => {
      e.preventDefault();

      // Validate all fields
      const { isValid, errors: validationErrors } = validateAll(formData);
      setErrors(validationErrors);
      setTouched({
        name: true,
        email: true,
        category: true,
        subject: true,
        message: true,
      });

      if (!isValid) return;

      setIsSubmitting(true);
      setSubmitError("");

      try {
        const payload = {
          customer_name: formData.name.trim(),
          email: formData.email.trim().toLowerCase(),
          channel: "web_form",
          subject: formData.subject.trim(),
          message: formData.message.trim(),
          category: formData.category,
          priority: PRIORITY_LABELS[formData.category] || "P3",
          timestamp: new Date().toISOString(),
        };

        const response = await fetch(apiEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.message || `Server error: ${response.status}`);
        }

        const data = await response.json();
        setTicketId(data.ticket?.ticket_id || data.ticket_id || "TF-" + Date.now());
        setEstimatedResponse(data.sla || "4 hours");
        setIsSuccess(true);

        if (onSubmit) onSubmit(data);
      } catch (err) {
        setSubmitError(err.message || "Something went wrong. Please try again.");
      } finally {
        setIsSubmitting(false);
      }
    },
    [formData, apiEndpoint, onSubmit]
  );

  const handleReset = useCallback(() => {
    setFormData({ name: "", email: "", category: "", subject: "", message: "" });
    setErrors({});
    setTouched({});
    setSubmitError("");
    setIsSuccess(false);
    setTicketId("");
    setEstimatedResponse("");
  }, []);

  // ── Derived state ──

  const messageCharCount = formData.message.length;
  const isMessageOverLimit = messageCharCount > MAX_MESSAGE_LENGTH;
  const isMessageNearLimit = messageCharCount > MAX_MESSAGE_LENGTH * 0.9;

  const isSubmitDisabled = useMemo(
    () =>
      isSubmitting ||
      !formData.name.trim() ||
      !formData.email.trim() ||
      !formData.category ||
      !formData.subject.trim() ||
      !formData.message.trim() ||
      messageCharCount < MIN_MESSAGE_LENGTH ||
      isMessageOverLimit ||
      Object.values(errors).some((e) => e),
    [isSubmitting, formData, errors, messageCharCount, isMessageOverLimit]
  );

  // ── Render: Success State ──

  if (isSuccess) {
    return (
      <div style={styles.container}>
        <div style={styles.successContainer}>
          <div style={styles.successIcon} role="img" aria-label="Success">
            ✅
          </div>
          <h2 style={styles.successTitle}>Ticket Submitted Successfully!</h2>
          <p style={styles.successMessage}>
            Thank you for contacting TaskFlow Support. We&apos;ve received your request
            and our team will get back to you shortly.
          </p>
          {ticketId && (
            <div style={styles.ticketBadge} data-testid="ticket-id">
              Ticket: {ticketId}
            </div>
          )}
          <div style={styles.slaInfo}>
            <strong>Expected response time:</strong> {estimatedResponse || "within 4 hours"}
            <br />
            <span style={{ fontSize: "12px" }}>
              We&apos;ll send a confirmation email to <strong>{formData.email}</strong> with
              your ticket details.
            </span>
          </div>
          <button
            type="button"
            style={styles.newTicketButton}
            onClick={handleReset}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = "#4361ee";
              e.target.style.color = "#fff";
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = "transparent";
              e.target.style.color = "#4361ee";
            }}
          >
            Submit Another Ticket
          </button>
        </div>
      </div>
    );
  }

  // ── Render: Form ──

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.logo}>TaskFlow</div>
        <h1 style={styles.title}>Contact Support</h1>
        <p style={styles.subtitle}>
          Tell us about your issue and we&apos;ll get back to you as soon as possible.
          <br />
          Average response time: <strong>under 4 hours</strong>.
        </p>
      </div>

      <form style={styles.form} onSubmit={handleSubmit} noValidate>
        {/* Global Error */}
        {submitError && (
          <div style={styles.globalError} role="alert" data-testid="submit-error">
            {submitError}
          </div>
        )}

        {/* Name */}
        <div style={styles.fieldGroup}>
          <label htmlFor="name" style={styles.label}>
            Full Name<span style={styles.required}>*</span>
          </label>
          <input
            id="name"
            type="text"
            value={formData.name}
            onChange={(e) => handleChange("name", e.target.value)}
            onBlur={() => handleBlur("name")}
            onFocus={() => handleFocus("name")}
            placeholder="e.g., Alice Johnson"
            style={{
              ...styles.input,
              ...(touched.name && errors.name ? styles.inputError : {}),
              ...(focusedField === "name" && !(touched.name && errors.name) ? styles.inputFocused : {}),
            }}
            aria-invalid={touched.name && !!errors.name}
            aria-describedby={errors.name ? "name-error" : undefined}
            maxLength={200}
            autoComplete="name"
          />
          {touched.name && errors.name && (
            <span id="name-error" style={styles.errorText} role="alert">
              {errors.name}
            </span>
          )}
        </div>

        {/* Email */}
        <div style={styles.fieldGroup}>
          <label htmlFor="email" style={styles.label}>
            Email Address<span style={styles.required}>*</span>
          </label>
          <input
            id="email"
            type="email"
            value={formData.email}
            onChange={(e) => handleChange("email", e.target.value)}
            onBlur={() => handleBlur("email")}
            onFocus={() => handleFocus("email")}
            placeholder="e.g., alice@company.com"
            style={{
              ...styles.input,
              ...(touched.email && errors.email ? styles.inputError : {}),
              ...(focusedField === "email" && !(touched.email && errors.email) ? styles.inputFocused : {}),
            }}
            aria-invalid={touched.email && !!errors.email}
            aria-describedby={errors.email ? "email-error" : undefined}
            maxLength={320}
            autoComplete="email"
          />
          {touched.email && errors.email && (
            <span id="email-error" style={styles.errorText} role="alert">
              {errors.email}
            </span>
          )}
        </div>

        {/* Category */}
        <div style={styles.fieldGroup}>
          <label style={styles.label}>
            Category<span style={styles.required}>*</span>
          </label>
          <div style={styles.categoryGrid} role="radiogroup" aria-label="Support category">
            {SUPPORT_CATEGORIES.map((cat) => (
              <button
                key={cat.value}
                type="button"
                role="radio"
                aria-checked={formData.category === cat.value}
                onClick={() => handleCategorySelect(cat.value)}
                style={styles.categoryCard(formData.category === cat.value)}
                onMouseEnter={(e) => {
                  if (formData.category !== cat.value) {
                    e.currentTarget.style.borderColor = "#4361ee";
                    e.currentTarget.style.backgroundColor = "#f8f9ff";
                  }
                }}
                onMouseLeave={(e) => {
                  if (formData.category !== cat.value) {
                    e.currentTarget.style.borderColor = "#d0d5dd";
                    e.currentTarget.style.backgroundColor = "#fff";
                  }
                }}
              >
                <span style={styles.categoryIcon}>{cat.icon}</span>
                {cat.label}
              </button>
            ))}
          </div>
          {touched.category && errors.category && (
            <span style={styles.errorText} role="alert">
              {errors.category}
            </span>
          )}
        </div>

        {/* Subject */}
        <div style={styles.fieldGroup}>
          <label htmlFor="subject" style={styles.label}>
            Subject<span style={styles.required}>*</span>
          </label>
          <input
            id="subject"
            type="text"
            value={formData.subject}
            onChange={(e) => handleChange("subject", e.target.value)}
            onBlur={() => handleBlur("subject")}
            onFocus={() => handleFocus("subject")}
            placeholder="Brief description of your issue"
            style={{
              ...styles.input,
              ...(touched.subject && errors.subject ? styles.inputError : {}),
              ...(focusedField === "subject" && !(touched.subject && errors.subject) ? styles.inputFocused : {}),
            }}
            aria-invalid={touched.subject && !!errors.subject}
            aria-describedby={errors.subject ? "subject-error" : undefined}
            maxLength={MAX_SUBJECT_LENGTH}
          />
          {touched.subject && errors.subject && (
            <span id="subject-error" style={styles.errorText} role="alert">
              {errors.subject}
            </span>
          )}
        </div>

        {/* Message */}
        <div style={styles.fieldGroup}>
          <label htmlFor="message" style={styles.label}>
            Message<span style={styles.required}>*</span>
          </label>
          <textarea
            id="message"
            value={formData.message}
            onChange={(e) => handleChange("message", e.target.value)}
            onBlur={() => handleBlur("message")}
            onFocus={() => handleFocus("message")}
            placeholder="Describe your issue in detail. Include any error messages, steps to reproduce, or screenshots."
            style={{
              ...styles.textarea,
              ...(touched.message && errors.message ? styles.inputError : {}),
              ...(focusedField === "message" && !(touched.message && errors.message) ? styles.inputFocused : {}),
            }}
            aria-invalid={touched.message && !!errors.message}
            aria-describedby={errors.message ? "message-error" : undefined}
            maxLength={MAX_MESSAGE_LENGTH + 100}
          />
          <div
            style={{
              ...styles.charCount,
              ...(isMessageOverLimit || isMessageNearLimit ? styles.charCountWarning : {}),
            }}
          >
            {messageCharCount} / {MAX_MESSAGE_LENGTH}
            {isMessageOverLimit && " — Message exceeds limit!"}
            {messageCharCount < MIN_MESSAGE_LENGTH && formData.message.length > 0 && (
              <span> — Minimum {MIN_MESSAGE_LENGTH} characters required</span>
            )}
          </div>
          {touched.message && errors.message && (
            <span id="message-error" style={styles.errorText} role="alert">
              {errors.message}
            </span>
          )}
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isSubmitDisabled}
          style={styles.submitButton(isSubmitDisabled)}
          onMouseEnter={(e) => {
            if (!isSubmitDisabled) e.target.style.backgroundColor = "#3451d1";
          }}
          onMouseLeave={(e) => {
            if (!isSubmitDisabled) e.target.style.backgroundColor = "#4361ee";
          }}
        >
          {isSubmitting ? (
            <>
              <span style={styles.spinner} />
              Submitting...
            </>
          ) : (
            "Submit Ticket"
          )}
        </button>
      </form>

      {/* Footer */}
      <div style={styles.formFooter}>
        Need immediate help? Check our{" "}
        <a href="/help" style={styles.formFooterLink}>
          Help Center
        </a>{" "}
        or contact us via{" "}
        <a href="mailto:support@techcorp.com" style={styles.formFooterLink}>
          email
        </a>
        .
        <br />
        <span style={{ fontSize: "12px", color: "#adb5bd" }}>
          Your data is processed according to our{" "}
          <a href="/privacy" style={{ ...styles.formFooterLink, color: "#adb5bd" }}>
            Privacy Policy
          </a>
          .
        </span>
      </div>

      {/* Spinner keyframe injection */}
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

// ============================================================
// PROP TYPES
// ============================================================

SupportForm.propTypes = {
  onSubmit: PropTypes.func,
  apiEndpoint: PropTypes.string,
};

// ============================================================
// EXPORT
// ============================================================

export default SupportForm;
