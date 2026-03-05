"use client";

import { useState } from "react";
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
import { KeyRound, LogOut } from "lucide-react";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [appKey, setAppKey] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [accountNo, setAccountNo] = useState("");
  const [isMock, setIsMock] = useState(true);
  const [saving, setSaving] = useState(false);

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
