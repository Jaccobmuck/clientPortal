import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Freelio",
  description: "Simple invoicing for freelancers",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
