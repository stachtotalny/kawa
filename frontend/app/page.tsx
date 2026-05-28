"use client";

import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { Play, Activity, Users, Award, CheckCircle2, Lock, Database, Save } from "lucide-react";

export default function Home() {

  const [passwordInput, setPasswordInput] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loginError, setLoginError] = useState(false);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    const correctPassword = process.env.NEXT_PUBLIC_APP_PASSWORD || "admin";
    if (passwordInput === correctPassword) {
      setIsAuthenticated(true);
      setLoginError(false);
    } else {
      setLoginError(true);
    }
  };

  const [formData, setFormData] = useState({
    liczba_wysp: 5,
    wielkosc_wyspy: 40,
    liczba_epok: 100,
    co_ile_kolonizacja: 10,
  });

  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<"IDLE" | "STARTING" | "RUNNING" | "COMPLETED" | "ERROR">("IDLE");
  const [simulationData, setSimulationData] = useState<any>(null);

  const [botName, setBotName] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [savedBots, setSavedBots] = useState<any[]>([]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: parseInt(e.target.value) || 0 });
  };

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  const fetchSavedBots = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/networks`);
      if (res.ok) {
        const data = await res.json();
        setSavedBots(data);
      }
    } catch (err) {
      console.error("Błąd pobierania botów z Neon:", err);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchSavedBots();
    }
  }, [isAuthenticated]);

  const handleStartSimulation = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("STARTING");
    setSimulationData(null);
    setSaveSuccess(false);

    try {
      const response = await fetch(`${apiUrl}/api/simulation/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      if (!response.ok) throw new Error("Błąd startu");
      const data = await response.json();
      setTaskId(data.task_id);
      setStatus("RUNNING");
    } catch (error) {
      console.error(error);
      setStatus("ERROR");
    }
  };

  useEffect(() => {
    let intervalId: NodeJS.Timeout;
    if (taskId && status === "RUNNING") {
      intervalId = setInterval(async () => {
        try {
          const response = await fetch(`${apiUrl}/api/simulation/status/${taskId}`);
          const data = await response.json();
          setSimulationData(data);

          if (data.status === "COMPLETED") {
            setStatus("COMPLETED");
            clearInterval(intervalId);
          }
        } catch (error) {
          console.error(error);
        }
      }, 1000);
    }
    return () => clearInterval(intervalId);
  }, [taskId, status]);


  const handleSaveToNeon = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!botName || !simulationData?.best_agent_weights) return;

    setIsSaving(true);
    try {
      const response = await fetch(`${apiUrl}/api/networks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: botName,
          weights: simulationData.best_agent_weights
        }),
      });

      if (response.ok) {
        setSaveSuccess(true);
        setBotName("");
        fetchSavedBots(); 
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  const latestEpochData = simulationData?.history?.length > 0 
    ? simulationData.history[simulationData.history.length - 1] 
    : null;

  const chartData = simulationData?.history?.map((item: any) => ({
    epoka: item.epoch,
    "Współpraca (%)": item.global_cooperation,
    "Max Fitness": item.highest_fitness,
  })) || [];

  if (!isAuthenticated) {
    return (
      <main className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl max-w-md w-full space-y-6 text-center">
          <div className="mx-auto w-12 h-12 bg-blue-500/10 text-blue-400 rounded-full flex items-center justify-center">
            <Lock className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-100">Dostęp Zablokowany</h1>
            <p className="text-sm text-slate-400 mt-1">Wpisz uniwersalne hasło dostępowe do platformy IPD</p>
          </div>
          <form onSubmit={handleLogin} className="space-y-4">
            <input 
              type="password" 
              placeholder="Wprowadź hasło..." 
              value={passwordInput} 
              onChange={(e) => setPasswordInput(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-center text-slate-100 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-all font-mono"
            />
            {loginError && <p className="text-xs text-red-400 font-medium">Niepoprawne hasło. Spróbuj ponownie.</p>}
            <button type="submit" className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl transition-colors">
              Odblokuj Panel
            </button>
          </form>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-900 text-slate-100 p-4 md:p-8 font-sans">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* NAGŁÓWEK */}
        <header className="flex flex-col md:flex-row justify-between items-center bg-slate-800 p-6 rounded-2xl border border-slate-700 gap-4 shadow-xl">
          <div>
            <h1 className="text-2xl md:text-3xl font-extrabold bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
              Iterated Prisoner's Dilemma
            </h1>
            <p className="text-slate-400 text-sm mt-1">Ewolucyjny Turniej Wyspowy • Panel Dashboard</p>
          </div>
          <div className="flex items-center gap-3 bg-slate-900/50 px-4 py-2 rounded-xl border border-slate-700/50">
            <Database className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-mono text-slate-300">Neon Storage: Connected</span>
          </div>
        </header>

        {/* GŁÓWNY GRID */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* LEWA KOLUMNA: CONFIG + REPOZYTORIUM NEON */}
          <div className="space-y-6">
            {/* FORMULARZ KONTROLNY */}
            <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-lg space-y-4">
              <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                <Activity className="w-5 h-5 text-blue-400" /> Konfiguracja Środowiska
              </h2>
              <form onSubmit={handleStartSimulation} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Liczba wysp</label>
                  <input type="number" name="liczba_wysp" value={formData.liczba_wysp} onChange={handleChange} className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-slate-100 font-mono outline-none" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Populacja wyspy</label>
                  <input type="number" name="wielkosc_wyspy" value={formData.wielkosc_wyspy} onChange={handleChange} className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-slate-100 font-mono outline-none" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Liczba epok</label>
                  <input type="number" name="liczba_epok" value={formData.liczba_epok} onChange={handleChange} className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-slate-100 font-mono outline-none" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Interwał kolonizacji</label>
                  <input type="number" name="co_ile_kolonizacja" value={formData.co_ile_kolonizacja} onChange={handleChange} className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-slate-100 font-mono outline-none" />
                </div>
                <button type="submit" disabled={status === "RUNNING" || status === "STARTING"} className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl disabled:opacity-40 flex items-center justify-center gap-2">
                  <Play className="w-4 h-4 fill-current" /> {status === "RUNNING" ? "Ewolucja..." : "Uruchom Proces"}
                </button>
              </form>
            </div>

            {/* REPOZYTORIUM BOTÓW (Z NEONA) */}
            <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-lg space-y-4">
              <h2 className="text-md font-bold text-slate-200 flex items-center gap-2">
                <Database className="w-4 h-4 text-cyan-400" /> Archiwum Neon Tech
              </h2>
              <div className="max-h-[220px] overflow-y-auto space-y-2 pr-1">
                {savedBots.length > 0 ? (
                  savedBots.map((bot) => (
                    <div key={bot.id} className="bg-slate-900/50 p-3 rounded-xl border border-slate-700/50 flex justify-between items-center text-xs">
                      <span className="font-semibold text-slate-300">{bot.name}</span>
                      <span className="text-[10px] text-slate-500 font-mono">{bot.id.slice(0, 8)}...</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-500 italic">Brak zapisanych agentów w bazie.</p>
                )}
              </div>
            </div>
          </div>

          {/* PRAWA KOLUMNA: WYKRESY, STATUSY I ZAPIS */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* STATYSTYKI */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                <p className="text-xs text-slate-400 font-medium">Status / Epoka</p>
                <p className="text-lg font-bold font-mono mt-1">{status} ({simulationData?.current_epoch || 0})</p>
              </div>
              <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                <p className="text-xs text-slate-400 font-medium">Współpraca</p>
                <p className="text-lg font-bold font-mono text-emerald-400 mt-1">{latestEpochData ? `${latestEpochData.global_cooperation}%` : "0%"}</p>
              </div>
              <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                <p className="text-xs text-slate-400 font-medium">Najwyższy Fitness</p>
                <p className="text-lg font-bold font-mono text-amber-400 mt-1">{latestEpochData?.highest_fitness || "0.00"}</p>
              </div>
            </div>

            {/* SEKCJA TRWAŁEGO ZAPISU PO UKOŃCZENIU SYMULACJI */}
            {status === "COMPLETED" && (
              <div className="bg-gradient-to-r from-emerald-950 to-slate-800 p-6 rounded-2xl border border-emerald-500/30 shadow-xl space-y-4 animate-fade-in">
                <div>
                  <h3 className="text-sm font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" /> Sukces: Ewolucja Zakończona!
                  </h3>
                  <p className="text-xs text-slate-300 mt-1">Najlepsza sieć neuronowa została wyizolowana. Możesz zapisać ją trwale w chmurze Neon.</p>
                </div>
                {!saveSuccess ? (
                  <form onSubmit={handleSaveToNeon} className="flex gap-3">
                    <input 
                      type="text" 
                      placeholder="Nadaj nazwę botowi (np. Strateg_Chytry_1)..." 
                      value={botName}
                      onChange={(e) => setBotName(e.target.value)}
                      className="flex-1 bg-slate-900 border border-slate-700 rounded-xl p-3 text-sm text-slate-100 outline-none focus:border-emerald-500"
                    />
                    <button type="submit" disabled={isSaving || !botName} className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white font-bold px-6 rounded-xl text-sm flex items-center gap-2 transition-colors">
                      <Save className="w-4 h-4" /> {isSaving ? "Zapis..." : "Zapisz w Neon"}
                    </button>
                  </form>
                ) : (
                  <div className="bg-emerald-900/30 border border-emerald-500/40 text-emerald-300 p-3 rounded-xl text-xs font-semibold text-center">
                    Agent został pomyślnie zrzutowany i zabezpieczony w bazie PostgreSQL Neon Tech!
                  </div>
                )}
              </div>
            )}

            {/* WYKRES */}
            <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-lg">
              <div className="h-[280px] w-full">
                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="epoka" stroke="#94a3b8" fontSize={11} />
                      <YAxis stroke="#94a3b8" fontSize={11} />
                      <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#475569' }} />
                      <Legend />
                      <Line type="monotone" dataKey="Współpraca (%)" stroke="#10b981" strokeWidth={2.5} dot={false} />
                      <Line type="monotone" dataKey="Max Fitness" stroke="#f59e0b" strokeWidth={1.5} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-slate-500 text-sm italic">
                    Uruchom proces, aby wygenerować wykres zbieżności
                  </div>
                )}
              </div>
            </div>

          </div>
        </div>
      </div>
    </main>
  );
}