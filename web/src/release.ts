// A tab that stays open across a deploy keeps running the old code. On every navigation the
// app asks the API which release is serving; when it differs from the one this tab started
// with, the page is reloaded so the person gets the new version (or the old one, after a
// rollback).

let loadedRelease: string | null = null;

async function servingRelease(): Promise<string | null> {
  try {
    const response = await fetch("/api/health");
    return response.ok ? ((await response.json()).release as string) : null;
  } catch {
    return null; // the API is restarting: try again on the next navigation
  }
}

/** Returns true when the tab was reloaded because a different release is now serving. */
export async function reloadIfReleaseChanged(reload = () => window.location.reload()) {
  const serving = await servingRelease();
  if (serving === null) return false;
  if (loadedRelease === null) {
    loadedRelease = serving;
    return false;
  }
  if (serving !== loadedRelease) {
    reload();
    return true;
  }
  return false;
}

export function forgetReleaseForTests() {
  loadedRelease = null;
}
