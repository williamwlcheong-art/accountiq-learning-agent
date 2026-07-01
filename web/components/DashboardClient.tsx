"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, FileText, LogOut, UploadCloud } from "lucide-react";
import { API_BASE, apiFetch } from "../lib/api";

type User = {
  id: number;
  email: string;
  is_admin?: number;
};

type Product = {
  key: string;
  name: string;
  report_type: string | null;
  price_cents: number | null;
  gst_cents: number | null;
  currency: string;
  enabled: boolean;
  description: string;
};

type UploadResult = {
  company_id: number;
  document_id: number;
  order_id: number;
  status: string;
};

type Order = {
  id: number;
  order_id: number;
  company_id: number;
  document_id: number;
  report_id: number | null;
  product_key: string;
  report_type: string;
  price_cents: number;
  gst_cents: number;
  currency: string;
  status: string;
  validation_status: string;
  payment_status: string;
  review_status: string;
  delivery_status: string;
  business_name: string;
  filename: string;
  document_status: string;
  report_status: string | null;
  product: Product | null;
};

type DemoReportResult = {
  order_id: number;
  report_id: number;
  status: string;
  order_status: string;
};

const STATUS_LABELS: Record<string, string> = {
  awaiting_payment: "Awaiting payment",
  awaiting_review: "Awaiting Todd review",
  delivered: "Delivered",
  demo: "Demo",
  failed: "Failed",
  failed_generation: "Generation failed",
  failed_validation: "Validation failed",
  generating: "Generating draft",
  needs_clarification: "Needs clarification",
  not_ready: "Not ready",
  not_started: "Not started",
  passed: "Validated",
  pending: "Pending",
  processing: "Processing",
  validating: "Validating",
};

function formatStatus(value: string | null | undefined) {
  if (!value) {
    return "Waiting";
  }
  return STATUS_LABELS[value] || value.replace(/_/g, " ");
}

function formatPrice(product: Product | null | undefined) {
  if (!product || product.price_cents === null) {
    return "Manual quote";
  }
  return `NZ$${(product.price_cents / 100).toLocaleString("en-NZ", {
    maximumFractionDigits: 0,
  })} + GST`;
}

function orderTimeline(order: Order | null) {
  return [
    {
      label: "Upload",
      value: order ? `Document #${order.document_id}` : "Waiting",
      state: order ? "done" : "waiting",
    },
    {
      label: "Validation",
      value: formatStatus(order?.validation_status),
      state: order?.validation_status === "passed" ? "done" : order ? "active" : "waiting",
    },
    {
      label: "Payment",
      value: order?.payment_status === "demo" ? "Demo mode" : formatStatus(order?.payment_status),
      state: order?.payment_status === "demo" ? "done" : order?.status === "awaiting_payment" ? "active" : "waiting",
    },
    {
      label: "Draft generation",
      value: order?.report_id ? `Report #${order.report_id}` : formatStatus(order?.report_status),
      state: order?.report_id ? "done" : order?.status === "generating" ? "active" : "waiting",
    },
    {
      label: "Todd review",
      value: formatStatus(order?.review_status),
      state: order?.review_status === "awaiting_review" ? "active" : "waiting",
    },
    {
      label: "Delivery",
      value: formatStatus(order?.delivery_status),
      state: order?.delivery_status === "delivered" ? "done" : "waiting",
    },
  ];
}

