import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface FlowNodeProps {
  title: string;
  description?: string;
  params?: { label: string; value: string }[];
  variant?: "default" | "entry" | "exit" | "action";
  active?: boolean;
  className?: string;
}

const variantStyles: Record<NonNullable<FlowNodeProps["variant"]>, string> = {
  default: "border-border bg-card",
  entry: "border-emerald-500/70 bg-emerald-50/50 dark:bg-emerald-950/30",
  exit: "border-red-500/70 bg-red-50/50 dark:bg-red-950/30",
  action: "border-blue-500/70 bg-blue-50/50 dark:bg-blue-950/30",
};

const paramBadgeStyles: Record<NonNullable<FlowNodeProps["variant"]>, string> =
  {
    default: "",
    entry:
      "border-emerald-200 bg-emerald-100 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300",
    exit: "border-red-200 bg-red-100 text-red-700 dark:border-red-800 dark:bg-red-900/60 dark:text-red-300",
    action:
      "border-blue-200 bg-blue-100 text-blue-700 dark:border-blue-800 dark:bg-blue-900/60 dark:text-blue-300",
  };

export function FlowNode({
  title,
  description,
  params,
  variant = "default",
  active = false,
  className,
}: FlowNodeProps) {
  return (
    <div
      className={cn(
        "min-w-[110px] max-w-[150px] shrink-0 rounded-lg border-2 p-2.5 text-center",
        variantStyles[variant],
        active && "ring-2 ring-primary ring-offset-2",
        className,
      )}
    >
      <div className="text-xs font-semibold leading-tight">{title}</div>
      {description && (
        <div className="mt-0.5 text-[10px] leading-snug text-muted-foreground">
          {description}
        </div>
      )}
      {params && params.length > 0 && (
        <div className="mt-1.5 flex flex-wrap justify-center gap-1">
          {params.map((p) => (
            <Badge
              key={`${p.label}-${p.value}`}
              variant="outline"
              className={cn(
                "h-4 px-1.5 py-0 font-mono text-[10px]",
                paramBadgeStyles[variant],
              )}
            >
              {p.label && `${p.label} `}
              {p.value}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
