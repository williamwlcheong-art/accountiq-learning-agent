"use client";

import { useState } from "react";

type LeadFormProps = {
  onSubmit?: (lead: { name: string; email: string; company: string; intent: string }) => void;
};

export function LeadForm({ onSubmit }: LeadFormProps) {
  const [lead, setLead] = useState({
    name: "",
    email: "",
    company: "",
    intent: "statement_review",
  });

  return (
    <form
      className="form-grid"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit?.(lead);
      }}
    >
      <div className="field">
        <label htmlFor="name">Name</label>
        <input
          id="name"
          required
          value={lead.name}
          onChange={(event) => setLead({ ...lead, name: event.target.value })}
        />
      </div>
      <div className="field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          required
          type="email"
          value={lead.email}
          onChange={(event) => setLead({ ...lead, email: event.target.value })}
        />
      </div>
      <div className="field">
        <label htmlFor="company">Company</label>
        <input
          id="company"
          required
          value={lead.company}
          onChange={(event) => setLead({ ...lead, company: event.target.value })}
        />
      </div>
      <div className="field">
        <label htmlFor="intent">What do you want reviewed?</label>
        <select
          id="intent"
          value={lead.intent}
          onChange={(event) => setLead({ ...lead, intent: event.target.value })}
        >
          <option value="statement_review">Financial statement review</option>
          <option value="cashflow_check">Cashflow check</option>
          <option value="lending_pack">Lending pack</option>
        </select>
      </div>
      <button className="button" type="submit">
        Save details
      </button>
    </form>
  );
}
