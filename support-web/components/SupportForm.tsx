"use client";

import { useState } from "react";

type FormData = {
  customer_name: string;
  email: string;
  subject: string;
  category: string;
  priority: string;
  message: string;
};

type SuccessData = {
  ticket_id: string;
  ai_response: string;
  status: string;
};

export default function SupportForm() {
  const [form, setForm] = useState<FormData>({
    customer_name: "",
    email: "",
    subject: "",
    category: "technical",
    priority: "P3",
    message: "",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<SuccessData | null>(null);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSuccess(null);

    try {
      const res = await fetch("http://localhost:8000/api/tickets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to submit ticket");
      }

      const data = await res.json();
      setSuccess({
        ticket_id: data.ticket_id,
        ai_response: data.ai_response,
        status: data.status,
      });
      setForm({
        customer_name: "",
        email: "",
        subject: "",
        category: "technical",
        priority: "P3",
        message: "",
      });
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="space-y-6 animate-in fade-in zoom-in duration-500">
        <div className="text-center">
          <div className="mx-auto flex items-center justify-center h-20 w-20 rounded-full bg-blue-500/20 border border-blue-500/50 mb-6 shadow-[0_0_30px_rgba(59,130,246,0.3)]">
            <svg className="h-10 w-10 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-3xl font-bold text-white mb-2">Ticket Ingested!</h2>
          <p className="text-blue-400 font-mono tracking-wider">
             ID: {success.ticket_id}
          </p>
        </div>

        <div className="glass p-6 rounded-2xl border-blue-500/20">
          <div className="flex items-center gap-2 mb-4">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-ping"></div>
              <h3 className="text-xs font-bold text-blue-400 uppercase tracking-[0.2em]">AI Analysis & Response</h3>
          </div>
          <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap font-light italic">
            "{success.ai_response}"
          </div>
        </div>

        <button
          onClick={() => setSuccess(null)}
          className="w-full py-4 rounded-xl border border-white/10 text-gray-400 hover:text-white hover:bg-white/5 transition-all text-sm font-medium"
        >
          Close & Create New Interaction
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-500/10 border border-red-500/50 text-red-400 px-4 py-3 rounded-xl text-xs font-medium animate-shake">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest ml-1">Full Name</label>
            <input
              type="text"
              name="customer_name"
              value={form.customer_name}
              onChange={handleChange}
              required
              className="form-input-ai"
              placeholder="Shama Sadaf"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest ml-1">Secure Email</label>
            <input
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              required
              className="form-input-ai"
              placeholder="shama@example.com"
            />
          </div>
      </div>

      <div className="space-y-1.5">
        <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest ml-1">Subject</label>
        <input
          type="text"
          name="subject"
          value={form.subject}
          onChange={handleChange}
          required
          className="form-input-ai"
          placeholder="What can our FTE help you with?"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest ml-1">Classification</label>
          <select
            name="category"
            value={form.category}
            onChange={handleChange}
            className="form-input-ai bg-[#0f172a]"
          >
            <option value="technical">Technical</option>
            <option value="billing">Billing</option>
            <option value="account">Account</option>
            <option value="feature">Feature Request</option>
            <option value="bug">Bug Report</option>
          </select>
        </div>

        <div className="space-y-1.5">
          <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest ml-1">System Priority</label>
          <select
            name="priority"
            value={form.priority}
            onChange={handleChange}
            className="form-input-ai bg-[#0f172a]"
          >
            <option value="P1">P1 - Mission Critical</option>
            <option value="P2">P2 - High Priority</option>
            <option value="P3">P3 - Standard</option>
            <option value="P4">P4 - Routine</option>
          </select>
        </div>
      </div>

      <div className="space-y-1.5">
        <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest ml-1">Detailed Message</label>
        <textarea
          name="message"
          value={form.message}
          onChange={handleChange}
          required
          rows={3}
          className="form-input-ai resize-none"
          placeholder="Speak to the agent..."
        />
      </div>

      <div className="pt-2">
          <button
            type="submit"
            disabled={loading}
            className="btn-ai-primary flex items-center justify-center gap-3 disabled:opacity-50"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Processing through Pipeline...
              </>
            ) : (
              <>
                <span>Engage AI Agent</span>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </>
            )}
          </button>
      </div>
    </form>
  );
}
