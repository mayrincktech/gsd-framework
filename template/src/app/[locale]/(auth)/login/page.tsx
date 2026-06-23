import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { LoginForm } from "@/components/auth/login-form";
import { GitHubButton } from "@/components/auth/github-button";

export default async function LoginPage() {
  const t = await getTranslations("Auth");
  const githubEnabled = !!process.env.AUTH_GITHUB_ID;

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-xl">{t("loginTitle")}</CardTitle>
        <CardDescription>{t("loginSubtitle")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <LoginForm />
        {githubEnabled && (
          <>
            <div className="relative py-2">
              <Separator />
              <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-card px-2 text-xs text-muted-foreground">
                {t("orContinueWith")}
              </span>
            </div>
            <GitHubButton label="GitHub" />
          </>
        )}
      </CardContent>
      <CardFooter className="justify-center">
        <p className="text-sm text-muted-foreground">
          {t("noAccount")}{" "}
          <Link href="/signup" className="text-foreground underline">
            {t("createAccount")}
          </Link>
        </p>
      </CardFooter>
    </Card>
  );
}
