import React from "react";
import Layout from "@/components/Layout";
import AskTenantAgent from "@/components/AskTenantAgent";
import { LifeBuoy, MessageCircle, Book, Zap } from "lucide-react";
import { Link } from "react-router-dom";

export default function Support() {
  return (
    <Layout>
      <div className="pt-8">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 grid place-items-center text-white shadow-lg">
            <LifeBuoy className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Support</h1>
            <p className="mt-0.5 text-[13px] text-slate-500">Get proactive help for InfraGenie portal and your Azure tenant. Chat with our support engineer AI, browse quick actions, or open a ticket.</p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <SupportCard icon={Zap} title="Reset onboarding" desc="Reconnect your Azure tenant if creds changed." to="/onboarding" testid="support-onboarding" />
          <SupportCard icon={Book} title="View documentation" desc="Provisioning agent, Terraform modules, RBAC." to="#" testid="support-docs" />
          <SupportCard icon={MessageCircle} title="Open a ticket" desc="Create an ITSM ticket with full details." to="/agents/itsm" testid="support-ticket" />
        </div>

        <div className="mt-6 grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-1 bg-white rounded-2xl border border-slate-200/80 p-5">
            <h3 className="text-[13.5px] font-semibold text-slate-900">Common issues</h3>
            <ul className="mt-3 space-y-2 text-[12.5px] text-slate-700">
              <li>• <span className="font-semibold">Provisioning stuck?</span> Ask the support agent to diagnose it.</li>
              <li>• <span className="font-semibold">Cost data missing?</span> Ensure SP has <span className="font-mono">Cost Management Reader</span>.</li>
              <li>• <span className="font-semibold">Chat not answering?</span> Verify Azure OpenAI deployment name in Settings.</li>
              <li>• <span className="font-semibold">Terraform apply fails?</span> Storage backend key rotated? Update Settings.</li>
            </ul>
          </div>
          <div className="xl:col-span-2">
            <AskTenantAgent
              title="Ask the Support Agent"
              placeholder="e.g. Why is my provisioning failing? Or how do I integrate ServiceNow?"
              hint="You are the InfraGenie Support Agent. You help users debug the InfraGenie portal AND their Azure tenant. Give step-by-step actionable guidance like an engineer."
              suggestedPrompts={[
                "How do I connect ServiceNow?",
                "My cost data is empty — what permissions do I need?",
                "How do I download a report?",
                "Diagnose issues with my last provisioning session",
              ]}
              testIdPrefix="support-ask"
            />
          </div>
        </div>
      </div>
    </Layout>
  );
}

function SupportCard({ icon: Icon, title, desc, to, testid }) {
  return (
    <Link to={to} data-testid={testid} className="bg-white rounded-2xl border border-slate-200/80 hover:border-indigo-300 hover:shadow-md transition p-5 block">
      <Icon className="h-5 w-5 text-indigo-500" />
      <div className="mt-3 text-[14px] font-semibold text-slate-900">{title}</div>
      <div className="mt-1 text-[12px] text-slate-500">{desc}</div>
    </Link>
  );
}
