"use client";

import { useEffect, useState } from "react";
import { api, ApiClientError } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
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
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { AlertCircle, CheckCircle2, KeyRound, LogOut } from "lucide-react";
import type { BrokerCredential } from "@/types/api";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [appKey, setAppKey] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [accountNo, setAccountNo] = useState("");
  const [isMock, setIsMock] = useState(true);
  const [saving, setSaving] = useState(false);
  const [credentials, setCredentials] = useState<BrokerCredential[]>([]);
  const [credLoading, setCredLoading] = useState(true);

  useEffect(() => {
    async function fetchCredentials() {
      try {
        const data = await api.get<BrokerCredential[]>("/api/v1/settings/broker");
        setCredentials(data);
      } catch {
        // 실패 시 무시
      } finally {
        setCredLoading(false);
      }
    }
    fetchCredentials();
  }, []);

  const saveCredentials = async () => {
    if (!appKey || !appSecret || !accountNo) {
      toast.error("모든 필드를 입력해주세요.");
      return;
    }
    setSaving(true);
    try {
      await api.post("/api/v1/settings/broker", {
        app_key: appKey,
        app_secret: appSecret,
        account_no: accountNo,
        is_mock: isMock,
      });
      toast.success("API 키가 저장되었습니다.");
      setAppKey("");
      setAppSecret("");
      setAccountNo("");
      const updated = await api.get<BrokerCredential[]>("/api/v1/settings/broker");
      setCredentials(updated);
    } catch (err) {
      const msg =
        err instanceof ApiClientError ? err.message : "저장에 실패했습니다.";
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">설정</h1>

      {/* 계정 정보 */}
      <Card>
        <CardHeader>
          <CardTitle>계정 정보</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">이메일</span>
            <span>{user?.email}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">역할</span>
            <Badge variant="outline">{user?.role}</Badge>
          </div>
        </CardContent>
        <CardFooter>
          <Button variant="outline" onClick={logout}>
            <LogOut className="mr-2 size-4" />
            로그아웃
          </Button>
        </CardFooter>
      </Card>

      <Separator />

      {/* 등록된 API 키 */}
      {credLoading ? (
        <div className="flex justify-center py-4">
          <Spinner className="size-6" />
        </div>
      ) : credentials.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>등록된 API 키</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {credentials.map((cred) => (
                <div
                  key={cred.id}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <div className="space-y-1">
                    <div className="text-sm font-medium">
                      계좌: {cred.account_no}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      등록일:{" "}
                      {new Date(cred.created_at).toLocaleDateString("ko-KR")}
                    </div>
                  </div>
                  <Badge variant={cred.is_mock ? "secondary" : "destructive"}>
                    {cred.is_mock ? "모의투자" : "실거래"}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Alert>
          <AlertCircle />
          <AlertTitle>등록된 API 키가 없습니다</AlertTitle>
          <AlertDescription>
            아래에서 키움증권 API 키를 등록하면 시세 조회와 주문이 가능합니다.
          </AlertDescription>
        </Alert>
      )}

      {/* 키움 API 키 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="size-5" />
            키움 API 키 등록
          </CardTitle>
          <CardDescription>
            키움증권 Open API에서 발급받은 키를 입력하세요. AES-256으로 암호화되어
            저장됩니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Button
              variant={isMock ? "default" : "outline"}
              size="sm"
              onClick={() => setIsMock(true)}
            >
              모의투자
            </Button>
            <Button
              variant={!isMock ? "default" : "outline"}
              size="sm"
              onClick={() => setIsMock(false)}
            >
              실거래
            </Button>
          </div>

          <div className="space-y-2">
            <Label htmlFor="app_key">App Key</Label>
            <Input
              id="app_key"
              value={appKey}
              onChange={(e) => setAppKey(e.target.value)}
              placeholder="앱 키 입력"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="app_secret">App Secret</Label>
            <Input
              id="app_secret"
              type="password"
              value={appSecret}
              onChange={(e) => setAppSecret(e.target.value)}
              placeholder="앱 시크릿 입력"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="account_no">계좌번호</Label>
            <Input
              id="account_no"
              value={accountNo}
              onChange={(e) => setAccountNo(e.target.value)}
              placeholder="계좌번호 (숫자만)"
            />
          </div>
        </CardContent>
        <CardFooter>
          <Button onClick={saveCredentials} disabled={saving}>
            {saving ? "저장 중..." : "저장"}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
