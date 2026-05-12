import { submitLeadPreview } from "@/app/upload/actions";

export default function UploadPage() {
  return (
    <section className="upload-panel">
      <div className="card">
        <div className="eyebrow">Step 1</div>
        <h1>Upload your statement</h1>
        <p>
          PDF, XLSX, or XLSM. We show a partial preview first, then lock the
          full analysis behind a review or payment CTA.
        </p>
      </div>
      <div className="card">
        <div className="eyebrow">Step 2</div>
        <h1>Where should we send the full review?</h1>
        <p>
          The flow captures lead details and creates a preview session. If
          Supabase is not configured locally, it routes to a sample preview.
        </p>
        <form action={submitLeadPreview} className="form-grid">
          <div className="field">
            <label htmlFor="statement">Financial statement</label>
            <input id="statement" name="statement" type="file" accept=".pdf,.xlsx,.xlsm" required />
          </div>
          <div className="field">
            <label htmlFor="name">Name</label>
            <input id="name" name="name" required />
          </div>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" name="email" type="email" required />
          </div>
          <div className="field">
            <label htmlFor="company">Company</label>
            <input id="company" name="company" required />
          </div>
          <div className="field">
            <label htmlFor="intent">What do you want reviewed?</label>
            <select id="intent" name="intent" defaultValue="statement_review">
              <option value="statement_review">Financial statement review</option>
              <option value="cashflow_check">Cashflow check</option>
              <option value="lending_pack">Lending pack</option>
            </select>
          </div>
          <input type="hidden" name="sourceUrl" value="/upload" />
          <button className="button" type="submit">
            Create preview
          </button>
        </form>
      </div>
    </section>
  );
}
