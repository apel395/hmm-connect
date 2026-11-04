import { rupiahWords } from "./phrInvoiceFormat";
import { type Invoice } from "./arInvoiceTypes";
const date = (value: string | null) =>
  value
    ? new Date(`${value}T12:00:00`).toLocaleDateString("id-ID", {
        day: "2-digit",
        month: "long",
        year: "numeric",
      })
    : "—";
const amount = (value: unknown) =>
  Number(value || 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

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
      .phr-invoice,.phr-invoice * { box-sizing:border-box; }
      .phr-invoice { width:198mm; max-width:100%; margin:0 auto; padding:0; background:#fff; color:#161616; font:10pt Roboto,Arial,sans-serif; line-height:1.35; }
      .phr-letterhead { display:flex; align-items:center; gap:7mm; border:1.5px solid #26365b; border-radius:4mm; padding:2mm 6mm; min-height:29mm; text-align:center; margin-bottom:1.5mm; }
      .phr-letterhead img { width:24mm; height:24mm; object-fit:contain; flex-shrink:0; }
      .phr-letterhead-copy { flex:1; }
      .phr-letterhead h1 { font:bold 19pt Roboto,Arial,sans-serif; color:#26365b; margin:0 0 3mm; white-space:nowrap; }
      .phr-letterhead p { font-size:8.5pt; font-weight:600; color:#26365b; }
      .phr-body { border:1.5px solid #26365b; border-radius:4mm; padding:4mm; min-height:228mm; }
      .phr-body h2 { font-size:20pt; font-weight:700; text-decoration:underline; text-align:center; margin:0 0 5mm; }
      .phr-meta { display:grid; grid-template-columns:58% 42%; gap:0; }
      .phr-bill-to { display:grid; grid-template-columns:8mm 1fr; gap:0 1mm; }
      .phr-bill-to p { margin:0 0 1mm; }
      .phr-meta dl { display:grid; grid-template-columns:26mm 1fr; align-content:start; gap:1mm 2mm; margin:0; font-size:9pt; }
      .phr-meta dd { margin:0; overflow-wrap:anywhere; }
      .phr-attention { display:flex; gap:3mm; margin-top:9mm; }
      .phr-service-description { margin:12mm 0 4mm!important; }
      .phr-invoice table { width:100%; border-collapse:collapse; table-layout:fixed; font-size:8pt; }
      .phr-invoice th,.phr-invoice td { border:1px solid #444; padding:1mm; vertical-align:top; overflow-wrap:anywhere; white-space:normal!important; }
      .phr-invoice th { font-weight:600; text-align:center; }
      .phr-invoice .phr-row-no { text-align:center; }
      .phr-invoice .phr-reg-no { text-align:center; }
      .phr-invoice .phr-money { white-space:nowrap!important; text-align:right; font-variant-numeric:tabular-nums; }
      .phr-currency { display:inline-block; margin-right:2mm; }
      .phr-invoice .phr-spacer td { height:4mm; padding:0; }
      .phr-invoice .phr-words { height:8mm; font-style:italic; }
      .phr-payment { display:grid; grid-template-columns:1fr 44mm; gap:14mm; margin:17mm 9mm 0; font-size:9pt; break-inside:avoid; }
      .phr-signature { height:24mm; }
      .phr-invoice p { white-space:pre-line; margin:1mm 0; }
      .phr-warning { color:#9b1c1c; border:1px solid #9b1c1c; padding:3mm; margin:0 0 3mm; }
      .phr-footer { margin-top:6mm!important; font-size:8pt; }
      @page { size:Letter portrait; margin:9mm; }
      @media print { .phr-invoice { width:100%; max-width:none; padding:0!important; } .phr-letterhead,.phr-payment { break-inside:avoid; } .phr-invoice thead { display:table-header-group; } .phr-invoice tr { break-inside:avoid; } .phr-invoice .phr-totals { break-inside:avoid; } }
      @media screen and (max-width:700px) { .phr-invoice { min-width:190mm; } }
    `}</style>
      {!data.print_ready && (
        <p className="phr-warning" role="alert">
          Complete invoice service details before printing. Service amounts plus
          tax must equal the AR invoice amount.
        </p>
      )}
      <header className="phr-letterhead">
        <img src="/logoprint.jpeg" alt="MMH" />
        <div className="phr-letterhead-copy">
          <h1>PT. MUTIARA MERDEKA HOTEL</h1>
          <p>
            {layout.company_address ||
              "Jln. Yos Sudarso 12 A  P.O. Box 1129  Hunting lines (0761) 31272 - 32526  Fax (0761) 32959\nPekanbaru - Riau - Indonesia"}
          </p>
        </div>
      </header>
      <section className="phr-body">
        <h2>{layout.title}</h2>
        <div className="phr-meta">
          <div className="phr-bill-to">
            <span>To :</span>
            <div>
              <p>{layout.billing_name || data.customer_name}</p>
              <p>{layout.billing_address || data.customer_address}</p>
            </div>
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
        <div className="phr-attention">
          <span>Attn :</span>
          <span>{layout.attention || "Finance & Accounting Dept."}</span>
        </div>
        <p className="phr-service-description">
          {doc.description ||
            layout.description.replace(/^Invoice amount$/, "") ||
            "Catering Service"}
        </p>
        <table aria-label="Invoice service details">
          <colgroup>
            <col style={{ width: "4.5%" }} />
            <col style={{ width: "27%" }} />
            <col style={{ width: "50%" }} />
            <col style={{ width: "18.5%" }} />
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
                <td className="phr-row-no">{i + 1}</td>
                <td className="phr-reg-no">{line.registration_number}</td>
                <td>{line.description}</td>
                <td className="phr-money">
                  <span className="phr-currency">Rp</span>
                  {amount(line.amount)}
                </td>
              </tr>
            ))}
            <tr className="phr-spacer" aria-hidden="true">
              <td />
              <td />
              <td />
              <td />
            </tr>
          </tbody>
          <tbody className="phr-totals">
            <tr>
              <td colSpan={3}>TOTAL</td>
              <td className="phr-money">
                <span className="phr-currency">Rp</span>
                {amount(subtotal)}
              </td>
            </tr>
            <tr>
              <td colSpan={3}>{doc.tax_label || "Tax"}</td>
              <td className="phr-money">
                <span className="phr-currency">Rp</span>
                {amount(doc.tax_amount)}
              </td>
            </tr>
            <tr>
              <td colSpan={3}>Grand Total</td>
              <td className="phr-money">
                <span className="phr-currency">Rp</span>
                {amount(data.amount)}
              </td>
            </tr>
            <tr className="phr-spacer" aria-hidden="true">
              <td colSpan={3} />
              <td />
            </tr>
            <tr style={{ fontWeight: "bold", fontStyle: "italic" }}>
              <td colSpan={3}>Total be Paid</td>
              <td className="phr-money">
                <span className="phr-currency">Rp</span>
                {amount(data.amount)}
              </td>
            </tr>
            <tr>
              <td className="phr-words" colSpan={4}>
                Said :&nbsp;{" "}
                {doc.amount_in_words || rupiahWords(String(data.amount))}
              </td>
            </tr>
            {layout.show_settlement && (
              <>
                <tr>
                  <td colSpan={3}>Received</td>
                  <td className="phr-money">
                    <span className="phr-currency">Rp</span>
                    {amount(data.received_amount)}
                  </td>
                </tr>
                <tr>
                  <td colSpan={3}>Outstanding</td>
                  <td className="phr-money">
                    <span className="phr-currency">Rp</span>
                    {amount(data.outstanding_amount)}
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
            <div className="phr-signature" aria-label="Signature space" />
            <p>
              <u>{layout.signer_name}</u>
            </p>
            <p>{layout.signer_position}</p>
          </div>
        </div>
        {layout.footer && <p className="phr-footer">{layout.footer}</p>}
      </section>
    </article>
  );
}
