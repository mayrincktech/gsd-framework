"use client";

import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { LayoutDashboard, FolderKanban, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/" as const, icon: LayoutDashboard, key: "dashboard" as const },
  { href: "/projects" as const, icon: FolderKanban, key: "projects" as const },
  { href: "/settings" as const, icon: Settings, key: "settings" as const },
];

export function BottomNav() {
  const t = useTranslations("Nav");
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex h-14 items-center justify-around border-t bg-background md:hidden">
      {navItems.map((item) => {
        const isActive = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex flex-col items-center gap-1 px-3 py-1.5 text-xs transition-colors",
              isActive ? "text-foreground" : "text-muted-foreground"
            )}
          >
            <item.icon className="size-5" />
            {t(item.key)}
          </Link>
        );
      })}
    </nav>
  );
}
