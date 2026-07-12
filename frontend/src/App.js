import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Login from "@/pages/Login";
import Onboarding from "@/pages/Onboarding";
import Dashboard from "@/pages/Dashboard";
import AgentDispatcher from "@/pages/AgentDispatcher";
import ProvisioningConversation from "@/pages/ProvisioningConversation";
import Tickets from "@/pages/Tickets";
import Settings from "@/pages/Settings";
import Support from "@/pages/Support";
import ChatScreen from "@/pages/ChatScreen";
import ActivityHistory from "@/pages/ActivityHistory";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />

            <Route
              path="/onboarding"
              element={
                <ProtectedRoute>
                  <Onboarding />
                </ProtectedRoute>
              }
            />

            <Route
              path="/dashboard"
              element={
                <ProtectedRoute requireOnboarded>
                  <Dashboard />
                </ProtectedRoute>
              }
            />

            <Route
              path="/agents/:agentKey"
              element={
                <ProtectedRoute requireOnboarded>
                  <AgentDispatcher />
                </ProtectedRoute>
              }
            />

            <Route
              path="/settings"
              element={
                <ProtectedRoute requireOnboarded>
                  <Settings />
                </ProtectedRoute>
              }
            />

            <Route
              path="/support"
              element={
                <ProtectedRoute requireOnboarded>
                  <Support />
                </ProtectedRoute>
              }
            />

            <Route
              path="/chat"
              element={
                <ProtectedRoute requireOnboarded>
                  <ChatScreen />
                </ProtectedRoute>
              }
            />

            <Route
              path="/activity"
              element={
                <ProtectedRoute requireOnboarded>
                  <ActivityHistory />
                </ProtectedRoute>
              }
            />

            <Route
              path="/provisioning/session/:sessionId"
              element={
                <ProtectedRoute requireOnboarded>
                  <ProvisioningConversation />
                </ProtectedRoute>
              }
            />

            <Route
              path="/tickets"
              element={
                <ProtectedRoute requireOnboarded>
                  <Tickets />
                </ProtectedRoute>
              }
            />

            <Route
              path="/tickets/:ticketId"
              element={
                <ProtectedRoute requireOnboarded>
                  <Tickets />
                </ProtectedRoute>
              }
            />

            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
