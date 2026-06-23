import { getTranslations } from "next-intl/server";
import { auth } from "@/lib/auth";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { FolderKanban, Activity, CheckCircle } from "lucide-react";

export default async function DashboardPage() {
  const t = await getTranslations("Dashboard");
  const session = await auth();

  const stats = [
    { label: t("stats.projects"), value: "0", icon: FolderKanban },
    { label: t("stats.active"), value: "0", icon: Activity },
    { label: t("stats.completed"), value: "0", icon: CheckCircle },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <p className="text-muted-foreground">
          {t("welcome")}, {session?.user?.name}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {stat.label}
                </CardTitle>
                <stat.icon className="size-4 text-muted-foreground" />
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{stat.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div>
        <h2 className="mb-4 text-lg font-semibold">{t("recentActivity")}</h2>
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            {t("noActivity")}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
