/* Shared operator contract. Domain interactions remain in core.js. */
let operatorPreferences = null;
let csrfValue = "";
let logCursors = {older: null, live: null};
let presentationSave = Promise.resolve();
let recoveryReview = null;
const updateState = {candidate: null, helper: null, saved: false, blob: null, receipt: "", filename: "", request: null, job: null, timer: null, delay: 1500, checking: false};

async function refreshKernel() {
  const config = await api("/v1/settings/kernel");
  el("kernelOrigin").value = config.url;
  el("kernelStatus").textContent = config.helper_sync_required ? "Kernel changed. Synchronize the host Updater before installing releases; see Documentation." : config.register_stale ? "Kernel is unavailable; the last valid Register is in use." : config.token_configured ? "Token configured. Check the authenticated connection." : "Kernel token has not been configured.";
}
function closeKernelToken() { el("kernelTokenBackdrop").classList.remove("open"); el("kernelTokenBackdrop").setAttribute("aria-hidden", "true"); el("kernelCurrentKey").value = ""; el("kernelNewToken").value = ""; }
async function rotateKernelToken() {
  await api("/v1/settings/kernel/token", {method: "POST", body: JSON.stringify({current_key: readOpaqueKey(el("kernelCurrentKey")), token: el("kernelNewToken").value})});
  closeKernelToken(); await refreshKernel(); notify("Kernel credential replaced.", "success");
}

