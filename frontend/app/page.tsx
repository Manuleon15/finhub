import Link from "next/link";

export default function HomePage() {
  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2">FinHub</h1>
      <p className="text-gray-400 mb-8">Tu plataforma personal de análisis de inversiones</p>

      {/* KPIs placeholder */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-bg-card border border-bg-border rounded-lg p-5">
          <p className="text-sm text-gray-500">Módulos activos</p>
          <p className="text-2xl font-bold text-accent mt-1">1 / 6</p>
          <p className="text-xs text-gray-600 mt-1">Equity Research disponible</p>
        </div>
        <div className="bg-bg-card border border-bg-border rounded-lg p-5">
          <p className="text-sm text-gray-500">Estado backend</p>
          <p className="text-2xl font-bold text-success mt-1">● Online</p>
          <p className="text-xs text-gray-600 mt-1">localhost:8000</p>
        </div>
        <div className="bg-bg-card border border-bg-border rounded-lg p-5">
          <p className="text-sm text-gray-500">IA</p>
          <p className="text-2xl font-bold text-gray-400 mt-1">Desactivada</p>
          <p className="text-xs text-gray-600 mt-1">Núcleo funciona sin LLM</p>
        </div>
      </div>

      {/* Roadmap */}
      <div className="bg-bg-card border border-bg-border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Módulos</h2>
        <div className="space-y-3">
          <Link
            href="/research"
            className="flex items-center justify-between p-3 rounded-md bg-bg-hover hover:bg-border transition-colors"
          >
            <div>
              <p className="text-white font-medium">🔍 Equity Research Terminal</p>
              <p className="text-sm text-gray-500">Análisis DCF + scoring BUY/HOLD/SELL</p>
            </div>
            <span className="text-success text-sm">✓ Disponible</span>
          </Link>

          {[
            { icon: "💼", name: "Portfolio Tracker", desc: "Migra tu Excel a web" },
            { icon: "⚙️", name: "Stock Screener", desc: "Filtros custom + IA" },
            { icon: "🔔", name: "Detector de caídas", desc: "Alertas diarias" },
            { icon: "📈", name: "Earnings Analyzer", desc: "Upload PDF de resultados" },
            { icon: "🤖", name: "Copiloto", desc: "Chat con tus datos" },
          ].map((m) => (
            <div
              key={m.name}
              className="flex items-center justify-between p-3 rounded-md bg-bg opacity-50"
            >
              <div>
                <p className="text-gray-400 font-medium">{m.icon} {m.name}</p>
                <p className="text-sm text-gray-600">{m.desc}</p>
              </div>
              <span className="text-gray-600 text-sm">Próximamente</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