export function DashboardClient() {
  const [user, setUser] = useState<User | null>(null);
  const [checkingUser, setCheckingUser] = useState(true);
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedProductKey, setSelectedProductKey] = useState("business_valuation");
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [businessName, setBusinessName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const selectedProduct = useMemo(
    () => products.find((product) => product.key === selectedProductKey) || products.find((product) => product.enabled) || null,
    [products, selectedProductKey],
  );

  const selectedOrder = useMemo(
    () => orders.find((order) => order.id === selectedOrderId) || orders[0] || null,
    [orders, selectedOrderId],
  );

  const canRequestDemoDraft = Boolean(
    selectedOrder?.validation_status === "passed"
      && !selectedOrder.report_id
      && (process.env.NODE_ENV !== "production" || user?.is_admin),
  );

  const reportViewHref = useMemo(() => {
    if (!selectedOrder?.report_id || selectedOrder.report_status !== "done") {
      return "";
    }
    return `${API_BASE}/wizard/report/${selectedOrder.report_id}/view`;
  }, [selectedOrder]);

  function applyOrders(nextOrders: Order[], preferredId?: number) {
    setOrders(nextOrders);
    setSelectedOrderId((current) => {
      if (preferredId && nextOrders.some((order) => order.id === preferredId)) {
        return preferredId;
      }
      if (current && nextOrders.some((order) => order.id === current)) {
        return current;
      }
      return nextOrders[0]?.id || null;
    });
  }

  async function loadOrders(preferredId?: number) {
    const nextOrders = await apiFetch<Order[]>("/wizard/orders");
    applyOrders(nextOrders, preferredId);
  }

  useEffect(() => {
    apiFetch<User>("/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setCheckingUser(false));
  }, []);

  useEffect(() => {
    if (!user) {
      return;
    }

    let cancelled = false;
    async function loadWorkspace() {
      try {
        const [nextProducts, nextOrders] = await Promise.all([
          apiFetch<Product[]>("/wizard/products"),
          apiFetch<Order[]>("/wizard/orders"),
        ]);
        if (cancelled) {
          return;
        }
        setProducts(nextProducts);
        setSelectedProductKey(nextProducts.find((product) => product.enabled)?.key || "business_valuation");
        applyOrders(nextOrders);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load workspace");
        }
      }
    }

    loadWorkspace();
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    if (!user || !selectedOrder || !["validating", "generating"].includes(selectedOrder.status)) {
      return;
    }

    const interval = window.setInterval(() => {
      loadOrders(selectedOrder.id).catch((err) => {
        setError(err instanceof Error ? err.message : "Could not refresh order status");
      });
    }, 1500);

    return () => window.clearInterval(interval);
  }, [selectedOrder?.id, selectedOrder?.status, user]);

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] || null);
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Select a statement file first.");
      return;
    }
    if (!selectedProduct?.enabled) {
      setError("Select an available product first.");
      return;
    }

    setBusy("upload");
    setError("");

    const body = new FormData();
    body.append("business_name", businessName);
    body.append("product_key", selectedProduct.key);
    body.append("file", file);

    try {
      const result = await apiFetch<UploadResult>("/wizard/upload", {
        method: "POST",
        body,
      });
      await loadOrders(result.order_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy("");
    }
  }

  async function generateDemoDraft() {
    if (!selectedOrder) {
      return;
    }

    setBusy("demo");
    setError("");

    try {
      const result = await apiFetch<DemoReportResult>(`/wizard/orders/${selectedOrder.id}/generate-demo-report`, {
        method: "POST",
      });
      await loadOrders(result.order_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo draft generation failed");
    } finally {
      setBusy("");
    }
  }

  async function logout() {
    await apiFetch<{ ok: boolean }>("/auth/logout", { method: "POST" });
    window.location.href = "/";
  }

  if (checkingUser) {
    return (
      <main className="screen dashboard-screen">
        <section className="empty-state">
          <h1>AccountIQ dashboard</h1>
          <p>Loading your report workspace.</p>
        </section>
      </main>
    );
  }

  if (user === null) {
    return (
      <main className="screen dashboard-screen">
        <section className="empty-state">
          <h1>AccountIQ dashboard</h1>
          <p>Sign in to upload statements and view report jobs.</p>
          <Link className="primary-button" href="/login">
            Sign in
            <ArrowRight aria-hidden="true" size={18} />
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="screen dashboard-screen">
      <nav className="app-nav">
        <Link className="brand small" href="/">
          <span className="brand-mark">a</span>
          AccountIQ
        </Link>
        <div className="nav-actions">
          <span>{user.email}</span>
          <button className="icon-button" onClick={logout} title="Sign out" type="button">
            <LogOut aria-hidden="true" size={18} />
          </button>
        </div>
      </nav>

      <section className="dashboard-grid">
        <div className="panel upload-panel">
          <div className="panel-heading">
            <UploadCloud aria-hidden="true" size={22} />
            <div>
              <h1>New valuation order</h1>
              <p>Select the product and upload recent financial statements.</p>
            </div>
          </div>

          <div className="product-picker" aria-label="Report product" role="radiogroup">
            {products.map((product) => (
              <label className={`product-option${product.key === selectedProductKey ? " selected" : ""}`} key={product.key}>
                <input
                  checked={product.key === selectedProductKey}
                  disabled={!product.enabled}
                  name="product"
                  onChange={() => setSelectedProductKey(product.key)}
                  type="radio"
                />
                <span>
                  <strong>{product.name}</strong>
                  <small>{product.enabled ? formatPrice(product) : "Coming later"}</small>
                </span>
              </label>
            ))}
          </div>

          <form onSubmit={upload}>
            <label>
              Business name
              <input
                onChange={(event) => setBusinessName(event.target.value)}
                required
                type="text"
                value={businessName}
              />
            </label>
            <label>
              Financial statements
              <input
                accept=".pdf,.xlsx,.xls,.xlsm,.docx"
                onChange={handleFile}
                required
                type="file"
              />
            </label>
            <button className="primary-button full-width" disabled={busy === "upload"} type="submit">
              <UploadCloud aria-hidden="true" size={18} />
              {busy === "upload" ? "Uploading" : "Create order"}
            </button>
          </form>

          <div className="order-history">
            <h2>Order history</h2>
            {orders.length ? (
              <div className="history-list">
                {orders.map((order) => (
                  <button
                    className={order.id === selectedOrder?.id ? "selected" : ""}
                    key={order.id}
                    onClick={() => setSelectedOrderId(order.id)}
                    type="button"
                  >
                    <span>
                      <strong>{order.business_name}</strong>
                      <small>{formatStatus(order.status)}</small>
                    </span>
                    <small>#{order.id}</small>
                  </button>
                ))}
              </div>
            ) : (
              <p className="muted-copy">No orders yet.</p>
            )}
          </div>
        </div>

        <div className="panel report-panel">
          <div className="panel-heading">
            <FileText aria-hidden="true" size={22} />
            <div>
              <h2>Order workspace</h2>
              <p>{selectedOrder ? selectedOrder.business_name : "Create an order to begin validation."}</p>
            </div>
          </div>

          <div className="order-summary">
            <div>
              <span>Product</span>
              <strong>{selectedOrder?.product?.name || selectedProduct?.name || "Business Valuation Report"}</strong>
            </div>
            <div>
              <span>Price</span>
              <strong>{selectedOrder ? formatPrice(selectedOrder.product) : formatPrice(selectedProduct)}</strong>
            </div>
          </div>

          <div className="timeline-list">
            {orderTimeline(selectedOrder).map((step) => (
              <div className={`timeline-step ${step.state}`} key={step.label}>
                <CheckCircle2 aria-hidden="true" size={18} />
                <span>{step.label}</span>
                <strong>{step.value}</strong>
              </div>
            ))}
          </div>

          {canRequestDemoDraft ? (
            <button
              className="primary-button full-width"
              disabled={busy === "demo"}
              onClick={generateDemoDraft}
              type="button"
            >
              <FileText aria-hidden="true" size={18} />
              {busy === "demo" ? "Creating draft" : "Generate demo draft"}
            </button>
          ) : null}

          {selectedOrder?.status === "awaiting_payment" ? (
            <p className="muted-copy">
              Payment is the next production gate. Stripe is intentionally not enabled in this slice.
            </p>
          ) : null}

          {selectedOrder?.status === "awaiting_review" ? (
            <p className="review-note">Draft ready for Todd review. This is not delivered to the customer yet.</p>
          ) : null}

          {reportViewHref ? (
            <a className="secondary-button full-width" href={reportViewHref} rel="noreferrer" target="_blank">
              Open generated draft (demo)
              <ArrowRight aria-hidden="true" size={18} />
            </a>
          ) : null}

          {error ? <p className="form-error">{error}</p> : null}
        </div>
      </section>
    </main>
  );
}
