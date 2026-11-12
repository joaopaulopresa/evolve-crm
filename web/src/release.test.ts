import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { forgetReleaseForTests, reloadIfReleaseChanged } from "./release";

function serve(release: string | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      release === null ? Promise.reject(new Error("down")) : { ok: true, json: async () => ({ release }) },
    ),
  );
}

beforeEach(() => forgetReleaseForTests());
afterEach(() => vi.unstubAllGlobals());

test("the same release never reloads", async () => {
  const reload = vi.fn();
  serve("abc");

  expect(await reloadIfReleaseChanged(reload)).toBe(false);
  expect(await reloadIfReleaseChanged(reload)).toBe(false);
  expect(reload).not.toHaveBeenCalled();
});

test("a new release reloads the tab on the next navigation", async () => {
  const reload = vi.fn();
  serve("abc");
  await reloadIfReleaseChanged(reload);

  serve("def");

  expect(await reloadIfReleaseChanged(reload)).toBe(true);
  expect(reload).toHaveBeenCalledOnce();
});

test("an API that is restarting is not mistaken for a new release", async () => {
  const reload = vi.fn();
  serve("abc");
  await reloadIfReleaseChanged(reload);

  serve(null);

  expect(await reloadIfReleaseChanged(reload)).toBe(false);
  expect(reload).not.toHaveBeenCalled();
});
