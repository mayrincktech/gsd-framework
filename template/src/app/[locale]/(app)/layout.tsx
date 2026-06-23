import { Sidebar } from "@/components/layout/sidebar";
import { BottomNav } from "@/components/layout/bottom-nav";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <Sidebar />

      {/* Main content */}
      <main className="flex-1 overflow-x-hidden pb-14 md:pb-0">
        <div className="mx-auto max-w-5xl px-4 py-8 md:px-8">{children}</div>
      </main>

      {/* Mobile bottom nav */}
      <BottomNav />
    </div>
  );
}
