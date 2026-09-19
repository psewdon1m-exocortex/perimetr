
    const state = { objects: [], subjects: [], pods: [], agents: [], overviewBlocks: [], audit: [], logs: [], metrics: null, backups: [], runtime: null, neptune: null, neptuneRelease: null, updateCheck: null, updaterRuntime: null, updateJob: null, pendingUpdateVersion: "", updateInstallPending: false, correlationPercentage: 0 };
    const uiState = {
      descriptionsByBlock: {},
      propertiesByBlock: {},
      propertyLibrary: [],
      activePropertyBlock: "",
      activeDescriptionBlock: "",
      draggedPropertyIndex: null,
      editingPropertyIndex: null,
      editingLibraryPropertyId: "",
      pendingEntityDelete: null,
      draggedNavView: "",
      draggedMetricId: "",
      draggedLibraryPropertyIndex: null,
      graphSettings: {},
    };
    const DEFAULT_GRAPH_SETTINGS = {
      property_color: "",
      entity_color: "",
      node_size: 6,
      link_thickness: 1,
      text_threshold: 0.15,
      center_force: 0.006,
      repel_force: 1800,
      link_force: 0.025,
      link_distance: 150,
      animate: true,
    };
    const graphState = {
      nodes: [], links: [], canvas: null, context: null, width: 0, height: 0,
      transform: { x: 0, y: 0, k: 1 }, draggedNode: null, panning: false,
      pointerX: 0, pointerY: 0, frame: 0, initialized: false,
    };
    let correlationSyncTimer = null;
    const PERIMETR_BLOCK_ID = "5f0b6d3d90f548a9a2f1d6e9cb7f3412";
    const OVERVIEW_BLOCK_DEFAULTS = {
      human_general: { name: "I as human in general", localBlockId: "human_general" },
      turkey_global: { name: "Turkey / Global sphere", localBlockId: "turkey_global" },
      russia_sphere: { name: "Russia influence sphere", localBlockId: "russia_sphere" },
      laboratory_block: { name: "Laboratory", localBlockId: "laboratory_block", blockType: "laboratory", backendBlockId: "laboratory" },
      perimetr_block: { name: "Perimetr", localBlockId: "perimetr_block", blockType: "perimetr", backendBlockId: PERIMETR_BLOCK_ID },
    };
    const agentUiState = {
      activeBlockType: "",
      activeBlockId: "",
      activeBlockTitle: "",
      activeAgentId: "",
      activeJobId: "",
      activeApproval: null,
      pendingCapability: null,
      pendingRemoveAgentId: "",
      viewingAgent: false,
      returnContext: null,
      libraryOnly: false,
      draggedAgentIndex: null,
      draggedLibraryAgentIndex: null,
      assignments: [],
      library: [],
      capabilities: [],
      jobs: [],
      events: [],
      approvals: [],
      presentedApprovalIds: new Set(),
    };
    const subjectPodState = { subjectId: "", config: null, provisioning: [], instances: [], selected: null };
    const modalDrag = { modal: null, offsetX: 0, offsetY: 0 };
    const headers = { "Content-Type": "application/json" };
    const subjectConversionInFlight = new Set();
    let pendingApiFeedbackTimer = null;
    let subjectProxyAutosaveTimer = null;
    let subjectProxyAutosaveGeneration = 0;

    async function api(path, options = {}) {
      const { feedback = true, ...requestOptions } = options;
      const requestHeaders = { ...headers, ...(requestOptions.headers || {}) };
      if (requestOptions.body instanceof FormData) delete requestHeaders["Content-Type"];
      const response = await fetch(path, { ...requestOptions, headers: requestHeaders });
      const text = await response.text();
      let body = null;
      try { body = text ? JSON.parse(text) : null; } catch (_) { body = null; }
      if (!response.ok) throw new Error(humanizeError(body?.error?.message || body?.detail || response.statusText));
      const method = String(requestOptions.method || "GET").toUpperCase();
      if (feedback !== false && method !== "GET" && path !== "/v1/correlation") {
        const message = typeof feedback === "string" ? feedback : method === "DELETE" ? "Deleted." : ["PUT", "PATCH"].includes(method) ? "Changes saved." : "Action completed.";
        scheduleApiFeedback(message);
      }
      return body;
    }
    function el(id) { return document.getElementById(id); }
    function esc(value) { return String(value ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
    function humanizeError(value) {
      const code = String(value || "operation_failed");
      const known = {
        invalid_credentials: "Access Key is incorrect.",
        new_password_confirmation_mismatch: "Passwords do not match.",
        pod_password_confirmation_mismatch: "Passwords do not match.",
        pod_decoy_password_confirmation_required: "Enter and repeat the decoy password, or leave both fields empty.",
        pod_decoy_password_confirmation_mismatch: "Decoy passwords do not match.",
        pod_decoy_password_must_differ: "The decoy password must differ from the primary password.",

        pod_password_too_short: "Password must contain at least 8 characters.",
        current_key_invalid: "Current password is incorrect.",
        pod_login_required: "Enter a Pod login.",
        invalid_vless_connection: "Enter a valid VLESS connection.",
        entity_image_too_large: "Image is too large. Maximum size is 4 MB.",
        entity_image_must_be_png: "The image could not be converted to PNG.",
      };
      const translated = known[code] || code.replaceAll("_", " ");
      return translated.charAt(0).toUpperCase() + translated.slice(1);
    }
    function notify(message, type = "error", timeout = null) {
      if (pendingApiFeedbackTimer) { window.clearTimeout(pendingApiFeedbackTimer); pendingApiFeedbackTimer = null; }
      const root = el("notificationStack");
      if (!root) return;
      const notice = document.createElement("div");
      notice.className = `system-notice ${type}`;
      notice.setAttribute("role", type === "error" ? "alert" : "status");
      notice.innerHTML = `<span>${esc(humanizeError(message))}</span><button aria-label="Dismiss notification">X</button>`;
      notice.querySelector("button").addEventListener("click", () => notice.remove());
      root.appendChild(notice);
      while (root.children.length > 5) root.firstElementChild?.remove();
      const lifetime = timeout === null ? (type === "error" ? 8000 : 4500) : timeout;
      if (lifetime) window.setTimeout(() => notice.remove(), lifetime);
      return notice;
    }
    function scheduleApiFeedback(message) {
      if (pendingApiFeedbackTimer) window.clearTimeout(pendingApiFeedbackTimer);
      pendingApiFeedbackTimer = window.setTimeout(() => {
        pendingApiFeedbackTimer = null;
        notify(message, "success");
      }, 120);
    }
    window.alert = message => notify(message, "error");
    function fmtBytes(value) {
      if (value == null || !Number.isFinite(Number(value))) return "—";
      if (!value) return "0 B";
      const units = ["B", "KB", "MB", "GB", "TB"];
      let next = Number(value), idx = 0;
      while (next >= 1024 && idx < units.length - 1) { next /= 1024; idx += 1; }
      return `${next.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
    }
    function fmtUptime(value) {
      const total = Math.max(0, Math.floor(Number(value) || 0));
      const days = Math.floor(total / 86400);
      const hours = Math.floor((total % 86400) / 3600);
      const minutes = Math.floor((total % 3600) / 60);
      return days > 0 ? `${days}d ${hours}h ${minutes}m` : `${hours}h ${minutes}m`;
    }
    function statusClass(status) {
      const normalized = String(status || "").toLowerCase();
      return ["active", "approved", "online", "healthy"].includes(normalized) ? "ok" : ["revoked", "disabled", "expired", "offline", "unreachable", "error"].includes(normalized) ? "bad" : "";
    }
    function row(title, status, meta, actions = "") {
      return `<article class="row"><div class="row-head"><div class="title">${esc(title)}</div>${status ? `<span class="pill ${statusClass(status)}">${esc(status)}</span>` : ""}</div><div class="meta">${meta.map(x => `<span>${esc(x)}</span>`).join("")}</div>${actions ? `<div class="actions">${actions}</div>` : ""}</article>`;
    }
    function uid() {
      return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    }
    function applySafeHoverScale(target) {
      if (!(target instanceof HTMLElement)) return;
      const rect = target.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const grow = Math.min(rect.width, rect.height) * 0.05;
      target.style.setProperty("--hover-scale-x", String((rect.width + grow) / rect.width));
      target.style.setProperty("--hover-scale-y", String((rect.height + grow) / rect.height));
      if (target.classList.contains("project-card")) {
        const grid = target.closest(".project-card-grid");
        const bounds = grid?.getBoundingClientRect();
        if (bounds) {
          const horizontal = rect.left - bounds.left < grow ? "left" : bounds.right - rect.right < grow ? "right" : "center";
          const vertical = rect.top - bounds.top < grow ? "top" : bounds.bottom - rect.bottom < grow ? "bottom" : "center";
          target.style.transformOrigin = `${horizontal} ${vertical}`;
        }
      }
    }
    function modalElementFromBackdrop(backdropId) {
      return el(backdropId)?.querySelector(".property-modal, .settings-modal, .agent-modal");
    }
    function resetModalPosition(backdropId) {
      const modal = modalElementFromBackdrop(backdropId);
      if (!modal) return;
      modal.style.position = "fixed";
      modal.style.left = "50%";
      modal.style.top = "50%";
      modal.style.transform = "translate(-50%, -50%)";
    }
    function correlationPayload() {
      return {
        descriptions_by_block: uiState.descriptionsByBlock,
        properties_by_block: uiState.propertiesByBlock,
        property_library: uiState.propertyLibrary,
        graph_settings: { ...DEFAULT_GRAPH_SETTINGS, ...uiState.graphSettings },
      };
    }
    function queueCorrelationSync() {
      window.clearTimeout(correlationSyncTimer);
      correlationSyncTimer = window.setTimeout(async () => {
        try {
          const result = await api("/v1/correlation", { method: "PUT", body: JSON.stringify(correlationPayload()) });
          state.correlationPercentage = Number(result.correlation_percentage || 0);
          renderCorrelationMetric();
        } catch (_) {}
      }, 350);
    }
    function cleanupUnusedLibraryProperties() {
      const used = new Set();
      Object.values(uiState.propertiesByBlock || {}).forEach(items => {
        (items || []).forEach(item => { if (item.id) used.add(item.id); });
      });
      uiState.propertyLibrary = (uiState.propertyLibrary || []).filter(item => used.has(item.id));
    }
    function saveLocalState() { queueCorrelationSync(); }
    function recordUiAction(action, targetType = "ui", targetId = "perimetr", payload = {}, result = {}, feedback = true) {
      api("/v1/audit/ui", { method: "POST", feedback, body: JSON.stringify({
        action,
        target_type: targetType,
        target_id: targetId,
        payload,
        result,
      }) }).catch(() => {});
    }
    function objectById(id) {
      return state.objects.find(item => item.id === id);
    }
    function projectItems() {
      const objectItems = state.objects.map(item => ({
        id: item.id,
        type: "object",
        title: item.name,
        source: item,
      }));
      const subjectItems = state.subjects.map(item => ({
          id: item.id,
          type: "subject",
          title: item.name,
          source: item,
      }));
      return [...objectItems, ...subjectItems];
    }
    function overviewBlockById(blockId) {
      const defaults = OVERVIEW_BLOCK_DEFAULTS[blockId];
      if (!defaults) return null;
      const stored = (state.overviewBlocks || []).find(item => item.id === blockId) || {};
      return { id: blockId, ...defaults, ...stored };
    }
    function renderOverviewBlocks() {
      document.querySelectorAll("[data-overview-block]").forEach(tile => {
        const block = overviewBlockById(tile.dataset.overviewBlock);
        if (!block) return;
        const title = tile.querySelector("span");
        if (title) title.textContent = block.name;
        tile.classList.toggle("has-image", Boolean(block.image_url));
        tile.style.backgroundImage = block.image_url ? `url('${block.image_url}')` : "";
        tile.setAttribute("aria-label", block.name);
      });
    }
    function correlationEntities() {
      const entities = Object.keys(OVERVIEW_BLOCK_DEFAULTS).map(blockId => ({
        id: blockId,
        label: overviewBlockById(blockId)?.name || OVERVIEW_BLOCK_DEFAULTS[blockId].name,
      }));
      state.objects.forEach(item => entities.push({ id: `object_${item.id}`, label: item.name }));
      state.subjects.forEach(item => entities.push({ id: `subject_${item.id}`, label: item.name }));
      return entities;
    }
    function correlationData() {
      const entities = correlationEntities();
      const validEntities = new Set(entities.map(item => item.id));
      const properties = new Map();
      (uiState.propertyLibrary || []).forEach(item => { if (item.id) properties.set(item.id, item); });
      Object.values(uiState.propertiesByBlock || {}).forEach(items => (items || []).forEach(item => {
        if (item.id && !properties.has(item.id)) properties.set(item.id, item);
      }));
      const links = [];
      Object.entries(uiState.propertiesByBlock || {}).forEach(([blockId, items]) => {
        if (!validEntities.has(blockId)) return;
        const linked = new Set();
        (items || []).forEach(item => {
          if (!item.id || linked.has(item.id)) return;
          linked.add(item.id);
          links.push({ sourceId: `property_${item.id}`, targetId: blockId });
        });
      });
      const propertyNodes = [...properties.values()].map(item => ({
        id: `property_${item.id}`, propertyId: item.id, label: item.value || item.key || item.type || "property", type: "property",
      }));
      const entityNodes = entities.map(item => ({ ...item, type: "entity" }));
      return { nodes: [...entityNodes, ...propertyNodes], links };
    }
    function clientCorrelationPercentage() {
      const data = correlationData();
      const entityCount = data.nodes.filter(item => item.type === "entity").length;
      const properties = data.nodes.filter(item => item.type === "property");
      if (!properties.length || entityCount < 2) return 0;
      const counts = new Map(properties.map(item => [item.id, 0]));
      data.links.forEach(link => counts.set(link.sourceId, (counts.get(link.sourceId) || 0) + 1));
      const score = [...counts.values()].reduce((sum, count) => sum + Math.max(0, count - 1) / (entityCount - 1), 0) / properties.length;
      return Math.round(score * 10000) / 100;
    }
    function renderCorrelationMetric() {
      const percentage = Number.isFinite(state.correlationPercentage) ? state.correlationPercentage : clientCorrelationPercentage();
      if (el("correlationPercent")) el("correlationPercent").textContent = `${percentage.toFixed(2).replace(/\.00$/, "")}%`;
      if (el("correlationMapScore")) el("correlationMapScore").textContent = `${percentage.toFixed(2).replace(/\.00$/, "")}% correlation`;
      if (el("correlationState")) el("correlationState").textContent = percentage > 0 ? "connected" : "none";
    }
    function graphColor(name, fallbackVariable) {
      const configured = uiState.graphSettings?.[name];
      return configured || getComputedStyle(document.documentElement).getPropertyValue(fallbackVariable).trim();
    }
    function hashPosition(value, axis) {
      let hash = axis ? 2166136261 : 16777619;
      for (let index = 0; index < value.length; index += 1) hash = Math.imul(hash ^ value.charCodeAt(index), 16777619);
      return ((hash >>> 0) % 1000) / 1000;
    }
    function rebuildCorrelationGraph() {
      const previous = new Map(graphState.nodes.map(node => [node.id, node]));
      const data = correlationData();
      const visibleNodes = data.nodes.slice(0, 500);
      const visibleIds = new Set(visibleNodes.map(item => item.id));
      const visibleLinks = data.links.filter(link => visibleIds.has(link.sourceId) && visibleIds.has(link.targetId)).slice(0, 2000);
      el("graphLimitHint").textContent = data.nodes.length > 500 || data.links.length > 2000 ? `Showing ${visibleNodes.length} of ${data.nodes.length} nodes and ${visibleLinks.length} of ${data.links.length} links. Saved data and the correlation score remain complete.` : "";
      graphState.nodes = visibleNodes.map((item, index) => {
        const saved = previous.get(item.id);
        const angle = hashPosition(item.id, false) * Math.PI * 2;
        const radius = 80 + hashPosition(item.id, true) * Math.min(360, 35 * Math.sqrt(data.nodes.length + 1));
        return {
          ...item,
          x: saved?.x ?? Math.cos(angle) * radius,
          y: saved?.y ?? Math.sin(angle) * radius,
          vx: saved?.vx ?? 0,
          vy: saved?.vy ?? 0,
          fixed: false,
          degree: 0,
        };
      });
      const nodesById = new Map(graphState.nodes.map(node => [node.id, node]));
      graphState.links = visibleLinks.map(link => ({ source: nodesById.get(link.sourceId), target: nodesById.get(link.targetId) })).filter(link => link.source && link.target);
      graphState.links.forEach(link => { link.source.degree += 1; link.target.degree += 1; });
      state.correlationPercentage = clientCorrelationPercentage();
      renderCorrelationMetric();
      drawCorrelationGraph();
    }
    function resizeCorrelationCanvas() {
      const canvas = graphState.canvas;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      graphState.width = rect.width;
      graphState.height = rect.height;
      canvas.width = Math.max(1, Math.round(rect.width * ratio));
      canvas.height = Math.max(1, Math.round(rect.height * ratio));
      graphState.context.setTransform(ratio, 0, 0, ratio, 0, 0);
      drawCorrelationGraph();
    }
    function stepCorrelationGraph() {
      const settings = { ...DEFAULT_GRAPH_SETTINGS, ...uiState.graphSettings };
      const nodes = graphState.nodes;
      const repel = Number(settings.repel_force);
      for (let left = 0; left < nodes.length; left += 1) {
        const a = nodes[left];
        for (let right = left + 1; right < nodes.length; right += 1) {
          const b = nodes[right];
          let dx = b.x - a.x, dy = b.y - a.y;
          const distanceSquared = Math.max(64, dx * dx + dy * dy);
          const distance = Math.sqrt(distanceSquared);
          const force = repel / distanceSquared;
          dx /= distance; dy /= distance;
          a.vx -= dx * force; a.vy -= dy * force;
          b.vx += dx * force; b.vy += dy * force;
        }
      }
      const desired = Number(settings.link_distance);
      const linkForce = Number(settings.link_force);
      graphState.links.forEach(link => {
        let dx = link.target.x - link.source.x, dy = link.target.y - link.source.y;
        const distance = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        const force = (distance - desired) * linkForce;
        dx /= distance; dy /= distance;
        link.source.vx += dx * force; link.source.vy += dy * force;
        link.target.vx -= dx * force; link.target.vy -= dy * force;
      });
      const center = Number(settings.center_force);
      nodes.forEach(node => {
        if (node !== graphState.draggedNode) {
          node.vx += -node.x * center;
          node.vy += -node.y * center;
          node.vx *= 0.82;
          node.vy *= 0.82;
          node.x += node.vx;
          node.y += node.vy;
        }
      });
    }
    function graphNodeRadius(node, settings = { ...DEFAULT_GRAPH_SETTINGS, ...uiState.graphSettings }) {
      const baseRadius = Number(settings.node_size);
      const connectionGrowth = Math.min(0.25, Math.sqrt(Math.max(0, node.degree || 0)) * 0.06);
      return baseRadius * (1 + connectionGrowth);
    }
    function drawCorrelationGraph() {
      const context = graphState.context;
      if (!context || !graphState.width || !graphState.height) return;
      const settings = { ...DEFAULT_GRAPH_SETTINGS, ...uiState.graphSettings };
      const style = getComputedStyle(document.documentElement);
      context.clearRect(0, 0, graphState.width, graphState.height);
      context.fillStyle = style.getPropertyValue("--dark").trim();
      context.fillRect(0, 0, graphState.width, graphState.height);
      context.save();
      context.translate(graphState.width / 2 + graphState.transform.x, graphState.height / 2 + graphState.transform.y);
      context.scale(graphState.transform.k, graphState.transform.k);
      context.strokeStyle = style.getPropertyValue("--line").trim();
      context.lineWidth = Number(settings.link_thickness) / graphState.transform.k;
      context.globalAlpha = 0.72;
      graphState.links.forEach(link => {
        context.beginPath();
        context.moveTo(link.source.x, link.source.y);
        context.lineTo(link.target.x, link.target.y);
        context.stroke();
      });
      context.globalAlpha = 1;
      const textFade = Math.max(0, Math.min(1, Number(settings.text_threshold)));
      const textOpacity = 1 - textFade;
      graphState.nodes.forEach(node => {
        const radius = graphNodeRadius(node, settings);
        context.beginPath();
        context.arc(node.x, node.y, radius, 0, Math.PI * 2);
        context.fillStyle = node.type === "entity" ? graphColor("entity_color", "--accent") : graphColor("property_color", "--light");
        context.fill();
        if (textOpacity > 0) {
          context.font = `${11 / graphState.transform.k}px Consolas, monospace`;
          context.fillStyle = style.getPropertyValue("--light").trim();
          context.globalAlpha = textOpacity;
          context.fillText(node.label, node.x + radius + 5 / graphState.transform.k, node.y + 4 / graphState.transform.k);
          context.globalAlpha = 1;
        }
      });
      context.restore();
    }
    function graphPointerWorld(event) {
      const rect = graphState.canvas.getBoundingClientRect();
      return {
        x: (event.clientX - rect.left - graphState.width / 2 - graphState.transform.x) / graphState.transform.k,
        y: (event.clientY - rect.top - graphState.height / 2 - graphState.transform.y) / graphState.transform.k,
      };
    }
    function graphNodeAt(event) {
      const point = graphPointerWorld(event);
      const settings = { ...DEFAULT_GRAPH_SETTINGS, ...uiState.graphSettings };
      return [...graphState.nodes].reverse().find(node => {
        const hitRadius = Math.max(12 / graphState.transform.k, graphNodeRadius(node, settings));
        return Math.hypot(node.x - point.x, node.y - point.y) <= hitRadius;
      }) || null;
    }
    function bindCorrelationCanvas() {
      const canvas = graphState.canvas;
      if (!canvas || canvas.dataset.ready) return;
      canvas.dataset.ready = "true";
      canvas.addEventListener("pointerdown", event => {
        canvas.setPointerCapture(event.pointerId);
        graphState.draggedNode = graphNodeAt(event);
        graphState.panning = !graphState.draggedNode;
        graphState.pointerX = event.clientX;
        graphState.pointerY = event.clientY;
        canvas.classList.add("dragging");
      });
      canvas.addEventListener("pointermove", event => {
        if (graphState.draggedNode) {
          const point = graphPointerWorld(event);
          graphState.draggedNode.x = point.x;
          graphState.draggedNode.y = point.y;
          graphState.draggedNode.vx = 0;
          graphState.draggedNode.vy = 0;
        } else if (graphState.panning) {
          graphState.transform.x += event.clientX - graphState.pointerX;
          graphState.transform.y += event.clientY - graphState.pointerY;
        }
        graphState.pointerX = event.clientX;
        graphState.pointerY = event.clientY;
        drawCorrelationGraph();
      });
      const release = event => {
        if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
        graphState.draggedNode = null;
        graphState.panning = false;
        canvas.classList.remove("dragging");
      };
      canvas.addEventListener("pointerup", release);
      canvas.addEventListener("pointercancel", release);
      canvas.addEventListener("wheel", event => {
        event.preventDefault();
        graphState.transform.k = Math.max(0.25, Math.min(4, graphState.transform.k * Math.exp(-event.deltaY * 0.001)));
        drawCorrelationGraph();
      }, { passive: false });
      canvas.addEventListener("dblclick", () => { graphState.transform = { x: 0, y: 0, k: 1 }; drawCorrelationGraph(); });
      new ResizeObserver(resizeCorrelationCanvas).observe(canvas);
    }
    function correlationFrame() {
      if (!document.hidden && el("correlationMap")?.classList.contains("active")) {
        if (uiState.graphSettings.animate !== false && !matchMedia('(prefers-reduced-motion: reduce)').matches) stepCorrelationGraph();
        drawCorrelationGraph();
      }
      graphState.frame = requestAnimationFrame(correlationFrame);
    }
    function initCorrelationMap() {
      const canvas = el("correlationCanvas");
      if (!canvas) return;
      graphState.canvas = canvas;
      graphState.context = canvas.getContext("2d");
      bindCorrelationCanvas();
      syncCorrelationControls();
      rebuildCorrelationGraph();
      resizeCorrelationCanvas();
      if (!graphState.frame) graphState.frame = requestAnimationFrame(correlationFrame);
    }
    function toggleGraphToolbar() {
      const toolbar = document.querySelector(".correlation-toolbar");
      if (!toolbar) return;
      const collapsed = toolbar.classList.toggle("collapsed");
      el("graphToolbarToggle").textContent = collapsed ? "Expand Controls" : "Collapse Controls";
      el("graphToolbarToggle").setAttribute("aria-expanded", String(!collapsed));
    }
    function syncCorrelationControls() {
      const settings = { ...DEFAULT_GRAPH_SETTINGS, ...uiState.graphSettings };
      const values = {
        graphTextThreshold: settings.text_threshold,
        graphNodeSize: settings.node_size,
        graphLinkThickness: settings.link_thickness,
        graphCenterForce: settings.center_force,
        graphRepelForce: settings.repel_force,
        graphLinkForce: settings.link_force,
        graphLinkDistance: settings.link_distance,
      };
      Object.entries(values).forEach(([id, value]) => { if (el(id)) el(id).value = value; });
      if (el("graphPropertyColor")) {
        el("graphPropertyColor").value = graphColor("property_color", "--light");
        el("graphPropertyColor").dataset.usesTheme = settings.property_color ? "false" : "true";
      }
      if (el("graphEntityColor")) {
        el("graphEntityColor").value = graphColor("entity_color", "--accent");
        el("graphEntityColor").dataset.usesTheme = settings.entity_color ? "false" : "true";
      }
      if (el("graphAnimate")) el("graphAnimate").checked = settings.animate !== false;
      updateCorrelationControlOutputs();
    }
    function updateCorrelationControlOutputs() {
      const pairs = {
        graphTextThresholdValue: `${Math.round(Number(el("graphTextThreshold")?.value || 0) * 100)}%`,
        graphNodeSizeValue: el("graphNodeSize")?.value,
        graphLinkThicknessValue: el("graphLinkThickness")?.value,
        graphCenterForceValue: el("graphCenterForce")?.value,
        graphRepelForceValue: el("graphRepelForce")?.value,
        graphLinkForceValue: el("graphLinkForce")?.value,
        graphLinkDistanceValue: el("graphLinkDistance")?.value,
      };
      Object.entries(pairs).forEach(([id, value]) => { if (el(id)) el(id).textContent = value; });
    }
    function updateGraphSettingsFromControls() {
      uiState.graphSettings = {
        ...uiState.graphSettings,
        property_color: el("graphPropertyColor").dataset.usesTheme === "true" ? "" : el("graphPropertyColor").value,
        entity_color: el("graphEntityColor").dataset.usesTheme === "true" ? "" : el("graphEntityColor").value,
        text_threshold: Number(el("graphTextThreshold").value),
        node_size: Number(el("graphNodeSize").value),
        link_thickness: Number(el("graphLinkThickness").value),
        center_force: Number(el("graphCenterForce").value),
        repel_force: Number(el("graphRepelForce").value),
        link_force: Number(el("graphLinkForce").value),
        link_distance: Number(el("graphLinkDistance").value),
        animate: el("graphAnimate").checked,
      };
      updateCorrelationControlOutputs();
      saveLocalState();
      drawCorrelationGraph();
    }
    function resetGraphColor(kind) {
      const key = kind === "entity" ? "entity_color" : "property_color";
      uiState.graphSettings = { ...uiState.graphSettings, [key]: "" };
      syncCorrelationControls();
      saveLocalState();
      drawCorrelationGraph();
    }
    function renderMetrics() {
      const metrics = state.metrics || {};
      el("cpuCores").textContent = `Host CPU · ${metrics.cpu_cores ?? "unknown"} logical cores`;
      el("cpuPercent").textContent = `${metrics.cpu_percent ?? "—"}%`;
      el("ramUsed").textContent = fmtBytes(metrics.ram_used_bytes);
      el("ramTotal").textContent = fmtBytes(metrics.ram_total_bytes);
      el("ramPercent").textContent = `${metrics.ram_percent ?? "—"}%`;
      el("diskUsed").textContent = fmtBytes(metrics.disk_used_bytes);
      el("diskTotal").textContent = fmtBytes(metrics.disk_total_bytes);
      el("diskPercent").textContent = `${metrics.disk_percent ?? "—"}%`;
      el("systemUptime").textContent = fmtUptime(metrics.uptime_seconds);
      renderCorrelationMetric();
    }
    function render() {
      renderMetrics();
      renderOverviewBlocks();
      renderProjectCards();
      renderPodsPage();
      renderObjects();
      renderSubjects();
      if (el("subjectObject")) el("subjectObject").innerHTML = state.objects.map(item => `<option value="${esc(item.id)}">${esc(item.name)} / ${esc(item.id)}</option>`).join("");
      if (el("backupList")) el("backupList").innerHTML = state.backups.map(item => row(item.filename, item.entity_type, [item.created_at], `<a class="button" href="/v1/backups/${item.id}">Download</a>`)).join("") || `<div class="muted">no backups yet</div>`;
      const limits = state.runtime?.audit_limits;
      if (el("loggerRetention") && limits) {
        el("loggerRetention").textContent = `Retention is capped at ${Number(limits.max_entries).toLocaleString("en-US")} entries, ${limits.retention_days} days, ${fmtBytes(limits.max_file_bytes)} per file and ${fmtBytes(limits.max_total_bytes)} total; the first reached limit wins.`;
      }
      renderLogger();
      renderUpdaterRuntime();
      if (el("correlationMap")?.classList.contains("active")) rebuildCorrelationGraph();
    }
    function fmtLogDate(value) {
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value || "-");
      const part = number => String(number).padStart(2, "0");
      return `${part(date.getDate())}.${part(date.getMonth() + 1)}.${date.getFullYear()} ${part(date.getHours())}:${part(date.getMinutes())}:${part(date.getSeconds())}`;
    }
    function logEventStatus(item) {
      const result = item?.result || {};
      return ["error", "failed", "denied", "rejected"].includes(result.outcome || result.status) ? "error" : "success";
    }
    function renderLogger() {
      const root = el("loggerStream");
      if (!root) return;
      root.innerHTML = (state.logs || []).map(item => {
        const status = logEventStatus(item);
        return `
          <div class="log-entry" data-log-id="${esc(item.id)}">
            <span class="log-status ${status}">${status}</span>
            <span title="${esc(item.action)}">${esc(item.action)}</span>
            <span title="${esc(item.target)}">${esc(item.target)}</span>
            <span title="${esc(item.actor)}">${esc(item.actor)}</span>
            <time datetime="${esc(item.created_at)}">${esc(fmtLogDate(item.created_at))}</time>
          </div>
        `;
      }).join("") || `<span class="muted">no log entries</span>`;
    }
    function renderProjectCards() {
      const root = el("projectCards");
      if (!root) return;
      const cards = projectItems().map(item => `
        <button class="project-card ${item.source.image_url ? "has-image" : ""}" ${item.source.image_url ? `style="background-image:url('${esc(item.source.image_url)}')"` : ""} data-project-type="${esc(item.type)}" data-project-id="${esc(item.id)}">
          <span class="project-card-title">${esc(item.title)}</span>
        </button>
      `);
      cards.push(`<button class="project-card plus" data-create-project="true" aria-label="create project">+</button>`);
      root.innerHTML = cards.join("");
    }
    function propertyLabel(item) {
      const value = item.value ? ` - ${item.value}` : "";
      return `${item.key || item.type}${value}`;
    }
    function sharedProperty(item) {
      return uiState.propertyLibrary.find(entry => entry.id === item.id) || item;
    }
    function renderProperties(blockId) {
      const root = el("humanProperties");
      if (!root) return;
      const items = uiState.propertiesByBlock[blockId] || [];
      root.innerHTML = items.map((item, index) => {
        const property = sharedProperty(item);
        return `
        <div class="property-item" draggable="true" data-property-index="${index}">
          <strong>${esc(property.key || property.type)}</strong>
          <span>${esc(property.value || "")}</span>
        </div>
      `}).join("") + `<button class="property-add" data-add-property="${esc(blockId)}">+</button>`;
    }
    function renderPropertyLibrary() {
      const content = uiState.propertyLibrary.map((item, index) => `
        <div class="library-item" draggable="true" data-library-property="${esc(item.id)}" data-library-property-index="${index}">
          ${esc(propertyLabel(item))}
        </div>
      `).join("") || `<div class="muted">library is empty</div>`;
      const root = el("propertyLibrary");
      if (root) root.innerHTML = content;
    }
    function adjustHumanDescriptionSize() {
      const field = el("humanDescription");
      if (!field) return;
      const length = field.value.length;
      const size = length > 720 ? 14 : length > 480 ? 16 : length > 280 ? 18 : length > 160 ? 22 : length > 86 ? 26 : 34;
      field.style.fontSize = `${size}px`;
      field.scrollTop = 0;
    }
    function blockInterfaceHtml(localBlockId, blockType = "", backendBlockId = "") {
      return `
        <div class="block-interface">
          <div class="human-layout">
            <section class="human-column">
              <h2>Description</h2>
              <textarea id="humanDescription" class="human-description" spellcheck="false">${esc(uiState.descriptionsByBlock[localBlockId] || "")}</textarea>
            </section>
            <section class="human-column">
              <h2>Properties</h2>
              <div id="humanProperties" class="property-list"></div>
            </section>
          </div>
        </div>
      `;
    }
    function overviewBlockControlsHtml(blockId) {
      const block = overviewBlockById(blockId);
      if (!block) return "";
      return `
        <div class="card overview-block-controls">
          <p class="hint">Edit the title directly above or use an image as this Overview card background.</p>
          <div class="actions">
            <button data-choose-overview-image="${esc(blockId)}">Upload Image</button>
            ${block.image_url ? `<button data-remove-overview-image="${esc(blockId)}">Remove Image</button>` : ""}
          </div>
          <input id="overviewBlockImageInput" type="file" accept="image/png,image/jpeg,image/webp" data-overview-block-id="${esc(blockId)}" hidden />
        </div>
      `;
    }
    function openBlockInterface(title, localBlockId, blockType = "", backendBlockId = "", overviewBlockId = "") {
      uiState.activePropertyBlock = localBlockId;
      uiState.activeDescriptionBlock = localBlockId;
      openFullscreen(title, `${overviewBlockControlsHtml(overviewBlockId)}${blockInterfaceHtml(localBlockId)}${agentPanelHtml(blockType, backendBlockId)}`);
      if (overviewBlockId) {
        el("fullscreenTitle").contentEditable = "true";
        el("fullscreenTitle").dataset.renameType = "overview_block";
        el("fullscreenTitle").dataset.renameId = overviewBlockId;
      }
      renderProperties(localBlockId);
      adjustHumanDescriptionSize();
      if (blockType && backendBlockId) loadAgentBlock(blockType, backendBlockId, title);
    }
    function openInfoPanel(title, blockId) {
      openBlockInterface(title, blockId, "", "", blockId);
    }
    function agentStatusPill(status) {
      const normal = ["online", "healthy", "active", "busy"].includes(String(status || "").toLowerCase());
      return `<span class="pill ${statusClass(status)}"><i class="status-spinner ${normal ? "" : "frozen"}"></i>${esc(status || "UNKNOWN")}</span>`;
    }
    function agentPanelHtml(blockType, blockId) {
      if (!blockType || !blockId) {
        return "";
      }
      return `
        <section class="agent-surface" data-agent-block-type="${esc(blockType)}" data-agent-block-id="${esc(blockId)}">
          <div><h2>Agent Nodes</h2><p class="hint">Agents are ordered top to bottom. Drag to reorder or open an Agent Node.</p></div>
          <div id="agentNodesList" class="agent-node-list"><span class="muted">loading agent nodes</span></div>
        </section>
      `;
    }
    function openAgentManagedBlock(title, blockType, blockId) {
      const localBlockId = `${blockType}_block`;
      const blockTitle = overviewBlockById(localBlockId)?.name || title;
      openBlockInterface(blockTitle, localBlockId, blockType, blockId, localBlockId);
    }
    function openOverviewBlock(blockId) {
      const block = overviewBlockById(blockId);
      if (!block) return;
      if (block.blockType) openAgentManagedBlock(block.name, block.blockType, block.backendBlockId);
      else openInfoPanel(block.name, block.localBlockId);
    }
    async function loadAgentBlock(blockType, blockId, title = "") {
      agentUiState.activeBlockType = blockType;
      agentUiState.activeBlockId = blockId;
      agentUiState.activeBlockTitle = title;
      const root = el("agentNodesList");
      if (root) root.innerHTML = `<span class="muted">loading agent nodes</span>`;
      try {
        agentUiState.assignments = await api(`/api/blocks/${encodeURIComponent(blockId)}/agents?block_type=${encodeURIComponent(blockType)}`);
      } catch (error) {
        agentUiState.assignments = [];
        if (root) root.innerHTML = `<span class="muted">${esc(error.message)}</span>`;
        return;
      }
      renderAgentNodes();
    }
    function renderAgentNodes() {
      const root = el("agentNodesList");
      if (!root) return;
      const assignments = agentUiState.assignments || [];
      root.innerHTML = assignments.map((item, index) => {
        const agent = item.agent || {};
        return `
          <div class="agent-node-row" data-agent-index="${index}" data-agent-assignment-id="${esc(item.id)}">
            <div class="agent-node-main" draggable="true" data-agent-drag-index="${index}" data-open-agent-node="${esc(agent.id || item.agent_id)}">
              <strong>${esc(agent.display_name || agent.agent_id || item.agent_id)}</strong>
            </div>
            <div class="agent-node-actions">${agentStatusPill(agent.status)}<button class="danger" data-detach-agent-node="${esc(agent.id || item.agent_id)}" aria-label="detach agent">X</button></div>
          </div>
        `;
      }).join("") + `<button id="openAgentLibraryModal" class="agent-add-button primary" aria-label="add agent node">+</button>`;
    }
    async function openAgentLibraryModal() {
      resetModalPosition("agentLibraryModalBackdrop");
      el("agentLibraryModalBackdrop").classList.add("open");
      el("agentLibraryModalBackdrop").setAttribute("aria-hidden", "false");
      await renderAgentLibrary();
    }
    function closeAgentLibraryModal() {
      el("agentLibraryModalBackdrop").classList.remove("open");
      el("agentLibraryModalBackdrop").setAttribute("aria-hidden", "true");
    }
    async function renderAgentLibrary() {
      const root = el("agentLibraryList");
      if (!root) return;
      root.innerHTML = `<span class="muted">loading library</span>`;
      agentUiState.library = await api("/api/agents/library");
      renderAgentLibraryList();
    }
    function renderAgentLibraryList() {
      const root = el("agentLibraryList");
      if (!root) return;
      const attached = new Set((agentUiState.assignments || []).map(item => item.agent_id));
      const query = (el("agentLibrarySearch")?.value || "").trim().toLowerCase();
      const filtered = (agentUiState.library || []).filter(agent => {
        const haystack = `${agent.display_name || ""} ${agent.agent_id || ""} ${agent.id || ""} ${agent.status || ""}`.toLowerCase();
        return !query || haystack.includes(query);
      });
      root.innerHTML = filtered.map(agent => `
          <div class="agent-node-row" data-agent-library-index="${agentUiState.library.indexOf(agent)}">
            <div class="agent-node-main" draggable="true" data-agent-library-drag-index="${agentUiState.library.indexOf(agent)}">
              <strong>${esc(agent.display_name || agent.agent_id)}</strong>
              <small>${esc(agent.status)} / attached to ${esc(agentAssignmentSummary(agent))}</small>
            </div>
          <button data-attach-agent-node="${esc(agent.id)}" ${attached.has(agent.id) ? "disabled" : ""}>Attach</button>
        </div>
      `).join("") || `<div class="muted">library is empty</div>`;
    }
    async function attachAgentNode(agentId) {
      if (!agentUiState.activeBlockType || !agentUiState.activeBlockId) return;
      await api(`/api/blocks/${encodeURIComponent(agentUiState.activeBlockId)}/agents?block_type=${encodeURIComponent(agentUiState.activeBlockType)}`, {
        method: "POST",
        body: JSON.stringify({ agent_id: agentId, created_by: "operator" }),
      });
      closeAgentLibraryModal();
      await loadAgentBlock(agentUiState.activeBlockType, agentUiState.activeBlockId, agentUiState.activeBlockTitle);
    }
    async function registerAgentNode() {
      const payload = {
        agent_id: el("agentEnrollId").value.trim(),
        display_name: el("agentEnrollName").value.trim(),
        domain: el("agentEnrollDomain").value.trim(),
        port: Number(el("agentEnrollPort").value || 7443),
        identity_fingerprint: el("agentEnrollFingerprint").value.trim(),
        enrollment_token: el("agentEnrollToken").value.trim(),
      };
      if (!payload.agent_id || !payload.display_name || !payload.domain || !payload.identity_fingerprint || !payload.enrollment_token) {
        return alert("agent id, display name, domain, fingerprint and enrollment token are required");
      }
      const agent = await api("/api/agents/enroll", { method: "POST", body: JSON.stringify(payload) });
      if (agentUiState.libraryOnly || !agentUiState.activeBlockType || !agentUiState.activeBlockId) {
        closeAgentLibraryModal();
        await renderAgentsPage();
      } else {
        await attachAgentNode(agent.id);
      }
      ["agentEnrollId", "agentEnrollName", "agentEnrollDomain", "agentEnrollFingerprint", "agentEnrollToken"].forEach(id => { el(id).value = ""; });
      el("agentEnrollPort").value = "7443";
    }
    async function openAgentNode(agentId) {
      if (!agentUiState.viewingAgent) {
        agentUiState.returnContext = agentUiState.activeBlockType === "subject" && agentUiState.activeBlockId
          ? { kind: "project", projectType: "subject", projectId: agentUiState.activeBlockId }
          : agentUiState.activeBlockType && agentUiState.activeBlockId
            ? { kind: "block", title: agentUiState.activeBlockTitle, blockType: agentUiState.activeBlockType, blockId: agentUiState.activeBlockId }
            : { kind: "agents" };
      }
      agentUiState.viewingAgent = true;
      agentUiState.activeAgentId = agentId;
      agentUiState.activeJobId = "";
      const agent = await api(`/api/agents/${encodeURIComponent(agentId)}`);
      const [capabilities, jobs, approvals] = await Promise.all([
        api(`/api/agents/${encodeURIComponent(agentId)}/capabilities`),
        api(`/api/agents/${encodeURIComponent(agentId)}/jobs`),
        api(`/api/agents/${encodeURIComponent(agentId)}/approvals`),
      ]);
      agentUiState.capabilities = capabilities.items || [];
      agentUiState.jobs = jobs || [];
      agentUiState.approvals = approvals || [];
      openFullscreen(agent.display_name || "Agent Node", `
        <div class="agent-workspace">
          <aside class="agent-left">
            <div class="agent-top">
              <h2>Agent Node</h2>
              <div class="agent-status-grid">
                <span>status<br><strong>${esc(agent.status)}</strong></span>
                <span>last heartbeat<br><strong>${esc(agent.last_heartbeat_at || "none")}</strong></span>
              </div>
              <details class="setting-group">
                <summary>Settings</summary>
                <div class="agent-status-grid">
                  <span>name<br><strong>${esc(agent.display_name || agent.agent_id)}</strong></span>
                  <span>agent id<br><strong>${esc(agent.id)}</strong></span>
                  <span>domain<br><strong>${esc(agent.domain || "unknown")}</strong></span>
                  <span>port<br><strong>${esc(agent.port || "-")}</strong></span>
                  <span>fingerprint<br><strong>${esc(agent.identity_fingerprint || "-")}</strong></span>
                  <span>certificate<br><strong>${esc(agent.certificate_serial || "-")}</strong></span>
                  <span>agent version<br><strong>${esc(agent.agent_version || "-")}</strong></span>
                  <span>sindri version<br><strong>${esc(agent.sindri_version || "-")}</strong></span>
                </div>
                <div class="actions">
                  <button data-refresh-agent-node="${esc(agent.id)}">Refresh</button>
                  <button class="danger" data-request-remove-agent-node="${esc(agent.id)}">Delete</button>
                </div>
              </details>
              <h3>Approval Queue</h3>
              <div id="agentApprovalList" class="approval-list"></div>
            </div>
            <div class="agent-commands">
              <h3>Commands / Capability Catalog</h3>
              <div id="agentCapabilityList" class="capability-list"></div>
            </div>
          </aside>
          <section class="agent-live">
            <div class="agent-live-head">
              <h2>Server live view</h2>
              <span id="agentActiveJob" class="pill">no active job</span>
            </div>
            <div class="agent-command-preview" id="agentCommandPreview">Live execution is waiting for a command from the left panel.</div>
            <div class="job-event-list" id="agentJobEvents"></div>
          </section>
        </div>
      `);
      el("fullscreenTitle").contentEditable = "true";
      el("fullscreenTitle").dataset.renameType = "agent";
      el("fullscreenTitle").dataset.renameId = agent.id;
      renderAgentCapabilityCatalog();
      renderAgentApprovals();
      renderAgentJobs();
    }
    function renderAgentCapabilityCatalog() {
      const root = el("agentCapabilityList");
      if (!root) return;
      root.innerHTML = (agentUiState.capabilities || []).map(item => `
        <button class="capability-card" data-run-agent-capability="${esc(item.action)}" ${item.available === false ? "disabled" : ""}>
          <strong>${esc(item.title || item.action)}</strong>
          <span>${esc(item.group || "Agent Node")} / ${esc(item.risk || "read")}</span>
          <small>${esc(item.description || item.action)}</small>
        </button>
      `).join("") || `<div class="muted">no capabilities reported</div>`;
    }
    function renderAgentApprovals() {
      const root = el("agentApprovalList");
      if (!root) return;
      root.innerHTML = (agentUiState.approvals || []).filter(item => String(item.status).toLowerCase() === "pending").map(item => `
        <button class="approval-card" data-open-agent-approval="${esc(item.approval_id)}" data-job-id="${esc(item.job_id)}">
          <strong>${esc(item.risk)} approval</strong>
          <span>${esc(item.warning || "Review execution plan")}</span>
        </button>
      `).join("") || `<div class="muted">no pending approvals</div>`;
    }
    function renderAgentJobs() {
      const root = el("agentJobEvents");
      if (!root) return;
      root.innerHTML = (agentUiState.jobs || []).slice(0, 8).map(job => `
        <div class="job-event">
          <strong>${esc(job.action)}</strong>
          <span>${esc(job.status)} / ${esc(job.job_id)}</span>
        </div>
      `).join("") || `<div class="muted">no jobs yet</div>`;
    }
    function capabilityInputControl(spec) {
      const name = String(spec.name || "");
      const prompt = String(spec.prompt || name);
      const required = spec.required ? " required" : "";
      const defaultValue = spec.default ?? "";
      const data = `data-capability-input="${esc(name)}"`;
      if (spec.type === "choice") {
        const values = Array.isArray(spec.values) ? spec.values : [];
        return `<label>${esc(prompt)}<select ${data}${required}>${values.map(value => `<option value="${esc(value)}" ${String(value) === String(defaultValue) ? "selected" : ""}>${esc(value)}</option>`).join("")}</select></label>`;
      }
      if (spec.type === "boolean") {
        const selected = defaultValue === true || String(defaultValue).toLowerCase() === "true";
        return `<label>${esc(prompt)}<select ${data}><option value="false" ${selected ? "" : "selected"}>No</option><option value="true" ${selected ? "selected" : ""}>Yes</option></select></label>`;
      }
      const type = spec.type === "integer" ? "number" : spec.type === "secret" || spec.secret ? "password" : "text";
      const constraints = spec.type === "integer"
        ? `${spec.minimum ? ` min="${Number(spec.minimum)}"` : ""}${spec.maximum ? ` max="${Number(spec.maximum)}"` : ""}`
        : "";
      return `<label>${esc(prompt)}<input type="${type}" ${data} value="${esc(defaultValue)}" autocomplete="${type === "password" ? "new-password" : "off"}"${constraints}${required} /></label>`;
    }
    function openAgentCapabilityInput(action) {
      const capability = (agentUiState.capabilities || []).find(item => item.action === action);
      if (!capability) return;
      agentUiState.pendingCapability = capability;
      el("agentCapabilityInputModalTitle").textContent = capability.title || capability.action;
      el("agentCapabilityInputDescription").textContent = capability.description || capability.action;
      el("agentCapabilityInputFields").innerHTML = (capability.inputs || []).map(capabilityInputControl).join("");
      resetModalPosition("agentCapabilityInputModalBackdrop");
      el("agentCapabilityInputModalBackdrop").classList.add("open");
      el("agentCapabilityInputModalBackdrop").setAttribute("aria-hidden", "false");
    }
    function closeAgentCapabilityInputModal() {
      el("agentCapabilityInputModalBackdrop").classList.remove("open");
      el("agentCapabilityInputModalBackdrop").setAttribute("aria-hidden", "true");
      agentUiState.pendingCapability = null;
    }
    function collectAgentCapabilityInputs() {
      const capability = agentUiState.pendingCapability;
      const inputs = {};
      for (const spec of capability?.inputs || []) {
        const field = el("agentCapabilityInputFields").querySelector(`[data-capability-input="${CSS.escape(String(spec.name || ""))}"]`);
        if (!field) continue;
        const raw = field.value;
        if (spec.required && !String(raw).trim()) throw new Error(`${spec.prompt || spec.name} is required`);
        if (spec.type === "integer") {
          const value = Number(raw);
          if (!Number.isInteger(value)) throw new Error(`${spec.prompt || spec.name} must be an integer`);
          inputs[spec.name] = value;
        } else if (spec.type === "boolean") {
          inputs[spec.name] = raw === "true";
        } else if (String(raw).length || spec.required) {
          inputs[spec.name] = raw;
        }
      }
      return inputs;
    }
    async function dispatchAgentCapability(action, inputs = {}) {
      if (!agentUiState.activeAgentId) return;
      const job = await api(`/api/agents/${encodeURIComponent(agentUiState.activeAgentId)}/jobs`, {
        method: "POST",
        body: JSON.stringify({ action, inputs, created_by: "operator" }),
      });
      agentUiState.activeJobId = job.job_id;
      el("agentActiveJob").textContent = job.status;
      el("agentCommandPreview").textContent = JSON.stringify({ job_id: job.job_id, action: job.action, status: job.status }, null, 2);
      agentUiState.jobs = [job, ...(agentUiState.jobs || [])];
      await refreshAgentJobEvents();
    }
    async function runAgentCapability(action) {
      const capability = (agentUiState.capabilities || []).find(item => item.action === action);
      if (!capability || !agentUiState.activeAgentId) return;
      if ((capability.inputs || []).length) {
        openAgentCapabilityInput(action);
        return;
      }
      await dispatchAgentCapability(action);
    }
    async function confirmAgentCapabilityInput() {
      const capability = agentUiState.pendingCapability;
      if (!capability) return;
      const inputs = collectAgentCapabilityInputs();
      closeAgentCapabilityInputModal();
      await dispatchAgentCapability(capability.action, inputs);
    }
    async function refreshAgentJobEvents() {
      if (!agentUiState.activeAgentId || !agentUiState.activeJobId) return;
      agentUiState.events = await api(`/api/agents/${encodeURIComponent(agentUiState.activeAgentId)}/jobs/${encodeURIComponent(agentUiState.activeJobId)}/events`);
      const root = el("agentJobEvents");
      if (root) root.innerHTML = agentUiState.events.map(item => `
        <div class="job-event">
          <strong>#${item.sequence} ${esc(item.event_type)}</strong>
          <span>${esc(item.status)} ${esc(item.message || "")}</span>
        </div>
      `).join("") || `<div class="muted">job created, waiting for Agent Node events</div>`;
    }
    function openAgentApproval(approvalId, jobId) {
      const approval = (agentUiState.approvals || []).find(item => item.approval_id === approvalId && item.job_id === jobId);
      if (!approval) return;
      agentUiState.activeApproval = approval;
      agentUiState.activeJobId = approval.job_id;
      const exterminatusConfirmation = approval.action === "system.exterminatus"
        ? `<div class="form-grid">
            <label>confirmation phrase<input id="agentApprovalConfirmationPhrase" autocomplete="off" placeholder="EXTERMINATUS" /></label>
            <label>agent hostname<input id="agentApprovalHostname" autocomplete="off" placeholder="${esc(approval.hostname || "exact agent hostname")}" /></label>
          </div>
          <p class="hint">This command requires the exact phrase <code>EXTERMINATUS</code> and the Agent hostname${approval.hostname ? ` (<code>${esc(approval.hostname)}</code>)` : ""}.</p>`
        : "";
      el("agentApprovalBody").innerHTML = `
        <div><strong>command</strong><br>${esc(approval.action || "agent command")}</div>
        <div><strong>risk</strong><br>${esc(approval.risk)}</div>
        <div><strong>warning</strong><br>${esc(approval.warning || "Review execution plan")}</div>
        <div class="agent-command-preview">${esc(JSON.stringify(approval.plan || [], null, 2))}</div>
        ${exterminatusConfirmation}
      `;
      resetModalPosition("agentApprovalModalBackdrop");
      el("agentApprovalModalBackdrop").classList.add("open");
      el("agentApprovalModalBackdrop").setAttribute("aria-hidden", "false");
    }
    async function refreshPendingApprovals() {
      if (document.querySelector(".modal-backdrop.open")) return;
      const approvals = await api("/api/approvals/pending");
      const next = (approvals || []).find(item => !agentUiState.presentedApprovalIds.has(item.approval_id));
      if (!next) return;
      agentUiState.presentedApprovalIds.add(next.approval_id);
      agentUiState.activeAgentId = next.agent_id;
      agentUiState.approvals = approvals;
      openAgentApproval(next.approval_id, next.job_id);
    }
    function closeAgentApprovalModal() {
      el("agentApprovalModalBackdrop").classList.remove("open");
      el("agentApprovalModalBackdrop").setAttribute("aria-hidden", "true");
      agentUiState.activeApproval = null;
    }
    function requestRemoveAgentNode(agentId) {
      agentUiState.pendingRemoveAgentId = agentId;
      resetModalPosition("agentRemoveModalBackdrop");
      el("agentRemoveModalBackdrop").classList.add("open");
      el("agentRemoveModalBackdrop").setAttribute("aria-hidden", "false");
    }
    function closeAgentRemoveModal() {
      el("agentRemoveModalBackdrop").classList.remove("open");
      el("agentRemoveModalBackdrop").setAttribute("aria-hidden", "true");
      agentUiState.pendingRemoveAgentId = "";
    }
    async function decideAgentApproval(decision) {
      const approval = agentUiState.activeApproval;
      if (!approval || !agentUiState.activeAgentId) return;
      const confirmationPhrase = el("agentApprovalConfirmationPhrase")?.value || "";
      const hostnameConfirmation = el("agentApprovalHostname")?.value || "";
      if (decision === "approve" && approval.action === "system.exterminatus") {
        if (confirmationPhrase !== "EXTERMINATUS") throw new Error("Enter the exact confirmation phrase EXTERMINATUS");
        if (!hostnameConfirmation.trim()) throw new Error("Enter the exact Agent hostname");
      }
      await api(`/api/agents/${encodeURIComponent(agentUiState.activeAgentId)}/jobs/${encodeURIComponent(approval.job_id)}/${decision}`, {
        method: "POST",
        body: JSON.stringify({
          approval_id: approval.approval_id,
          plan_hash: approval.plan_hash,
          decided_by: "operator",
          confirmation_phrase: confirmationPhrase,
          hostname_confirmation: hostnameConfirmation,
        }),
      });
      closeAgentApprovalModal();
      if (el("agentApprovalList")) await openAgentNode(agentUiState.activeAgentId);
      await refreshPendingApprovals();
    }
    async function removeAgentNode(agentId) {
      await api(`/api/agents/${encodeURIComponent(agentId)}`, { method: "DELETE" });
      closeAgentRemoveModal();
      agentUiState.viewingAgent = false;
      await refresh();
      closeFullscreen();
      showView("agents");
    }
    async function detachAgentNode(agentId) {
      if (!agentUiState.activeBlockType || !agentUiState.activeBlockId) return;
      await api(`/api/blocks/${encodeURIComponent(agentUiState.activeBlockId)}/agents/${encodeURIComponent(agentId)}?block_type=${encodeURIComponent(agentUiState.activeBlockType)}`, { method: "DELETE" });
      await loadAgentBlock(agentUiState.activeBlockType, agentUiState.activeBlockId, agentUiState.activeBlockTitle);
    }
    function moveOrderedItem(items, from, to, after = false) {
      if (from === null || to === null || from < 0 || to < 0 || !items[from] || !items[to]) return items;
      let insertion = to + (after ? 1 : 0);
      const next = [...items];
      const [moved] = next.splice(from, 1);
      if (from < insertion) insertion -= 1;
      next.splice(Math.max(0, Math.min(next.length, insertion)), 0, moved);
      return next;
    }
    function isDropAfter(event, item) {
      const rect = item.getBoundingClientRect();
      return event.clientY >= rect.top + rect.height / 2;
    }
    function isMetricDropAfter(event, item) {
      const rect = item.getBoundingClientRect();
      if (event.clientY >= rect.top && event.clientY <= rect.bottom) return event.clientX >= rect.left + rect.width / 2;
      return event.clientY >= rect.top + rect.height / 2;
    }
    function clearDropIndicators() {
      document.querySelectorAll(".drop-before, .drop-after").forEach(item => item.classList.remove("drop-before", "drop-after"));
    }
    function showDropIndicator(item, after) {
      clearDropIndicators();
      item.classList.add(after ? "drop-after" : "drop-before");
    }
    async function reorderAgentNodes(from, to, after = false) {
      if (from === null || to === null) return;
      const assignments = [...(agentUiState.assignments || [])];
      const reordered = moveOrderedItem(assignments, from, to, after);
      if (reordered.every((item, index) => item === assignments[index])) return;
      agentUiState.assignments = reordered;
      renderAgentNodes();
      await api(`/api/blocks/${encodeURIComponent(agentUiState.activeBlockId)}/agents/reorder?block_type=${encodeURIComponent(agentUiState.activeBlockType)}`, {
        method: "POST",
        body: JSON.stringify({ ordered_agent_ids: reordered.map(item => item.agent_id) }),
      });
      await loadAgentBlock(agentUiState.activeBlockType, agentUiState.activeBlockId, agentUiState.activeBlockTitle);
    }
    async function reorderAgentLibrary(from, to, after = false) {
      const current = [...(agentUiState.library || [])];
      const reordered = moveOrderedItem(current, from, to, after);
      if (reordered.every((item, index) => item === current[index])) return;
      agentUiState.library = reordered;
      renderAgentLibraryList();
      renderAgentsPageList();
      await api("/api/agents/reorder", {
        method: "POST",
        body: JSON.stringify({ ordered_agent_ids: reordered.map(item => item.id) }),
      });
    }
    function reorderPropertyLibrary(from, to, after = false) {
      const current = [...(uiState.propertyLibrary || [])];
      const reordered = moveOrderedItem(current, from, to, after);
      if (reordered.every((item, index) => item === current[index])) return;
      uiState.propertyLibrary = reordered;
      saveLocalState();
      renderPropertyLibrary();
      renderPropertiesPage();
    }
    function updatePropertyModalMode() {
      const type = el("propertyType").value;
      const isAttachment = type === "attachment";
      const input = el("propertyValue");
      const inputTypes = { number: "number", date: "date", phone_number: "tel", email_address: "email", web_address: "url" };
      const placeholders = {
        plain_text: "Enter text",
        number: "Enter a number",
        date: "Select a date",
        geo_location: "Latitude, longitude or location name",
        service_id: "Enter service ID",
        document_id: "Enter document ID",
        device_id: "Enter device ID",
        phone_number: "+1 555 0100",
        email_address: "name@example.com",
        web_address: "https://example.com",
        network_address: "Hostname, IP address or CIDR",
      };
      input.type = inputTypes[type] || "text";
      input.inputMode = type === "number" ? "decimal" : type === "phone_number" ? "tel" : type === "email_address" ? "email" : type === "web_address" ? "url" : "text";
      input.placeholder = placeholders[type] || "Enter a value";
      el("propertyAttachmentField").classList.toggle("visible", isAttachment);
      input.closest("label").style.display = isAttachment ? "none" : "block";
    }
    function openPropertyModal(blockId, index = null) {
      uiState.activePropertyBlock = blockId;
      uiState.editingPropertyIndex = index;
      const libraryMode = blockId === "__library__";
      const property = index === null ? null : (libraryMode ? uiState.propertyLibrary[index] : sharedProperty((uiState.propertiesByBlock[blockId] || [])[index]));
      uiState.editingLibraryPropertyId = libraryMode ? (property?.id || "") : "";
      el("propertyModalTitle").textContent = property ? "Edit Property" : "Create Property";
      el("saveProperty").textContent = property ? "Save Property" : "Create Property";
      el("deleteProperty").classList.toggle("visible", Boolean(property));
      el("propertyType").value = property?.type === "mail_address" ? "email_address" : (property?.type || "plain_text");
      el("propertyKey").value = property?.key || "";
      el("propertyValue").value = property?.type === "attachment" ? "" : (property?.value || "");
      el("propertyAttachment").value = "";
      updatePropertyModalMode();
      renderPropertyLibrary();
      resetModalPosition("propertyModalBackdrop");
      el("propertyModalBackdrop").classList.add("open");
      el("propertyModalBackdrop").setAttribute("aria-hidden", "false");
    }
    function closePropertyModal() {
      el("propertyModalBackdrop").classList.remove("open");
      el("propertyModalBackdrop").setAttribute("aria-hidden", "true");
      uiState.editingPropertyIndex = null;
    }
    function openPasswordModal() {
      resetModalPosition("passwordModalBackdrop");
      ["currentPassword", "newPassword", "confirmPassword"].forEach(id => el(id).value = "");
      el("passwordModalBackdrop").classList.add("open");
      el("passwordModalBackdrop").setAttribute("aria-hidden", "false");
    }
    function closePasswordModal() {
      ["currentPassword", "newPassword", "confirmPassword"].forEach(id => el(id).value = "");
      el("passwordModalBackdrop").classList.remove("open");
      el("passwordModalBackdrop").setAttribute("aria-hidden", "true");
    }
    function openBackupImportModal() {
      resetModalPosition("backupImportModalBackdrop");
      el("backupImportModalBackdrop").classList.add("open");
      el("backupImportModalBackdrop").setAttribute("aria-hidden", "false");
    }
    function closeBackupImportModal() {
      el("backupImportModalBackdrop").classList.remove("open");
      el("backupImportModalBackdrop").setAttribute("aria-hidden", "true");
    }
    function addPropertyToBlock(blockId, property, insertionIndex = null) {
      const next = { ...property, id: property.id || uid() };
      if ((uiState.propertiesByBlock[blockId] || []).some(item => item.id === next.id)) {
        renderProperties(blockId);
        return;
      }
      const items = [...(uiState.propertiesByBlock[blockId] || [])];
      items.splice(insertionIndex === null ? items.length : Math.max(0, Math.min(items.length, insertionIndex)), 0, next);
      uiState.propertiesByBlock[blockId] = items;
      saveLocalState();
      renderProperties(blockId);
    }
    function propagateSharedProperty(property) {
      uiState.propertyLibrary = uiState.propertyLibrary.some(item => item.id === property.id)
        ? uiState.propertyLibrary.map(item => item.id === property.id ? property : item)
        : [...uiState.propertyLibrary, property];
      Object.keys(uiState.propertiesByBlock).forEach(blockId => {
        uiState.propertiesByBlock[blockId] = (uiState.propertiesByBlock[blockId] || []).map(item => item.id === property.id ? { ...property } : item);
      });
    }
    function savePropertyFromModal() {
      const file = el("propertyAttachment").files?.[0];
      const type = el("propertyType").value;
      const currentBlock = uiState.activePropertyBlock || "human_general";
      const libraryMode = currentBlock === "__library__";
      const currentItems = libraryMode ? uiState.propertyLibrary : (uiState.propertiesByBlock[currentBlock] || []);
      const previous = uiState.editingPropertyIndex === null ? null : (libraryMode ? currentItems[uiState.editingPropertyIndex] : sharedProperty(currentItems[uiState.editingPropertyIndex]));
      const property = {
        id: previous?.id || uid(),
        type,
        key: el("propertyKey").value.trim() || el("propertyType").selectedOptions[0].textContent,
        value: type === "attachment" ? (file?.name || previous?.value || "") : el("propertyValue").value.trim(),
      };
      if (libraryMode) {
        propagateSharedProperty(property);
        saveLocalState();
        renderPropertiesPage();
        recordUiAction(previous ? "property.updated" : "property.created", "property_library", property.id, { key: property.key, type: property.type });
      } else if (uiState.editingPropertyIndex === null) {
        uiState.propertyLibrary = [...uiState.propertyLibrary, property];
        addPropertyToBlock(currentBlock, property);
        recordUiAction("property.created", "overview_block", currentBlock, { key: property.key, type: property.type });
      } else {
        currentItems[uiState.editingPropertyIndex] = property;
        uiState.propertiesByBlock[currentBlock] = currentItems;
        propagateSharedProperty(property);
        saveLocalState();
        renderProperties(currentBlock);
        renderPropertyLibrary();
        recordUiAction("property.updated", "overview_block", currentBlock, { property_id: property.id, key: property.key, type: property.type });
      }
      closePropertyModal();
    }
    function deletePropertyFromModal() {
      if (uiState.editingPropertyIndex === null) return;
      const currentBlock = uiState.activePropertyBlock || "human_general";
      if (currentBlock === "__library__") {
        const property = uiState.propertyLibrary[uiState.editingPropertyIndex];
        uiState.propertyLibrary = uiState.propertyLibrary.filter(item => item.id !== property?.id);
        Object.keys(uiState.propertiesByBlock).forEach(blockId => {
          uiState.propertiesByBlock[blockId] = (uiState.propertiesByBlock[blockId] || []).filter(item => item.id !== property?.id);
        });
        saveLocalState();
        renderPropertiesPage();
        closePropertyModal();
        return;
      }
      const items = [...(uiState.propertiesByBlock[currentBlock] || [])];
      items.splice(uiState.editingPropertyIndex, 1);
      uiState.propertiesByBlock[currentBlock] = items;
      saveLocalState();
      renderProperties(currentBlock);
      recordUiAction("property.deleted", "overview_block", currentBlock);
      closePropertyModal();
    }
    function renderObjects() {
      if (!el("objectsList")) return;
      el("objectsList").innerHTML = state.objects.map(item => row(item.name, "", [`id ${item.id}`, `kind ${item.kind}`], `<button data-object-subject="${item.id}">Create Subject</button><button class="danger" data-request-entity-delete="object" data-entity-id="${item.id}" data-entity-name="${esc(item.name)}">Delete Object</button>`)).join("") || `<div class="muted">no objects</div>`;
    }
    function renderSubjects() {
      if (!el("subjectsList")) return;
      el("subjectsList").innerHTML = state.subjects.map(item => row(
        item.name,
        "",
        [`id ${item.id}`, `runtime ${item.runtime_type}`, `route ${item.primary_route || "none"}`],
        `<button data-create-pod="${item.id}">Create Pod</button><button class="danger" data-request-entity-delete="subject" data-entity-id="${item.id}" data-entity-name="${esc(item.name)}">Delete Subject</button>`
      )).join("") || `<div class="muted">no subjects</div>`;
    }
    async function renderAgentsPage() {
      const root = el("agentsPageList");
      if (!root) return;
      const agents = await api("/api/agents/library");
      agentUiState.library = agents;
      renderAgentsPageList();
    }
    function agentAssignmentSummary(agent) {
      const assignments = agent.assignments || [];
      if (!assignments.length) return "not attached";
      return assignments.map(item => `${item.name} (${item.block_type})`).join(", ");
    }
    function renderAgentsPageList() {
      const root = el("agentsPageList");
      if (!root) return;
      const query = String(el("agentsPageSearch")?.value || "").trim().toLowerCase();
      const agents = (agentUiState.library || [])
        .map((agent, index) => ({ agent, index }))
        .filter(({ agent }) => !query || `${agent.display_name || ""} ${agent.agent_id || ""} ${agent.id || ""} ${agent.status || ""} ${agentAssignmentSummary(agent)}`.toLowerCase().includes(query));
      root.innerHTML = agents.map(({ agent, index }) => `
        <div class="agent-node-row" data-agent-library-index="${index}" data-open-library-agent="${esc(agent.id)}">
          <div class="agent-node-main" draggable="true" data-agent-library-drag-index="${index}"><strong>${esc(agent.display_name || agent.agent_id)}</strong><small>id ${esc(agent.id)} / attached to ${esc(agentAssignmentSummary(agent))}</small></div>
          ${agentStatusPill(agent.status)}
        </div>
      `).join("") || `<div class="muted">${query ? "No agents match this search." : "No agents registered."}</div>`;
    }
    function renderPodsPage() {
      const root = el("podsPageList");
      if (!root) return;
      const query = String(el("podsPageSearch")?.value || "").trim().toLowerCase();
      const pods = (state.pods || []).filter(item => !query || `${item.login || ""} ${item.name || ""} ${item.id || ""} ${item.subject_name || ""} ${item.subject_id || ""} ${item.kind || ""} ${item.status || ""}`.toLowerCase().includes(query));
      root.innerHTML = pods.map(item => {
        const active = String(item.status || "").toLowerCase() === "active";
        const status = item.kind === "instance" ? (active ? "Online" : "Offline") : humanizeError(item.status || "Pending");
        return `
          <div class="agent-node-row" data-open-global-pod="${esc(item.id)}">
            <div class="agent-node-main">
              <strong>${esc(item.login || item.name)}</strong>
              <small>subject ${esc(item.subject_name || item.subject_id)} / id ${esc(item.subject_id)} / ${esc(item.kind)}</small>
            </div>
            <span class="pill ${active ? "ok" : ""}"><i class="status-spinner ${active ? "" : "frozen"}"></i>${esc(status)}</span>
          </div>`;
      }).join("") || `<div class="muted">${query ? "No pods match this search." : "No pods registered."}</div>`;
    }
    async function loadPodsPage() {
      state.pods = await api("/v1/pods");
      renderPodsPage();
    }
    function openGlobalPodItem(id) {
      const item = (state.pods || []).find(entry => entry.id === id);
      if (!item) return;
      if (item.kind === "instance") {
        openPodModal(item.login || item.name, `${podSettingsHtml(item)}<p class="hint">Manage or delete this Pod from its Subject workspace.</p>`);
        return;
      }
      openPodModal(item.login || item.name, `<div class="pod-settings-grid"><div class="pod-setting"><small>Subject</small><strong>${esc(item.subject_name || item.subject_id)}</strong></div><div class="pod-setting"><small>Status</small><strong>${esc(item.status)}</strong></div><div class="pod-setting"><small>Bundle version</small><strong>${esc(item.bundle_version)}</strong></div><div class="pod-setting"><small>Created</small><strong>${esc(item.created_at)}</strong></div></div><p class="hint">Pending Pod bundles are managed from their Subject workspace.</p>`);
    }
    function renderPropertiesPage() {
      const root = el("propertiesPageList");
      if (!root) return;
      const query = String(el("propertiesPageSearch")?.value || "").trim().toLowerCase();
      const properties = (uiState.propertyLibrary || [])
        .map((property, index) => ({ property, index }))
        .filter(({ property }) => !query || `${property.key || ""} ${property.value || ""} ${property.type || ""} ${property.id || ""}`.toLowerCase().includes(query));
      root.innerHTML = properties.map(({ property, index }) => `
        <div class="library-property-row" draggable="true" data-library-property-index="${index}" data-edit-library-property="${index}">
          <strong>${esc(property.key || property.type)}</strong><span>${esc(property.value || "")}</span>
        </div>
      `).join("") || `<div class="muted">${query ? "No properties match this search." : "No properties registered."}</div>`;
    }
    function subjectPodWorkspaceHtml(subjectId) {
      return `
        <div class="subject-pod-workspace" data-subject-pod-workspace="${esc(subjectId)}">
          <div class="subject-pod-head">
            <h2>Pods Settings</h2>
            <button class="primary" data-open-create-pod="${esc(subjectId)}">Create Pod</button>
          </div>
          <section class="subject-pod-section">
            <h3>Subject Network</h3>
            <label>VLESS connection<textarea id="subjectVlessConnection" spellcheck="false" placeholder="vless://..."></textarea></label>
            <p class="hint">One active VLESS URI is inherited by every Pod of this Subject. It saves automatically after typing stops; direct fallback is blocked.</p>
            <label>Update channel<select id="subjectUpdateChannel"><option value="stable">Stable</option><option value="beta">Beta</option></select></label>
            <p class="hint">Stable accepts production releases. Beta accepts prerelease builds. Both require a signed update manifest; without one, the Pod does not download updates.</p>
          </section>
          <section class="subject-pod-section">
            <h3>System Tabs</h3>
            <p class="hint">Required tabs open on every launch and cannot be closed. Optional System Tabs may be closed during the current Pod session.</p>
            <div id="subjectSystemTabs" class="subject-tab-list"></div>
            <div class="actions"><button data-add-system-tab="true">Add System Tab</button><button class="primary" data-save-subject-pod-config="${esc(subjectId)}">Save Pod Settings</button></div>
          </section>
          <section class="subject-pod-section">
            <h3>Pods List</h3>
            <div id="subjectPodsList" class="pod-list"><div class="pod-empty">loading pods</div></div>
          </section>
        </div>`;
    }
    function renderSubjectSystemTabs(tabs = []) {
      const root = el("subjectSystemTabs");
      if (!root) return;
      root.innerHTML = tabs.map((tab, index) => `
        <div class="subject-tab-row" data-system-tab-index="${index}">
          <input data-system-tab-title value="${esc(tab.title || "")}" placeholder="Site" />
          <input data-system-tab-url value="${esc(tab.url || "")}" placeholder="https://example.com" />
          <label class="check"><input data-system-tab-required type="checkbox" ${tab.required !== false ? "checked" : ""} /> Required</label>
          <button data-remove-system-tab="${index}" aria-label="remove system tab">X</button>
          <input data-system-tab-id type="hidden" value="${esc(tab.id || uid())}" />
        </div>`).join("") || `<div class="pod-empty">no system tabs configured</div>`;
    }
    function podLastSeen(value) {
      if (!value) return "Not activated";
      const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
      if (seconds < 60) return `${seconds} sec ago`;
      if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
      if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`;
      return `${Math.floor(seconds / 86400)} days ago`;
    }
    function renderSubjectPods() {
      const root = el("subjectPodsList");
      if (!root) return;
      const active = subjectPodState.instances.map(item => ({ ...item, kind: "instance" }));
      root.innerHTML = active.map(item => {
        const online = String(item.status || "").toLowerCase() === "active";
        return `
        <button class="pod-row" data-open-pod-kind="${item.kind}" data-open-pod-id="${esc(item.id)}">
          <strong>${esc(item.login || item.name)}</strong><span class="pod-status"><i class="status-spinner ${online ? "" : "frozen"}"></i>${online ? "Online" : "Offline"}</span><span>Last seen: ${esc(podLastSeen(item.last_seen_at))}</span>
        </button>`;
      }).join("") || `<div class="pod-empty">no activated pods</div>`;
    }
    async function loadSubjectWorkspace(subjectId) {
      window.clearTimeout(subjectProxyAutosaveTimer);
      subjectProxyAutosaveGeneration += 1;
      const [config, pods] = await Promise.all([api(`/v1/subjects/${encodeURIComponent(subjectId)}/pod-config`), api(`/v1/subjects/${encodeURIComponent(subjectId)}/pods`)]);
      subjectPodState.subjectId = subjectId;
      subjectPodState.config = config;
      subjectPodState.provisioning = pods.provisioning || [];
      subjectPodState.instances = pods.instances || [];
      if (!el("subjectVlessConnection")) return;
      el("subjectVlessConnection").value = config.vless_connection || "";
      el("subjectUpdateChannel").value = config.update_channel || "stable";
      renderSubjectSystemTabs(config.system_tabs || []);
      renderSubjectPods();
    }
    function collectSubjectSystemTabs() {
      return [...document.querySelectorAll("[data-system-tab-index]")].map((row, position) => ({
        id: row.querySelector("[data-system-tab-id]").value || uid(), title: row.querySelector("[data-system-tab-title]").value.trim(),
        url: row.querySelector("[data-system-tab-url]").value.trim(), required: row.querySelector("[data-system-tab-required]").checked, position,
      })).filter(tab => tab.title || tab.url);
    }
    async function saveSubjectPodConfig(subjectId) {
      window.clearTimeout(subjectProxyAutosaveTimer);
      subjectProxyAutosaveGeneration += 1;
      await api(`/v1/subjects/${encodeURIComponent(subjectId)}/pod-config`, { method: "PUT", body: JSON.stringify({
        vless_connection: el("subjectVlessConnection").value.trim(), system_tabs: collectSubjectSystemTabs(),
        update_channel: el("subjectUpdateChannel").value,
      }) });
      await loadSubjectWorkspace(subjectId);
      recordUiAction("subject.pod_config.updated", "subject", subjectId);
    }
    function scheduleSubjectProxyAutosave(subjectId, value) {
      window.clearTimeout(subjectProxyAutosaveTimer);
      const generation = ++subjectProxyAutosaveGeneration;
      subjectProxyAutosaveTimer = window.setTimeout(async () => {
        if (subjectPodState.subjectId !== subjectId || generation !== subjectProxyAutosaveGeneration) return;
        try {
          const saved = await api(`/v1/subjects/${encodeURIComponent(subjectId)}/pod-config`, {
            method: "PUT",
            feedback: false,
            body: JSON.stringify({ vless_connection: value.trim() }),
          });
          if (generation !== subjectProxyAutosaveGeneration) return;
          subjectPodState.config = saved;
          notify("Proxy connection saved automatically.", "success");
        } catch (error) {
          if (generation === subjectProxyAutosaveGeneration) notify(error.message, "error");
        }
      }, 850);
    }
    function openPodModal(title, body) {
      el("podModalTitle").textContent = title; el("podModalBody").innerHTML = body; resetModalPosition("podModalBackdrop");
      el("podModalBackdrop").classList.add("open"); el("podModalBackdrop").setAttribute("aria-hidden", "false");
    }
    function closePodModal() { el("podModalBackdrop").classList.remove("open"); el("podModalBackdrop").setAttribute("aria-hidden", "true"); subjectPodState.selected = null; }
    function closeBackdrop(backdrop) {
      const closers = {
        updateWarningBackdrop: cancelUpdatePreparation,
        kernelTokenBackdrop: closeKernelToken,
        projectCreateModalBackdrop: closeProjectCreateModal,
        propertyModalBackdrop: closePropertyModal,
        passwordModalBackdrop: closePasswordModal,
        backupImportModalBackdrop: closeBackupImportModal,
        updateInstallModalBackdrop: closeUpdateInstallModal,
        agentLibraryModalBackdrop: closeAgentLibraryModal,
        agentRemoveModalBackdrop: closeAgentRemoveModal,
        entityDeleteModalBackdrop: closeEntityDeleteModal,
        agentApprovalModalBackdrop: closeAgentApprovalModal,
        agentCapabilityInputModalBackdrop: closeAgentCapabilityInputModal,
        podModalBackdrop: closePodModal,
      };
      closers[backdrop?.id]?.();
    }
    function openCreatePodModal(subjectId) {
      subjectPodState.subjectId = subjectId;
      openPodModal("Create Pod", `<div class="form-grid"><label class="full">Login<input id="newPodLogin" autocomplete="username" /></label><label>Password<input id="newPodPassword" type="password" autocomplete="new-password" /></label><label>Repeat Password<input id="newPodPasswordConfirm" type="password" autocomplete="new-password" /></label><label>Decoy Password <small>(optional)</small><input id="newPodDecoyPassword" type="password" autocomplete="new-password" /></label><label>Repeat Decoy Password<input id="newPodDecoyPasswordConfirm" type="password" autocomplete="new-password" /></label></div><p class="hint">The primary password opens the Subject. The optional decoy password opens a clean Pod with only the default Google search in an isolated temporary profile. Passwords are stored only as salted hashes.</p><div class="actions"><button class="primary" data-confirm-create-pod="true">Create Pod</button></div>`);
    }
    async function createPodProvisioning() {
      const login = el("newPodLogin").value.trim();
      const password = el("newPodPassword").value;
      const confirmPassword = el("newPodPasswordConfirm").value;
      const decoyPassword = el("newPodDecoyPassword").value;
      const confirmDecoyPassword = el("newPodDecoyPasswordConfirm").value;
      const progress = notify("Checking the latest verified Pod release...", "info", 0);
      let record;
      try {
        record = await api(`/v1/subjects/${encodeURIComponent(subjectPodState.subjectId)}/pods`, { method: "POST", body: JSON.stringify({ login, password, confirm_password: confirmPassword, decoy_password: decoyPassword || null, confirm_decoy_password: confirmDecoyPassword || null }) });
      } finally {
        progress?.remove();
      }
      notify(
        record.runtime_warning
          ? `Pod ${record.bundle_version} created from last-known-good runtime. ${record.runtime_warning}`
          : `Verified Pod ${record.bundle_version} selected.`,
        record.runtime_warning ? "info" : "success",
        record.runtime_warning ? 8000 : null,
      );
      const download = document.createElement("a");
      download.href = record.download_url;
      download.download = `${login || "perimetr-pod"}.zip`;
      document.body.appendChild(download); download.click(); download.remove();
      closePodModal();
      await loadSubjectWorkspace(subjectPodState.subjectId);
    }
    function podSettingsHtml(item) {
      const online = String(item.status || "").toLowerCase() === "active";
      const values = [["Login", item.login || item.name], ["Password", "Stored securely; use the form below to replace it"], ["Pod ID", item.id], ["Subject ID", item.subject_id], ["Certificate fingerprint", item.certificate_fingerprint], ["Device binding fingerprint", item.device_binding_fingerprint], ["Status", online ? "Online" : "Offline"], ["Pod version", item.pod_version], ["Last seen", item.last_seen_at || "never"], ["Last heartbeat", item.last_heartbeat_at || "never"], ["Device binding", item.device_binding_status], ["xray-core", item.xray_version], ["VLESS profile version", item.network_profile_version], ["System Tabs version", item.system_tabs_profile_version]];
      return `<div class="pod-settings-grid">${values.map(([label, value]) => `<div class="pod-setting"><small>${esc(label)}</small><strong>${esc(value ?? "")}</strong></div>`).join("")}</div>`;
    }
    function openPodItem(kind, id) {
      const item = kind === "instance" ? subjectPodState.instances.find(entry => entry.id === id) : subjectPodState.provisioning.find(entry => entry.id === id);
      if (!item) return;
      subjectPodState.selected = { kind, item };
      if (kind !== "instance") return;
      openPodModal(item.login || item.name, `${podSettingsHtml(item)}<section class="setting-group"><h3>Change Password</h3><div class="form-grid"><label>New Password<input id="podNewPassword" type="password" autocomplete="new-password" /></label><label>Repeat Password<input id="podNewPasswordConfirm" type="password" autocomplete="new-password" /></label></div><div class="actions"><button data-change-pod-password="${esc(item.id)}">Change Password</button></div></section><div class="actions"><button class="danger" data-request-revoke-pod="${esc(item.id)}">Delete Pod</button></div>`);
    }
    function requestRevokePod(id) {
      const item = subjectPodState.instances.find(entry => entry.id === id); if (!item) return;
      subjectPodState.selected = { kind: "instance", item };
      el("podModalBody").innerHTML = `<div class="pod-confirm">Delete ${esc(item.name)} from Perimetr? Its Pod ID, certificate fingerprint and device binding will be blacklisted. The local copy will stop opening after its next heartbeat.</div><div class="actions"><button class="danger" data-confirm-revoke-pod="${esc(id)}">Delete Pod</button><button data-cancel-pod-delete="true">Cancel</button></div>`;
    }
    async function refreshSubjectPodsAndModal(close = true) { if (close) closePodModal(); await loadSubjectWorkspace(subjectPodState.subjectId); }
    async function changePodPassword(id) {
      await api(`/v1/pods/${encodeURIComponent(id)}/password`, { method: "PUT", body: JSON.stringify({
        new_password: el("podNewPassword").value,
        confirm_password: el("podNewPasswordConfirm").value,
      }) });
      await refreshSubjectPodsAndModal();
    }
    function openFullscreen(title, body = "") {
      el("fullscreenTitle").textContent = title;
      el("fullscreenTitle").contentEditable = "false";
      delete el("fullscreenTitle").dataset.renameType;
      delete el("fullscreenTitle").dataset.renameId;
      el("fullscreenBody").innerHTML = body;
      el("fullscreenBody").classList.remove("entity-detail");
      el("fullscreenPanel").classList.add("open");
      el("fullscreenPanel").setAttribute("aria-hidden", "false");
      render();
    }
    function openProjectDetail(type, id) {
      const item = type === "object" ? state.objects.find(entry => entry.id === id) : type === "subject" ? state.subjects.find(entry => entry.id === id) : agentUiState.library.find(entry => entry.id === id);
      if (!item) return;
      const title = item.name;
      const actions = type === "object"
        ? `<button data-object-subject="${item.id}">Create Subject</button><button data-choose-entity-image="object" data-entity-id="${item.id}">Upload Image</button>${item.image_url ? `<button data-remove-entity-image="object" data-entity-id="${item.id}">Remove Image</button>` : ""}<button class="danger" data-request-entity-delete="object" data-entity-id="${item.id}" data-entity-name="${esc(item.name)}">Delete Object</button>`
        : `<button data-choose-entity-image="subject" data-entity-id="${item.id}">Upload Image</button>${item.image_url ? `<button data-remove-entity-image="subject" data-entity-id="${item.id}">Remove Image</button>` : ""}<button class="danger" data-request-entity-delete="subject" data-entity-id="${item.id}" data-entity-name="${esc(item.name)}">Delete Subject</button>`;
      const localBlockId = `${type}_${id}`;
      const agentBlock = type === "subject" ? { blockType: "subject", blockId: item.id } : { blockType: "", blockId: "" };
      uiState.activePropertyBlock = localBlockId;
      uiState.activeDescriptionBlock = localBlockId;
      openFullscreen(title, `
        <div class="card">
          <div class="stack">
            <div>type: <strong>${esc(type)}</strong></div>
            <div>id: <strong>${esc(item.id)}</strong></div>
          </div>
          <div class="actions" style="margin-top:14px">${actions}</div>
          <input id="entityImageInput" type="file" accept="image/png,image/jpeg,image/webp" hidden />
         </div>
         ${blockInterfaceHtml(localBlockId)}
         ${agentPanelHtml(agentBlock.blockType, agentBlock.blockId)}
         ${type === "subject" ? subjectPodWorkspaceHtml(item.id) : ""}
       `);
      el("fullscreenBody").classList.add("entity-detail");
      el("fullscreenTitle").contentEditable = "true";
      el("fullscreenTitle").dataset.renameType = type;
      el("fullscreenTitle").dataset.renameId = item.id;
      renderProperties(localBlockId);
      adjustHumanDescriptionSize();
      if (type === "subject") {
        loadAgentBlock("subject", item.id, title);
        loadSubjectWorkspace(item.id).catch(error => alert(error.message));
      }
    }
    async function normalizeEntityImage(file) {
      if (!file) throw new Error("Select an image.");
      if (file.size > 12 * 1024 * 1024) throw new Error("Image is too large. Maximum source size is 12 MB.");
      const bitmap = await createImageBitmap(file);
      const side = Math.min(bitmap.width, bitmap.height);
      const canvas = document.createElement("canvas");
      canvas.width = 256; canvas.height = 256;
      canvas.getContext("2d").drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, 256, 256);
      bitmap.close();
      return new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error("Image conversion failed.")), "image/png"));
    }
    async function uploadEntityImage(type, id, file) {
      const image = await normalizeEntityImage(file);
      const form = new FormData();
      form.append("image", image, "entity.png");
      await api(`/v1/${type === "object" ? "objects" : "subjects"}/${encodeURIComponent(id)}/image`, { method: "PUT", body: form });
      await refresh();
      notify("Image updated.", "success");
      openProjectDetail(type, id);
    }
    async function removeEntityImage(type, id) {
      await api(`/v1/${type === "object" ? "objects" : "subjects"}/${encodeURIComponent(id)}/image`, { method: "DELETE" });
      await refresh();
      notify("Image removed.", "success");
      openProjectDetail(type, id);
    }
    async function uploadOverviewBlockImage(blockId, file) {
      const image = await normalizeEntityImage(file);
      const form = new FormData();
      form.append("image", image, "overview-block.png");
      await api(`/v1/overview-blocks/${encodeURIComponent(blockId)}/image`, { method: "PUT", body: form });
      await refresh();
      notify("Image updated.", "success");
      openOverviewBlock(blockId);
    }
    async function removeOverviewBlockImage(blockId) {
      await api(`/v1/overview-blocks/${encodeURIComponent(blockId)}/image`, { method: "DELETE" });
      await refresh();
      notify("Image removed.", "success");
      openOverviewBlock(blockId);
    }
    function openProjectCreateModal() {
      resetModalPosition("projectCreateModalBackdrop");
      el("newProjectName").value = "";
      el("projectCreateModalBackdrop").classList.add("open");
      el("projectCreateModalBackdrop").setAttribute("aria-hidden", "false");
      window.setTimeout(() => el("newProjectName").focus(), 0);
    }
    function closeProjectCreateModal() {
      el("projectCreateModalBackdrop").classList.remove("open");
      el("projectCreateModalBackdrop").setAttribute("aria-hidden", "true");
    }
    async function createQuickProject() {
      const name = el("newProjectName").value.trim();
      if (!name) {
        notify("Enter a project name.", "error");
        el("newProjectName").focus();
        return;
      }
      const button = el("confirmProjectCreate");
      button.disabled = true;
      try {
        await api("/v1/objects", { method: "POST", feedback: "Project created.", body: JSON.stringify({
          name,
          kind: "workspace",
          description: "",
          tags: [],
        }) });
        closeProjectCreateModal();
        await refresh();
      } finally {
        button.disabled = false;
      }
    }
    function closeFullscreen() {
      if (agentUiState.viewingAgent) {
        const destination = agentUiState.returnContext;
        agentUiState.viewingAgent = false;
        agentUiState.activeAgentId = "";
        if (destination?.kind === "block") {
          openAgentManagedBlock(destination.title || "Agent Nodes", destination.blockType, destination.blockId);
          return;
        }
        if (destination?.kind === "project") {
          openProjectDetail(destination.projectType, destination.projectId);
          return;
        }
        agentUiState.activeBlockType = "";
        agentUiState.activeBlockId = "";
        showView("agents");
      }
      el("fullscreenPanel").classList.remove("open");
      el("fullscreenPanel").setAttribute("aria-hidden", "true");
      el("fullscreenTitle").textContent = "";
      el("fullscreenTitle").contentEditable = "false";
      el("fullscreenBody").innerHTML = "";
    }
    async function refresh() {
      const [objects, subjects, pods, agents, overviewBlocks, audit, logs, metrics, backups, correlation, runtime, updaterRuntime] = await Promise.all([
        api("/v1/objects"),
        api("/v1/subjects"),
        api("/v1/pods"),
        api("/v1/agents"),
        api("/v1/overview-blocks"),
        api("/v1/audit"),
        api("/v1/logs/audit"),
        api("/v1/system/metrics"),
        api("/v1/backups"),
        api("/v1/correlation"),
        api("/v1/settings/runtime"),
        api("/v1/updater/status"),
      ]);
      Object.assign(state, { objects, subjects, pods, agents, overviewBlocks, audit, logs: logs.entries || [], metrics, backups, runtime, updaterRuntime });

      uiState.descriptionsByBlock = correlation.descriptions_by_block || {};
      uiState.propertiesByBlock = correlation.properties_by_block || {};
      uiState.propertyLibrary = correlation.property_library || [];
      uiState.graphSettings = { ...DEFAULT_GRAPH_SETTINGS, ...(correlation.graph_settings || {}) };
      logCursors = {older: logs.older_cursor, live: logs.live_cursor};
      state.correlationPercentage = Number(correlation.correlation_percentage || clientCorrelationPercentage());
      render();
    }
    async function createObject() {
      const name = el("objectName").value.trim();
      if (!name) return alert("name is required");
      await api("/v1/objects", { method: "POST", body: JSON.stringify({
        name,
        kind: el("objectKind").value,
        description: el("objectDescription").value,
        tags: el("objectTags").value.split(",").map(x => x.trim()).filter(Boolean),
      }) });
      el("objectName").value = ""; el("objectDescription").value = ""; el("objectTags").value = "";
      await refresh();
    }
    async function createSubject(objectId = null) {
      const selectedObjectId = objectId || el("subjectObject")?.value;
      if (!selectedObjectId) return alert("create an object first");
      if (subjectConversionInFlight.has(selectedObjectId)) return;
      subjectConversionInFlight.add(selectedObjectId);
      document.querySelectorAll(`[data-object-subject="${CSS.escape(selectedObjectId)}"]`).forEach(button => button.disabled = true);
      let transformed;
      try {
        transformed = await api("/v1/subjects", { method: "POST", body: JSON.stringify({ object_id: selectedObjectId, runtime_type: "web" }) });
      } finally {
        subjectConversionInFlight.delete(selectedObjectId);
      }
      const objectBlock = `object_${selectedObjectId}`;
      const subjectBlock = `subject_${transformed.id}`;
      if (Object.hasOwn(uiState.descriptionsByBlock, objectBlock)) {
        uiState.descriptionsByBlock[subjectBlock] = uiState.descriptionsByBlock[objectBlock];
        delete uiState.descriptionsByBlock[objectBlock];
      }
      if (Object.hasOwn(uiState.propertiesByBlock, objectBlock)) {
        uiState.propertiesByBlock[subjectBlock] = uiState.propertiesByBlock[objectBlock];
        delete uiState.propertiesByBlock[objectBlock];
      }
      saveLocalState();
      await refresh();
      openProjectDetail("subject", transformed.id);
    }
    async function renameProjectFromTitle(titleElement) {
      const type = titleElement.dataset.renameType;
      const id = titleElement.dataset.renameId;
      if (!type || !id) return;
      const item = type === "object"
        ? state.objects.find(entry => entry.id === id)
        : type === "subject"
          ? state.subjects.find(entry => entry.id === id)
          : type === "agent"
            ? agentUiState.library.find(entry => entry.id === id)
            : overviewBlockById(id);
      const name = titleElement.textContent.trim();
      if (!name) {
        titleElement.textContent = item?.name || item?.display_name || "Untitled";
        return;
      }
      const previousName = item?.name || item?.display_name;
      if (name === previousName) return;
      const path = type === "agent"
        ? `/api/agents/${encodeURIComponent(id)}`
        : type === "overview_block"
          ? `/v1/overview-blocks/${encodeURIComponent(id)}`
          : `/v1/${type === "object" ? "objects" : "subjects"}/${encodeURIComponent(id)}`;
      await api(path, {
        method: "PATCH",
        body: JSON.stringify(type === "agent" ? { display_name: name } : { name }),
      });
      await refresh();
      titleElement.textContent = name;
      recordUiAction(`${type}.renamed`, type, id, { name });
    }
    function requestEntityDelete(type, id, name) {
      uiState.pendingEntityDelete = { type, id, name };
      el("entityDeleteModalTitle").textContent = `Delete ${type === "subject" ? "Subject" : "Object"}`;
      el("entityDeleteMessage").textContent = `Permanently delete ${name || id} from Perimetr? This action cannot be undone.`;
      resetModalPosition("entityDeleteModalBackdrop");
      el("entityDeleteModalBackdrop").classList.add("open");
      el("entityDeleteModalBackdrop").setAttribute("aria-hidden", "false");
    }
    function closeEntityDeleteModal() {
      el("entityDeleteModalBackdrop").classList.remove("open");
      el("entityDeleteModalBackdrop").setAttribute("aria-hidden", "true");
      uiState.pendingEntityDelete = null;
    }
    async function confirmEntityDelete() {
      const pending = uiState.pendingEntityDelete;
      if (!pending) return;
      await api(`/v1/${pending.type === "subject" ? "subjects" : "objects"}/${encodeURIComponent(pending.id)}`, { method: "DELETE" });
      closeEntityDeleteModal();
      closeFullscreen();
      await refresh();
    }
    function showView(viewName) {
      const button = document.querySelector(`.sidebar button[data-view="${viewName}"]`);
      const view = el(viewName);
      if (!button || !view) return;
      document.querySelectorAll(".sidebar button[data-view]").forEach(x => x.classList.remove("active"));
      document.querySelectorAll(".view").forEach(x => x.classList.remove("active"));
      button.classList.add("active");
      view.classList.add("active");
      el("viewTitle").textContent = button.querySelector("span")?.textContent || button.textContent;
      if (viewName === "correlationMap") requestAnimationFrame(initCorrelationMap);
      if (viewName === "agents") renderAgentsPage().catch(error => alert(error.message));
      if (viewName === "pods") loadPodsPage().catch(error => alert(error.message));
      if (viewName === "properties") renderPropertiesPage();
    }
    function filterDocumentation(query) {
      const normalized = String(query || "").trim().toLowerCase();
      let visible = 0;
      document.querySelectorAll(".documentation-content article").forEach(article => {
        const searchable = `${article.dataset.docTitle || ""} ${article.textContent || ""}`.toLowerCase();
        article.hidden = Boolean(normalized) && !searchable.includes(normalized);
        if (!article.hidden) visible += 1;
      });
      document.querySelectorAll(".documentation-nav a").forEach(link => {
        const target = document.querySelector(link.getAttribute("href"));
        link.hidden = Boolean(target?.hidden);
      });
      el("documentationEmpty").hidden = visible !== 0;
    }
    document.querySelectorAll(".nav button").forEach(button => button.addEventListener("click", () => {
      showView(button.dataset.view);
    }));
    document.querySelectorAll(".sidebar-footer button[data-view]").forEach(button => button.addEventListener("click", () => {
      showView(button.dataset.view);
    }));
    el("documentationSearch")?.addEventListener("input", event => filterDocumentation(event.currentTarget.value));
    ["graphPropertyColor", "graphEntityColor"].forEach(id => {
      el(id)?.addEventListener("input", event => {
        event.currentTarget.dataset.usesTheme = "false";
        updateGraphSettingsFromControls();
      });
    });
    [
      "graphTextThreshold", "graphNodeSize", "graphLinkThickness",
      "graphCenterForce", "graphRepelForce", "graphLinkForce", "graphLinkDistance", "graphAnimate",
    ].forEach(id => {
      el(id)?.addEventListener(id === "graphAnimate" ? "change" : "input", updateGraphSettingsFromControls);
    });
    document.addEventListener("click", async event => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      try {
        if (target.matches(".modal-backdrop.open")) { closeBackdrop(target); return; }
        if (target.dataset.chooseEntityImage && target.dataset.entityId) {
          const input = el("entityImageInput");
          input.dataset.entityType = target.dataset.chooseEntityImage;
          input.dataset.entityId = target.dataset.entityId;
          input.value = "";
          input.click();
          return;
        }
        if (target.dataset.removeEntityImage && target.dataset.entityId) {
          await removeEntityImage(target.dataset.removeEntityImage, target.dataset.entityId);
          return;
        }
        if (target.dataset.chooseOverviewImage) {
          const input = el("overviewBlockImageInput");
          input.dataset.overviewBlockId = target.dataset.chooseOverviewImage;
          input.value = "";
          input.click();
          return;
        }
        if (target.dataset.removeOverviewImage) {
          await removeOverviewBlockImage(target.dataset.removeOverviewImage);
          return;
        }
        if (target.id === "closeFullscreen") closeFullscreen();
        if (target.id === "graphToolbarToggle") toggleGraphToolbar();
        if (target.dataset.resetGraphColor) resetGraphColor(target.dataset.resetGraphColor);
        if (target.id === "closePropertyModal") closePropertyModal();
        if (target.id === "openPasswordModal") openPasswordModal();
        if (target.id === "closePasswordModal") closePasswordModal();
        if (target.id === "closeProjectCreateModal" || target.id === "cancelProjectCreate") closeProjectCreateModal();
        if (target.id === "confirmProjectCreate") await createQuickProject();
        if (target.id === "openImportBackupModal") openBackupImportModal();
        if (target.id === "closeBackupImportModal") closeBackupImportModal();
        if (target.id === "closeUpdateInstallModal" || target.id === "cancelInstallUpdate") closeUpdateInstallModal();
        if (target.id === "confirmInstallUpdate") await installUpdate();
        if (target.id === "openAgentLibraryModal") { agentUiState.libraryOnly = false; await openAgentLibraryModal(); }
        if (target.dataset.addAgentLibrary) {
          agentUiState.libraryOnly = true;
          agentUiState.activeBlockType = "";
          agentUiState.activeBlockId = "";
          await openAgentLibraryModal();
        }
        if (target.dataset.addLibraryProperty) openPropertyModal("__library__");
        const libraryProperty = target.closest("[data-edit-library-property]");
        if (libraryProperty?.dataset.editLibraryProperty !== undefined) openPropertyModal("__library__", Number(libraryProperty.dataset.editLibraryProperty));
        if (target.id === "closeAgentLibraryModal") closeAgentLibraryModal();
        if (target.id === "closeAgentApprovalModal") closeAgentApprovalModal();
        if (target.id === "closeAgentCapabilityInputModal" || target.id === "cancelAgentCapabilityInput") closeAgentCapabilityInputModal();
        if (target.id === "closeAgentRemoveModal" || target.id === "cancelRemoveAgentNode") closeAgentRemoveModal();
        if (target.id === "closeEntityDeleteModal" || target.id === "cancelEntityDelete") closeEntityDeleteModal();
        if (target.id === "closePodModal" || target.dataset.closePodAfterCreate) closePodModal();
        if (target.dataset.addSystemTab) renderSubjectSystemTabs([...collectSubjectSystemTabs(), { id: uid(), title: "", url: "", required: true, position: collectSubjectSystemTabs().length }]);
        if (target.dataset.removeSystemTab !== undefined) {
          const tabs = collectSubjectSystemTabs(); tabs.splice(Number(target.dataset.removeSystemTab), 1); renderSubjectSystemTabs(tabs);
        }
        if (target.dataset.saveSubjectPodConfig) await saveSubjectPodConfig(target.dataset.saveSubjectPodConfig);
        if (target.dataset.openCreatePod || target.dataset.createPod) openCreatePodModal(target.dataset.openCreatePod || target.dataset.createPod);
        if (target.dataset.confirmCreatePod) await createPodProvisioning();
        const podItem = target.closest("[data-open-pod-id]");
        if (podItem?.dataset.openPodId) openPodItem(podItem.dataset.openPodKind, podItem.dataset.openPodId);
        const globalPodItem = target.closest("[data-open-global-pod]");
        if (globalPodItem?.dataset.openGlobalPod) openGlobalPodItem(globalPodItem.dataset.openGlobalPod);
        if (target.dataset.savePodName) {
          await api(`/v1/pods/${encodeURIComponent(target.dataset.savePodName)}`, { method: "PATCH", body: JSON.stringify({ name: el("podInstanceName").value.trim() }) });
          await refreshSubjectPodsAndModal();
        }
        if (target.dataset.changePodPassword) await changePodPassword(target.dataset.changePodPassword);
        if (target.dataset.removePodProvisioning) {
          await api(`/v1/subjects/${encodeURIComponent(subjectPodState.subjectId)}/pods/provisioning/${encodeURIComponent(target.dataset.removePodProvisioning)}`, { method: "DELETE" });
          await refreshSubjectPodsAndModal();
        }
        if (target.dataset.requestRevokePod) requestRevokePod(target.dataset.requestRevokePod);
        if (target.dataset.cancelPodDelete && subjectPodState.selected) openPodItem(subjectPodState.selected.kind, subjectPodState.selected.item.id);
        if (target.dataset.confirmRevokePod) { await api(`/v1/pods/${encodeURIComponent(target.dataset.confirmRevokePod)}`, { method: "DELETE" }); await refreshSubjectPodsAndModal(); }
        if (target.id === "confirmEntityDelete") await confirmEntityDelete();
        if (target.id === "registerAgentNode") await registerAgentNode();
        if (target.id === "approveAgentJob") await decideAgentApproval("approve");
        if (target.id === "rejectAgentJob") await decideAgentApproval("reject");
        if (target.id === "confirmAgentCapabilityInput") await confirmAgentCapabilityInput();
        if (target.id === "confirmRemoveAgentNode" && agentUiState.pendingRemoveAgentId) await removeAgentNode(agentUiState.pendingRemoveAgentId);
        if (target.id === "saveProperty") savePropertyFromModal();
        if (target.id === "deleteProperty") deletePropertyFromModal();
        const propertyItem = target.closest(".property-item");
        if (propertyItem?.dataset.propertyIndex) {
          openPropertyModal(uiState.activePropertyBlock || "human_general", Number(propertyItem.dataset.propertyIndex));
          return;
        }
        if (target.dataset.addProperty) openPropertyModal(target.dataset.addProperty);
        if (target.dataset.libraryProperty) {
          const property = uiState.propertyLibrary.find(item => item.id === target.dataset.libraryProperty);
          if (property) {
            addPropertyToBlock(uiState.activePropertyBlock || "human_general", property);
            recordUiAction("property.attached", "overview_block", uiState.activePropertyBlock || "human_general", { property_id: property.id, key: property.key });
            closePropertyModal();
          }
        }
        const overviewTile = target.closest("[data-overview-block]");
        if (overviewTile?.dataset.overviewBlock) {
          openOverviewBlock(overviewTile.dataset.overviewBlock);
          return;
        }
        const expandable = target.closest("[data-expand]");
        if (expandable?.dataset.expand) {
          const panelName = expandable.dataset.expand;
          if (panelName === "I as human in general") openInfoPanel("I as human in general", "human_general");
          else if (panelName === "Turkey / Global sphere") openInfoPanel("Turkey / Global sphere", "turkey_global");
          else if (panelName === "Russia influence sphere") openInfoPanel("Russia influence sphere", "russia_sphere");
          else if (panelName === "Laboratory") openAgentManagedBlock("Laboratory", "laboratory", "laboratory");
          else if (panelName === "Perimetr") openAgentManagedBlock("Perimetr", "perimetr", PERIMETR_BLOCK_ID);
          else openFullscreen(panelName);
        }
        const projectCard = target.closest("[data-project-type][data-project-id]");
        if (projectCard?.dataset.projectType && projectCard.dataset.projectId) openProjectDetail(projectCard.dataset.projectType, projectCard.dataset.projectId);
        if (target.dataset.attachAgentNode) await attachAgentNode(target.dataset.attachAgentNode);
        const agentNodeItem = target.closest("[data-open-agent-node]");
        if (agentNodeItem?.dataset.openAgentNode) await openAgentNode(agentNodeItem.dataset.openAgentNode);
        const libraryAgent = target.closest("[data-open-library-agent]");
        if (libraryAgent?.dataset.openLibraryAgent) {
          agentUiState.activeBlockType = "";
          agentUiState.activeBlockId = "";
          agentUiState.activeBlockTitle = "";
          await openAgentNode(libraryAgent.dataset.openLibraryAgent);
        }
        if (target.dataset.detachAgentNode) await detachAgentNode(target.dataset.detachAgentNode);
        if (target.dataset.refreshAgentNode) await openAgentNode(target.dataset.refreshAgentNode);
        if (target.dataset.requestRemoveAgentNode) requestRemoveAgentNode(target.dataset.requestRemoveAgentNode);
        if (target.dataset.removeAgentNode) requestRemoveAgentNode(target.dataset.removeAgentNode);
        const capabilityItem = target.closest("[data-run-agent-capability]");
        if (capabilityItem?.dataset.runAgentCapability) await runAgentCapability(capabilityItem.dataset.runAgentCapability);
        const approvalItem = target.closest("[data-open-agent-approval]");
        if (approvalItem?.dataset.openAgentApproval && approvalItem.dataset.jobId) openAgentApproval(approvalItem.dataset.openAgentApproval, approvalItem.dataset.jobId);
        if (target.dataset.createProject) openProjectCreateModal();
        if (target.id === "createObject") await createObject();
        if (target.id === "createSubject") await createSubject();
        if (target.id === "applyTheme") await applyTheme();
        if (target.id === "resetTheme") previewAccent("#00A8FF");
        if (target.id === "createBackup") await createBackup();
        if (target.id === "checkForUpdates") await checkForUpdates();
        if (target.id === "installUpdate") openUpdateInstallModal();
        if (target.id === "importBackup") await importBackup();
        if (target.id === "changePassword") await changePassword();
        if (target.dataset.objectSubject) await createSubject(target.dataset.objectSubject);
        if (target.dataset.requestEntityDelete && target.dataset.entityId) requestEntityDelete(target.dataset.requestEntityDelete, target.dataset.entityId, target.dataset.entityName);
      } catch (error) {
        alert(error.message);
      }
    });
    document.addEventListener("keydown", event => {
      const target = event.target;
      if (target instanceof HTMLElement && target.id === "newProjectName" && event.key === "Enter") {
        event.preventDefault();
        createQuickProject().catch(error => notify(error.message, "error"));
        return;
      }
      if (target instanceof HTMLElement && target.id === "fullscreenTitle" && event.key === "Enter") {
        event.preventDefault();
        target.blur();
      }
    });
    document.addEventListener("focusout", event => {
      const target = event.target;
      if (!(target instanceof HTMLElement) || target.id !== "fullscreenTitle" || !target.dataset.renameType) return;
      renameProjectFromTitle(target).catch(error => alert(error.message));
    });
    document.addEventListener("pointerover", event => {
      const target = event.target instanceof HTMLElement
        ? event.target.closest("button, a.button, input, select, textarea, .overview-tile, .project-card, .property-item, .library-item, .agent-node-row, .capability-card, .approval-card")
        : null;
      if (target instanceof HTMLElement && !target.classList.contains("human-description")) {
        applySafeHoverScale(target);
      }
    });
    document.addEventListener("mousedown", event => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.closest("button, input, select, textarea, a")) return;
      const head = target.closest(".modal-head");
      if (!head) return;
      const modal = head.closest(".property-modal, .settings-modal, .agent-modal");
      if (!(modal instanceof HTMLElement)) return;
      const rect = modal.getBoundingClientRect();
      modal.style.position = "fixed";
      modal.style.left = `${rect.left}px`;
      modal.style.top = `${rect.top}px`;
      modal.style.transform = "none";
      modalDrag.modal = modal;
      modalDrag.offsetX = event.clientX - rect.left;
      modalDrag.offsetY = event.clientY - rect.top;
      event.preventDefault();
    });
    document.addEventListener("mousemove", event => {
      const modal = modalDrag.modal;
      if (!modal) return;
      const rect = modal.getBoundingClientRect();
      const left = Math.max(8, Math.min(window.innerWidth - rect.width - 8, event.clientX - modalDrag.offsetX));
      const top = Math.max(8, Math.min(window.innerHeight - rect.height - 8, event.clientY - modalDrag.offsetY));
      modal.style.left = `${left}px`;
      modal.style.top = `${top}px`;
    });
    document.addEventListener("mouseup", () => {
      modalDrag.modal = null;
    });
    document.addEventListener("input", event => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.id === "humanDescription") {
        uiState.descriptionsByBlock[uiState.activeDescriptionBlock || "human_general"] = target.value;
        adjustHumanDescriptionSize();
        saveLocalState();
      }
      if (target.id === "subjectVlessConnection" && subjectPodState.subjectId) {
        scheduleSubjectProxyAutosave(subjectPodState.subjectId, target.value);
      }
      if (target.id === "agentLibrarySearch") renderAgentLibraryList();
      if (target.id === "agentsPageSearch") renderAgentsPageList();
      if (target.id === "podsPageSearch") renderPodsPage();
      if (target.id === "propertiesPageSearch") renderPropertiesPage();
      if (target.id === "propertyType") updatePropertyModalMode();
    });
    document.addEventListener("dragstart", event => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.matches(".nav button[data-view]")) {
        uiState.draggedNavView = target.dataset.view || "";
        target.classList.add("dragging");
        event.dataTransfer?.setData("application/x-perimetr-nav", uiState.draggedNavView);
      }
      if (target.matches(".metric[data-metric-id]")) {
        uiState.draggedMetricId = target.dataset.metricId || "";
        target.classList.add("dragging");
        event.dataTransfer?.setData("application/x-perimetr-metric", uiState.draggedMetricId);
      }
      if (target.dataset.propertyIndex !== undefined) {
        uiState.draggedPropertyIndex = Number(target.dataset.propertyIndex);
        target.classList.add("dragging");
        event.dataTransfer?.setData("text/plain", target.dataset.propertyIndex);
      }
      if (target.dataset.agentDragIndex !== undefined) {
        agentUiState.draggedAgentIndex = Number(target.dataset.agentDragIndex);
        target.classList.add("dragging");
        event.dataTransfer?.setData("application/x-perimetr-agent-index", target.dataset.agentDragIndex);
      }
      if (target.dataset.agentLibraryDragIndex !== undefined) {
        agentUiState.draggedLibraryAgentIndex = Number(target.dataset.agentLibraryDragIndex);
        target.classList.add("dragging");
        event.dataTransfer?.setData("application/x-perimetr-agent-library-index", target.dataset.agentLibraryDragIndex);
      }
      if (target.dataset.libraryPropertyIndex !== undefined) {
        uiState.draggedLibraryPropertyIndex = Number(target.dataset.libraryPropertyIndex);
        target.classList.add("dragging");
        event.dataTransfer?.setData("application/x-perimetr-property-library-index", target.dataset.libraryPropertyIndex);
      }
      if (target.dataset.libraryProperty) {
        event.dataTransfer?.setData("application/x-perimetr-library-property", target.dataset.libraryProperty);
      }
    });
    document.addEventListener("dragend", event => {
      const target = event.target;
      if (target instanceof HTMLElement) target.classList.remove("dragging");
      uiState.draggedPropertyIndex = null;
      uiState.draggedNavView = "";
      uiState.draggedMetricId = "";
      uiState.draggedLibraryPropertyIndex = null;
      agentUiState.draggedAgentIndex = null;
      agentUiState.draggedLibraryAgentIndex = null;
      clearDropIndicators();
    });
    document.addEventListener("dragover", event => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const navTarget = target.closest(".nav button[data-view]");
      if (navTarget && uiState.draggedNavView) { event.preventDefault(); showDropIndicator(navTarget, isDropAfter(event, navTarget)); return; }
      const metricTarget = target.closest(".metric[data-metric-id]");
      if (metricTarget && uiState.draggedMetricId) { event.preventDefault(); showDropIndicator(metricTarget, isMetricDropAfter(event, metricTarget)); return; }
      const agentTarget = target.closest("[data-agent-index]");
      if (agentTarget && agentUiState.draggedAgentIndex !== null) { event.preventDefault(); showDropIndicator(agentTarget, isDropAfter(event, agentTarget)); return; }
      const agentLibraryTarget = target.closest("[data-agent-library-index]");
      if (agentLibraryTarget && agentUiState.draggedLibraryAgentIndex !== null) { event.preventDefault(); showDropIndicator(agentLibraryTarget, isDropAfter(event, agentLibraryTarget)); return; }
      const propertyTarget = target.closest("[data-property-index]");
      if (propertyTarget && (uiState.draggedPropertyIndex !== null || uiState.draggedLibraryPropertyIndex !== null)) { event.preventDefault(); showDropIndicator(propertyTarget, isDropAfter(event, propertyTarget)); return; }
      const propertyLibraryTarget = target.closest("[data-library-property-index]");
      if (propertyLibraryTarget && uiState.draggedLibraryPropertyIndex !== null) { event.preventDefault(); showDropIndicator(propertyLibraryTarget, isDropAfter(event, propertyLibraryTarget)); return; }
      const propertyList = target.closest(".property-list");
      if (propertyList && (uiState.draggedPropertyIndex !== null || uiState.draggedLibraryPropertyIndex !== null)) { event.preventDefault(); showDropIndicator(propertyList, false); return; }
      if (target.closest(".agent-node-list")) event.preventDefault();
    });
    document.addEventListener("drop", event => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const navTarget = target.closest(".nav button[data-view]");
      const draggedView = event.dataTransfer?.getData("application/x-perimetr-nav") || uiState.draggedNavView;
      if (navTarget && draggedView) {
        const dragged = document.querySelector(`.nav button[data-view="${draggedView}"]`);
        if (dragged && dragged !== navTarget) {
          navTarget.parentElement?.insertBefore(dragged, isDropAfter(event, navTarget) ? navTarget.nextSibling : navTarget);
          persistOrder("navigation", [...document.querySelectorAll(".nav button[data-view]")].map(item => item.dataset.view));
          updateNavNumbers();
          recordUiAction("navigation.reordered", "sidebar", "navigation", {}, {}, false);
        }
        clearDropIndicators();
        event.preventDefault();
        return;
      }
      const metricTarget = target.closest(".metric[data-metric-id]");
      const draggedMetricId = event.dataTransfer?.getData("application/x-perimetr-metric") || uiState.draggedMetricId;
      if (metricTarget && draggedMetricId) {
        const dragged = document.querySelector(`.metric[data-metric-id="${draggedMetricId}"]`);
        if (dragged && dragged !== metricTarget) {
          metricTarget.parentElement?.insertBefore(dragged, isMetricDropAfter(event, metricTarget) ? metricTarget.nextSibling : metricTarget);
          persistOrder("dashboard", [...document.querySelectorAll(".dashboard-metrics .metric[data-metric-id]")].map(item => item.dataset.metricId));
          recordUiAction("dashboard.metrics.reordered", "dashboard", "metrics");
        }
        clearDropIndicators(); event.preventDefault(); return;
      }
      const agentLibraryItem = target.closest("[data-agent-library-index]");
      if (agentLibraryItem && agentUiState.draggedLibraryAgentIndex !== null) {
        event.preventDefault();
        const after = isDropAfter(event, agentLibraryItem);
        clearDropIndicators();
        reorderAgentLibrary(agentUiState.draggedLibraryAgentIndex, Number(agentLibraryItem.dataset.agentLibraryIndex), after).catch(error => alert(error.message));
        return;
      }
      const agentItem = target.closest("[data-agent-index]");
      if (agentItem && agentUiState.draggedAgentIndex !== null) {
        event.preventDefault();
        const after = isDropAfter(event, agentItem);
        clearDropIndicators();
        reorderAgentNodes(agentUiState.draggedAgentIndex, Number(agentItem.dataset.agentIndex), after).catch(error => alert(error.message));
        return;
      }
      const propertyLibraryItem = target.closest("[data-library-property-index]");
      if (propertyLibraryItem && uiState.draggedLibraryPropertyIndex !== null) {
        event.preventDefault();
        const after = isDropAfter(event, propertyLibraryItem);
        clearDropIndicators();
        reorderPropertyLibrary(uiState.draggedLibraryPropertyIndex, Number(propertyLibraryItem.dataset.libraryPropertyIndex), after);
        return;
      }
      const list = target.closest(".property-list");
      if (!list) return;
      event.preventDefault();
      const blockId = uiState.activePropertyBlock || "human_general";
      const libraryId = event.dataTransfer?.getData("application/x-perimetr-library-property");
      if (libraryId) {
        const property = uiState.propertyLibrary.find(item => item.id === libraryId);
        if (property) {
          const destination = target.closest(".property-item");
          const destinationIndex = destination
            ? Number(destination.dataset.propertyIndex) + (isDropAfter(event, destination) ? 1 : 0)
            : null;
          addPropertyToBlock(blockId, property, destinationIndex);
          recordUiAction("property.attached", "overview_block", blockId, { property_id: property.id, key: property.key });
        }
        clearDropIndicators();
        return;
      }
      const from = uiState.draggedPropertyIndex;
      const item = target.closest(".property-item");
      if (from === null || item?.dataset.propertyIndex === undefined) return;
      const to = Number(item.dataset.propertyIndex);
      const items = [...(uiState.propertiesByBlock[blockId] || [])];
      uiState.propertiesByBlock[blockId] = moveOrderedItem(items, from, to, isDropAfter(event, item));
      clearDropIndicators();
      saveLocalState();
      renderProperties(blockId);
    });
    document.addEventListener("change", async event => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.id === "entityImageInput") {
        try {
          await uploadEntityImage(target.dataset.entityType, target.dataset.entityId, target.files?.[0]);
        } catch (error) {
          notify(error.message, "error");
        }
        return;
      }
      if (target.id === "overviewBlockImageInput") {
        try {
          await uploadOverviewBlockImage(target.dataset.overviewBlockId, target.files?.[0]);
        } catch (error) {
          notify(error.message, "error");
        }
        return;
      }
      if (target.id === "humanDescription") {
        recordUiAction("description.updated", "overview_block", uiState.activeDescriptionBlock || "human_general");
      }
    });
