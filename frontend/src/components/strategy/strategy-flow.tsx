import { FlowNode } from "./flow-node";
import { FlowConnector } from "./flow-connector";

function ExitGroup({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2 rounded-lg border border-dashed border-muted-foreground/30 p-3">
      {children}
    </div>
  );
}

export function MomentumStrategyFlow() {
  return (
    <div className="flex flex-col items-center gap-1 py-4">
      {/* 진입 조건 */}
      <div className="flex items-center overflow-x-auto">
        <FlowNode title="스크리닝" description="유니버스 필터링" variant="default" />
        <FlowConnector />
        <FlowNode
          title="52주 고점"
          description="돌파 확인"
          params={[{ label: "≥", value: "70%" }]}
          variant="entry"
        />
        <FlowConnector />
        <FlowNode
          title="거래량 확인"
          description="시간보정"
          params={[{ label: "≥", value: "0.5x" }]}
          variant="entry"
        />
        <FlowConnector />
        <FlowNode title="매수" description="시장가 주문" variant="action" />
      </div>

      <FlowConnector direction="vertical" />

      {/* 보유 중 감시 */}
      <FlowNode
        title="보유 중 감시"
        description="포지션 모니터링"
        variant="default"
      />

      <FlowConnector direction="vertical" label="청산 조건" />

      {/* 청산 조건들 */}
      <ExitGroup>
        <FlowNode
          title="손절"
          variant="exit"
          params={[{ label: "", value: "-0.5%" }]}
        />
        <FlowNode
          title="익절"
          variant="exit"
          params={[{ label: "", value: "+1.0%" }]}
        />
        <FlowNode
          title="강제청산"
          description="장 마감"
          params={[{ label: "", value: "14:30" }]}
          variant="exit"
        />
      </ExitGroup>

      <FlowConnector direction="vertical" />

      {/* 매도 완료 */}
      <FlowNode title="매도 완료" description="시장가 청산" variant="action" />
    </div>
  );
}

export function MeanReversionStrategyFlow() {
  return (
    <div className="flex flex-col items-center gap-1 py-4">
      {/* 진입 조건 */}
      <div className="flex items-center overflow-x-auto">
        <FlowNode title="스크리닝" description="유니버스 필터링" variant="default" />
        <FlowConnector />
        <FlowNode
          title="RSI 과매도"
          params={[{ label: "<", value: "40" }]}
          variant="entry"
        />
        <FlowConnector />
        <FlowNode
          title="BB 하단 돌파"
          params={[{ label: "", value: "1.5σ" }]}
          variant="entry"
        />
        <FlowConnector />
        <FlowNode
          title="거래량 확인"
          params={[{ label: "≥", value: "0.8x" }]}
          variant="entry"
        />
        <FlowConnector />
        <FlowNode title="매수" description="시장가 주문" variant="action" />
      </div>

      <FlowConnector direction="vertical" />

      {/* 보유 중 감시 */}
      <FlowNode
        title="보유 중 감시"
        description="포지션 모니터링"
        variant="default"
      />

      <FlowConnector direction="vertical" label="청산 조건" />

      {/* 청산 조건들 */}
      <ExitGroup>
        <FlowNode
          title="손절"
          variant="exit"
          params={[{ label: "", value: "-1.5%" }]}
        />
        <FlowNode
          title="RSI 과매수"
          variant="exit"
          params={[{ label: ">", value: "70" }]}
        />
        <FlowNode title="BB 중심 회귀" variant="exit" />
        <FlowNode
          title="익절"
          variant="exit"
          params={[{ label: "", value: "+1.5%" }]}
        />
      </ExitGroup>

      <FlowConnector direction="vertical" />

      {/* 매도 완료 */}
      <FlowNode title="매도 완료" description="시장가 청산" variant="action" />
    </div>
  );
}