async function operatorResponse(path, options = {}) {
  const requestHeaders = {...(options.headers || {})};
  if (!["GET", "HEAD"].includes(options.method || "GET")) requestHeaders["X-CSRF-Token"] = csrfValue;
  if (typeof options.body === "string" && !requestHeaders["Content-Type"]) requestHeaders["Content-Type"] = "application/json";
  const response = await fetch(path, {...options, headers: requestHeaders, credentials: "same-origin", cache: "no-store"});
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if (response.status === 403 && String(body.error?.message || "").startsWith("perimetr_")) {
      notify("Your session has ended. Sign in again.", "error");
      location.replace("/");
    }
    throw new Error(body.error?.message || "The operation could not be completed.");
  }
  return response;
}
async function api(path, options = {}) {
  const response = await operatorResponse(path, options);
  const method = (options.method || "GET").toUpperCase();
  if (options.feedback !== false && !["GET", "HEAD"].includes(method) && !path.startsWith("/v1/updater/") && path !== "/v1/correlation" && path !== "/v1/audit/ui") scheduleApiFeedback(typeof options.feedback === "string" ? options.feedback : "Changes saved.");
  return response.status === 204 ? null : response.json();
}
function applyPresentation() {
  if (!operatorPreferences) return;
  previewAccent(operatorPreferences.theme.accent);
  const auto = operatorPreferences.sidebar.auto_hide;
  el("sidebarAuto").checked = auto;
  document.body.classList.toggle("sidebar-auto", auto);
  document.body.classList.toggle("sidebar-fixed", !auto);
  const scopes = {navigation: [".nav", "data-view"], dashboard: [".dashboard-metrics", "data-metric-id"], settings: [".settings-grid", "data-setting-id"]};
  for (const [scope, [parent, attribute]] of Object.entries(scopes)) {
    const container = document.querySelector(parent);
    for (const id of operatorPreferences.layout[scope] || []) {
      const item = container.querySelector(`[${attribute}="${CSS.escape(id)}"]`);
      if (item) container.appendChild(item);
    }
  }
  updateNavNumbers();
}
function updateNavNumbers() {
  document.querySelectorAll(".nav [data-view] small").forEach((node, index) => node.textContent = String(index + 1).padStart(2, "0"));
}
function savePresentation(change) {
  presentationSave = presentationSave.catch(() => {}).then(async () => {
    try {
      operatorPreferences = await api("/v1/settings/preferences", {method: "PATCH", feedback: false, body: JSON.stringify({...change, expected_revision: operatorPreferences.revision})});
      applyPresentation();
    } catch (error) {
      operatorPreferences = await api("/v1/settings/preferences").catch(() => operatorPreferences);
      applyPresentation();
      notify(error.message, "error");
      throw error;
    }
  });
  return presentationSave;
}
function previewAccent(value) {
  el("accentHex").value = value.toUpperCase();
  if (!/^#[0-9a-f]{6}$/i.test(value)) return;
  el("colorAccent").value = value;
  document.documentElement.style.setProperty("--accent", value);
  if (graphState.canvas) { syncCorrelationControls(); drawCorrelationGraph(); }
}
async function applyTheme() {
  await savePresentation({theme: {accent: el("accentHex").value}});
  notify("Accent saved.", "success");
}
function persistOrder(scope, order) { savePresentation({layout: {[scope]: order}}).then(() => notify("Order saved.", "success")).catch(() => {}); }
async function changePassword() {
  const result = await api("/v1/settings/access-key", {method: "POST", body: JSON.stringify({
    current_key: readOpaqueKey(el("currentPassword")), new_key: readOpaqueKey(el("newPassword")), confirm_key: readOpaqueKey(el("confirmPassword"))
  })});
  csrfValue = result.csrf_token;
  closePasswordModal();
  notify("Access Key changed. Other sessions have been revoked.", "success");
}
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob), link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
async function createBackup() {
  const response = await operatorResponse("/v1/backups", {method: "POST"});
  downloadBlob(await response.blob(), "perimetr-full-backup.zip");
  notify("Backup download started. Keep the recovery secret separately.", "success");
}
async function importBackup() {
  const file = el("backupImportFile").files?.[0];
  if (!file) throw new Error("Select a backup ZIP first.");
  const summary = await api("/v1/backups/preflight", {method: "POST", body: file, headers: {"Content-Type": "application/zip"}});
  recoveryReview = {file, summary};
  const count = Object.values(summary.members).reduce((n, entry) => n + entry.rows, 0);
  el("restoreSummary").textContent = `Version ${summary.version} · ${count} records · ${summary.created_at}. ${summary.warnings.join(" ")}`;
  el("confirmRestore").hidden = false;
}
async function confirmRestore() {
  if (!recoveryReview || recoveryReview.file !== el("backupImportFile").files?.[0]) throw new Error("Check the selected archive first.");
  await api("/v1/backups/import", {method: "POST", body: recoveryReview.file, headers: {
    "Content-Type": "application/zip", "X-Backup-Sha256": recoveryReview.summary.sha256, "X-Confirm-Replace": "true"
  }});
  location.assign("/");
}
function renderUpdaterRuntime() {
  const runtime = state.updaterRuntime;
  el("updaterAvailability").textContent = runtime?.available ? `Updater ${runtime.version || "unknown"} · ${runtime.compatible ? "ready" : "protocol upgrade required"}` : "Updater is unreachable. Check its host service before installation.";
}
function revealUpdates() {
  resetModalPosition("updateInstallModalBackdrop");
  el("updateInstallModalBackdrop").classList.add("open");
  el("updateInstallModalBackdrop").setAttribute("aria-hidden", "false");
}
function closeUpdateInstallModal() {
  if (el("updateWarningBackdrop")?.classList.contains("open")) cancelUpdatePreparation();
  el("updateInstallModalBackdrop").classList.remove("open");
  el("updateInstallModalBackdrop").setAttribute("aria-hidden", "true");
  // Closing the view never cancels an accepted host operation.
}
async function checkForUpdates(open = true) {
  if (open) revealUpdates();
  if (updateState.checking) return;
  updateState.checking = true;
  el("discoveryText").textContent = "Checking for updates…";
  el("updateRegistry").textContent = "Checking…";
  el("checkUpdatesAgain").disabled = true;
  el("installUpdate").hidden = true;
  el("installHelperUpdate").hidden = true;
  try {
    const results = await Promise.allSettled([api("/v1/updater/check", {method: "POST"}), api("/v1/updater/check?component=updater", {method: "POST"}), api("/v1/updater/status")]);
    const [appResult, helperResult, runtimeResult] = results;
    if (runtimeResult.status === "fulfilled") state.updaterRuntime = runtimeResult.value;
    renderUpdaterRuntime();
    updateState.candidate = appResult.status === "fulfilled" ? appResult.value : null;
    updateState.helper = helperResult.status === "fulfilled" ? helperResult.value : null;
    const candidate = updateState.candidate;
    el("updateInstalled").textContent = candidate?.installed_version || state.runtime?.version || "Unknown";
    el("updateHelper").textContent = state.updaterRuntime?.available ? `${state.updaterRuntime.version} · ${updateState.helper?.update_available ? `available ${updateState.helper.available_version}` : helperResult.status === "fulfilled" ? "current" : "discovery unavailable"}` : "Unreachable";
    el("updateRegistry").textContent = candidate ? candidate.registry || "Checked" : "Unavailable";
    if (!candidate) throw appResult.reason;
    el("discoveryText").textContent = candidate.update_available ? `Perimetr ${candidate.available_version} is available. The helper verifies the signed artifact and health during installation.` : "No newer stable Perimetr release is available.";
    const link = el("releaseNotes");
    const safeRelease = /^https:\/\/github\.com\/[^/]+\/[^/]+\/releases\//.test(candidate.release_url || "");
    link.hidden = !safeRelease;
    if (safeRelease) link.href = candidate.release_url;
    const active = updateState.job && !terminalJob(updateState.job);
    el("installUpdate").hidden = !candidate.update_available || active;
    el("installUpdate").disabled = !state.updaterRuntime?.compatible;
    el("installHelperUpdate").hidden = !updateState.helper?.update_available || active;
  } catch (error) {
    el("discoveryText").textContent = error?.message || "Discovery is unavailable. Check the Kernel connection and Updater.";
  } finally {
    updateState.checking = false;
    el("checkUpdatesAgain").disabled = false;
  }
}
function openUpdateInstallModal() {
  revealUpdates();
  if (!updateState.candidate?.update_available) return;
  updateState.saved = false; updateState.blob = null; updateState.receipt = "";
  updateState.request = {request_id: crypto.randomUUID(), version: updateState.candidate.available_version, component: "perimetr"};
  el("updateWarning").hidden = false;
  resetModalPosition("updateWarningBackdrop");
  el("updateWarningBackdrop").classList.add("open");
  el("updateWarningBackdrop").setAttribute("aria-hidden", "false");
  el("savedAcknowledgement").hidden = true;
  el("operatorSaved").checked = false;
  el("saveBackupStatus").textContent = "Save the ZIP to enable installation.";
  el("confirmInstallUpdate").hidden = false;
  el("confirmInstallUpdate").disabled = true;
  el("installUpdate").hidden = true;
}
function cancelUpdatePreparation() {
  el("updateWarningBackdrop").classList.remove("open");
  el("updateWarningBackdrop").setAttribute("aria-hidden", "true");
  el("updateWarning").hidden = true;
  updateState.blob = null; updateState.receipt = ""; updateState.saved = false;
  el("installUpdate").hidden = !updateState.candidate?.update_available;
}
async function saveUpdateBackup() {
  if (!updateState.request) return;
  let handle = null;
  // The file chooser is opened in the click gesture, before any network await.
  if (window.showSaveFilePicker) {
    try { handle = await showSaveFilePicker({suggestedName: `perimetr-before-${updateState.request.version}.zip`, types: [{description: "ZIP backup", accept: {"application/zip": [".zip"]}}]}); }
    catch (error) { if (error.name === "AbortError") return; throw error; }
  }
  el("saveUpdateBackup").disabled = true;
  el("saveBackupStatus").textContent = "Preparing the full snapshot…";
  try {
    const response = await operatorResponse("/v1/updater/prepare", {method: "POST", body: JSON.stringify(updateState.request)});
    updateState.blob = await response.blob();
    updateState.receipt = response.headers.get("X-Backup-Receipt");
    updateState.filename = response.headers.get("X-Backup-Filename");
    if (handle) {
      const writable = await handle.createWritable();
      await writable.write(updateState.blob);
      await writable.close();
      updateState.saved = true;
      el("saveBackupStatus").textContent = "Backup saved. Keep it for recovery.";
    } else {
      downloadBlob(updateState.blob, updateState.filename);
      el("savedAcknowledgement").hidden = false;
      el("saveBackupStatus").textContent = "Wait for the download, verify it is saved, then tick the confirmation.";
    }
    el("confirmInstallUpdate").disabled = !updateState.saved;
  } catch (error) {
    updateState.saved = false; updateState.blob = null;
    el("saveBackupStatus").textContent = error.message;
  } finally { el("saveUpdateBackup").disabled = false; }
}
function retainUpdateRequest() { localStorage.setItem("perimetr.updateOperation", JSON.stringify(updateState.request)); }
async function lookupUpdate() {
  if (!updateState.request) return null;
  const result = await api(`/v1/updater/jobs?request_id=${encodeURIComponent(updateState.request.request_id)}`);
  return result.jobs?.find(job => job.request_id === updateState.request.request_id) || null;
}
async function installUpdate() {
  if (!updateState.saved || !updateState.blob || !updateState.request) return;
  retainUpdateRequest(); // Persist identity before sending. No archive or secret is stored.
  el("confirmInstallUpdate").disabled = true;
  try {
    const existing = await lookupUpdate();
    const job = existing || await api(`/v1/updater/install?request_id=${encodeURIComponent(updateState.request.request_id)}&version=${encodeURIComponent(updateState.request.version)}`, {
      method: "POST", body: updateState.blob, headers: {"Content-Type": "application/zip", "X-Backup-Receipt": updateState.receipt, "X-Operator-Saved": "true"}
    });
    updateState.blob = null; updateState.receipt = "";
    el("updateWarning").hidden = true;
    el("updateWarningBackdrop").classList.remove("open");
    el("updateWarningBackdrop").setAttribute("aria-hidden", "true");
    renderUpdateJob(job); pollUpdate();
  } catch (error) {
    el("updateJobMessage").textContent = `${error.message} Reconnect to check whether the request was accepted.`;
    el("reconnectUpdate").hidden = false;
  }
}
function terminalJob(job) { return ["COMPLETED", "SUCCEEDED", "FAILED", "ROLLED_BACK", "ROLLBACK_FAILED", "INTERRUPTED", "CANCELLED"].includes(job.state); }
function renderUpdateJob(job) {
  updateState.job = job;
  updateState.request = {...updateState.request, request_id: job.request_id, job_id: job.id, version: job.version};
  retainUpdateRequest();
  el("updateJobMessage").textContent = `${job.state}: ${job.message || job.progress?.label || "Working…"}`;
  const progress = el("updateProgress"), measured = job.progress?.mode === "determinate" && Number.isFinite(job.progress?.completed) && Number.isFinite(job.progress?.total) && job.progress.total > 0;
  progress.hidden = false;
  progress.classList.toggle("measured", measured);
  if (measured) { const percent = Math.max(0, Math.min(100, job.progress.completed * 100 / job.progress.total)); progress.setAttribute("aria-valuenow", percent); progress.firstElementChild.style.width = `${percent}%`; }
  else { progress.removeAttribute("aria-valuenow"); progress.firstElementChild.style.width = "35%"; }
  const terminal = terminalJob(job);
  if (terminal) { progress.hidden = true; el("confirmInstallUpdate").hidden = true; }
  const rollback = terminal && job.rollback_available;
  el("rollbackLabel").hidden = !rollback; el("rollbackUpdate").hidden = !rollback;
  el("reconnectUpdate").hidden = true;
}
async function pollUpdate() {
  clearTimeout(updateState.timer);
  try {
    const job = updateState.request?.job_id ? await api(`/v1/updater/jobs/${encodeURIComponent(updateState.request.job_id)}`) : await lookupUpdate();
    if (!job) { el("updateJobMessage").textContent = "No accepted job found. Prepare and save a fresh backup before a new request."; el("reconnectUpdate").hidden = false; return; }
    renderUpdateJob(job); updateState.delay = 1500;
    if (terminalJob(job)) {
      state.runtime = await api("/v1/settings/runtime");
      // Fresh runtime and helper discovery confirm the installed version.
      await checkForUpdates(false);
      return;
    }
  } catch (error) {
    updateState.delay = Math.min(updateState.delay * 2, 30000);
    el("updateJobMessage").textContent = "Connection interrupted. Reconnecting to the same operation…";
    el("reconnectUpdate").hidden = false;
  }
  updateState.timer = setTimeout(pollUpdate, updateState.delay);
}
async function installHelperUpdate() {
  if (!updateState.helper?.update_available) return;
  updateState.request = {request_id: crypto.randomUUID(), version: updateState.helper.available_version, component: "updater"};
  retainUpdateRequest();
  const job = await api("/v1/updater/component", {method: "POST", body: JSON.stringify(updateState.request)});
  renderUpdateJob(job); pollUpdate();
}
async function rollbackUpdate() {
  const file = el("rollbackFile").files?.[0];
  if (!file || !updateState.job) throw new Error("Select the original recovery ZIP.");
  const job = await api(`/v1/updater/jobs/${encodeURIComponent(updateState.job.id)}/rollback`, {method: "POST", body: file, headers: {"Content-Type": "application/zip", "X-Backup-Filename": file.name}});
  renderUpdateJob(job); pollUpdate();
}
async function loadLogPage(older = false) {
  const root = el("loggerStream"), anchor = root.querySelector("[data-log-id]");
  const oldTop = anchor?.getBoundingClientRect().top, anchorId = anchor?.dataset.logId;
  const cursor = older ? logCursors.older : logCursors.live;
  const result = await api(`/v1/logs/audit?limit=200${cursor ? `&${older ? "before" : "after"}=${encodeURIComponent(cursor)}` : ""}`);
  const merged = [...(older ? state.logs : result.entries), ...(older ? result.entries : state.logs)];
  state.logs = [...new Map(merged.map(event => [event.id, event])).values()].slice(older ? -1000 : 0, older ? undefined : 1000);
  if (older) logCursors.older = result.older_cursor; else logCursors.live = result.live_cursor;
  renderLogger();
  const restored = anchorId && root.querySelector(`[data-log-id="${CSS.escape(anchorId)}"]`);
  if (restored && oldTop !== undefined && root.scrollTop > 0) root.scrollTop += restored.getBoundingClientRect().top - oldTop;
  el("olderLogs").disabled = older && !result.has_more;
}

