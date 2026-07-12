# InfraGenie – PRD (Live)

## Product
InfraGenie – AI cloud operations platform for Azure tenants. Everything is grounded in live tenant data via a function-calling bridge between Azure OpenAI and Azure ARM APIs.

## Architecture (as of 2026-07-02)

### Backend (`/app/backend`)
- **server.py** – FastAPI app, auth (JWT via HttpOnly cookies), guest user seeding, tenant chat endpoint
- **provisioning_service.py** – 15 Terraform modules catalog, multi-turn AI orchestration, module-locked flow
- **provisioning_api.py** – Session→chat→plan→approve→apply lifecycle, portal settings, integrations, users CRUD
- **tenant_ai_service.py** – **NEW**: Azure OpenAI + 8 function-calling tools (list_resource_groups, list_resources, list_vms, get_costs, get_secure_score, get_advisor_recommendations, list_alerts, list_policy_assignments)
- **agent_api.py** – **NEW**: `/tenant/summary` (cached KPIs), `/reports/*` (PDF + Blob upload), `/assessments/*`, ITSM ext, policy remediation
- **azure_services.py** / **ai_provider_service.py** / **terraform_runtime.py** / **pricing_service.py**

### Frontend (`/app/frontend/src`)
- **components/AskTenantAgent.jsx** – **NEW**: shared chat panel powered by `/api/tenant/chat` (used on every agent page)
- **hooks/useTenantSummary.js** – **NEW**: cached tenant snapshot hook
- **pages/**: Dashboard (rewritten for accuracy), AgentObservability (NEW, charts+PDF/CSV), AgentAssessment (NEW, 6 assessment types), AgentReports (NEW), AgentOptimization/Troubleshoot/Policy (all rewired to tenant bridge), Support (proactive), Settings (theme reset + user CRUD + Foundry/ServiceNow/Slack/PagerDuty integrations), Tickets (manual create modal + delete-with-destroy), Onboarding (Azure OpenAI relabel), ProvisioningConversation (Generate Plan button fixed)

## Deployed & verified 2026-07-02

### Foundation
- **Azure OpenAI ↔ tenant bridge** (`POST /api/tenant/chat`) — verified: "list resource groups" returns actual 3 RGs
- **8 function-calling tools** — verified: `get_costs` returned actual top spenders (₹0.10 cognitive services, ₹0.03 storage)

### Provisioning agent
- Module lock after session start (fixes Linux → Windows auto-switch bug)
- Generate Plan button visible (fixes `ready` vs `ready_for_plan` mismatch)
- AI now asks ALL missing vars in one message + gives sizing recommendations (verified: recommended `Standard_D4s_v5` for staging Docker workload)
- End-to-end deployment verified — deployed `rg-infragenie-test` to Azure Central India

### Dashboard & agents (all backed by tenant bridge)
- **Dashboard**: 5 KPI cards from live scan, cache with refresh button, cost 2-decimal
- **Observability**: KPI cards + PieChart (type mix) + BarChart (locations) + RG table + PDF/CSV export
- **Optimization**: cost-focused Ask Agent, type/location breakdown, KPIs
- **Troubleshoot**: security-score/alerts focused Ask Agent
- **Policy & Compliance**: policy list + remediation with approval dialog
- **Assessment**: 6 assessment types (Security, Cost, Governance, Reliability, Compliance, Ops), Run → PDF/CSV export
- **Reports**: form-driven PDF generation, uploaded to Azure Blob (`infrageniestrg/infragenie-reports/<user_id>/`), 7-day SAS download links
- **ITSM/Tickets**: manual create ticket modal (title, desc, priority, category, resource ref, assignee), delete-with-destroy option
- **Support**: proactive support agent + quick actions
- **Settings**: rebranding with **Reset to default**, user CRUD (admin only), ServiceNow/Foundry/Slack/PagerDuty integration cards

### Sidebar
- Migration agent removed
- Reports Agent added below Policy

### CORS
- `CORS_ORIGINS` whitelisted to preview URLs, credentials-safe. Same-origin frontend↔backend eliminates preflight.

## Verified end-to-end (real Azure calls)
1. Guest login → dashboard renders in <2s
2. `GET /api/tenant/summary` → 3 RGs, 2 resources, ₹0.12 MTD, secure score
3. Provisioning: intent → chat (locked module, one-shot vars ask) → plan → approve → apply → RG created in Azure
4. Reports: generate → Azure OpenAI + tools → ReportLab PDF → uploaded to `infrageniestrg` blob (3941 bytes) → SAS link

## Backlog (P3 for next iteration)
- **Provisioning bundle mode** (intent → propose bundle of RG+VNet+NSG+etc. before collecting) — big backend redesign
- **Custom Observability view builder** — save named views ("My VM metrics", etc.) selectable via dropdown
- **ServiceNow live forwarding** — implement real SN API when creds are supplied
- **Azure Foundry integration** — swap in AIProjectClient when Foundry creds saved (tenant bridge already scaffolded for this)
- **Compliance framework scoring** (per-framework GDPR/HIPAA gauges) — currently query-via-agent only
- **Rebranding: logo upload + full-portal color propagation**
- **Dashboard chat → create ITSM change request auto-flow**
