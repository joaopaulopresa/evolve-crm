import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import App from "./App";

type Route = { status?: number; body: unknown };

/** Replaces fetch with canned responses keyed by "METHOD /path". */
function stubApi(routes: Record<string, Route>) {
  const calls: { key: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
      calls.push({ key, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      const route = routes[key] ?? { status: 404, body: { detail: `No stub for ${key}` } };
      const status = route.status ?? 200;
      return { ok: status < 400, status, json: async () => route.body };
    }),
  );
  return calls;
}

const alice = { id: 7, email: "alice@example.test", name: "Alice Stone", role: "user" };
const dashboard = {
  pipeline: [
    { stage: "lead", count: 2, value: 3000 },
    { stage: "qualified", count: 0, value: 0 },
    { stage: "proposal", count: 1, value: 9000 },
    { stage: "negotiation", count: 0, value: 0 },
  ],
  won_this_month: { count: 1, value: 4500 },
  overdue_tasks: [],
};

beforeEach(() => {
  localStorage.clear();
  window.history.pushState({}, "", "/");
});
afterEach(() => vi.unstubAllGlobals());

test("signing in shows the dashboard with pipeline totals", async () => {
  const calls = stubApi({
    "POST /api/auth/login": { body: { access_token: "t0ken", user: alice } },
    "GET /api/dashboard": { body: dashboard },
  });
  render(<App />);

  await userEvent.type(await screen.findByLabelText("E-mail"), "alice@example.test");
  await userEvent.type(screen.getByLabelText("Password"), "secret123");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

  expect(await screen.findByTestId("open-pipeline")).toHaveTextContent("$12,000");
  expect(screen.getByTestId("won-this-month")).toHaveTextContent("$4,500");
  expect(screen.getByText("Alice Stone")).toBeInTheDocument();
  expect(calls[0]).toEqual({
    key: "POST /api/auth/login",
    body: { email: "alice@example.test", password: "secret123" },
  });
  expect(localStorage.getItem("evolve.token")).toBe("t0ken");
});

test("a wrong password shows the reason and stays on the sign-in form", async () => {
  stubApi({ "POST /api/auth/login": { status: 401, body: { detail: "Wrong e-mail or password" } } });
  render(<App />);

  await userEvent.type(await screen.findByLabelText("E-mail"), "alice@example.test");
  await userEvent.type(screen.getByLabelText("Password"), "nope");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Wrong e-mail or password");
});

test("an expired session returns to the sign-in form", async () => {
  localStorage.setItem("evolve.token", "stale");
  stubApi({ "GET /api/auth/me": { status: 401, body: { detail: "Not authenticated" } } });
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  await waitFor(() => expect(localStorage.getItem("evolve.token")).toBeNull());
});
