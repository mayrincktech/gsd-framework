import { getTranslations } from "next-intl/server";
import { auth } from "@/lib/auth";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { LanguageSwitcher } from "@/components/layout/language-switcher";

export default async function SettingsPage() {
  const t = await getTranslations("Settings");
  const session = await auth();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">{t("title")}</h1>
      </div>

      {/* Appearance */}
      <Card>
        <CardHeader>
          <CardTitle>{t("appearance")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{t("theme")}</p>
              <p className="text-sm text-muted-foreground">
                {t("light")} / {t("dark")}
              </p>
            </div>
            <ThemeToggle />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{t("language")}</p>
              <p className="text-sm text-muted-foreground">PT-BR / EN</p>
            </div>
            <LanguageSwitcher />
          </div>
        </CardContent>
      </Card>

      {/* Account */}
      <Card>
        <CardHeader>
          <CardTitle>{t("account")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm text-muted-foreground">{t("name")}</p>
            <p className="font-medium">{session?.user?.name}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">{t("email")}</p>
            <p className="font-medium">{session?.user?.email}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
