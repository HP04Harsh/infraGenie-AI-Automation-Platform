import React from "react";
import { useParams } from "react-router-dom";
import AgentPlaceholder from "@/pages/AgentPlaceholder";
import AgentOptimization from "@/pages/AgentOptimization";
import AgentPolicy from "@/pages/AgentPolicy";
import AgentTroubleshoot from "@/pages/AgentTroubleshoot";
import AgentObservability from "@/pages/AgentObservability";
import AgentAssessment from "@/pages/AgentAssessment";
import AgentReports from "@/pages/AgentReports";
import ProvisioningAgent from "@/pages/ProvisioningAgent";
import Tickets from "@/pages/Tickets";

export default function AgentDispatcher() {
  const { agentKey } = useParams();
  switch (agentKey) {
    case "provisioning":     return <ProvisioningAgent />;
    case "assessment":       return <AgentAssessment />;
    case "observability":    return <AgentObservability />;
    case "optimization":     return <AgentOptimization />;
    case "troubleshoot":     return <AgentTroubleshoot />;
    case "policy":           return <AgentPolicy />;
    case "reports":          return <AgentReports />;
    case "itsm":             return <Tickets />;
    default:                 return <AgentPlaceholder />;
  }
}
