import { type Invoice, money } from "./arInvoiceTypes";
const date = (value: string | null) =>
  value
    ? new Date(`${value}T12:00:00`).toLocaleDateString("id-ID", {
        day: "2-digit",
        month: "long",
        year: "numeric",
      })
    : "—";

export default function PHRInvoice({ data }: { data: Invoice }) {
  const { layout, document: doc } = data;
  const subtotal = doc.lines.reduce(
    (sum, line) => sum + Number(line.amount),
    0,
  );
  return (
    <article
      className="phr-invoice print-document"
      data-print-ready={data.print_ready ? "true" : "false"}
    >
      <style>{`
      .phr-invoice { max-width:210mm; margin:auto; padding:6mm; background:white; color:#111; font:12px Arial,sans-serif; }
      .phr-letterhead { display:flex; align-items:center; gap:18px; border:2px solid #223755; border-radius:12px; padding:16px; text-align:center; margin-bottom:6px; }
      .phr-letterhead img { width:24mm; height:24mm; object-fit:contain; flex-shrink:0; }
      .phr-letterhead h1 { font: bold 22px Georgia,serif; color:#223755; margin:0 0 10px; }
      .phr-body { border:2px solid #223755; border-radius:12px; padding:22px; min-height:240mm; }
      .phr-body h2 { font-size:23px; text-decoration:underline; text-align:center; margin:0 0 24px; }
      .phr-meta { display:grid; grid-template-columns:1.2fr 1fr; gap:20px; margin-bottom:28px; }
      .phr-meta dl { display:grid; grid-template-columns:auto 1fr; gap:5px 12px; }
      .phr-meta dd { margin:0; overflow-wrap:anywhere; }
      .phr-invoice table { width:100%; border-collapse:collapse; margin-top:20px; table-layout:fixed; }
      .phr-invoice th,.phr-invoice td { border:1px solid #444; padding:5px; vertical-align:top; overflow-wrap:anywhere; white-space:normal!important; }
      .phr-invoice th:first-child { white-space:nowrap!important; }
      .phr-invoice .phr-money { text-align:right; white-space:nowrap!important; font-variant-numeric:tabular-nums; }
      .phr-payment { display:grid; grid-template-columns:1.4fr 1fr; gap:30px; margin-top:40px; break-inside:avoid; }
      .phr-signature { min-height:65px; }
      .phr-invoice p { white-space:pre-line; margin:4px 0; }
      .phr-warning { color:#a33; border:1px solid #a33; padding:8px; margin-bottom:10px; }
      @page { size:A4 portrait; margin:10mm; }
      @media print { .phr-invoice { max-width:none; padding:0!important; font-size:9pt; } .phr-body { min-height:240mm; } .phr-letterhead { break-inside:avoid; } .phr-invoice thead { display:table-header-group; } .phr-invoice tr { break-inside:avoid; } }
    `}</style>
      {!data.print_ready && (
        <p className="phr-warning">
          Complete invoice service details before printing. Service amounts plus
          tax must equal the AR invoice amount.
        </p>
      )}
      <header className="phr-letterhead">
        <img src="/logoprint.jpeg" alt="MMH" />
        <div><h1>PT. MUTIARA MERDEKA HOTEL</h1>
        <p>{layout.company_address}</p></div>
      </header>
      <section className="phr-body">
        <h2>{layout.title}</h2>
        <div className="phr-meta">
          <div>
            <p>
              <b>To:</b> {layout.billing_name || data.customer_name}
            </p>
            <p>{layout.billing_address || data.customer_address}</p>
            <p style={{ marginTop: 24 }}>
              <b>Attn:</b> {layout.attention}
            </p>
          </div>
          <dl>
            <dt>Inv. Date</dt>
            <dd>: {date(data.invoice_date)}</dd>
            <dt>Inv. Number</dt>
            <dd>: {data.invoice_number}</dd>
            <dt>Contract No.</dt>
            <dd>: {doc.contract_number || layout.contract_number || "—"}</dd>
            <dt>Contract Date</dt>
            <dd>: {date(doc.contract_date || layout.contract_date)}</dd>
          </dl>
        </div>
        <p>{doc.description}</p>
        <table>
          <colgroup>
            <col style={{ width: "6%" }} />
            <col style={{ width: "25%" }} />
            <col style={{ width: "46%" }} />
            <col style={{ width: "23%" }} />
          </colgroup>
          <thead>
            <tr>
              <th>No.</th>
              <th>Reg No.</th>
              <th>Service</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {doc.lines.map((line, i) => (
              <tr key={i}>
                <td>{i + 1}</td>
                <td>{line.registration_number}</td>
                <td>{line.description}</td>
                <td className="phr-money">Rp {money(line.amount)}</td>
              </tr>
            ))}
            <tr>
              <td colSpan={3}>TOTAL</td>
              <td className="phr-money">Rp {money(subtotal)}</td>
            </tr>
            <tr>
              <td colSpan={3}>{doc.tax_label}</td>
              <td className="phr-money">Rp {money(doc.tax_amount)}</td>
            </tr>
            <tr>
              <td colSpan={3}>Grand Total</td>
              <td className="phr-money">Rp {money(data.amount)}</td>
            </tr>
            <tr style={{ fontWeight: "bold" }}>
              <td colSpan={3}><i>Total be Paid</i></td>
              <td className="phr-money">Rp {money(data.amount)}</td>
            </tr>
            {doc.amount_in_words && (
              <tr>
                <td colSpan={4}>
                  <i>Said: {doc.amount_in_words}</i>
                </td>
              </tr>
            )}
            {layout.show_settlement && (
              <>
                <tr>
                  <td colSpan={3}>Received</td>
                  <td className="phr-money">
                    Rp {money(data.received_amount)}
                  </td>
                </tr>
                <tr>
                  <td colSpan={3}>Outstanding</td>
                  <td className="phr-money">
                    Rp {money(data.outstanding_amount)}
                  </td>
                </tr>
              </>
            )}
          </tbody>
        </table>
        <div className="phr-payment">
          <div>
            <p>{layout.payment_instructions}</p>
          </div>
          <div>
            <p>Authorized by,</p>
            <p>PT. Mutiara Merdeka Hotel</p>
            <div className="phr-signature" />
            <p>
              <u>{layout.signer_name}</u>
            </p>
            <p>{layout.signer_position}</p>
          </div>
        </div>
        {layout.footer && <p style={{ marginTop: 24 }}>{layout.footer}</p>}
      </section>
    </article>
  );
}
