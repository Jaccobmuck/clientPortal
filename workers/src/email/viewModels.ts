export type InvoiceRow = {
  id: string;
  org_id: string;
  client_id: string;
  invoice_number: string;
  status: string;
  pay_token: string;
  due_date: string | null;
  issued_at: string | null;
  sent_at: string | null;
  paid_at: string | null;
  subtotal: string;
  tax_rate: string;
  tax_amount: string;
  total: string;
  notes: string | null;
};

export type ClientRow = {
  id: string;
  name: string;
  email: string;
  company: string | null;
};

export type OrgRow = {
  id: string;
  name: string;
  slug: string;
};

export type InvoiceEmailViewModel = {
  invoiceNumber: string;
  invoiceStatus: string;
  clientName: string;
  clientEmail: string;
  clientCompany: string | null;
  orgName: string;
  totalFormatted: string;
  subtotalFormatted: string;
  taxFormatted: string;
  dueDateFormatted: string | null;
  issuedAtFormatted: string | null;
  paidAtFormatted: string | null;
  payUrl: string | null;
  reminderOffsetDays: number | undefined;
};

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
});

const dateFormatter = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "long",
  day: "numeric",
  timeZone: "UTC",
});

export function formatCurrency(dbValue: string): string {
  const num = Number(dbValue);
  if (Number.isNaN(num)) {
    return "$0.00";
  }
  return currencyFormatter.format(num);
}

export function formatDate(isoString: string | null): string | null {
  if (!isoString) {
    return null;
  }
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return dateFormatter.format(date);
}

export function buildPayUrl(payToken: string, frontendUrl: string): string {
  const base = frontendUrl.replace(/\/+$/, "");
  return `${base}/pay/${payToken}`;
}

export function buildViewModel(params: {
  invoice: InvoiceRow;
  client: ClientRow;
  org: OrgRow;
  frontendUrl: string;
  reminderOffsetDays?: number;
}): InvoiceEmailViewModel {
  const { invoice, client, org, frontendUrl, reminderOffsetDays } = params;

  return {
    invoiceNumber: invoice.invoice_number,
    invoiceStatus: invoice.status,
    clientName: client.name,
    clientEmail: client.email,
    clientCompany: client.company,
    orgName: org.name,
    totalFormatted: formatCurrency(invoice.total),
    subtotalFormatted: formatCurrency(invoice.subtotal),
    taxFormatted: formatCurrency(invoice.tax_amount),
    dueDateFormatted: formatDate(invoice.due_date),
    issuedAtFormatted: formatDate(invoice.issued_at),
    paidAtFormatted: formatDate(invoice.paid_at),
    payUrl: buildPayUrl(invoice.pay_token, frontendUrl),
    reminderOffsetDays,
  };
}
