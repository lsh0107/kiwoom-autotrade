import { cn } from "@/lib/utils";
import { ArrowDown, ArrowRight } from "lucide-react";

interface FlowConnectorProps {
  direction?: "horizontal" | "vertical";
  label?: string;
  className?: string;
}

export function FlowConnector({
  direction = "horizontal",
  label,
  className,
}: FlowConnectorProps) {
  if (direction === "vertical") {
    return (
      <div className={cn("flex flex-col items-center", className)}>
        <div className="h-4 w-px bg-border" />
        {label && (
          <span className="px-1 text-[10px] text-muted-foreground">
            {label}
          </span>
        )}
        <ArrowDown className="size-3 text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className={cn("flex items-center", className)}>
      <div className="h-px w-5 bg-border" />
      {label && (
        <span className="px-1 text-[10px] text-muted-foreground">{label}</span>
      )}
      <ArrowRight className="size-3 text-muted-foreground" />
    </div>
  );
}
