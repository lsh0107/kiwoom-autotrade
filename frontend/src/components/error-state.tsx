"use client";

import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Button } from "@/components/ui/button";
import { KeyRound } from "lucide-react";
import Link from "next/link";

const ERROR_CONFIGS: Record<
  string,
  { title: string; desc: string; showLink: boolean }
> = {
  no_credentials: {
    title: "API 키를 등록해주세요",
    desc: "키움증권 Open API 키를 등록하면 계좌 잔고와 보유종목을 조회할 수 있습니다.",
    showLink: true,
  },
  rate_limit: {
    title: "잠시 후 다시 시도해주세요",
    desc: "API 요청이 너무 많습니다. 잠시 기다린 후 페이지를 새로고침해주세요.",
    showLink: false,
  },
  broker_auth: {
    title: "API 키 인증 오류",
    desc: "키움 API 키가 만료되었거나 올바르지 않습니다. 설정에서 키를 다시 등록해주세요.",
    showLink: true,
  },
  unknown: {
    title: "잔고를 불러올 수 없습니다",
    desc: "일시적인 오류가 발생했습니다. 잠시 후 페이지를 새로고침해주세요.",
    showLink: false,
  },
};

export function ErrorState({ error }: { error: string }) {
  const cfg = ERROR_CONFIGS[error] ?? ERROR_CONFIGS.unknown;

  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <KeyRound />
        </EmptyMedia>
        <EmptyTitle>{cfg.title}</EmptyTitle>
        <EmptyDescription>{cfg.desc}</EmptyDescription>
      </EmptyHeader>
      {cfg.showLink && (
        <EmptyContent>
          <Button asChild>
            <Link href="/settings">설정으로 이동</Link>
          </Button>
        </EmptyContent>
      )}
    </Empty>
  );
}
