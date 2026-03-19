"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth } from "@/hooks/use-auth";
import { useCredentials } from "@/hooks/queries/use-credentials";
import { useSaveCredential } from "@/hooks/mutations/use-save-credential";
import { useDeleteCredential } from "@/hooks/mutations/use-delete-credential";
import { formatLocalDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  CheckCircle2,
  KeyRound,
  LogOut,
  Mail,
  Shield,
  Trash2,
  User,
  XCircle,
} from "lucide-react";

/* ── API 키 등록 Zod 스키마 ── */
const credentialSchema = z.object({
  app_key: z.string().min(1, "App Key를 입력해주세요"),
  app_secret: z.string().min(1, "App Secret을 입력해주세요"),
  account_no: z.string().min(1, "계좌번호를 입력해주세요"),
  is_mock: z.boolean(),
});
type CredentialFormValues = z.infer<typeof credentialSchema>;

/* ── Skeleton Loading ── */
function SettingsSkeleton() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Skeleton className="h-8 w-24" />
        <Skeleton className="mt-1 h-4 w-48" />
      </div>
      <Skeleton className="h-px w-full" />
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-24" />
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-40" />
          </div>
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-12" />
            <Skeleton className="h-5 w-16" />
          </div>
        </CardContent>
        <CardFooter>
          <Skeleton className="h-9 w-24" />
        </CardFooter>
      </Card>
      <Skeleton className="h-px w-full" />
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-32" />
        </CardHeader>
        <CardContent className="space-y-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-md" />
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-36" />
          <Skeleton className="mt-1 h-4 w-64" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-9 w-40" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </CardContent>
        <CardFooter>
          <Skeleton className="h-9 w-16" />
        </CardFooter>
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const { data: credentials = [], isLoading: credLoading } = useCredentials();
  const saveCredential = useSaveCredential();
  const deleteCredential = useDeleteCredential();

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<CredentialFormValues>({
    resolver: zodResolver(credentialSchema),
    defaultValues: {
      app_key: "",
      app_secret: "",
      account_no: "",
      is_mock: true,
    },
  });

  const isMock = watch("is_mock");

  const onSubmit = (values: CredentialFormValues) => {
    saveCredential.mutate(values, {
      onSuccess: () => reset(),
    });
  };

  if (credLoading) return <SettingsSkeleton />;

  return (
    <div className="@container/main mx-auto flex max-w-2xl flex-1 flex-col gap-4 md:gap-6">
      {/* 페이지 헤더 */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">설정</h1>
        <p className="text-sm text-muted-foreground">
          계정 정보 및 키움 API 키를 관리합니다.
        </p>
      </div>

      <Separator />

      {/* 계정 정보 */}
      <Card>
        <CardHeader className="border-b bg-muted/30 pb-4">
          <div className="flex items-center gap-2">
            <User className="size-4 text-muted-foreground" />
            <CardTitle className="text-lg">계정 정보</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Mail className="size-3.5" />
              이메일
            </div>
            <span className="text-sm font-medium">{user?.email}</span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Shield className="size-3.5" />
              역할
            </div>
            <Badge
              variant="outline"
              className={
                user?.role === "admin"
                  ? "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300"
                  : ""
              }
            >
              {user?.role}
            </Badge>
          </div>
        </CardContent>
        <CardFooter className="border-t pt-4">
          <Button variant="outline" onClick={logout}>
            <LogOut className="mr-2 size-4" />
            로그아웃
          </Button>
        </CardFooter>
      </Card>

      <Separator />

      {/* 등록된 API 키 */}
      {credentials.length > 0 ? (
        <Card className="overflow-hidden">
          <CardHeader className="border-b bg-muted/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <KeyRound className="size-4 text-muted-foreground" />
                <CardTitle className="text-lg">등록된 API 키</CardTitle>
              </div>
              <Badge variant="secondary">{credentials.length}개</Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y">
              {credentials.map((cred) => (
                <div
                  key={cred.id}
                  className="flex items-center justify-between p-4 transition-colors hover:bg-muted/30"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex size-9 items-center justify-center rounded-lg bg-muted">
                      <KeyRound className="size-4 text-muted-foreground" />
                    </div>
                    <div className="space-y-0.5">
                      <div className="text-sm font-medium tabular-nums">
                        계좌: {cred.account_no}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        등록일: {formatLocalDate(cred.created_at)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className={
                        cred.is_mock
                          ? "border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-300"
                          : "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
                      }
                    >
                      {cred.is_mock ? "모의투자" : "실거래"}
                    </Badge>
                    {cred.is_active ? (
                      <Badge
                        variant="outline"
                        className="border-green-200 text-green-700 dark:border-green-800 dark:text-green-300"
                      >
                        <CheckCircle2 className="mr-1 size-3" />
                        활성
                      </Badge>
                    ) : (
                      <Badge
                        variant="outline"
                        className="text-muted-foreground"
                      >
                        <XCircle className="mr-1 size-3" />
                        비활성
                      </Badge>
                    )}
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8 text-muted-foreground hover:text-destructive"
                          disabled={deleteCredential.isPending}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>API 키 삭제</AlertDialogTitle>
                          <AlertDialogDescription>
                            이 키를 삭제하면 자동매매가 중단될 수 있습니다. 정말
                            삭제하시겠습니까?
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>취소</AlertDialogCancel>
                          <AlertDialogAction
                            variant="destructive"
                            onClick={() => deleteCredential.mutate(cred.id)}
                          >
                            삭제
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <KeyRound />
            </EmptyMedia>
            <EmptyTitle>등록된 API 키가 없습니다</EmptyTitle>
            <EmptyDescription>
              아래에서 키움증권 API 키를 등록하면 시세 조회와 주문이 가능합니다.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}

      {/* 키움 API 키 등록 */}
      <Card>
        <CardHeader className="border-b bg-muted/30">
          <div className="flex items-center gap-2">
            <KeyRound className="size-4 text-muted-foreground" />
            <CardTitle className="text-lg">키움 API 키 등록</CardTitle>
          </div>
          <CardDescription>
            키움증권 Open API에서 발급받은 키를 입력하세요. AES-256으로 암호화되어
            저장됩니다.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-4 pt-4">
            {/* 모의/실거래 토글 */}
            <div className="flex gap-2">
              <Button
                type="button"
                variant={isMock ? "default" : "outline"}
                size="sm"
                className={
                  isMock
                    ? "bg-green-600 text-white hover:bg-green-700 dark:bg-green-700 dark:hover:bg-green-800"
                    : ""
                }
                onClick={() => setValue("is_mock", true)}
              >
                <Shield className="mr-1.5 size-3.5" />
                모의투자
              </Button>
              <Button
                type="button"
                variant={!isMock ? "default" : "outline"}
                size="sm"
                className={
                  !isMock
                    ? "bg-red-600 text-white hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-800"
                    : ""
                }
                onClick={() => setValue("is_mock", false)}
              >
                <Shield className="mr-1.5 size-3.5" />
                실거래
              </Button>
            </div>

            {!isMock && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
                실거래 모드는 실제 매매가 실행됩니다. 신중하게 사용해주세요.
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="app_key">App Key</Label>
              <Input
                id="app_key"
                {...register("app_key")}
                placeholder="앱 키 입력"
              />
              {errors.app_key && (
                <p className="text-xs text-destructive">
                  {errors.app_key.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="app_secret">App Secret</Label>
              <Input
                id="app_secret"
                type="password"
                {...register("app_secret")}
                placeholder="앱 시크릿 입력"
              />
              {errors.app_secret && (
                <p className="text-xs text-destructive">
                  {errors.app_secret.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="account_no">계좌번호</Label>
              <Input
                id="account_no"
                {...register("account_no")}
                placeholder="계좌번호 (숫자만)"
              />
              {errors.account_no && (
                <p className="text-xs text-destructive">
                  {errors.account_no.message}
                </p>
              )}
            </div>
          </CardContent>
          <CardFooter className="border-t pt-4">
            <Button type="submit" disabled={saveCredential.isPending}>
              {saveCredential.isPending ? "저장 중..." : "저장"}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
