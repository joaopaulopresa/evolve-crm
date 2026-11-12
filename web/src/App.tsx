import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { Companies } from "./pages/Companies";
import { Ask } from "./pages/Ask";
import { ContactDetail } from "./pages/ContactDetail";
import { Contacts } from "./pages/Contacts";
import { DashboardPage } from "./pages/Dashboard";
import { Implement } from "./pages/Implement";
import { Login } from "./pages/Login";
import { Pipeline } from "./pages/Pipeline";

function Screens() {
  const { user, ready } = useAuth();
  if (!ready) return null;
  if (!user) return <Login />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="pipeline" element={<Pipeline />} />
        <Route path="contacts" element={<Contacts />} />
        <Route path="contacts/:contactId" element={<ContactDetail />} />
        <Route path="companies" element={<Companies />} />
        <Route path="ask" element={<Ask />} />
        {user.role === "admin" && <Route path="implement" element={<Implement />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Screens />
      </AuthProvider>
    </BrowserRouter>
  );
}
