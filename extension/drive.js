// The user's own Google Drive, with the narrowest scope Google offers (drive.file):
// the extension can only see files it created itself. Nothing goes anywhere else.

const API = "https://www.googleapis.com/drive/v3";
const UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name";
export const FOLDER_NAME = "Feed Unfucker";
const FOLDER_MIME = "application/vnd.google-apps.folder";

export async function getToken(interactive) {
  const result = await chrome.identity.getAuthToken({ interactive });
  return typeof result === "string" ? result : result && result.token;
}

async function call(url, init = {}, retried = false) {
  const token = await getToken(false);
  if (!token) throw new Error("drive_not_connected");
  const res = await fetch(url, { ...init, headers: { ...(init.headers || {}), Authorization: `Bearer ${token}` } });
  if (res.status === 401 && !retried) {
    await chrome.identity.removeCachedAuthToken({ token });
    return call(url, init, true);
  }
  if (!res.ok) throw new Error(`drive_${res.status}: ${(await res.text()).slice(0, 200)}`);
  return res.status === 204 ? null : res.json();
}

async function folderId() {
  const { driveFolderId } = await chrome.storage.local.get("driveFolderId");
  if (driveFolderId) {
    try {
      const f = await call(`${API}/files/${driveFolderId}?fields=id,trashed`);
      if (f && !f.trashed) return f.id;
    } catch (e) {
      // Deleted or unreachable: make a new one below.
    }
  }
  const q = encodeURIComponent(`name='${FOLDER_NAME}' and mimeType='${FOLDER_MIME}' and trashed=false`);
  const found = await call(`${API}/files?q=${q}&fields=files(id)`);
  let id = found.files && found.files[0] && found.files[0].id;
  if (!id) {
    const made = await call(`${API}/files?fields=id`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: FOLDER_NAME, mimeType: FOLDER_MIME }),
    });
    id = made.id;
  }
  await chrome.storage.local.set({ driveFolderId: id });
  return id;
}

export async function saveCapture(name, record) {
  const parent = await folderId();
  const boundary = "fu" + Math.random().toString(36).slice(2);
  const meta = { name, mimeType: "application/json", parents: [parent] };
  const body =
    `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${JSON.stringify(meta)}\r\n` +
    `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${JSON.stringify(record)}\r\n` +
    `--${boundary}--`;
  return call(UPLOAD, { method: "POST", headers: { "Content-Type": `multipart/related; boundary=${boundary}` }, body });
}

// Captures older than keepDays are deleted, so friends' posts don't pile up in Drive.
export async function pruneCaptures(keepDays) {
  const parent = await folderId();
  const cutoff = new Date(Date.now() - keepDays * 86400000).toISOString();
  const q = encodeURIComponent(`'${parent}' in parents and name contains 'capture-' and createdTime < '${cutoff}' and trashed=false`);
  const old = await call(`${API}/files?q=${q}&fields=files(id)&pageSize=100`);
  for (const f of old.files || []) await call(`${API}/files/${f.id}`, { method: "DELETE" });
}
