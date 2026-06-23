import { auth } from "@/lib/auth";
import createIntlMiddleware from "next-intl/middleware";
import { routing } from "@/i18n/routing";
import { NextResponse } from "next/server";

const intlMiddleware = createIntlMiddleware(routing);

const AUTH_PAGES = ["/login", "/signup"];

function isAuthPage(pathname: string): boolean {
  return AUTH_PAGES.some((page) => pathname.endsWith(page));
}

function getLocaleFromPath(pathname: string): string {
  const segment = pathname.split("/")[1];
  return routing.locales.includes(segment as never) ? segment : routing.defaultLocale;
}

export default auth((req) => {
  const { pathname } = req.nextUrl;

  // Let next-intl handle locale detection + rewriting
  const response = intlMiddleware(req);

  const isAuth = !!req.auth;
  const isAuthRoute = isAuthPage(pathname);

  // Not authenticated + trying to access protected page → redirect to login
  if (!isAuth && !isAuthRoute && !pathname.startsWith("/api")) {
    const locale = getLocaleFromPath(pathname);
    const loginUrl = new URL(`/${locale}/login`, req.url);
    return NextResponse.redirect(loginUrl);
  }

  // Authenticated + trying to access login/signup → redirect to dashboard
  if (isAuth && isAuthRoute) {
    const locale = getLocaleFromPath(pathname);
    const homeUrl = new URL(`/${locale}`, req.url);
    return NextResponse.redirect(homeUrl);
  }

  return response;
});

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
