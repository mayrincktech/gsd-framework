export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen items-center justify-center px-4">
      {/* Subtle gradient background */}
      <div
        className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_var(--color-accent)_0%,_transparent_50%)] opacity-50"
        aria-hidden
      />
      <div className="w-full max-w-sm">{children}</div>
    </div>
  );
}