function enhanceSearch() {
  const icon = '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" aria-hidden="true"><circle cx="8" cy="8" r="5.5"/><path d="m12 12 5 5"/></svg>';
  document.querySelectorAll('input[type="search"],#documentationSearch').forEach(input => {
    let wrapper = input.closest(".library-search");
    if (!wrapper) { wrapper = document.createElement("label"); wrapper.className = "search-control"; input.before(wrapper); wrapper.append(input); }
    wrapper.querySelector("span")?.remove();
    wrapper.insertAdjacentHTML("afterbegin", icon);
    const clear = document.createElement("button"); clear.type = "button"; clear.className = "search-clear empty"; clear.textContent = "×"; clear.setAttribute("aria-label", "Clear search"); wrapper.append(clear);
    input.addEventListener("input", () => clear.classList.toggle("empty", !input.value));
    clear.addEventListener("click", () => { input.value = ""; input.dispatchEvent(new Event("input", {bubbles: true})); input.focus(); if (input.id === "documentationSearch") document.querySelector(".documentation-content").scrollTop = 0; });
  });
  const content = document.querySelector(".documentation-content");
  document.querySelectorAll(".documentation-nav a").forEach(link => link.addEventListener("click", event => {
    event.preventDefault(); const article = document.querySelector(link.getAttribute("href"));
    if (article) content.scrollTo({top: article.offsetTop - content.offsetTop - 30, behavior: "instant"});
  }));
  content.addEventListener("scroll", () => {
    const threshold = content.getBoundingClientRect().top + 31;
    const articles = [...content.querySelectorAll("article:not([hidden])")];
    const active = articles.filter(article => article.getBoundingClientRect().top <= threshold).at(-1) || articles[0];
    document.querySelectorAll(".documentation-nav a").forEach(link => link.classList.toggle("active", link.hash === `#${active?.id}`));
  });
}
function enhanceOrdering() {
  const cards = document.querySelectorAll(".settings-card");
  cards.forEach((card, index) => card.dataset.settingId = ["appearance", "security", "backup", "updates", "logs"][index]);
  const scopes = [["settings", ".settings-card", "settingId"], ["dashboard", ".metric", "metricId"], ["navigation", ".nav>button", "view"]];
  for (const [scope, selector, key] of scopes) {
    for (const item of document.querySelectorAll(selector)) {
      item.tabIndex = 0;
      item.setAttribute("aria-description", "Hold Alt and press Up or Down to reorder");
      if (scope === "settings") {
        const handle = document.createElement("button"); handle.className = "order-handle"; handle.textContent = "⠿"; handle.draggable = true; handle.setAttribute("aria-label", `Reorder ${item.dataset[key]}`); item.append(handle);
        handle.addEventListener("dragstart", event => event.dataTransfer.setData("text/perimetr-setting", item.dataset[key]));
        item.addEventListener("dragover", event => event.preventDefault());
        item.addEventListener("drop", event => { const id = event.dataTransfer.getData("text/perimetr-setting"); const source = document.querySelector(`[data-setting-id="${CSS.escape(id)}"]`); if (!source || source === item) return; event.preventDefault(); item.before(source); persistOrder(scope, [...item.parentElement.children].map(node => node.dataset[key])); });
      }
      item.addEventListener("keydown", event => {
        if (!event.altKey || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
        event.preventDefault();
        const sibling = event.key === "ArrowUp" ? item.previousElementSibling : item.nextElementSibling;
        if (!sibling) return;
        if (event.key === "ArrowUp") sibling.before(item); else sibling.after(item);
        item.focus(); persistOrder(scope, [...item.parentElement.children].map(node => node.dataset[key]));
      });
    }
  }
}
function enhanceDialogs() {
  document.addEventListener("keydown", event => {
    const opened = [...document.querySelectorAll(".modal-backdrop.open")].at(-1);
    if (!opened) return;
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); closeBackdrop(opened); }
    if (event.key === "Tab" && !opened.contains(document.activeElement)) {
      event.preventDefault(); opened.querySelector('button:not(:disabled),input:not(:disabled)')?.focus();
    }
  }, true);
  const returnFocus = new WeakMap();
  document.querySelectorAll(".modal-backdrop").forEach(backdrop => {
    let wasOpen = false;
    new MutationObserver(() => {
      const open = backdrop.classList.contains("open"); if (open === wasOpen) return; wasOpen = open;
      if (open) { returnFocus.set(backdrop, document.activeElement); backdrop.querySelector('input:not([type=hidden]),button,[tabindex="0"]')?.focus(); }
      else { backdrop.querySelectorAll('input[type=password]').forEach(clearOpaqueKey); returnFocus.get(backdrop)?.focus(); }
    }).observe(backdrop, {attributes: true, attributeFilter: ["class"]});
    backdrop.addEventListener("keydown", event => {
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); closeBackdrop(backdrop); return; }
      if (event.key !== "Tab") return;
      const nodes = [...backdrop.querySelectorAll('button:not(:disabled),input:not(:disabled),select,a[href],[tabindex="0"]')].filter(node => node.getClientRects().length);
      if (!nodes.length) return;
      if (event.shiftKey && document.activeElement === nodes[0]) { event.preventDefault(); nodes.at(-1).focus(); }
      if (!event.shiftKey && document.activeElement === nodes.at(-1)) { event.preventDefault(); nodes[0].focus(); }
    });
  });
}

