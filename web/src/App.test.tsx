import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import App from "./App";

afterEach(() => vi.unstubAllGlobals());

test("shows the API status reported by the health endpoint", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", environment: "test", release: "abc123" }),
    }),
  );

  render(<App />);

  expect(await screen.findByText(/API ok · test · release abc123/)).toBeInTheDocument();
});

test("tells the user when the API is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

  render(<App />);

  expect(await screen.findByRole("alert")).toHaveTextContent("not reachable");
});
