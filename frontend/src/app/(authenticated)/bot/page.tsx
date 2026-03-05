"use client";

import { useEffect, useState } from "react";
import { api, ApiClientError } from "@/lib/api";
import type { Strategy } from "@/types/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Play, Square, ShieldAlert } from "lucide-react";

export default function BotPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const data = await api.get<Strategy[]>("/api/v1/bot/strategies");
        setStrategies(data);
      } catch {
        // API 미연동 시 빈 목록
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, []);

  const toggleStrategy = async (id: string, status: string) => {
    try {
      const action = status === "active" ? "stop" : "start";
      await api.post(`/api/v1/bot/strategies/${id}/${action}`);
      setStrategies((prev) =>
        prev.map((s) =>
          s.id === id
            ? { ...s, status: status === "active" ? "stopped" : "active" }
            : s,
        ),
      );
      toast.success(
        status === "active"
          ? "전략이 중지되었습니다."
          : "전략이 시작되었습니다.",
      );
    } catch (err) {
      const msg =
        err instanceof ApiClientError ? err.message : "실패했습니다.";
      toast.error(msg);
    }
  };

  const killSwitch = async () => {
    if (!confirm("모든 자동매매를 긴급 중지합니다. 계속하시겠습니까?")) return;
    try {
      await api.post("/api/v1/bot/kill-switch", { active: true });
      setStrategies((prev) =>
        prev.map((s) => ({ ...s, status: "stopped" as const })),
      );
      toast.success("Kill Switch 발동 — 모든 전략이 중지되었습니다.");
    } catch (err) {
      const msg =
        err instanceof ApiClientError ? err.message : "Kill Switch 실패";
      toast.error(msg);
    }
  };

  if (loading) {
    return <div className="text-muted-foreground">로딩 중...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">자동매매</h1>
        <Button variant="destructive" onClick={killSwitch}>
          <ShieldAlert className="mr-2 size-4" />
          Kill Switch
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>전략 목록</CardTitle>
        </CardHeader>
        <CardContent>
          {strategies.length === 0 ? (
            <p className="py-8 text-center text-muted-foreground">
              등록된 전략이 없습니다.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>전략명</TableHead>
                  <TableHead>종목</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead className="text-right">제어</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {strategies.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium">{s.name}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {s.symbols.map((sym) => (
                          <Badge key={sym} variant="outline">
                            {sym}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={s.status === "active" ? "destructive" : "secondary"}
                      >
                        {s.status === "active" ? "실행 중" : "중지"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => toggleStrategy(s.id, s.status)}
                      >
                        {s.status === "active" ? (
                          <Square className="size-4" />
                        ) : (
                          <Play className="size-4" />
                        )}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