el("colorAccent").addEventListener("input", event => previewAccent(event.target.value));
el("accentHex").addEventListener("input", event => previewAccent(event.target.value));
el("sidebarAuto").addEventListener("change", event => savePresentation({sidebar: {auto_hide: event.target.checked}}).catch(() => {}));
el("operatorSaved").addEventListener("change", event => { updateState.saved = Boolean(updateState.blob && event.target.checked); el("confirmInstallUpdate").disabled = !updateState.saved; });
el("backupImportFile").addEventListener("change", () => { recoveryReview = null; el("confirmRestore").hidden = true; el("restoreSummary").textContent = ""; });
const operatorActions = {cancelUpdatePreparation, toggleSidebar: () => { const open = document.body.classList.toggle("mobile-nav-open"); el("toggleSidebar").setAttribute("aria-expanded", String(open)); }, signOut: async () => { await api("/v1/auth/logout", {method: "POST"}); location.assign("/"); }, confirmRestore, saveUpdateBackup, checkUpdatesAgain: checkForUpdates, installHelperUpdate, reconnectUpdate: pollUpdate, rollbackUpdate, olderLogs: () => loadLogPage(true),
  saveKernelOrigin: async () => { await api("/v1/settings/kernel", {method: "PATCH", body: JSON.stringify({url: el("kernelOrigin").value})}); await refreshKernel(); },
  checkKernel: async () => { el("kernelStatus").textContent = "Checking authenticated connection…"; try { await api("/v1/settings/kernel/check", {method: "POST"}); el("kernelStatus").textContent = "Kernel is reachable and authenticated."; } catch (error) { el("kernelStatus").textContent = error.message; } },
  openKernelToken: () => { el("kernelCurrentKey").value = ""; el("kernelNewToken").value = ""; el("kernelTokenBackdrop").classList.add("open"); el("kernelTokenBackdrop").setAttribute("aria-hidden", "false"); }, closeKernelToken, rotateKernelToken};
