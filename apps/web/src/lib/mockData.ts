export const summaryStats = [
  {
    title: "Total invoices",
    value: "182",
    trend: "+12 created this month",
    badge: "TI",
    tone: "green",
  },
  {
    title: "Total payments",
    value: "14",
    trend: "8 settled this week",
    badge: "TP",
    tone: "mint",
  },
  {
    title: "Total revenue",
    value: "$12,856.14",
    trend: "+18.2% from April",
    badge: "TR",
    tone: "cream",
  },
  {
    title: "Overdue invoices",
    value: "5",
    trend: "$2,150 needs attention",
    badge: "OI",
    tone: "orange",
  },
];

export const revenueData = [
  { label: "Jan", value: "$7.8k", height: 45 },
  { label: "Feb", value: "$9.1k", height: 58 },
  { label: "Mar", value: "$8.4k", height: 51 },
  { label: "Apr", value: "$10.9k", height: 72 },
  { label: "May", value: "$12.8k", height: 86 },
  { label: "Jun", value: "$11.4k", height: 76 },
];

export const invoiceStatus = [
  { label: "Draft", count: 18, progress: 26, tone: "draft" },
  { label: "Sent", count: 62, progress: 68, tone: "sent" },
  { label: "Paid", count: 97, progress: 88, tone: "paid" },
  { label: "Overdue", count: 5, progress: 18, tone: "overdue" },
];

export const recentInvoices = [
  {
    client: "Redesign Mobile App",
    invoice: "INV-2026-001",
    status: "Paid",
    dueDate: "May 14, 2026",
    amount: "$2,400",
  },
  {
    client: "Website Refresh",
    invoice: "INV-2026-002",
    status: "Sent",
    dueDate: "May 22, 2026",
    amount: "$1,850",
  },
  {
    client: "Brand Kit Design",
    invoice: "INV-2026-003",
    status: "Overdue",
    dueDate: "Apr 30, 2026",
    amount: "$950",
  },
  {
    client: "Monthly Retainer",
    invoice: "INV-2026-004",
    status: "Draft",
    dueDate: "Jun 01, 2026",
    amount: "$3,200",
  },
];

export const quickActions = [
  "Create invoice",
  "Add client",
  "Record payment",
  "View reports",
];

export const categories = [
  { title: "Consulting", value: "$4,260", detail: "32 billable hours", tone: "green" },
  { title: "Design", value: "$3,350", detail: "5 active projects", tone: "cream" },
  { title: "Development", value: "$3,996", detail: "2 milestones due", tone: "mint" },
  { title: "Marketing", value: "$1,250", detail: "3 retainers", tone: "orange" },
];
