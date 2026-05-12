import { recentInvoices } from "@/lib/mockData";

const statusClassName: Record<string, string> = {
  Draft: "draft",
  Overdue: "overdue",
  Paid: "paid",
  Sent: "sent",
};

export function RecentInvoices() {
  return (
    <section className="recent-card card" aria-labelledby="recent-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Recent work</p>
          <h2 id="recent-title">Recent invoices</h2>
        </div>
        <button className="ghost-button table-action" type="button">
          View all
        </button>
      </div>

      <table className="invoice-table">
        <thead>
          <tr>
            <th>Client</th>
            <th>Invoice #</th>
            <th>Status</th>
            <th>Due date</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          {recentInvoices.map((invoice) => (
            <tr key={invoice.invoice}>
              <td data-label="Client">{invoice.client}</td>
              <td data-label="Invoice #">{invoice.invoice}</td>
              <td data-label="Status">
                <span className={`status-pill status-pill--${statusClassName[invoice.status]}`}>
                  {invoice.status}
                </span>
              </td>
              <td data-label="Due date">{invoice.dueDate}</td>
              <td data-label="Amount">{invoice.amount}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
