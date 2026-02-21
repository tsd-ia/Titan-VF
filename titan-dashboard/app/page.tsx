"use client";
import { useEffect, useState } from "react";
import { db } from "@/lib/firebase";
import { ref, onValue, update } from "firebase/database";
import {
  ShieldAlert,
  Terminal,
  TrendingDown,
  TrendingUp,
  Activity,
  DollarSign,
  Zap,
  Power,
  RotateCcw,
  Target,
  BrainCircuit,
  History,
  LayoutDashboard,
  Settings2,
  Cpu,
} from "lucide-react";

interface SentinelData {
  ts: string;
  bid: number;
  ask: number;
  spread: number;
  atr: number;
  rsi: number;
  ema20: number;
  ema50: number;
  ema200: number;
  bb_pos: number;
  m5_trend: string;
  h1_trend: string;
  margin_level: number;
  vel1: number;
  vel5: number;
  balance: number;
  equity: number;
  total_float: number;
  auto_mode: boolean;
  pos: Array<{
    tipo: string;
    open: number;
    profit: number;
    ticket: number;
    magic: number;
  }>;
  gemini: string;
  ai_insight: string;
  radar?: Array<{
    symbol: string;
    signal: string;
    confidence: number;
    rsi: number;
    lot: number;
  }>;
  alertas: string[];
  last_best_sym?: string;
  pnl?: number;
  goal_progress?: number;
  goal_usd?: number;
  health: {
    mt5: boolean;
    ai: boolean;
  };
  oro_brain_on?: boolean;
  btc_brain_on?: boolean;
}

