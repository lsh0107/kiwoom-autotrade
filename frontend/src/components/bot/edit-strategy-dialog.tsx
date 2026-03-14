"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useUpdateStrategy } from "@/hooks/mutations/use-update-strategy";
import type { Strategy } from "@/types/api";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const strategySchema = z.object({
  name: z.string().min(1, "전략명을 입력해주세요"),
  description: z.string().optional(),
  symbols: z.string().min(1, "종목코드를 입력해주세요"),
  max_investment: z
    .number({ error: "숫자를 입력해주세요" })
    .positive("0보다 커야 합니다"),
  max_loss_pct: z
    .number({ error: "숫자를 입력해주세요" })
    .max(0, "음수여야 합니다"),
  max_position_pct: z
    .number({ error: "숫자를 입력해주세요" })
    .positive("0보다 커야 합니다")
    .max(100, "100 이하여야 합니다"),
});

type FormValues = z.infer<typeof strategySchema>;

interface EditStrategyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  strategy: Strategy | null;
}

/** 전략 편집 Sheet 다이얼로그 */
export function EditStrategyDialog({
  open,
  onOpenChange,
  strategy,
}: EditStrategyDialogProps) {
  const updateStrategy = useUpdateStrategy();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(strategySchema),
  });

  // 전략 데이터 변경 시 폼 초기화
  useEffect(() => {
    if (strategy) {
      reset({
        name: strategy.name,
        description: strategy.description,
        symbols: strategy.symbols.join(", "),
        max_investment: strategy.max_investment,
        max_loss_pct: strategy.max_loss_pct,
        max_position_pct: strategy.max_position_pct,
      });
    }
  }, [strategy, reset]);

  const onSubmit = (values: FormValues) => {
    if (!strategy) return;
    updateStrategy.mutate(
      {
        id: strategy.id,
        name: values.name,
        description: values.description,
        symbols: values.symbols
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        max_investment: values.max_investment,
        max_loss_pct: values.max_loss_pct,
        max_position_pct: values.max_position_pct,
      },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto">
        <SheetHeader>
          <SheetTitle>전략 편집</SheetTitle>
        </SheetHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 px-4 pb-4">
          <div className="space-y-1.5">
            <Label htmlFor="edit-name">전략명 *</Label>
            <Input
              id="edit-name"
              {...register("name")}
              placeholder="전략 이름"
            />
            {errors.name && (
              <p className="text-xs text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-description">설명</Label>
            <Input
              id="edit-description"
              {...register("description")}
              placeholder="전략 설명 (선택)"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-symbols">종목코드 *</Label>
            <Input
              id="edit-symbols"
              {...register("symbols")}
              placeholder="예: 005930, 000660"
            />
            <p className="text-xs text-muted-foreground">
              콤마(,)로 구분하여 여러 종목 입력
            </p>
            {errors.symbols && (
              <p className="text-xs text-destructive">
                {errors.symbols.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-max_investment">최대 투자금 (원)</Label>
            <Input
              id="edit-max_investment"
              type="number"
              {...register("max_investment", { valueAsNumber: true })}
            />
            {errors.max_investment && (
              <p className="text-xs text-destructive">
                {errors.max_investment.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-max_loss_pct">최대 손실률 (%)</Label>
            <Input
              id="edit-max_loss_pct"
              type="number"
              step="0.1"
              {...register("max_loss_pct", { valueAsNumber: true })}
            />
            <p className="text-xs text-muted-foreground">음수로 입력 (예: -3.0)</p>
            {errors.max_loss_pct && (
              <p className="text-xs text-destructive">
                {errors.max_loss_pct.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-max_position_pct">최대 포지션 비율 (%)</Label>
            <Input
              id="edit-max_position_pct"
              type="number"
              step="0.1"
              {...register("max_position_pct", { valueAsNumber: true })}
            />
            {errors.max_position_pct && (
              <p className="text-xs text-destructive">
                {errors.max_position_pct.message}
              </p>
            )}
          </div>

          <SheetFooter className="px-0 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              취소
            </Button>
            <Button type="submit" disabled={updateStrategy.isPending}>
              {updateStrategy.isPending ? "저장 중..." : "저장"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
