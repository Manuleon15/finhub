# FinHub — Plataforma Personal de Análisis de Inversiones

## 🚀 Setup rápido

```bash
# 1. Instalar dependencias
make install

# 2. Configurar entorno
cp .env.example .env
# Edita .env con tu email de Google (ALLOWED_EMAILS) y API keys

# 3. Inicializar DB
make db-init

# 4. Arrancar
make dev
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

## 📋 Prerrequisitos

- Python 3.11+
- Node.js 18+
- Cuenta de Google (para OAuth)

## 🔐 Configurar Google OAuth

1. Ve a https://console.cloud.google.com/
2. Crea un proyecto nuevo
3. APIs & Services → Credentials → Create Credentials → OAuth client ID
4. Application type: Web application
5. Authorized redirect URIs:
   - `http://localhost:3000/api/auth/callback/google`
6. Copia Client ID y Client Secret a `.env`

## 📦 Módulos

1. **Equity Research Terminal** — Ticker → DCF + recomendación
2. **Portfolio Tracker** — Migra tu Excel
3. **Stock Screener** — Filtros custom
4. **Detector de caídas** — Alertas diarias
5. **Earnings Analyzer** — Análisis de PDFs
6. **Copiloto** — Chat con tus datos
7. **IRPF Optimizer** — Impuestos español (próximamente)

## 🛠️ Comandos

| Comando | Qué hace |
|---|---|
| `make install` | Instala backend + frontend |
| `make db-init` | Crea tablas DB |
| `make dev` | Arranca backend + frontend |
| `make test` | Ejecuta tests |
| `make clean` | Limpia caches |

## 📝 Licencia

MIT — uso personal.

