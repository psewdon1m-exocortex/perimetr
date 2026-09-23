/* Shared operator contract. Domain interactions remain in core.js. */
let operatorPreferences = null;
let csrfValue = "";
let logCursors = {older: null, live: null};
let presentationSave = Promise.resolve();
const presentationDefaults = {};
let recoveryReview = null;
const updateState = {candidate: null, helper: null, saved: false, blob: null, receipt: "", filename: "", request: null, job: null, timer: null, delay: 1500, checking: false};

async function refreshKernel() {
  const config = await api("/v1/settings/kernel");
  el("kernelOrigin").value = config.url;
  el("kernelOrigin").dataset.confirmed = config.url;
  el("kernelStatus").textContent = config.register_stale ? "Last known configuration" : config.token_configured ? "Checking reachability…" : "Not configured";
  el("kernelReachability").dataset.status = "unknown";
  el("kernelDetail").textContent = config.helper_sync_required ? "Synchronize the host Updater after this connection change; see Documentation." : "";
  if (config.token_configured && !config.register_stale) {
    try { await api("/v1/settings/kernel/check", {method: "POST", feedback: false}); el("kernelStatus").textContent = "Service reachable"; el("kernelReachability").dataset.status = "healthy"; }
    catch (_) { el("kernelStatus").textContent = "Service unavailable"; el("kernelReachability").dataset.status = "failed"; }
  }
}
async function commitKernelOrigin() {
  const field = el("kernelOrigin");
  if (field.disabled || field.value === field.dataset.confirmed) return;
  field.disabled = true; el("kernelStatus").textContent = "Validating connection…";
  try { await api("/v1/settings/kernel", {method: "PATCH", body: JSON.stringify({url: field.value})}); await refreshKernel(); }
  catch (error) { field.value = field.dataset.confirmed || ""; el("kernelStatus").textContent = "Previous connection retained"; el("kernelDetail").textContent = error.message; notify(error.message, "error"); }
  finally { field.disabled = false; }
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
    const ordered = [...new Set([...(operatorPreferences.layout[scope] || []), ...(presentationDefaults[scope] || [])])];
    for (const id of ordered) {
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
  if (!/^#[0-9a-f]{6}$/i.test(value)) { el("accentHex").setCustomValidity("Use a complete six-digit hex color, for example #00A8FF."); return; }
  const rgb = value.slice(1).match(/../g).map(channel => { const c = parseInt(channel, 16) / 255; return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; });
  if ((rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722 + .05) / .05 < 4.5) { el("accentHex").setCustomValidity("Choose a brighter accent with at least 4.5:1 contrast against black."); return; }
  el("accentHex").setCustomValidity("");
  el("accentHex").value = value.toUpperCase();
  el("colorAccent").value = value;
  document.documentElement.style.setProperty("--accent", value);
  if (graphState.canvas) { syncCorrelationControls(); drawCorrelationGraph(); }
}
async function applyTheme() {
  if (!el("accentHex").reportValidity()) return;
  await savePresentation({theme: {accent: el("accentHex").value}});
  notify("Accent saved.", "success");
}
function persistOrder(scope, order) { updateNavNumbers(); savePresentation({layout: {[scope]: order}}).then(() => notify("Order saved.", "success")).catch(() => {}); }
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
  el("updaterAvailability").textContent = runtime?.available ? runtime.compatible ? "Service reachable" : "Protocol upgrade required" : "Service unavailable";
  el("updaterStatusRow").dataset.status = runtime?.available && runtime.compatible ? "healthy" : "failed";
  el("installedAppVersion").textContent = state.runtime?.version || "Unknown";
  el("installedHelperVersion").textContent = runtime?.version || "Unavailable";
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
async function checkForUpdates(open = true, component = updateState.component || "perimetr") {
  updateState.component = component;
  el("updateInstallModalTitle").textContent = component === "updater" ? "Updater updates" : "Updates";
  if (open) revealUpdates();
  if (updateState.job && !terminalJob(updateState.job)) { renderUpdateJob(updateState.job); return; }
  if (updateState.checking) return;
  updateState.checking = true;
  el("discoveryText").textContent = "Checking for updates…";
  el("discoveryDetail").textContent = "";
  el("releaseNotes").hidden = true;
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
    const candidate = component === "updater" ? updateState.helper : updateState.candidate;
    el("updateInstalled").textContent = candidate?.installed_version || (component === "updater" ? state.updaterRuntime?.version : state.runtime?.version) || "Unknown";
    el("updateHelper").textContent = state.updaterRuntime?.available ? `${state.updaterRuntime.version} · ${updateState.helper?.update_available ? `available ${updateState.helper.available_version}` : helperResult.status === "fulfilled" ? "current" : "discovery unavailable"}` : "Unreachable";
    el("updateRegistry").textContent = candidate ? candidate.registry || "Checked" : "Unavailable";
    el("registryAvailability").textContent = candidate ? "Verified release discovery" : "Discovery unavailable";
    el("registryStatusRow").dataset.status = candidate ? "healthy" : "failed";
    if (!candidate) throw (component === "updater" ? helperResult : appResult).reason;
    const name = component === "updater" ? "Updater" : "Perimetr";
    el("discoveryText").textContent = candidate.update_available ? `${name} ${candidate.available_version} is available.` : `No newer stable ${name} release is available.`;
    el("discoveryDetail").textContent = "Release identity and version are checked here. Signed artifacts and service health are verified by the local update helper during installation.";
    const link = el("releaseNotes");
    const safeRelease = /^https:\/\/github\.com\/[^/]+\/[^/]+\/releases\//.test(candidate.release_url || "");
    link.hidden = !safeRelease;
    if (safeRelease) link.href = candidate.release_url;
    const active = updateState.job && !terminalJob(updateState.job);
    el("installUpdate").hidden = component !== "perimetr" || !candidate.update_available || active;
    el("installUpdate").textContent = `Install ${candidate.available_version || "update"}`;
    el("installUpdate").disabled = !state.updaterRuntime?.compatible;
    el("installHelperUpdate").hidden = component !== "updater" || !candidate.update_available || active;
    el("installHelperUpdate").textContent = `Install Updater ${candidate.available_version || "update"}`;
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
  el("updateTargetQuestion").textContent = `Install Perimetr ${updateState.candidate.available_version}?`;
  el("confirmInstallUpdate").textContent = `Install ${updateState.candidate.available_version}`;
  el("confirmInstallUpdate").classList.add("danger");
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
  el("updateJobPanel").hidden = false;
  el("updateJobId").textContent = job.id || "Accepted";
  el("updateJobState").textContent = job.state;
  el("updateJobState").style.color = ["COMPLETED", "SUCCEEDED"].includes(job.state) ? "var(--success)" : terminalJob(job) ? "var(--danger)" : "var(--white)";
  el("checkUpdatesAgain").disabled = !terminalJob(job);
  el("installUpdate").hidden = true;
  el("installHelperUpdate").hidden = true;
  updateState.job = job;
  updateState.request = {...updateState.request, request_id: job.request_id, job_id: job.id, version: job.version};
  retainUpdateRequest();
  el("updateJobMessage").textContent = `${job.state}: ${job.message || job.progress?.label || "Working…"}`;
  const progress = el("updateProgress"), measured = job.progress?.mode === "determinate" && Number.isFinite(job.progress?.completed) && Number.isFinite(job.progress?.total) && job.progress.total > 0;
  progress.hidden = false;
  progress.classList.toggle("measured", measured);
  if (measured) { const percent = Math.max(0, Math.min(100, job.progress.completed * 100 / job.progress.total)); progress.setAttribute("aria-valuenow", percent); progress.firstElementChild.style.width = `${percent}%`; }
  else { progress.removeAttribute("aria-valuenow"); progress.firstElementChild.style.width = "35%"; }
  el("updateProgressLabel").textContent = measured ? `${job.progress.completed} / ${job.progress.total}${job.progress.unit ? " " + job.progress.unit : ""}` : job.progress?.label || "Operation in progress";
  progress.setAttribute("aria-valuetext", el("updateProgressLabel").textContent);
  const terminal = terminalJob(job);
  el("updateProgressLabel").hidden = terminal;
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

function syncDocumentationCurrent() {
  const content = document.querySelector(".documentation-content");
  const articles = [...content.querySelectorAll("article:not([hidden])")];
  const threshold = content.getBoundingClientRect().top + 31;
  const atEnd = content.scrollHeight > content.clientHeight && content.scrollTop + content.clientHeight >= content.scrollHeight - 2;
  const active = atEnd ? articles.at(-1) : articles.filter(article => article.getBoundingClientRect().top <= threshold).at(-1) || articles[0];
  document.querySelectorAll(".documentation-nav a").forEach(link => {
    const current = link.hash === `#${active?.id}` && !link.hidden;
    link.classList.toggle("active", current);
    if (current) link.setAttribute("aria-current", "location"); else link.removeAttribute("aria-current");
  });
}
const crossIcon = '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m5 5 10 10M15 5 5 15"/></svg>';
function enhanceSearch() {
  const icon = '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" aria-hidden="true"><circle cx="8" cy="8" r="5.5"/><path d="m12 12 5 5"/></svg>';
  document.querySelectorAll('input[type="search"],#documentationSearch').forEach(input => {
    let wrapper = input.closest(".library-search");
    if (!wrapper) { wrapper = document.createElement("div"); wrapper.className = "search-control"; input.before(wrapper); wrapper.append(input); }
    wrapper.querySelector("span")?.remove(); wrapper.insertAdjacentHTML("afterbegin", icon);
    const clear = document.createElement("button"); clear.type = "button"; clear.className = "search-clear empty"; clear.innerHTML = crossIcon; clear.setAttribute("aria-label", "Clear search"); wrapper.append(clear);
    const update = () => { const empty = !input.value; clear.classList.toggle("empty", empty); clear.disabled = empty; clear.tabIndex = empty ? -1 : 0; clear.setAttribute("aria-hidden", String(empty)); };
    const reset = () => { input.value = ""; input.dispatchEvent(new Event("input", {bubbles: true})); requestAnimationFrame(() => input.focus()); };
    input.addEventListener("input", update); clear.addEventListener("click", reset); update();
    input.addEventListener("keydown", event => { if (event.key === "Escape" && input.value) { event.preventDefault(); event.stopPropagation(); reset(); } });
  });
  const content = document.querySelector(".documentation-content"), nav = document.querySelector(".documentation-nav");
  content.tabIndex = 0; content.setAttribute("role", "region"); content.setAttribute("aria-label", "Operator guide articles"); nav.setAttribute("aria-label", "Documentation navigation");
  document.querySelectorAll(".documentation-nav a").forEach(link => link.addEventListener("click", event => {
    event.preventDefault(); const article = document.querySelector(link.hash);
    if (article) content.scrollTo({top: content.scrollTop + article.getBoundingClientRect().top - content.getBoundingClientRect().top - 30, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});
  }));
  content.addEventListener("scroll", syncDocumentationCurrent); new ResizeObserver(syncDocumentationCurrent).observe(content); syncDocumentationCurrent();
}

function enhanceOrdering() {
  document.querySelectorAll(".settings-card").forEach((card, index) => card.dataset.settingId = ["appearance", "security", "backup", "updates", "logs"][index]);
  const dots = '<svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><circle cx="4.5" cy="4.5" r="1.5"/><circle cx="10.5" cy="4.5" r="1.5"/><circle cx="4.5" cy="10.5" r="1.5"/><circle cx="10.5" cy="10.5" r="1.5"/></svg>';
  for (const [scope, selector, key] of [["settings", ".settings-card", "settingId"], ["dashboard", ".metric", "metricId"], ["navigation", ".nav>button", "view"]]) {
    const items = [...document.querySelectorAll(selector)], container = items[0].parentElement;
    presentationDefaults[scope] = items.map(node => node.dataset[key]);
    let drag = null;
    const finish = commit => {
      if (!drag) return;
      const {source, placeholder, original} = drag;
      if (commit) placeholder.before(source); else original.forEach(node => container.append(node));
      for (const property of ["position", "left", "top", "width", "height", "z-index", "pointer-events", "transform"]) source.style.removeProperty(property);
      source.classList.remove("dragging"); placeholder.remove(); drag = null;
      if (commit) persistOrder(scope, [...container.querySelectorAll(selector)].map(node => node.dataset[key]));
    };
    for (const item of items) {
      item.tabIndex = 0; item.setAttribute("aria-description", "Hold Alt and press Up or Down to reorder");
      if (scope !== "navigation") {
        item.draggable = false;
        const handle = document.createElement("button"); handle.className = "order-handle"; handle.innerHTML = dots; handle.setAttribute("aria-label", `Reorder ${item.querySelector("h2").textContent}`); item.append(handle);
        let pointer = null;
        handle.addEventListener("pointerdown", event => {
          if (event.button !== 0) return;
          pointer = {id: event.pointerId, x: event.clientX, y: event.clientY, rect: item.getBoundingClientRect()};
          handle.setPointerCapture(event.pointerId); event.stopPropagation();
        });
        handle.addEventListener("pointermove", event => {
          if (!pointer || pointer.id !== event.pointerId) return;
          if (!drag && Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y) < 6) return;
          event.preventDefault();
          if (!drag) {
            const placeholder = document.createElement("div"); placeholder.className = "card-placeholder"; placeholder.style.height = `${item.offsetHeight}px`; placeholder.style.gridColumn = getComputedStyle(item).gridColumn;
            drag = {source: item, placeholder, original: [...container.children]};
            item.before(placeholder); item.classList.add("dragging");
            Object.assign(item.style, {position:"fixed",width:`${item.offsetWidth}px`,height:`${item.offsetHeight}px`,zIndex:"135",pointerEvents:"none",transform:"none"});
          }
          item.style.left = `${pointer.rect.left + event.clientX - pointer.x}px`; item.style.top = `${pointer.rect.top + event.clientY - pointer.y}px`;
          const target = document.elementFromPoint(event.clientX, event.clientY)?.closest(selector);
          if (!target || target === item || !container.contains(target)) return;
          const rect = target.getBoundingClientRect(), sideBySide = scope === "dashboard" && rect.width < container.clientWidth * .75;
          const after = sideBySide ? event.clientX > rect.left + rect.width / 2 : event.clientY > rect.top + rect.height / 2;
          if (after) target.after(drag.placeholder); else target.before(drag.placeholder);
        });
        handle.addEventListener("pointerup", event => {
          if (!pointer || pointer.id !== event.pointerId) return;
          const bounds = container.getBoundingClientRect();
          const within = event.clientX >= bounds.left && event.clientX <= bounds.right && event.clientY >= bounds.top && event.clientY <= bounds.bottom;
          finish(within); pointer = null; handle.releasePointerCapture(event.pointerId); handle.focus();
        });
        handle.addEventListener("pointercancel", () => {finish(false); pointer = null;});
        handle.addEventListener("keydown", event => {if (event.key === "Escape" && drag) {event.preventDefault(); finish(false); pointer = null;}});
      }
      item.addEventListener("keydown", event => {
        if (!event.altKey || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
        event.preventDefault(); event.stopPropagation(); const sibling = event.key === "ArrowUp" ? item.previousElementSibling : item.nextElementSibling; if (!sibling) return;
        if (event.key === "ArrowUp") sibling.before(item); else sibling.after(item);
        item.focus(); persistOrder(scope, [...container.children].map(node => node.dataset[key]));
        notify(`${item.querySelector("h2,span")?.textContent || "Item"} moved to position ${[...container.children].indexOf(item) + 1}.`, "info");
      });
    }
  }
}

function enhanceDialogs() {
  document.addEventListener("keydown", event => {
    const opened = [...document.querySelectorAll(".modal-backdrop.open")].at(-1);
    if (!opened) return;
    if (event.key === "Escape") { if (document.activeElement?.type === "search" && document.activeElement.value) return; event.preventDefault(); event.stopPropagation(); closeBackdrop(opened); }
    if (event.key === "Tab" && !opened.contains(document.activeElement)) {
      event.preventDefault(); opened.querySelector('button:not(:disabled),input:not(:disabled)')?.focus();
    }
  }, true);
  const returnFocus = new WeakMap();
  const syncInert = () => {
    const opened = [...document.querySelectorAll(".modal-backdrop.open")], top = opened.at(-1);
    document.querySelectorAll(".app,.sidebar").forEach(node => node.inert = Boolean(top));
    opened.forEach(node => node.inert = node !== top);
    document.querySelectorAll(".modal-backdrop:not(.open)").forEach(node => node.inert = false);
  };
  document.querySelectorAll(".modal-backdrop").forEach(backdrop => {
    let wasOpen = false;
    new MutationObserver(() => {
      const open = backdrop.classList.contains("open"); if (open === wasOpen) return; wasOpen = open; syncInert();
      backdrop.dataset.dirty = "false";
      if (open) { returnFocus.set(backdrop, document.activeElement); backdrop.querySelector('input:not([type=hidden]),button,[tabindex="0"]')?.focus(); }
      else { backdrop.querySelectorAll('input[type=password]').forEach(clearOpaqueKey); returnFocus.get(backdrop)?.focus(); }
    }).observe(backdrop, {attributes: true, attributeFilter: ["class"]});
    backdrop.addEventListener("input", () => backdrop.dataset.dirty = "true");
    backdrop.addEventListener("change", () => backdrop.dataset.dirty = "true");
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
  checkHelperUpdates: () => checkForUpdates(true, "updater"),
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
  const warningBody = document.createElement("div"); warningBody.className = "warning-body";
  while (warning.firstChild) warningBody.append(warning.firstChild);
  warningBody.querySelector("h3").remove();
  warning.insertAdjacentHTML("afterbegin", '<div class="modal-head"><h2>Install Perimetr update</h2><button id="closeUpdateWarning" class="close-panel" aria-label="Close backup warning">' + crossIcon + '</button></div>');
  warningBody.insertAdjacentHTML("afterbegin", '<p id="updateTargetQuestion" class="warning-question"></p>');
  warning.append(warningBody);
  el("closeUpdateWarning").addEventListener("click", cancelUpdatePreparation);
  const footer = document.createElement("div"); footer.className = "actions"; footer.innerHTML = '<button id="cancelUpdatePreparation">Cancel</button>'; footer.append(el("confirmInstallUpdate")); warningBody.append(footer);
  const menu = document.createElement("button"); menu.id = "toggleSidebar"; menu.textContent = "☰"; menu.setAttribute("aria-label", "Toggle navigation"); menu.setAttribute("aria-expanded", "false"); menu.setAttribute("aria-controls", "perimetrSidebar"); document.querySelector(".sidebar").id = "perimetrSidebar"; document.querySelector(".top").prepend(menu);
  document.querySelectorAll("button[data-view]").forEach(button => button.addEventListener("click", () => { document.body.classList.remove("mobile-nav-open"); menu.setAttribute("aria-expanded", "false"); if (innerWidth <= 720) { button.blur(); el(button.dataset.view).scrollTop = 0; } }));
  document.querySelectorAll(".close-panel").forEach(button => button.innerHTML = crossIcon);
  el("kernelOrigin").addEventListener("blur", commitKernelOrigin);
  el("kernelOrigin").addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); commitKernelOrigin(); } });
  for (const [id, label, action, text] of [["pods", "Pods", null, null], ["properties", "Properties", "data-add-library-property", "Add Property"]]) {
    const page = document.querySelector(`#${id} .library-page`), bar = document.createElement("div"); bar.className = "collection-command-bar"; bar.setAttribute("role", "region"); bar.setAttribute("aria-label", `${label} collection controls`);
    bar.append(page.querySelector(".library-search")); bar.insertAdjacentHTML("beforeend", `<div class="collection-info">${label}<strong id="${id}Count" aria-live="polite">Loading…</strong></div>`);
    if (action) { const button = page.querySelector(`[${action}]`); button.textContent = text; bar.append(button); }
    page.prepend(bar);
  }
  const updateJob = document.createElement("section"); updateJob.id = "updateJobPanel"; updateJob.className = "update-job"; updateJob.hidden = true;
  updateJob.innerHTML = '<dl class="update-metadata"><dt>Job</dt><dd id="updateJobId"></dd><dt>State</dt><dd id="updateJobState"></dd></dl>';
  for (const id of ["updateJobMessage", "updateProgress", "reconnectUpdate", "rollbackLabel", "rollbackUpdate"]) updateJob.append(el(id));
  updateJob.querySelector("#updateProgress").insertAdjacentHTML("afterend", '<p id="updateProgressLabel" class="hint"></p>');
  document.querySelector(".updates-body").append(updateJob);
  for (const name of ["pointerover", "focusin"]) document.addEventListener(name, event => {
    const item = event.target.closest?.(".metric,.search-control,.library-search,button,input,select,textarea"); if (!item || item.classList.contains("order-handle")) return;
    applySafeHoverScale(item);
    const rect = item.getBoundingClientRect(), parent = item.closest(".dashboard-metrics,.settings-grid,.view")?.getBoundingClientRect();
    if (parent) item.style.transformOrigin = `${rect.left - parent.left < 12 ? "left" : parent.right - rect.right < 12 ? "right" : "center"} ${rect.top - parent.top < 12 ? "top" : "center"}`;
  });
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
  setInterval(() => { if (!document.hidden) { if (el("settings").classList.contains("active")) loadLogPage().catch(() => {}); } }, 3000);
}
initializeOperator().catch(error => notify(error.message, "error"));
