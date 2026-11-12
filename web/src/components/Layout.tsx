import { useEffect } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth";
import { initials } from "../format";
import { reloadIfReleaseChanged } from "../release";

// Add a page: create it in src/pages, add its route in App.tsx and its link here.
const LINKS: { to: string; label: string; adminOnly?: boolean }[] = [
  { to: "/", label: "Dashboard" },
  { to: "/pipeline", label: "Pipeline" },
  { to: "/contacts", label: "Contacts" },
  { to: "/companies", label: "Companies" },
  { to: "/ask", label: "Ask" },
  { to: "/implement", label: "Implement", adminOnly: true },
];

export function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  useEffect(() => {
    void reloadIfReleaseChanged();
  }, [location.pathname]);
  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          Evolve CRM
        </div>
        <nav aria-label="Main">
          {LINKS.filter((link) => !link.adminOnly || user!.role === "admin").map((link) => (
            <NavLink key={link.to} to={link.to} end={link.to === "/"}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="rail-user">
          <span className="avatar">{initials(user!.name)}</span>
          <div>
            <strong>{user!.name}</strong>
            <span>{user!.role === "admin" ? "Admin" : "Sales"}</span>
          </div>
          <button type="button" className="link-button" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
