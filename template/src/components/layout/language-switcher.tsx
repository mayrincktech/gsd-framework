"use client";

import { useLocale } from "next-intl";
import { useRouter, usePathname } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { Button } from "@/components/ui/button";

const localeLabels: Record<string, string> = {
  "pt-BR": "Português",
  en: "English",
};

export function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  const switchLocale = (newLocale: string) => {
    router.replace(pathname, { locale: newLocale });
  };

  return (
    <div className="flex gap-2">
      {routing.locales.map((l) => (
        <Button
          key={l}
          variant={locale === l ? "default" : "outline"}
          size="sm"
          onClick={() => switchLocale(l)}
        >
          {localeLabels[l]}
        </Button>
      ))}
    </div>
  );
}
