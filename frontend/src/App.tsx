import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api/client";
import { AccountSummary } from "./components/AccountSummary";
import { ConnectionStatus } from "./components/ConnectionStatus";
import { KillSwitchButton } from "./components/KillSwitchButton";
import { ManualOrderPanel } from "./components/ManualOrderPanel";
import { MarketChartPanel } from "./components/MarketChartPanel";
import { OrderLogTable } from "./components/OrderLogTable";
import { PositionTable } from "./components/PositionTable";
import { StrategyPanel } from "./components/StrategyPanel";
import { SystemLog } from "./components/SystemLog";
import type { AccountSummaryData, Position } from "./types/account";
import type { ChartPeriod, MarketBar, MarketQuote } from "./types/market";
import type { Order } from "./types/order";
import type { HealthStatus, StrategyStatusData, SystemLogEntry } from "./types/strategy";

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [account, setAccount] = useState<AccountSummaryData | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [strategy, setStrategy] = useState<StrategyStatusData | null>(null);
  const [quote, setQuote] = useState<MarketQuote | null>(null);
  const [bars, setBars] = useState<MarketBar[]>([]);
  const [chartPeriod, setChartPeriod] = useState<ChartPeriod>("10m");
  const [marketError, setMarketError] = useState("");
  const [error, setError] = useState("");
  const [logs, setLogs] = useState<SystemLogEntry[]>([]);
  const previousHealth = useRef<HealthStatus | null>(null);

  const appendLog = useCallback((category: SystemLogEntry["category"], level: SystemLogEntry["level"], message: string) => {
    setLogs((current) => {
      if (current[0]?.category === category && current[0]?.message === message) return current;
      return [{ id: `${Date.now()}-${Math.random()}`, timestamp: new Date().toISOString(), category, level, message }, ...current].slice(0, 50);
    });
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [nextHealth, nextAccount, nextPositions, nextOrders, nextStrategy] = await Promise.all([
        api.health(), api.account(), api.positions(), api.orders(), api.strategy(),
      ]);
      const symbol = nextStrategy.watched_symbols?.[0] ?? "005930";
      try {
        const nextQuote = await api.marketQuote(symbol);
        setQuote(nextQuote);
        const nextBars = await api.marketBars(symbol, chartPeriod);
        setBars(nextBars); setMarketError("");
      } catch (caught) {
        setMarketError(caught instanceof Error ? caught.message : "시세 데이터를 가져오지 못했습니다.");
      }
      const previous = previousHealth.current;
      if (!previous) {
        appendLog("API", "INFO", "REST API 연결이 확인되었습니다.");
        appendLog("WEBSOCKET", nextHealth.websocket_connected ? "INFO" : "ERROR", nextHealth.websocket_connected ? "실시간 시세 연결이 확인되었습니다." : "실시간 시세 연결이 끊겨 있습니다.");
        appendLog("TELEGRAM", nextHealth.telegram_configured ? "INFO" : "WARN", nextHealth.telegram_configured ? "Telegram 알림이 설정되어 있습니다." : "Telegram 알림이 설정되지 않았습니다.");
      }
      if (previous?.websocket_connected && !nextHealth.websocket_connected) appendLog("WEBSOCKET", "ERROR", "실시간 시세 연결이 끊겼습니다. 자동매매를 중지해야 합니다.");
      if (previous && !previous.websocket_connected && nextHealth.websocket_connected) appendLog("WEBSOCKET", "INFO", "실시간 시세 연결이 복구되었습니다.");
      if (previous?.emergency_stopped !== nextHealth.emergency_stopped) appendLog("RISK", nextHealth.emergency_stopped ? "BLOCK" : "INFO", nextHealth.emergency_stopped ? "긴급 STOP이 활성화되었습니다." : "긴급 STOP이 해제되었습니다.");
      previousHealth.current = nextHealth;
      setHealth(nextHealth); setAccount(nextAccount); setPositions(nextPositions); setOrders(nextOrders); setStrategy(nextStrategy); setError("");
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "백엔드 연결에 실패했습니다.";
      setError(message); appendLog("API", "ERROR", message);
    }
  }, [appendLog, chartPeriod]);

  useEffect(() => {
    appendLog("SYSTEM", "INFO", "PulseTrade 대시보드가 시작되었습니다.");
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(timer);
  }, [appendLog, refresh]);

  async function toggleAutomation(enabled: boolean) {
    try {
      const result = await api.setAutomation(enabled);
      appendLog("SYSTEM", "INFO", `자동주문이 ${result.enabled ? "활성화" : "비활성화"}되었습니다.`);
      await refresh();
    } catch (caught) { appendLog("API", "ERROR", caught instanceof Error ? caught.message : "자동주문 설정에 실패했습니다."); }
  }

  async function toggleStop(stopped: boolean) {
    try { await api.setKillSwitch(stopped); await refresh(); }
    catch (caught) { appendLog("API", "ERROR", caught instanceof Error ? caught.message : "긴급 정지 요청에 실패했습니다."); }
  }

  async function cancelOrder(orderId: string) {
    try {
      const result = await api.cancelOrder(orderId);
      appendLog("ORDER", "INFO", `${result.state}: ${result.message}`);
      await refresh();
    } catch (caught) {
      appendLog("ORDER", "ERROR", caught instanceof Error ? caught.message : "주문 취소에 실패했습니다.");
    }
  }

  const mode = health?.mode ?? "SIM";
  const liveEnabled = health?.live_enabled ?? false;
  const stopped = health?.emergency_stopped ?? false;

  return (
    <div className={`app-shell mode-shell-${mode.toLowerCase()}`}>
      <header className="app-header">
        <div className="brand-block"><div className="brand-symbol"><span /></div><div><p className="brand-name">PulseTrade</p><span className="brand-subtitle">AUTOMATED TRADING CONTROL</span></div></div>
        <div className="header-center"><span className={`mode-badge mode-${mode.toLowerCase()}`}>{mode === "LIVE" && <i />} {mode} MODE</span><ConnectionStatus health={health} /></div>
        <div className="emergency-dock"><KillSwitchButton stopped={stopped} onChange={toggleStop} /></div>
      </header>

      {mode === "LIVE" && !liveEnabled && <div className="live-mode-banner"><strong>LIVE 잠금 상태</strong><span>실계좌 주문 라우팅이 현재 설정에서 비활성화되어 있습니다.</span></div>}
      {mode === "LIVE" && liveEnabled && <div className="live-mode-banner"><strong>LIVE 수동 주문 활성</strong><span>자동매매는 비활성화되어 있고 수동 주문만 확인 절차 후 전송됩니다.</span></div>}
      {stopped && <div className="stop-banner"><strong>긴급 정지 상태</strong><span>신규 주문과 자동매매가 차단되었습니다.</span></div>}
      {error && <div className="error-banner"><strong>REST API 연결 오류</strong><span>{error}</span></div>}

      <main className="dashboard">
        <AccountSummary data={account} positions={positions} orders={orders} />
        <MarketChartPanel quote={quote} bars={bars} strategy={strategy} error={marketError} period={chartPeriod} onPeriodChange={setChartPeriod} />
        <div className="control-grid">
          <ManualOrderPanel mode={mode} liveEnabled={liveEnabled} emergencyStopped={stopped} onSubmitted={refresh} onSystemMessage={(message, isError) => appendLog(isError ? "RISK" : "ORDER", isError ? "BLOCK" : "INFO", message)} />
          <StrategyPanel strategy={strategy} emergencyStopped={stopped} onAutoOrderToggle={toggleAutomation} />
        </div>
        <PositionTable positions={positions} />
        <OrderLogTable orders={orders} onCancel={cancelOrder} />
        <SystemLog logs={logs} />
      </main>

      <footer className="app-footer"><span>PulseTrade MVP</span><span>기본 주문 비활성화 · RiskManager 필수 · 수익을 보장하지 않습니다.</span></footer>
    </div>
  );
}
