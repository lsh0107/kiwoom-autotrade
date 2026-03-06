"use client";

import React from "react";
import { AuthContext, useAuthProvider } from "@/hooks/use-auth";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const auth = useAuthProvider();

  return <AuthContext value={auth}>{children}</AuthContext>;
}
