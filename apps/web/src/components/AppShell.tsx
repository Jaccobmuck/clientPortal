import { ReactNode } from "react";
import { TopNav } from "@/components/TopNav";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <main className="freelio-page dashboard-page">
      <div className="app-shell">
        <TopNav />
        {children}
      </div>
    </main>
  );
}