document.addEventListener("click", async event => {
  const button = event.target.closest("button"), action = operatorActions[button?.id]; if (!action) return;
  button.disabled = true;
  try { await action(); } catch (error) { notify(error.message, "error"); } finally { button.disabled = false; }
});
async function initializeOperator() {
  ["currentPassword", "newPassword", "confirmPassword", "kernelCurrentKey"].forEach(id => bindOpaqueKey(el(id)));
  const warningBackdrop = document.createElement("div");
  warningBackdrop.id = "updateWarningBackdrop"; warningBackdrop.className = "modal-backdrop top"; warningBackdrop.setAttribute("aria-hidden", "true");
  document.body.append(warningBackdrop);
  const warning = el("updateWarning"); warning.classList.add("settings-modal"); warning.setAttribute("role", "alertdialog"); warning.setAttribute("aria-modal", "true"); warning.setAttribute("aria-label", "Save your recovery copy");
  warningBackdrop.append(warning);
  const footer = document.createElement("div"); footer.className = "actions"; footer.innerHTML = '<button id="cancelUpdatePreparation">Cancel</button>'; footer.append(el("confirmInstallUpdate")); warning.append(footer);
  const menu = document.createElement("button"); menu.id = "toggleSidebar"; menu.textContent = "☰"; menu.setAttribute("aria-label", "Toggle navigation"); menu.setAttribute("aria-expanded", "false"); menu.setAttribute("aria-controls", "perimetrSidebar"); document.querySelector(".sidebar").id = "perimetrSidebar"; document.querySelector(".top").prepend(menu);
  document.querySelectorAll("button[data-view]").forEach(button => button.addEventListener("click", () => { document.body.classList.remove("mobile-nav-open"); menu.setAttribute("aria-expanded", "false"); if (innerWidth <= 760) { button.blur(); el(button.dataset.view).scrollTop = 0; } }));
  enhanceSearch(); enhanceOrdering(); enhanceDialogs();
  const session = await api("/v1/auth/session"); csrfValue = session.csrf_token;
  operatorPreferences = await api("/v1/settings/preferences");
  // Only presentation is eligible for a one-time legacy local migration.
  if (!operatorPreferences.presentation_initialized) {
    const legacy = {presentation_initialized: true};
    try { const theme = JSON.parse(localStorage.getItem("perimetr.theme") || "null"); if (theme?.accent) legacy.theme = {accent: theme.accent}; } catch (_) {}
    try { const auto = JSON.parse(localStorage.getItem("perimetr.sidebarAuto") || "null"); if (typeof auto === "boolean") legacy.sidebar = {auto_hide: auto}; } catch (_) {}
    legacy.layout = {};
    for (const [scope, key, selector, attribute] of [["navigation", "perimetr.navOrder", ".nav>button", "view"], ["dashboard", "perimetr.metricOrder", ".metric", "metricId"]]) {
      try { const order = JSON.parse(localStorage.getItem(key) || "null"), allowed = [...document.querySelectorAll(selector)].map(node => node.dataset[attribute]); if (Array.isArray(order)) legacy.layout[scope] = [...new Set(order.filter(id => allowed.includes(id)))]; } catch (_) {}
    }
    await savePresentation(legacy).catch(() => {});
  }
  if (operatorPreferences.presentation_initialized) for (const key of ["perimetr.theme", "perimetr.sidebarAuto", "perimetr.navOrder", "perimetr.metricOrder"]) localStorage.removeItem(key);
  applyPresentation();
  await refresh();
  await refreshKernel();
  try { updateState.request = JSON.parse(localStorage.getItem("perimetr.updateOperation") || "null"); } catch (_) {}
  if (updateState.request) pollUpdate();
  setInterval(() => { if (!document.hidden) api("/v1/system/metrics").then(metrics => {state.metrics = metrics; renderMetrics();}).catch(() => {}); }, 2000);
  setInterval(() => { if (!document.hidden) { refreshPendingApprovals().catch(() => {}); if (el("settings").classList.contains("active")) loadLogPage().catch(() => {}); } }, 3000);
}
initializeOperator().catch(error => notify(error.message, "error"));