export default function TitanDashboard() {
  const [data, setData] = useState<SentinelData | null>(null);
  const [activeTab, setActiveTab] = useState<"radar" | "audit" | "history" | "system">("radar");
  const [connecting, setConnecting] = useState(true);

  useEffect(() => {
    const liveRef = ref(db, "live");
    const unsub = onValue(liveRef, (snap) => {
      if (snap.exists()) {
        setData(snap.val());
        setConnecting(false);
      }
    });
    return () => unsub();
  }, []);

  const sendCommand = async (cmd: string, val: any) => {
    await update(ref(db, "commands"), { [cmd]: val });
    alert(`ACCIÓN ENVIADA: ${cmd.toUpperCase()}`);
  };

  if (connecting || !data) {
    return (
      <div className="min-h-screen bg-black flex flex-col items-center justify-center text-cyan-500 font-mono italic animate-pulse">
        <Cpu className="w-16 h-16 mb-4" />
        <p className="tracking-[0.5em] text-sm text-center uppercase">Enlazando con Titan Institutional Core...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-200 font-mono selection:bg-cyan-500 selection:text-black">
      <nav className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-black tracking-tighter uppercase italic text-white flex items-center gap-2">
              Titan <span className="text-cyan-500">Sentinel</span>
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.8)]" />
            </h1>
            <span className="text-[10px] bg-cyan-500/10 text-cyan-500 px-2 py-0.5 rounded border border-cyan-500/20 font-black">v7.8 RADAR</span>
          </div>

          <div className="flex bg-black/40 rounded-xl p-1 border border-gray-800 backdrop-blur-md">
            <TabBtn id="radar" active={activeTab} icon={<LayoutDashboard size={14} />} label="RADAR" onClick={setActiveTab} />
            <TabBtn id="audit" active={activeTab} icon={<RotateCcw size={14} />} label="AUDIT" onClick={setActiveTab} />
            <TabBtn id="history" active={activeTab} icon={<History size={14} />} label="ENGAGEMENTS" onClick={setActiveTab} />
            <TabBtn id="system" active={activeTab} icon={<Settings2 size={14} />} label="CORE CONFIG" onClick={setActiveTab} />
          </div>

          <div className="flex items-center gap-4">
            <button onClick={() => sendCommand("panic", true)} className="bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white border border-red-500/20 p-2.5 rounded-xl transition-all shadow-lg hover:shadow-red-500/20">
              <ShieldAlert size={20} />
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto p-4 lg:p-8">
        {activeTab === "radar" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="lg:col-span-8 space-y-8">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatBox label="BALANCE" value={`$${(data.balance || 0).toFixed(2)}`} icon={<DollarSign size={14} />} />
                <StatBox label="EQUIDAD" value={`$${(data.equity || 0).toFixed(2)}`} icon={<Activity size={14} />} color={(data.equity || 0) < (data.balance || 0) ? "red" : "cyan"} />
                <StatBox label="PROF. FLOTANTE" value={`$${(data.total_float || 0).toFixed(2)}`} icon={<TrendingUp size={14} />} color={(data.total_float || 0) < 0 ? "red" : "emerald"} />
                <StatBox label="MT5" value={data.health?.mt5 ? "ONLINE" : "OFFLINE"} icon={<Zap size={14} />} color={data.health?.mt5 ? "cyan" : "red"} />
              </div>

              {/* BARRA DE PROGRESO DE META (v7.8) */}
              <div className="bg-gray-900 border border-white/5 rounded-[2rem] p-6 shadow-xl space-y-4">
                <div className="flex justify-between items-center px-2">
                  <span className="text-[10px] font-black tracking-[0.3em] uppercase text-cyan-500">Objetivo Diario: +500% ($173.95)</span>
                  <span className="text-xl font-black text-white">{data.goal_progress || 0}%</span>
                </div>
                <div className="w-full h-3 bg-black/50 rounded-full overflow-hidden border border-white/10 p-0.5">
                  <div
                    className="h-full bg-gradient-to-r from-cyan-600 via-blue-500 to-emerald-400 rounded-full transition-all duration-1000 shadow-[0_0_15px_rgba(34,211,238,0.5)]"
                    style={{ width: `${data.goal_progress || 0}%` }}
                  />
                </div>
              </div>


              {/* BANNER DE CONSEJO HUMANO (v7.8) */}
              <div className="bg-gradient-to-r from-cyan-600 to-blue-600 rounded-[2rem] p-6 text-center shadow-[0_0_30px_rgba(6,182,212,0.3)] border border-cyan-400/30 animate-pulse">
                <h2 className="text-2xl md:text-3xl font-black text-white tracking-tight uppercase italic underline decoration-cyan-300 decoration-2 underline-offset-4">
                  {data.gemini || "VIGILANCIA TÁCTICA ACTIVA"}
                </h2>
              </div>

              <div className="bg-gray-900 border border-white/5 rounded-[2.5rem] p-8 lg:p-12 relative overflow-hidden shadow-3xl bg-gradient-to-br from-gray-900 to-black">
                <div className="absolute top-0 right-0 p-8 opacity-[0.03] pointer-events-none">
                  <Target size={300} className="text-white" />
                </div>
                <header className="flex justify-between items-start mb-8 relative z-10">
                  <div>
                    <h3 className="text-xs font-black text-cyan-500/60 tracking-[0.4em] mb-2 uppercase italic">Target HUD // {data.last_best_sym || "XAUUSDm"}</h3>
                    <div className="flex items-center gap-6">
                      <span className="text-7xl lg:text-8xl font-black text-white tracking-tighter tabular-nums drop-shadow-2xl">{(data.bid || 0).toFixed(2)}</span>
                      <div className="flex flex-col gap-2">
                        <div className={`px-2 py-1 rounded text-[10px] font-bold flex items-center gap-2 ${data.m5_trend && data.m5_trend.includes('🟢') ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                          <span className="opacity-50 text-[8px]">M5</span> {data.m5_trend}
                        </div>
                        <div className={`px-2 py-1 rounded text-[10px] font-bold flex items-center gap-2 ${data.h1_trend === 'BUY' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                          <span className="opacity-50 text-[8px]">H1</span> {data.h1_trend}
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] font-black text-cyan-500/40 tracking-widest mb-1 uppercase">Margin Vigilance</p>
                    <p className={`text-4xl font-black tabular-nums transition-all ${data.margin_level < 200 ? 'text-red-500 animate-pulse' : 'text-white'}`}>
                      {(data.margin_level || 0).toFixed(0)}<span className="text-sm opacity-50 ml-1">%</span>
                    </p>
                  </div>
                </header>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative z-10">
                  <div className="space-y-4">
                    <IndicatorPill label="RSI SENTINEL" value={(data.rsi || 0).toFixed(1)} color={data.rsi > 70 ? "red" : data.rsi < 30 ? "emerald" : "cyan"} />
                    <IndicatorPill label="BOLLINGER POS" value={`${((data.bb_pos || 0) * 100).toFixed(0)}%`} color={data.bb_pos > 0.8 ? "red" : data.bb_pos < 0.2 ? "emerald" : "gray"} />
                  </div>
                  <div className="space-y-4">
                    <IndicatorPill label="SPREAD PTS" value={(data.spread || 0).toFixed(0)} color={data.spread > 50 ? "red" : "gray"} />
                    <IndicatorPill label="EQUITY" value={`$${(data.equity || 0).toFixed(0)}`} color="cyan" />
                  </div>
                  <div className="space-y-4">
                    <IndicatorPill label="DAILY PNL" value={`$${(data.pnl || 0).toFixed(2)}`} color={(data.pnl || 0) >= 0 ? "emerald" : "red"} />
                    <IndicatorPill label="IA BIAS" value={data.ai_insight || "NEUTRAL"} color={data.ai_insight?.includes("SI") ? "emerald" : data.ai_insight?.includes("NO") ? "red" : "gray"} />
                  </div>
                </div>
              </div>

              {/* RADAR MÚLTIPLE (v7.8) */}
              <section className="bg-gray-900 border border-gray-800 rounded-[2.5rem] overflow-hidden shadow-xl">
                <div className="p-6 border-b border-gray-800 flex justify-between items-center bg-black/20">
                  <h2 className="text-[10px] font-black tracking-[0.2em] uppercase italic flex items-center gap-2 text-white">
                    <Zap size={16} className="text-yellow-500" /> RADAR DE OPORTUNIDADES (MULTI-ASSET)
                  </h2>
                </div>
                <div className="overflow-x-auto min-h-[300px]">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="text-gray-500 uppercase font-black border-b border-gray-800 bg-black/40">
                        <th className="p-6">Símbolo</th>
                        <th className="p-6">Señal</th>
                        <th className="p-6">Confianza</th>
                        <th className="p-6">RSI</th>
                        <th className="p-6 text-right">Lote</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800/50">
                      {data.radar && data.radar.length > 0 ? data.radar.map((r: any, i: number) => (
                        <tr key={i} className="hover:bg-white/5 transition-colors group">
                          <td className="p-6 font-black text-white italic">{r.symbol}</td>
                          <td className="p-6">
                            <span className={`px-3 py-1 rounded-full font-black text-[10px] ${r.signal === 'BUY' ? 'bg-emerald-500/10 text-emerald-400' : r.signal === 'SELL' ? 'bg-red-500/10 text-red-400' : 'bg-gray-800 text-gray-500'}`}>
                              {r.signal}
                            </span>
                          </td>
                          <td className="p-6 font-black text-cyan-400">{(r.confidence * 100).toFixed(0)}%</td>
                          <td className="p-6 font-bold text-gray-400">{r.rsi.toFixed(0)}</td>
                          <td className="p-6 text-right font-mono text-gray-500">{r.lot}</td>
                        </tr>
                      )) : (
                        <tr><td colSpan={5} className="p-24 text-center text-gray-700 italic font-black uppercase tracking-widest">Scanning Global Markets...</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>

            <div className="lg:col-span-4 space-y-8">
              <section className="bg-gradient-to-b from-cyan-500/10 to-transparent border border-cyan-500/20 rounded-[2.5rem] p-8 shadow-2xl relative">
                <div className="flex justify-between items-center mb-8">
                  <h3 className="text-cyan-500 text-[10px] font-black tracking-[0.4em] uppercase flex items-center gap-2">
                    <BrainCircuit size={18} /> COGNITIVE CORE
                  </h3>
                  <div className="bg-cyan-500 text-black text-[9px] font-black px-2 py-0.5 rounded leading-none">OLLAMA CLOUD</div>
                </div>
                <div className="min-h-[120px] flex flex-col justify-center">
                  <p className="text-sm font-bold leading-relaxed italic text-gray-100 border-l-2 border-cyan-500 pl-6 py-2">
                    "{data.ai_insight || "Analyzing proposal for 500% daily profit..."}"
                  </p>
                </div>
              </section>

              <section className="bg-black border border-gray-800 rounded-[2.5rem] overflow-hidden shadow-2xl flex flex-col h-[520px]">
                <div className="p-5 bg-gray-900/80 border-b border-gray-800 flex justify-between items-center">
                  <span className="text-[10px] font-black tracking-widest text-emerald-500 flex items-center gap-2">
                    <Terminal size={14} /> TACTICAL_TELEMETRY.LOG
                  </span>
                </div>
                <div className="p-8 overflow-y-auto space-y-5 font-mono text-[10px] leading-relaxed scrollbar-hide">
                  {data.alertas && data.alertas.map((log: string, i: number) => (
                    <div key={i} className="flex gap-4 group">
                      <span className="text-gray-700 font-bold shrink-0">{i.toString().padStart(3, '0')}</span>
                      <p className={`${log.includes('⚠️') ? 'text-yellow-500' : log.includes('🚨') ? 'text-red-500 font-black' : log.includes('✅') ? 'text-emerald-500' : 'text-gray-400'}`}>
                        {log}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </div>
        )}

        {activeTab === "audit" && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-gray-900 border border-white/5 rounded-[2.5rem] p-8 lg:p-12 shadow-3xl">
              <h2 className="text-3xl font-black text-white mb-8 tracking-tighter italic uppercase">Institutional <span className="text-cyan-500">Comparative Audit</span></h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-gray-800 text-cyan-500 uppercase text-[10px] font-black tracking-widest">
                      <th className="py-4 px-6">Feature</th>
                      <th className="py-4 px-6">Legacy VPIN</th>
                      <th className="py-4 px-6">Sentinel 7.8 (Current)</th>
                      <th className="py-4 px-6">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/40 text-gray-300">
                    <tr>
                      <td className="py-6 px-6 font-bold">Radar Scannning</td>
                      <td className="py-6 px-6 italic text-gray-500">Single Asset (XAU)</td>
                      <td className="py-6 px-6 font-black text-white uppercase">Multi-Asset Radar (6 Targets)</td>
                      <td className="py-6 px-6"><span className="bg-emerald-500/10 text-emerald-400 px-3 py-1 rounded-full text-[9px] font-black">INTEGRATED</span></td>
                    </tr>
                    <tr>
                      <td className="py-6 px-6 font-bold">Decision HUD</td>
                      <td className="py-6 px-6 italic text-gray-500">Technical Data Only</td>
                      <td className="py-6 px-6 font-black text-white uppercase italic">Natural Language + Profit Est.</td>
                      <td className="py-6 px-6"><span className="bg-emerald-500/10 text-emerald-400 px-3 py-1 rounded-full text-[9px] font-black">INTEGRATED</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === "system" && (
          <div className="max-w-5xl mx-auto space-y-8 animate-in zoom-in-95 duration-300">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <SystemMiniCard label="MT5 LINK" status="ONLINE" color="emerald" />
              <SystemMiniCard label="RADAR ENGINE" status="7.8 ALPHA" color="cyan" />
              <SystemMiniCard label="STRATEGY" status="SCALPER PRO" color="yellow" />
              <SystemMiniCard label="SECURITY" status="TITANIUM" color="emerald" />
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-[2.5rem] p-10">
              <h3 className="text-xs font-black tracking-[0.3em] uppercase mb-8 text-white text-center italic">Titan Mission Orchestrator</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <button onClick={() => sendCommand("auto_mode", !data.auto_mode)} className={`flex items-center justify-between p-6 rounded-3xl border transition-all ${data.auto_mode ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-500' : 'bg-gray-800/10 border-gray-800 text-gray-500'}`}>
                  <div className="flex items-center gap-4">
                    <Power size={24} />
                    <div className="text-left">
                      <p className="font-black text-xs uppercase tracking-widest text-white">Autonomous Fire</p>
                      <p className="text-[10px] opacity-60 uppercase font-bold">Total control engagement</p>
                    </div>
                  </div>
                  <span className="text-xs font-black">{data.auto_mode ? 'ON' : 'OFF'}</span>
                </button>
                <button onClick={() => sendCommand("start_mission", true)} className="bg-cyan-500 hover:bg-cyan-400 text-black flex items-center justify-between p-6 rounded-3xl transition-all shadow-[0_0_50px_rgba(6,182,212,0.3)] group">
                  <div className="flex items-center gap-4">
                    <Target size={24} className="group-hover:scale-125 transition-transform" />
                    <div className="text-left">
                      <p className="font-black text-xs uppercase tracking-widest">Force Start Mission</p>
                      <p className="text-[10px] font-bold opacity-80 uppercase">Capture Market Momentum (500% Target)</p>
                    </div>
                  </div>
                </button>
              </div>

              {/* v7.9: BRAIN INDEPENDENTS */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                <button onClick={() => sendCommand("oro_brain_on", !data.oro_brain_on)} className={`flex items-center justify-between p-6 rounded-3xl border transition-all ${data.oro_brain_on ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-500' : 'bg-gray-800/10 border-gray-800 text-gray-400'}`}>
                  <div className="flex items-center gap-4">
                    <BrainCircuit size={24} />
                    <div className="text-left">
                      <p className="font-black text-xs uppercase tracking-widest text-white">CEREBRO ORO</p>
                      <p className="text-[10px] opacity-60 uppercase font-bold text-yellow-500/80">XAUUSD + FX Analysis</p>
                    </div>
                  </div>
                  <span className="text-xs font-black">{data.oro_brain_on ? 'ONLINE' : 'OFFLINE'}</span>
                </button>
                <button onClick={() => sendCommand("btc_brain_on", !data.btc_brain_on)} className={`flex items-center justify-between p-6 rounded-3xl border transition-all ${data.btc_brain_on ? 'bg-orange-500/10 border-orange-500/30 text-orange-500' : 'bg-gray-800/10 border-gray-800 text-gray-400'}`}>
                  <div className="flex items-center gap-4">
                    <BrainCircuit size={24} />
                    <div className="text-left">
                      <p className="font-black text-xs uppercase tracking-widest text-white">CEREBRO BTC</p>
                      <p className="text-[10px] opacity-60 uppercase font-bold text-orange-500/80">Bitcoin 24/7 Neural Core</p>
                    </div>
                  </div>
                  <span className="text-xs font-black">{data.btc_brain_on ? 'ONLINE' : 'OFFLINE'}</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === "history" && (
          <div className="max-w-4xl mx-auto animate-in fade-in duration-500">
            <div className="bg-gray-900 border-2 border-dashed border-gray-800 rounded-[3rem] p-24 text-center space-y-8">
              <div className="w-20 h-20 bg-gray-800 rounded-full flex items-center justify-center mx-auto text-gray-600">
                <History size={40} />
              </div>
              <div>
                <h2 className="text-xl font-black italic uppercase tracking-[0.2em] text-white mb-2 italic">Engagements Archives</h2>
                <p className="text-[10px] text-gray-500 leading-relaxed uppercase font-bold tracking-widest max-w-sm mx-auto">
                  Encryption module active. Data synced post-market closure.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="p-12 text-center opacity-20 border-t border-gray-900/50 mt-20">
        <p className="text-[9px] font-black tracking-[1.5em] uppercase italic">Private Institutional Infrastructure // TSD v7.8 (RADAR_SCALPER)</p>
      </footer>
    </div>
  );
}

function TabBtn({ id, active, icon, label, onClick }: any) {
  const isActive = active === id;
  return (
    <button onClick={() => onClick(id)} className={`px-8 py-3 rounded-2xl flex items-center gap-3 text-[10px] font-black tracking-[0.3em] transition-all duration-500 relative group ${isActive ? 'bg-cyan-500 text-black shadow-[0_0_30px_rgba(6,182,212,0.5)] scale-105' : 'text-gray-500 hover:text-cyan-400 hover:bg-cyan-500/5'}`}>
      {icon}
      <span>{label}</span>
      {isActive && <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-4 h-1 bg-white rounded-full blur-[1px]" />}
    </button>
  );
}

function StatBox({ label, value, icon, color = "white" }: any) {
  const colors: any = {
    white: "text-white shadow-[0_0_20px_rgba(255,255,255,0.05)]",
    cyan: "text-cyan-400 shadow-[0_0_20px_rgba(34,211,238,0.1)]",
    red: "text-red-500 shadow-[0_0_20px_rgba(239,68,68,0.1)]",
    emerald: "text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.1)]",
    yellow: "text-yellow-500 shadow-[0_0_20px_rgba(234,179,8,0.1)]"
  };
  return (
    <div className="bg-gray-900/60 backdrop-blur-2xl border border-white/5 p-6 rounded-[2.5rem] hover:border-cyan-500/30 transition-all duration-300 group overflow-hidden relative shadow-2xl">
      <div className="absolute -right-6 -top-6 w-16 h-16 bg-gradient-to-br from-cyan-500/10 to-transparent blur-2xl group-hover:scale-150 transition-transform duration-700" />
      <div className="flex items-center gap-3 opacity-40 mb-4">
        <div className="p-1.5 bg-black/40 rounded-lg text-white ring-1 ring-white/10">{icon}</div>
        <span className="text-[10px] font-black tracking-[0.4em] uppercase">{label}</span>
      </div>
      <p className={`text-3xl font-black tabular-nums tracking-tighter ${colors[color]}`}>{value}</p>
      {color === "cyan" && <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-cyan-500/30 to-transparent mt-4" />}
    </div>
  );
}

function IndicatorPill({ label, value, color }: any) {
  const colors: any = {
    emerald: "bg-emerald-500/5 text-emerald-400 border-emerald-500/10",
    red: "bg-red-500/5 text-red-400 border-red-500/10",
    cyan: "bg-cyan-500/5 text-cyan-400 border-cyan-500/10",
    yellow: "bg-yellow-500/5 text-yellow-400 border-yellow-500/10",
    gray: "bg-gray-800 text-gray-500 border-gray-700"
  };
  return (
    <div className={`px-6 py-3 rounded-2xl border text-[11px] font-black tracking-[0.2em] flex items-center justify-between gap-12 tabular-nums transition-all hover:scale-[1.02] ${colors[color]}`}>
      <span className="opacity-40 uppercase">{label}</span>
      <span className="text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.2)]">{value}</span>
    </div>
  );
}

function SystemMiniCard({ label, status, color }: any) {
  const c: any = {
    emerald: "text-emerald-400 border-emerald-500/10 bg-emerald-500/5 shadow-[inset_0_0_15px_rgba(16,185,129,0.05)]",
    cyan: "text-cyan-400 border-cyan-500/10 bg-cyan-500/5 shadow-[inset_0_0_15px_rgba(6,182,212,0.05)]",
    yellow: "text-yellow-400 border-yellow-500/10 bg-yellow-400/5 shadow-[inset_0_0_15px_rgba(234,179,8,0.05)]"
  };
  return (
    <div className={`p-5 rounded-[2rem] border flex flex-col justify-between h-24 transition-all hover:-translate-y-1 ${c[color]}`}>
      <span className="text-[10px] font-black opacity-30 tracking-[0.3em] uppercase">{label}</span>
      <span className="text-sm font-black tracking-tight flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-current animate-pulse shadow-[0_0_10px_currentColor]" />
        <span className="text-white">{status}</span>
      </span>
    </div>
  );
}
