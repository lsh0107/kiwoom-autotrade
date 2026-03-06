"use client";

import { useRouter } from "next/navigation";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { useAuth } from "@/hooks/use-auth";
import { Spinner } from "@/components/ui/spinner";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner className="size-6" />
      </div>
    );
  }

  // middleware가 1차 차단하지만, 토큰 만료 등으로 인증 실패 시 fallback
  if (!user) {
    router.replace("/login");
    return null;
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <main className="flex-1">
        <header className="flex h-14 items-center gap-4 border-b px-6">
          <SidebarTrigger />
          <div className="ml-auto text-sm text-muted-foreground">
            {user.email}
          </div>
        </header>
        <div className="p-6">{children}</div>
      </main>
    </SidebarProvider>
  );
}
