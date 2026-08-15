from __future__ import annotations


def build_core_index_html() -> str:
    template = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>perimetr</title>
  <style>
    :root {{
      --dark: #000000;
      --light: #ffffff;
      --accent: #00a8ff;
      --line: color-mix(in srgb, var(--light) 50%, transparent);
      --line-mid: color-mix(in srgb, var(--light) 75%, transparent);
      --line-outer: var(--light);
      --muted: #9a9a9a;
      --surface: #050505;
      --surface-2: #0b0b0b;
      --danger: #ff4d4d;
      --ok: #2dff9a;
      --sidebar-width: 242px;
      --border-base: 1px;
      --border-mid: 1px;
      --border-outer: 1px;
    }}
    * {{ box-sizing: border-box; scrollbar-width: none; }}
    *::-webkit-scrollbar {{ width: 0; height: 0; display: none; }}
    [hidden] {{ display: none !important; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--dark);
      color: var(--light);
      font-family: Consolas, "Cascadia Mono", "Segoe UI Mono", monospace;
      letter-spacing: 0;
    }}
    button, input, textarea, select {{ font: inherit; }}
    button, a.button {{
      min-height: 36px;
      border: var(--border-base) solid var(--line);
      background: var(--dark);
      color: var(--light);
      padding: 0 10px;
      text-decoration: none;
      cursor: pointer;
      transform-origin: center;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: background-color .16s ease, border-color .16s ease, color .16s ease, transform .16s ease;
    }}
    button:hover, a.button:hover {{
      background: color-mix(in srgb, var(--dark) 90%, var(--light) 10%);
      border-color: var(--accent);
      color: var(--accent);
      transform: scale(var(--hover-scale-x, 1.03), var(--hover-scale-y, 1.03));
    }}
    button:active:not(:disabled), a.button:active {{
      transform: scale(.985);
      transition-duration: 60ms;
    }}
    button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible {{
      outline: 1px solid var(--accent);
      outline-offset: 2px;
    }}
    button:disabled {{ opacity: .45; cursor: wait; transform: none; }}
    button.primary, a.primary {{ border-color: var(--line); color: var(--accent); }}
    button.danger {{ border-color: var(--line); color: #ff8d8d; }}
    input, textarea, select {{
      width: 100%;
      border: var(--border-base) solid var(--line);
      background: var(--dark);
      color: var(--light);
      padding: 8px;
      transform-origin: center;
      transition: background-color .16s ease, border-color .16s ease, color .16s ease, transform .16s ease;
    }}
    input:hover, textarea:hover, select:hover,
    input:focus, textarea:focus, select:focus {{
      background: color-mix(in srgb, var(--dark) 90%, var(--light) 10%);
      border-color: var(--accent);
      color: var(--accent);
      transform: scale(var(--hover-scale-x, 1.03), var(--hover-scale-y, 1.03));
      outline: none;
    }}
    input[type="color"] {{
      height: 38px;
      padding: 2px;
    }}
    textarea {{ min-height: 88px; resize: vertical; }}
    .sidebar-zone {{
      position: fixed;
      inset: 0 auto 0 0;
      width: 18px;
      z-index: 20;
    }}
    .sidebar {{
      position: fixed;
      inset: 0 auto 0 0;
      width: var(--sidebar-width);
      transform: translateX(-100%);
      transition: transform .18s ease;
      background: var(--dark);
      border-right: var(--border-outer) solid var(--line-outer);
      z-index: 30;
      display: grid;
      grid-template-rows: 88px minmax(0, 1fr) auto;
    }}
    body.sidebar-fixed .sidebar,
    body.sidebar-auto .sidebar:hover,
    body.sidebar-auto .sidebar-zone:hover + .sidebar {{
      transform: translateX(0);
    }}
    .brand {{
      width: 100%;
      min-height: 88px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 18px;
      color: var(--accent);
      font-weight: 900;
      font-size: 30px;
      line-height: 1;
    }}
    .nav {{
      display: grid;
      align-content: start;
      gap: 4px;
      min-height: 0;
      padding: 18px 10px;
    }}
    .nav button {{
      width: 100%;
      min-height: 42px;
      position: relative;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      border-color: transparent;
      background: transparent;
      text-align: left;
      padding: 8px 10px;
      transform-origin: left center;
    }}
    .nav button.active {{
      border-color: var(--accent);
      color: var(--accent);
    }}
    .nav button.active::before {{
      content: "";
      position: absolute;
      inset: 7px auto 7px -11px;
      width: 2px;
      background: var(--accent);
    }}
    .nav button small {{ color: var(--muted); }}
    .nav button.dragging {{ opacity: .45; }}
    .sidebar-footer {{
      padding: 18px;
      display: grid;
      gap: 9px;
      justify-items: start;
    }}
    .sidebar-footer > button {{ width: 100%; text-align: left; }}
    .sidebar-footer > button.active {{ border-color: var(--accent); color: var(--accent); }}
    .sidebar-footer form {{ margin: 0; }}
    .sidebar-footer form button {{ width: 140px; }}
    .drop-before,
    .drop-after {{ position: relative; }}
    .drop-before::before,
    .drop-after::after {{
      content: "";
      position: absolute;
      left: 4px;
      right: 4px;
      height: 1px;
      background: var(--accent);
      box-shadow: 0 0 4px color-mix(in srgb, var(--accent) 70%, transparent);
      z-index: 20;
      pointer-events: none;
    }}
    .drop-before::before {{ top: -6px; }}
    .drop-after::after {{ bottom: -6px; }}
    .app {{
      min-height: 100vh;
      padding: 18px 24px 24px 42px;
    }}
    body.sidebar-fixed .app {{
      padding-left: calc(var(--sidebar-width) + 24px);
    }}
    .top {{
      display: flex;
      align-items: center;
      justify-content: flex-start;
      gap: 12px;
      margin-bottom: 16px;
    }}
    h1 {{ margin: 0; font-size: 22px; font-weight: 700; color: var(--accent); }}
    #viewTitle {{ text-transform: uppercase; }}
    h2 {{ margin: 0 0 10px; font-size: 14px; color: var(--accent); }}
    h3 {{ margin: 0 0 8px; font-size: 13px; color: var(--light); }}
    .muted {{ color: var(--muted); }}
    .view {{ display: none; }}
    .view.active {{ display: grid; gap: 14px; }}
    .grid3 {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .two {{ display: grid; grid-template-columns: 0.92fr 1.08fr; gap: 14px; }}
    .card {{
      border: var(--border-outer) solid var(--line-outer);
      background: var(--dark);
      padding: 12px;
    }}
    .metric {{
      min-height: 0;
      aspect-ratio: 3 / 1;
      cursor: grab;
    }}
    .metric.dragging {{ cursor: grabbing; opacity: .45; }}
    .metric-value {{
      font-size: 24px;
      margin: 14px 0 8px;
      color: var(--light);
    }}
    .metric-lines {{
      display: grid;
      gap: 6px;
      font-size: 12px;
    }}
    .metric-lines div {{
      display: flex;
      justify-content: space-between;
      border-bottom: 1px dotted var(--line);
      padding-bottom: 2px;
    }}
    .dashboard-metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .correlation-page {{
      position: relative;
      height: calc(100vh - 78px);
      min-height: 520px;
      overflow: hidden;
      border: var(--border-outer) solid var(--line-outer);
      background: var(--dark);
    }}
    #correlationCanvas {{
      display: block;
      width: 100%;
      height: 100%;
      cursor: grab;
      touch-action: none;
    }}
    #correlationCanvas.dragging {{ cursor: grabbing; }}
    .correlation-toolbar {{
      position: absolute;
      top: 12px;
      right: 12px;
      z-index: 2;
      width: min(280px, calc(100% - 24px));
      max-height: calc(100% - 24px);
      overflow-y: auto;
      scrollbar-width: none;
      border: var(--border-mid) solid var(--line-mid);
      background: color-mix(in srgb, var(--dark) 94%, transparent);
      backdrop-filter: blur(8px);
      padding: 12px;
      display: grid;
      gap: 12px;
    }}
    .correlation-toolbar::-webkit-scrollbar {{ width: 0; }}
    .correlation-toolbar section {{
      border-top: var(--border-base) solid var(--line);
      padding-top: 10px;
      display: grid;
      gap: 8px;
    }}
    .correlation-toolbar section:first-child {{ border-top: 0; padding-top: 0; }}
    .graph-toolbar-toggle {{ display: inline-flex; width: 100%; }}
    .correlation-toolbar.collapsed {{ overflow: hidden; }}
    .correlation-toolbar.collapsed section,
    .correlation-toolbar.collapsed .graph-legend {{ display: none; }}
    .correlation-toolbar h2 {{ margin: 0; }}
    .correlation-control {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 6px 10px;
      align-items: center;
      color: var(--light);
      font-size: 12px;
    }}
    .correlation-control input[type="range"] {{
      grid-column: 1 / -1;
      padding: 0;
      height: 20px;
      accent-color: var(--accent);
      transform: none;
    }}
    .correlation-colors {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
    .correlation-color-field {{ display: grid; gap: 6px; min-width: 0; }}
    .correlation-color-field label {{ font-size: 12px; }}
    .correlation-color-field button {{ min-height: 28px; width: 100%; }}
    .correlation-score {{
      position: absolute;
      left: 14px;
      top: 14px;
      z-index: 2;
      color: var(--accent);
      font-size: 18px;
      font-weight: 700;
      pointer-events: none;
    }}
    .graph-legend {{ display: flex; gap: 14px; color: var(--muted); font-size: 11px; }}
    .graph-legend span::before {{
      content: "";
      display: inline-block;
      width: 8px;
      height: 8px;
      margin-right: 6px;
      background: var(--legend-color);
    }}
    .overview-page {{
      height: calc(100vh - 78px);
      border: var(--border-base) solid transparent;
      display: grid;
      grid-template-rows: 1fr;
      overflow: hidden;
    }}
    .overview-frame {{
      border: var(--border-outer) solid var(--line-outer);
      padding: 14px;
      min-height: 0;
      height: 100%;
      overflow: hidden;
    }}
    .overview-grid {{
      display: grid;
      grid-template-columns: minmax(360px, 1fr) minmax(360px, 1fr);
      gap: 14px;
      height: 100%;
    }}
    .overview-left {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      grid-template-rows: 92px 92px minmax(220px, 1fr);
      gap: 12px;
    }}
    .overview-tile {{
      border: var(--border-mid) solid var(--line-mid);
      background: var(--dark);
      color: var(--light);
      padding: 14px;
      min-height: 84px;
      display: flex;
      align-items: center;
      text-align: left;
      cursor: pointer;
      transform-origin: center;
      transition: background-color .16s ease, border-color .16s ease, color .16s ease, transform .16s ease;
    }}
    .overview-tile:hover {{
      background: color-mix(in srgb, var(--dark) 90%, var(--light) 10%);
      border-color: var(--accent);
      color: var(--accent);
      transform: scale(var(--hover-scale-x, 1.03), var(--hover-scale-y, 1.03));
    }}
    .overview-tile > span {{
      font-size: 18px;
      line-height: 1.2;
    }}
    .overview-tile.has-image {{
      background-position: center;
      background-repeat: no-repeat;
      background-size: cover;
    }}
    .overview-tile.has-image > span {{
      padding: 7px 9px;
      background: rgba(0, 0, 0, .76);
      color: var(--light);
    }}
    .wide {{ grid-column: 1 / -1; }}
    .tall {{ min-height: 220px; align-items: center; justify-content: center; }}
    .projects-tile {{
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 16px;
      min-height: 100%;
      align-items: stretch;
      cursor: default;
    }}
    .projects-tile:hover {{
      background: var(--dark);
      border-color: var(--line-mid);
      color: var(--light);
      transform: none;
    }}
    .project-card-grid {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
      align-content: start;
      align-self: start;
      overflow-y: auto;
      scrollbar-width: none;
      padding: 2px 4px 8px 2px;
      max-height: calc(100vh - 168px);
    }}
    .project-card-grid::-webkit-scrollbar {{
      width: 0;
      height: 0;
    }}
    .project-card {{
      aspect-ratio: 3 / 4;
      min-width: 0;
      border: var(--border-base) solid var(--line);
      background: var(--dark);
      color: var(--light);
      padding: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      cursor: pointer;
      overflow-wrap: anywhere;
      transform-origin: center;
      transition: background-color .16s ease, border-color .16s ease, color .16s ease, transform .16s ease;
    }}
    .project-card.has-image {{
      background-position: center;
      background-repeat: no-repeat;
      background-size: cover;
    }}
    .project-card-title {{
      max-width: 100%;
      padding: 6px 8px;
      background: rgba(0, 0, 0, .76);
      color: var(--light);
      overflow-wrap: anywhere;
    }}
    .project-card:hover {{
      background: color-mix(in srgb, var(--dark) 90%, var(--light) 10%);
      border-color: var(--accent);
      color: var(--accent);
      transform: scale(var(--hover-scale-x, 1.03), var(--hover-scale-y, 1.03));
      position: relative;
      z-index: 3;
    }}
    .project-card.plus {{
      font-size: 32px;
    }}
    .stack {{ display: grid; gap: 10px; }}
    .row {{
      border: var(--border-mid) solid var(--line-mid);
      padding: 10px;
      display: grid;
      gap: 8px;
      background: var(--surface);
    }}
    .row-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
    }}
    .title {{ font-weight: 800; }}
    .pill {{
      border: var(--border-base) solid var(--line);
      color: var(--muted);
      font-size: 12px;
      padding: 2px 6px;
      text-transform: uppercase;
    }}
    .pill.ok {{ color: var(--ok); border-color: var(--line); }}
    .pill.bad {{ color: var(--danger); border-color: var(--line); }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 7px 14px;
      color: var(--muted);
      font-size: 12px;
    }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .form-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .full {{ grid-column: 1 / -1; }}
    .settings-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 24px;
    }}
    .settings-card {{ padding: 20px; }}
    .setting-group {{
      border: var(--border-mid) solid var(--line-mid);
      padding: 18px;
      display: grid;
      gap: 16px;
      margin-top: 18px;
    }}
    .setting-group h3 {{
      color: var(--accent);
      margin: 0;
    }}
    .hint {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }}
    .log-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 12px;
    }}
    .logger-card {{ padding: 0; }}
    .logger-card .log-head {{
      min-height: 52px;
      margin: 0;
      padding: 10px 18px;
      border-bottom: var(--border-mid) solid var(--line-mid);
      gap: 18px;
    }}
    .logger-card .log-head h2 {{
      margin: 0;
      color: var(--accent);
      font-size: 15px;
      font-weight: 500;
    }}
    .logger-card .log-head a {{
      min-height: 32px;
      margin-left: auto;
      padding: 6px 12px;
    }}
    .logger-card .setting-group {{
      margin: 0;
      border: 0;
      padding: 18px;
      gap: 18px;
    }}
    .updater-result {{
      display: grid;
      grid-template-columns: auto minmax(140px, 1fr);
      gap: 8px 16px;
      border-top: var(--border-base) solid var(--line);
      padding-top: 14px;
    }}
    .updater-result span {{ color: var(--muted); }}
    .updater-result a {{ grid-column: 1 / -1; color: var(--accent); }}
    .updater-availability {{
      border: var(--border-base) solid var(--line);
      padding: 12px 14px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }}
    .updater-availability strong {{
      display: block;
      color: var(--light);
      margin-bottom: 3px;
    }}
    .updater-availability.is-available strong {{ color: var(--ok); }}
    .updater-availability.is-unavailable strong {{ color: var(--danger); }}
    .log-stream {{
      max-height: 460px;
      overflow: auto;
      padding: 0;
      color: var(--light);
      line-height: 1.45;
      scrollbar-width: none;
      display: grid;
      align-content: start;
    }}
    .log-stream::-webkit-scrollbar {{
      width: 0;
      height: 0;
    }}
    .log-entry {{
      display: grid;
      grid-template-columns: 62px minmax(150px, 1.2fr) minmax(130px, 1fr) minmax(100px, .8fr) 150px;
      gap: 12px;
      min-height: 36px;
      padding: 8px 0;
      align-items: center;
      font-size: 11px;
    }}
    .log-entry .log-status {{
      font-weight: 700;
      text-transform: uppercase;
    }}
    .log-entry .log-status.success {{ color: #2dff9a; }}
    .log-entry .log-status.error {{ color: #ff4d4d; }}
    .log-entry time {{ color: var(--muted); text-align: right; white-space: nowrap; }}
    .accent {{
      color: var(--accent);
    }}
    label.check {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
    }}
    label.check input {{ width: auto; }}
    .fullscreen-panel {{
      position: fixed;
      inset: 0;
      z-index: 100;
      background: var(--dark);
      color: var(--light);
      display: none;
      padding: 26px 32px;
    }}
    .fullscreen-panel.open {{
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 18px;
    }}
    .fullscreen-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: var(--border-mid) solid var(--line-mid);
      padding-bottom: 14px;
    }}
    .fullscreen-head h2 {{
      margin: 0;
      font-size: 22px;
      text-transform: uppercase;
    }}
    .fullscreen-head h2[contenteditable="true"] {{
      min-width: min(560px, calc(100vw - 120px));
      cursor: text;
      outline: none;
      border-bottom: var(--border-base) solid transparent;
    }}
    .fullscreen-head h2[contenteditable="true"]:focus {{
      border-bottom-color: var(--accent);
    }}
    .fullscreen-body {{
      overflow: auto;
      display: grid;
      grid-auto-rows: max-content;
      align-content: start;
      gap: 14px;
      scrollbar-width: none;
    }}
    .fullscreen-body::-webkit-scrollbar {{ width: 0; height: 0; }}
    .close-panel {{
      width: 38px;
      min-height: 38px;
      font-size: 24px;
      line-height: 1;
    }}
    .human-layout {{
      height: 100%;
      min-height: 0;
      display: grid;
      grid-template-columns: minmax(280px, 1fr) minmax(320px, 1.05fr);
      gap: 12px;
    }}
    .block-interface {{
      min-height: 815px;
      height: auto;
      border: var(--border-outer) solid var(--line-outer);
      padding: 12px;
      display: grid;
      grid-template-rows: minmax(360px, 1fr);
      gap: 14px;
    }}
    .fullscreen-body.entity-detail .block-interface {{ min-height: 658px; }}
    .human-column {{
      min-height: 0;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 12px;
    }}
    .human-column > h2 {{
      margin: 10px 0 0;
      color: var(--accent);
    }}
    .human-description {{
      width: 100%;
      height: 100%;
      min-height: 100%;
      resize: none;
      border: var(--border-base) solid transparent;
      background: transparent;
      padding: 28px 0;
      line-height: 1.35;
      color: var(--light);
      overflow: hidden;
      scrollbar-width: none;
      align-self: start;
      display: block;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }}
    .human-description:hover,
    .human-description:focus {{
      background: transparent;
      border-color: transparent;
      color: var(--light);
      transform: none;
      outline: none;
    }}
    .human-description::-webkit-scrollbar {{
      width: 0;
      height: 0;
    }}
    .property-list {{
      min-height: 0;
      border: var(--border-mid) solid var(--line-mid);
      padding: 20px 14px;
      display: grid;
      align-content: start;
      gap: 14px;
      overflow-y: auto;
      scrollbar-width: none;
      transition: border-color .16s ease;
    }}
    .property-list:hover {{
      border-color: var(--accent);
    }}
    .property-list::-webkit-scrollbar {{
      width: 0;
      height: 0;
    }}
    .property-item {{
      border: var(--border-base) solid var(--line);
      min-height: 54px;
      padding: 10px 14px;
      display: grid;
      grid-template-columns: minmax(100px, .7fr) minmax(100px, 1fr);
      gap: 12px;
      align-items: center;
      color: var(--light);
      cursor: grab;
      transition: background-color .16s ease, border-color .16s ease, color .16s ease, transform .16s ease;
    }}
    .property-item:hover {{
      background: color-mix(in srgb, var(--dark) 90%, var(--light) 10%);
      border-color: var(--accent);
      color: var(--accent);
      transform: scale(var(--hover-scale-x, 1.02), var(--hover-scale-y, 1.02));
    }}
    .property-item span {{
      justify-self: end;
      text-align: right;
      padding-right: 14px;
    }}
    .property-item.dragging {{
      opacity: .45;
    }}
    .property-add {{
      border: var(--border-base) solid var(--line);
      min-height: 54px;
      color: var(--light);
      font-size: 34px;
      display: grid;
      place-items: center;
    }}
    .property-add:hover {{
      border-color: var(--accent);
      color: var(--accent);
    }}
    .modal-backdrop {{
      position: fixed;
      inset: 0;
      z-index: 140;
      display: none;
      place-items: center;
      background: rgba(0,0,0,.35);
      backdrop-filter: blur(9px);
    }}
    .modal-backdrop.open {{
      display: grid;
    }}
    .notification-stack {{
      position: fixed;
      top: 18px;
      right: 18px;
      z-index: 300;
      width: min(410px, calc(100vw - 36px));
      display: grid;
      gap: 8px;
      pointer-events: none;
    }}
    .system-notice {{
      min-height: 44px;
      border: var(--border-base) solid var(--accent);
      background: var(--dark);
      color: var(--light);
      padding: 8px 8px 8px 12px;
      pointer-events: auto;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 30px;
      gap: 12px;
      align-items: center;
      animation: notice-in .16s ease-out;
    }}
    .system-notice.error {{ border-color: #ff4d4d; color: #ff4d4d; }}
    .system-notice.success {{ border-color: #2dff9a; color: var(--light); }}
    .system-notice.info {{ border-color: var(--accent); color: var(--light); }}
    .system-notice button {{
      width: 30px;
      min-height: 30px;
      padding: 0;
    }}
    @keyframes notice-in {{ from {{ opacity: 0; transform: translateY(-8px); }} }}
    .modal-backdrop.top {{
      place-items: center;
      padding-top: 0;
    }}
    .property-modal,
    .settings-modal {{
      width: min(760px, calc(100vw - 48px));
      max-height: min(720px, calc(100vh - 48px));
      overflow: auto;
      border: var(--border-outer) solid var(--line-outer);
      background: var(--dark);
      padding: 18px;
      display: grid;
      gap: 14px;
      position: relative;
    }}
    .update-install-modal {{ width: min(620px, calc(100vw - 48px)); }}
    .update-install-modal > .actions {{ justify-content: flex-end; }}
    .attachment-field {{
      display: none;
    }}
    .attachment-field.visible {{
      display: block;
    }}
    #saveProperty,
    #deleteProperty.visible,
    .modal-action {{
      border-color: var(--line);
      color: var(--light);
      align-items: center;
      justify-content: center;
    }}
    #saveProperty:hover,
    #deleteProperty.visible:hover,
    .modal-action:hover {{
      border-color: var(--accent);
      color: var(--accent);
    }}
    #deleteProperty {{
      display: none;
    }}
    #deleteProperty.visible {{
      display: inline-flex;
    }}
    .modal-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      cursor: move;
      user-select: none;
    }}
    .property-library {{
      border: var(--border-mid) solid var(--line-mid);
      min-height: 90px;
      padding: 10px;
      display: grid;
      gap: 8px;
    }}
    .library-item {{
      border: var(--border-base) solid var(--line);
      padding: 8px 10px;
      cursor: grab;
    }}
    .library-item:hover {{
      border-color: var(--accent);
      color: var(--accent);
    }}
    .agent-surface {{
      border: var(--border-mid) solid var(--line-mid);
      padding: 14px;
      display: grid;
      gap: 12px;
      min-height: 0;
      align-content: start;
      grid-template-rows: auto auto;
      overflow: visible;
    }}
    .agent-surface h2,
    .agent-surface h3 {{
      margin: 0;
      color: var(--accent);
    }}
    .agent-node-list {{
      display: grid;
      gap: 10px;
      align-content: start;
      min-height: 0;
      padding: 2px;
    }}
    .agent-node-row {{
      border: var(--border-base) solid var(--line);
      min-height: 58px;
      padding: 10px 12px;
      display: grid;
      grid-template-columns: minmax(180px, 1fr) auto;
      gap: 12px;
      align-items: center;
      cursor: pointer;
      transition: background-color .16s ease, border-color .16s ease, color .16s ease, transform .16s ease;
    }}
    .agent-node-main {{ display: grid; gap: 4px; min-width: 0; cursor: grab; }}
    .agent-node-main:active {{ cursor: grabbing; }}
    .agent-node-actions {{ display: flex; align-items: center; gap: 10px; }}
    .status-spinner {{
      display: inline-block;
      width: 12px;
      height: 12px;
      border: 2px solid var(--line);
      border-top-color: currentColor;
      border-radius: 50%;
      animation: status-spin .8s linear infinite;
      vertical-align: -2px;
      margin-right: 6px;
    }}
    .status-spinner.frozen {{ animation-play-state: paused; }}
    @keyframes status-spin {{ to {{ transform: rotate(360deg); }} }}
    .agent-node-row:hover {{
      background: color-mix(in srgb, var(--dark) 90%, var(--light) 10%);
      border-color: var(--accent);
      color: var(--accent);
      transform: scale(var(--hover-scale-x, 1.02), var(--hover-scale-y, 1.02));
    }}
    .agent-node-row small {{
      color: var(--muted);
      display: block;
      margin-top: 4px;
    }}
    .agent-node-row.dragging {{
      opacity: .45;
    }}
    .agent-add-button {{
      min-height: 58px;
      font-size: 32px;
      width: 100%;
    }}
    .library-page {{
      border: var(--border-outer) solid var(--line-outer);
      min-height: calc(100vh - 80px);
      padding: 18px;
      display: grid;
      align-content: start;
      gap: 12px;
    }}
    .library-page-list {{ display: grid; gap: 10px; align-content: start; }}
    .library-search {{
      width: 100%;
      min-height: 36px;
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      align-items: center;
      gap: 12px;
      border: var(--border-mid) solid var(--line-mid);
      background: var(--dark);
      color: var(--light);
      padding: 10px 12px;
      transition: border-color .16s ease, background-color .16s ease;
    }}
    .library-search:focus-within {{
      border-color: var(--accent);
      background: color-mix(in srgb, var(--dark) 90%, var(--light) 10%);
    }}
    .library-search span {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .08em;
    }}
    .library-search input {{
      min-height: 34px;
      border: 0;
      background: transparent;
      color: var(--light);
      padding: 8px 0;
      transform: none;
    }}
    .library-search input:hover,
    .library-search input:focus {{
      border: 0;
      background: transparent;
      color: var(--light);
      outline: none;
      transform: none;
    }}
    .library-property-row {{
      border: var(--border-base) solid var(--line);
      min-height: 58px;
      padding: 10px 12px;
      display: grid;
      grid-template-columns: minmax(180px, 1fr) auto;
      gap: 12px;
      align-items: center;
      cursor: pointer;
    }}
    .agent-workspace {{
      display: grid;
      grid-template-columns: minmax(280px, .75fr) minmax(360px, 1.25fr);
      gap: 12px;
      min-height: 520px;
      border: var(--border-outer) solid var(--line-outer);
      padding: 12px;
    }}
    .agent-left,
    .agent-live {{
      border: var(--border-mid) solid var(--line-mid);
      padding: 12px;
      display: grid;
      gap: 12px;
      align-content: start;
    }}
    .agent-left {{
      grid-template-rows: auto 1fr;
      min-height: 0;
    }}
    .agent-top,
    .agent-commands {{
      display: grid;
      gap: 12px;
      align-content: start;
    }}
    .agent-commands {{
      align-self: end;
    }}
    .agent-status-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
    }}
    .capability-list,
    .job-event-list,
    .approval-list {{
      display: grid;
      gap: 8px;
      align-content: start;
    }}
    .capability-card,
    .job-event,
    .approval-card {{
      border: var(--border-base) solid var(--line);
      padding: 10px;
      display: grid;
      gap: 6px;
    }}
    .capability-card strong {{
      color: var(--light);
    }}
    .capability-card:hover,
    .approval-card:hover {{
      border-color: var(--accent);
      color: var(--accent);
      background: color-mix(in srgb, var(--dark) 90%, var(--light) 10%);
      transform: scale(var(--hover-scale-x, 1.02), var(--hover-scale-y, 1.02));
    }}
    .agent-live-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
    }}
    .agent-command-preview {{
      border: var(--border-base) solid var(--line);
      padding: 12px;
      min-height: 360px;
      color: var(--muted);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: var(--surface);
      overflow: auto;
      scrollbar-width: none;
    }}
    .agent-command-preview::-webkit-scrollbar {{
      width: 0;
      height: 0;
    }}
    .subject-pod-workspace {{ border: var(--border-outer) solid var(--line-outer); display: grid; gap: 18px; padding: 18px; }}
    .subject-pod-head {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
    .subject-pod-head h2 {{ margin: 0; }}
    .subject-pod-section {{ border: var(--border-mid) solid var(--line-mid); padding: 18px; display: grid; gap: 14px; }}
    .subject-pod-section > h3 {{ margin: 0; color: var(--accent); font-size: 15px; }}
    .subject-pod-section .hint {{ margin: 0; }}
    .subject-pod-section textarea {{ min-height: 82px; resize: vertical; }}
    .subject-tab-list, .pod-list {{ display: grid; gap: 8px; }}
    .subject-tab-row {{ display: grid; grid-template-columns: 160px minmax(240px, 1fr) auto auto; gap: 8px; align-items: center; border: var(--border-base) solid var(--line); padding: 8px; }}
    .subject-tab-row input {{ min-width: 0; }}
    .pod-row {{ width: 100%; min-height: 64px; display: grid; grid-template-columns: minmax(0, 1fr) 140px 190px; gap: 14px; align-items: center; text-align: left; color: var(--light); }}
    .pod-row strong {{ overflow: hidden; text-overflow: ellipsis; }}
    .pod-row span {{ color: var(--muted); }}
    .pod-row .pod-status {{ color: var(--accent); text-transform: uppercase; display: inline-flex; align-items: center; gap: 8px; }}
    .pod-empty {{ color: var(--muted); padding: 16px 0; }}
    .pod-settings-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .pod-setting {{ border: var(--border-base) solid var(--line); padding: 10px; display: grid; gap: 4px; }}
    .pod-setting small {{ color: var(--muted); }}
    .pod-setting strong {{ overflow-wrap: anywhere; }}
    .pod-confirm {{ border: var(--border-base) solid var(--danger); padding: 12px; color: var(--light); }}
    .documentation-page {{
      border: var(--border-outer) solid var(--line-outer);
      min-height: calc(100vh - 88px);
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
    }}
    .documentation-nav {{
      border-right: var(--border-mid) solid var(--line-mid);
      padding: 20px 14px;
      align-self: stretch;
    }}
    .documentation-nav-inner {{ position: sticky; top: 18px; display: grid; gap: 18px; }}
    .documentation-nav input {{ width: 100%; }}
    .documentation-nav-group {{ display: grid; gap: 6px; }}
    .documentation-nav-group strong {{ color: var(--accent); font-size: 12px; text-transform: uppercase; }}
    .documentation-nav a {{ color: var(--muted); text-decoration: none; line-height: 1.45; padding: 4px 0; }}
    .documentation-nav a:hover {{ color: var(--accent); background: transparent; transform: none; }}
    .documentation-content {{ padding: 24px 32px 64px; min-width: 0; }}
    .documentation-content > header {{ padding-bottom: 24px; border-bottom: var(--border-mid) solid var(--line-mid); display: grid; gap: 10px; }}
    .documentation-kicker {{ color: var(--accent); text-transform: uppercase; font-size: 12px; }}
    .documentation-content > header h2 {{ margin: 0; font-size: 24px; }}
    .documentation-content > header p {{ margin: 0; color: var(--muted); line-height: 1.6; }}
    .documentation-content article {{
      display: grid;
      gap: 12px;
      padding: 28px 0;
      border-bottom: var(--border-mid) solid var(--line-mid);
      scroll-margin-top: 18px;
    }}
    .documentation-content article:last-child {{ border-bottom: 0; }}
    .documentation-page h2 {{ margin: 0; font-size: 18px; }}
    .documentation-page h3 {{ margin: 12px 0 0; color: var(--accent); font-size: 14px; }}
    .documentation-page p {{ margin: 0; color: var(--muted); line-height: 1.65; }}
    .documentation-page code {{ color: var(--light); background: var(--surface-2); padding: 2px 5px; }}
    .documentation-page pre {{ margin: 0; padding: 14px; border: var(--border-base) solid var(--line); overflow: auto; color: var(--light); line-height: 1.55; }}
    .documentation-page ul, .documentation-page ol {{ margin: 0; padding-left: 22px; color: var(--muted); line-height: 1.75; }}
    .documentation-note {{ border-left: 3px solid var(--accent); padding: 10px 12px; color: var(--muted); background: var(--surface); line-height: 1.55; }}
    .documentation-table {{ width: 100%; border-collapse: collapse; color: var(--muted); }}
    .documentation-table th, .documentation-table td {{ padding: 10px; border: var(--border-base) solid var(--line); text-align: left; vertical-align: top; }}
    .documentation-table th {{ color: var(--light); }}
    .documentation-empty {{ color: var(--muted); padding: 24px 0; }}
    @media (max-width: 1200px) {{
      .documentation-page {{ grid-template-columns: 200px minmax(0, 1fr); }}
    }}
    @media (max-width: 1000px) {{
      .grid3, .dashboard-metrics, .two, .overview-grid, .overview-left, .project-card-grid, .settings-grid, .form-grid, .human-layout, .agent-workspace, .pod-settings-grid {{
        grid-template-columns: 1fr;
      }}
      .subject-tab-row, .pod-row {{ grid-template-columns: 1fr; }}
      .overview-left {{ grid-template-rows: none; }}
      .app {{ padding-left: 28px; }}
      body.sidebar-fixed .app {{ padding-left: 28px; }}
      .documentation-page {{ grid-template-columns: 1fr; }}
      .documentation-nav {{ border-right: 0; border-bottom: var(--border-mid) solid var(--line-mid); }}
      .documentation-nav-inner {{ position: static; }}
      .documentation-nav-group {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .documentation-nav-group strong {{ grid-column: 1 / -1; }}
      .documentation-content {{ padding: 20px; }}
    }}
    @media (max-width: 700px) {{
      .correlation-toolbar {{ width: min(260px, calc(100% - 24px)); }}
    }}
  </style>
</head>
<body class="sidebar-auto">
  <div id="notificationStack" class="notification-stack" aria-live="polite"></div>
  <div class="sidebar-zone" aria-hidden="true"></div>
  <aside class="sidebar">
    <div class="brand" aria-label="PERIMETR"><span aria-hidden="true">P</span><span aria-hidden="true">E</span><span aria-hidden="true">R</span><span aria-hidden="true">I</span><span aria-hidden="true">M</span><span aria-hidden="true">E</span><span aria-hidden="true">T</span><span aria-hidden="true">R</span></div>
    <nav class="nav">
      <button draggable="true" data-view="dashboard" class="active"><span>Dashboard</span><small>01</small></button>
      <button draggable="true" data-view="overview"><span>Overview</span><small>02</small></button>
      <button draggable="true" data-view="correlationMap"><span>Correlation Map</span><small>03</small></button>
      <button draggable="true" data-view="agents"><span>Agents</span><small>04</small></button>
      <button draggable="true" data-view="pods"><span>Pods</span><small>05</small></button>
      <button draggable="true" data-view="properties"><span>Properties</span><small>06</small></button>
      <button draggable="true" data-view="settings"><span>Settings</span><small>07</small></button>
    </nav>
    <div class="sidebar-footer">
      <button data-view="documentation">Documentation</button>
      <form method="post" action="/v1/auth/logout">
        <button type="submit">Logout</button>
      </form>
    </div>
  </aside>

  <main class="app">
    <div class="top">
      <h1 id="viewTitle">Dashboard</h1>
    </div>

    <section id="dashboard" class="view active">
      <div class="grid3 dashboard-metrics">
        <div class="card metric" draggable="true" data-metric-id="cpu">
          <h2>CPU Usage</h2>
          <div class="metric-value" id="cpuPercent">-</div>
        </div>
        <div class="card metric" draggable="true" data-metric-id="ram">
          <h2>RAM Usage</h2>
          <div class="metric-lines">
            <div><span>used</span><strong id="ramUsed">-</strong></div>
            <div><span>total</span><strong id="ramTotal">-</strong></div>
            <div><span>percent</span><strong id="ramPercent">-</strong></div>
          </div>
        </div>
        <div class="card metric" draggable="true" data-metric-id="disk">
          <h2>Server Disk</h2>
          <div class="metric-lines">
            <div><span>used</span><strong id="diskUsed">-</strong></div>
            <div><span>total</span><strong id="diskTotal">-</strong></div>
            <div><span>percent</span><strong id="diskPercent">-</strong></div>
          </div>
        </div>
        <div class="card metric" draggable="true" data-metric-id="correlation">
          <h2>System Correlation</h2>
          <div class="metric-value" id="correlationPercent">0%</div>
          <div class="metric-lines"><div><span>shared properties</span><strong id="correlationState">none</strong></div></div>
        </div>
        <div class="card metric" draggable="true" data-metric-id="uptime">
          <h2>System Uptime</h2>
          <div class="metric-value" id="systemUptime">-</div>
        </div>
      </div>
    </section>

    <section id="agents" class="view">
      <div class="library-page">
        <label class="library-search"><span>SEARCH</span><input id="agentsPageSearch" type="search" placeholder="Search agents" aria-label="Search agents" autocomplete="off" /></label>
        <div id="agentsPageList" class="library-page-list"></div>
        <button class="agent-add-button" data-add-agent-library="true" aria-label="add agent">+</button>
      </div>
    </section>

    <section id="pods" class="view">
      <div class="library-page">
        <label class="library-search"><span>SEARCH</span><input id="podsPageSearch" type="search" placeholder="Search pods" aria-label="Search pods" autocomplete="off" /></label>
        <div id="podsPageList" class="library-page-list"></div>
      </div>
    </section>

    <section id="properties" class="view">
      <div class="library-page">
        <label class="library-search"><span>SEARCH</span><input id="propertiesPageSearch" type="search" placeholder="Search properties" aria-label="Search properties" autocomplete="off" /></label>
        <div id="propertiesPageList" class="library-page-list"></div>
        <button class="agent-add-button" data-add-library-property="true" aria-label="add property">+</button>
      </div>
    </section>

    <section id="overview" class="view">
      <div class="overview-page">
        <div class="overview-frame">
          <div class="overview-grid">
            <div class="overview-left">
              <button class="overview-tile wide" data-overview-block="human_general"><span>I as human in general</span></button>
              <button class="overview-tile" data-overview-block="turkey_global"><span>Turkey / Global sphere</span></button>
              <button class="overview-tile" data-overview-block="russia_sphere"><span>Russia influence sphere</span></button>
              <button class="overview-tile tall" data-overview-block="laboratory_block"><span>Laboratory</span></button>
              <button class="overview-tile tall" data-overview-block="perimetr_block"><span>Perimetr</span></button>
            </div>
            <div class="overview-tile projects-tile">
              <span>Projects</span>
              <div class="project-card-grid" id="projectCards"></div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section id="correlationMap" class="view">
      <div class="correlation-page" id="correlationPage">
        <canvas id="correlationCanvas" aria-label="Correlation graph"></canvas>
        <div class="correlation-score" id="correlationMapScore">0% correlation</div>
        <aside class="correlation-toolbar collapsed">
          <button id="graphToolbarToggle" class="graph-toolbar-toggle" aria-expanded="false">Expand Controls</button>
          <section>
            <h2>Display</h2>
            <div class="correlation-colors">
              <div class="correlation-color-field">
                <label>Properties<input id="graphPropertyColor" type="color" value="#ffffff" /></label>
                <button type="button" data-reset-graph-color="property">Reset</button>
              </div>
              <div class="correlation-color-field">
                <label>Entities<input id="graphEntityColor" type="color" value="#00a8ff" /></label>
                <button type="button" data-reset-graph-color="entity">Reset</button>
              </div>
            </div>
            <label class="correlation-control"><span>Text fade</span><output id="graphTextThresholdValue">15%</output><input id="graphTextThreshold" type="range" min="0" max="1" step="0.05" value="0.15" /></label>
            <label class="correlation-control"><span>Node size</span><output id="graphNodeSizeValue">6</output><input id="graphNodeSize" type="range" min="2" max="18" step="1" value="6" /></label>
            <label class="correlation-control"><span>Link thickness</span><output id="graphLinkThicknessValue">1</output><input id="graphLinkThickness" type="range" min="0.5" max="6" step="0.5" value="1" /></label>
            <label class="check"><input id="graphAnimate" type="checkbox" checked /> Animate</label>
          </section>
          <section>
            <h2>Forces</h2>
            <label class="correlation-control"><span>Center force</span><output id="graphCenterForceValue">0.006</output><input id="graphCenterForce" type="range" min="0" max="0.05" step="0.001" value="0.006" /></label>
            <label class="correlation-control"><span>Repel force</span><output id="graphRepelForceValue">1800</output><input id="graphRepelForce" type="range" min="0" max="3000" step="50" value="1800" /></label>
            <label class="correlation-control"><span>Link force</span><output id="graphLinkForceValue">0.025</output><input id="graphLinkForce" type="range" min="0" max="0.15" step="0.005" value="0.025" /></label>
            <label class="correlation-control"><span>Link distance</span><output id="graphLinkDistanceValue">150</output><input id="graphLinkDistance" type="range" min="30" max="300" step="5" value="150" /></label>
          </section>
          <div class="graph-legend"><span style="--legend-color:var(--light)">property</span><span style="--legend-color:var(--accent)">entity</span></div>
        </aside>
      </div>
    </section>

    <section id="settings" class="view">
      <div class="settings-grid">
        <div class="card settings-card">
          <h2>Appearance</h2>
          <div class="setting-group">
            <h3>Color correction</h3>
            <div class="form-grid">
              <label>dark<input id="colorDark" type="color" value="#000000" /></label>
              <label>light<input id="colorLight" type="color" value="#ffffff" /></label>
              <label>accent<input id="colorAccent" type="color" value="#00a8ff" /></label>
            </div>
            <p class="hint">These colors are applied to the core UI and login page.</p>
            <div class="actions">
              <button id="applyTheme" class="primary">Apply</button>
              <button id="resetTheme">Reset</button>
            </div>
          </div>
          <div class="setting-group">
            <h3>Left menu</h3>
            <label class="check"><input id="sidebarAuto" type="checkbox" checked /> Auto open and hide sidebar on mouse hover</label>
            <p class="hint">Disable this option to keep the left menu fixed open.</p>
          </div>
        </div>
        <div class="card settings-card">
          <h2>Security</h2>
          <div class="setting-group">
            <h3>Password</h3>
            <p class="hint">Password is used for the direct browser login. Minimum length is 8 symbols.</p>
            <div class="actions">
              <button id="openPasswordModal" class="primary">Change Password</button>
            </div>
          </div>
        </div>
        <div class="card settings-card">
          <h2>Backup</h2>
          <div class="setting-group">
            <h3>System snapshot</h3>
            <p class="hint">Creates a full system snapshot with objects, subjects, pods, agents, commands, audit, logs and settings.</p>
            <div class="actions">
              <button id="createBackup" class="primary">Create Backup</button>
            </div>
          </div>
          <div class="setting-group">
            <h3>Restore</h3>
            <p class="hint">Import a backup zip created by this Perimetr instance.</p>
            <div class="actions">
              <button id="openImportBackupModal">Import Backup</button>
            </div>
          </div>
        </div>
        <div class="card settings-card">
          <h2>Updater</h2>
          <div class="setting-group">
            <h3>Release discovery</h3>
            <p class="hint">Refreshes Register, reads repositories.perimetr.url and checks matching GitHub releases. The local updater verifies and applies the selected release only on this VPS.</p>
            <div id="updaterAvailability" class="updater-availability">Updater status is loading.</div>
            <div class="actions">
              <button id="checkForUpdates" class="primary">Check for Updates</button>
              <button id="installUpdate" class="primary" hidden disabled>Install Update</button>
            </div>
            <div id="updaterResult" class="updater-result" hidden>
              <span>Installed</span><strong id="updaterInstalled">-</strong>
              <span>Available</span><strong id="updaterAvailable">-</strong>
              <span>Status</span><strong id="updaterStatus">-</strong>
              <a id="updaterReleaseLink" href="#" target="_blank" rel="noreferrer" hidden>Open Release Notes</a>
            </div>
            <div id="updaterJob" class="updater-result" hidden>
              <span>Job</span><strong id="updaterJobId">-</strong>
              <span>State</span><strong id="updaterJobState">-</strong>
              <span>Message</span><strong id="updaterJobMessage">-</strong>
            </div>
          </div>
        </div>
        <div class="card settings-card logger-card">
          <div class="log-head">
            <h2>LOGGER</h2>
            <a class="button" href="/v1/logs/download">Download Logs Zip</a>
          </div>
          <div class="setting-group">
            <h3>Action stream</h3>
            <p class="hint">Shows actions from the browser UI and API operations with time, responsible actor and target.</p>
            <p id="loggerRetention" class="hint">Retention limits are loading.</p>
            <div id="loggerStream" class="log-stream">not loaded</div>
          </div>
        </div>
      </div>
    </section>

    <section id="documentation" class="view">
      <div class="documentation-page">
        <aside class="documentation-nav">
          <div class="documentation-nav-inner">
            <input id="documentationSearch" type="search" placeholder="Search documentation" aria-label="search documentation" />
            <div class="documentation-nav-group">
              <strong>Get Started</strong>
              <a href="#docs-introduction">Introduction</a>
              <a href="#docs-requirements">System Requirements</a>
              <a href="#docs-installation">Installation</a>
              <a href="#docs-first-run">First Run</a>
            </div>
            <div class="documentation-nav-group">
              <strong>Operate</strong>
              <a href="#docs-concepts">Core Concepts</a>
              <a href="#docs-workflow">Objects And Subjects</a>
              <a href="#docs-correlation">Properties And Correlation</a>
              <a href="#docs-agents">Agent Nodes</a>
              <a href="#docs-pods">Pods</a>
            </div>
            <div class="documentation-nav-group">
              <strong>Maintain</strong>
              <a href="#docs-settings">Settings</a>
              <a href="#docs-backup">Backup And Restore</a>
              <a href="#docs-api">API And Logger</a>
              <a href="#docs-troubleshooting">Troubleshooting</a>
            </div>
          </div>
        </aside>
        <div class="documentation-content">
          <header>
            <span class="documentation-kicker">Perimetr / Operator Guide</span>
            <h2>Welcome To Perimetr</h2>
            <p>A practical guide to installing, configuring and operating the logical core, its entities, shared data, Agent Nodes and Subject Pods.</p>
          </header>
          <article id="docs-introduction" data-doc-title="Introduction architecture purpose">
            <h2>Introduction</h2>
            <p>Perimetr is the authoritative logical and operational core. It stores Objects, Subjects, shared Properties, correlation state, Agent Nodes, Pod identities, security deny-lists, audit events and backups.</p>
            <p>Laboratory and desktop Gate clients are external modules. They consume Perimetr contracts but are not required to operate the core web interface.</p>
            <div class="documentation-note">Start with an Object when you only need to describe an entity. Transform it into a Subject when the entity requires a controlled browser Pod, network route or attached Agent Nodes.</div>
          </article>
          <article id="docs-requirements" data-doc-title="System requirements Docker CPU RAM storage ports">
            <h2>System Requirements</h2>
            <h3>Required Software</h3>
            <ul><li>Docker Engine with Docker Compose v2, or Docker Desktop on Windows.</li><li>A modern Chromium or Firefox browser for the web UI.</li><li>PowerShell on Windows or a POSIX shell on Linux for operator commands.</li></ul>
            <h3>Practical Baseline</h3>
            <table class="documentation-table"><thead><tr><th>Resource</th><th>Minimum</th><th>Recommended</th></tr></thead><tbody><tr><td>CPU</td><td>2 logical cores</td><td>4 logical cores</td></tr><tr><td>RAM</td><td>2 GB available</td><td>4 GB available</td></tr><tr><td>Storage</td><td>10 GB</td><td>20 GB plus backup retention</td></tr></tbody></table>
            <p>Perimetr listens on <code>PERIMETR_LISTEN_PORT</code> (default <code>18080</code>). PostgreSQL and Redis stay inside the Compose network and are not published on the host.</p>
          </article>
          <article id="docs-installation" data-doc-title="Installation Docker Compose Windows Linux start stop restart update logs">
            <h2>Installation</h2>
            <h3>1. Prepare Configuration</h3>
            <p>Open <code>perimetr/.env</code>. Set a strong entry password, signing secret and a public URL reachable by every Pod and Agent Node. Do not use <code>localhost</code> as the public URL for remote clients.</p>
            <pre>PERIMETR_ENTRY_PASSWORD=replace-with-a-strong-password
PERIMETR_POD_SIGNING_SECRET=replace-with-a-random-secret
PERIMETR_PUBLIC_URL=https://perimetr.example.com</pre>
            <h3>2. Build And Start</h3>
            <pre>cd perimetr
docker compose up -d --build</pre>
            <h3>3. Check Runtime</h3>
            <pre>docker compose ps
docker compose logs -f perimetr-api</pre>
            <p>Open <code>http://localhost:18080</code> for a local installation, or the configured public HTTPS endpoint for a remote installation.</p>
            <h3>Service Commands</h3>
            <pre># Restart only the API
docker compose restart perimetr-api

# Stop the complete stack
docker compose down

# Rebuild after a source update
docker compose up -d --build</pre>
          </article>
          <article id="docs-first-run" data-doc-title="First run login password sidebar security">
            <h2>First Run</h2>
            <ol><li>Sign in with the username and password configured in <code>.env</code>.</li><li>Open <code>Settings / Security</code> and replace the initial password.</li><li>Open <code>Settings / Appearance</code> and select dark, light and accent colors.</li><li>Create a full backup before adding production identities.</li></ol>
            <p>The left menu opens on hover by default. Disable <code>Auto open and hide sidebar on mouse hover</code> to keep it fixed. Navigation tabs can be dragged into a preferred order; Documentation and Logout remain in the bottom operator group.</p>
          </article>
          <article id="docs-concepts" data-doc-title="Core concepts dashboard overview entities ids properties">
            <h2>Core Concepts</h2>
            <table class="documentation-table"><thead><tr><th>Element</th><th>Responsibility</th></tr></thead><tbody><tr><td>Object</td><td>A described entity without controlled Pod access.</td></tr><tr><td>Subject</td><td>An Object transformed in place while preserving its ID, with Pod and Agent integration.</td></tr><tr><td>Property</td><td>A shared entity referenced by one or more blocks. Editing it updates every reference.</td></tr><tr><td>Agent Node</td><td>A persistent remote execution identity attached to one or more entities.</td></tr><tr><td>Pod</td><td>A device-bound browser gate belonging to one Subject.</td></tr></tbody></table>
            <p>Entity IDs use a stable 16-character uppercase identifier. Renaming an entity changes its visible name but never its ID or existing relations.</p>
          </article>
          <article id="docs-workflow" data-doc-title="Object Subject create transform rename image delete description">
            <h2>Objects And Subjects</h2>
            <h3>System Overview Cards</h3>
            <p>The five permanent Overview cards can be renamed by editing the title in their full-screen view. Each card also accepts an uploaded image as its Overview background; removing the image restores the themed card surface.</p>
            <h3>Create And Describe</h3>
            <ol><li>Open <code>Overview</code> and select the plus card in Projects.</li><li>Open the new Object card.</li><li>Edit the title directly in the upper-left heading.</li><li>Write the Description and attach shared Properties.</li><li>Optionally upload an image; it becomes the Overview card background and Pod taskbar image.</li></ol>
            <h3>Transform Into A Subject</h3>
            <p>Select <code>Create Subject</code>. The current Object is transformed rather than duplicated, so its ID, name, image, description and Property relations remain intact.</p>
            <h3>Delete</h3>
            <p><code>Delete Object</code> and <code>Delete Subject</code> require explicit confirmation. Subject deletion also removes its active Pod configuration, so create a backup first.</p>
          </article>
          <article id="docs-correlation" data-doc-title="Properties library correlation map graph shared links score">
            <h2>Properties And Correlation</h2>
            <p>Create a Property inside an entity or in the Properties library. A Property is one shared record, not a copied template. Reordering changes only its position in a block; editing changes the shared value everywhere.</p>
            <p>Available Property types are Plain Text, Number, Date, Geo Location, Service ID, Document ID, Device ID, Phone Number, Email Address, Web Address, Network Address and Attachment.</p>
            <p>The Correlation Map draws entities in the accent color and Property values in the configured light color. Each undirected line means that the Property belongs to the entity. Node size grows slightly with its number of links.</p>
            <p>The correlation percentage is based on Properties shared by multiple entities. Display colors, node size, link thickness and graph forces affect visualization only and do not change stored relations.</p>
          </article>
          <article id="docs-agents" data-doc-title="Agent Nodes enroll heartbeat commands approval delete detach">
            <h2>Agent Nodes</h2>
            <ol><li>Enroll an Agent Node from the Agents library or attach an existing library record to a compatible entity.</li><li>Open the Agent to inspect heartbeat status, enrollment data and available commands.</li><li>Dispatch a declared command. High-risk commands wait for explicit approval before execution.</li><li>Use the card remove action to detach an Agent from one entity.</li></ol>
            <p>The Delete action inside the Agent removes it globally, clears every assignment and deny-lists its certificate identity. This does not uninstall files from the remote server; use Sindri for remote uninstall.</p>
            <div class="documentation-note">A revoked certificate cannot return through variable or certificate rotation. Revocation is checked against the persistent Agent identity and deny-list history.</div>
          </article>
          <article id="docs-pods" data-doc-title="Pods create unlock VLESS tabs required update channel revoke portable">
            <h2>Pods</h2>
            <h3>Configure A Subject</h3>
            <ol><li>Enter one valid VLESS connection in <code>Subject Network</code>. It saves automatically after typing stops and a green notice confirms the saved value.</li><li>Add System Tabs with a title and HTTPS URL.</li><li>Mark a tab Required only when it must remain open for the entire session.</li><li>Select Stable for production manifests or Beta for prerelease manifests.</li></ol>
            <p>For a VPS installation, publish the correct <code>services.perimetr.sni</code> and <code>services.perimetr.port</code> in Kernel Register before creating a Pod. Perimetr derives its public HTTPS endpoint and embeds it in the bootstrap. The SNI inside the VLESS URI belongs to the proxy server and is independent from the Perimetr API hostname.</p>
            <h3>Create And Activate</h3>
            <ol><li>Select <code>Create Pod</code>, enter a unique login and a strong primary password, then confirm it.</li><li>Optionally enter and confirm a different Decoy Password. It opens only Google Search in an isolated temporary profile; it never opens Subject System Tabs or their persistent cookies.</li><li>Perimetr reads <code>repositories.pod.url</code> from Kernel, checks the signed <code>pod-current</code> manifest and pins the exact version and SHA-256 to this provisioning record.</li><li>Extract the downloaded ZIP completely. Do not move only the EXE away from its <code>state</code> directory.</li><li>Run the login-named EXE and enter the intended credentials.</li><li>Wait for <code>Proxy verified</code>. The selected access mode then opens through the Subject proxy.</li></ol>
            <div class="documentation-note">If Kernel or the Pod repository is temporarily unavailable, Perimetr uses its verified last-known-good artifact. A factory runtime embedded in the Perimetr image is the cold-start fallback. Invalid signatures, checksum mismatches and version downgrades never replace the cache.</div>
            <p>The delivered portable is normally close to 100 MB. The roughly 430 MB unpacked Electron directory is a build-time diagnostic artifact and is not included in Pod downloads.</p>
            <p>Successful activation writes <code>pod.enrolled</code>; every successful open writes <code>pod.session.opened</code>; ongoing connectivity writes signed <code>pod.heartbeat</code> events to Logger.</p>
            <h3>Revoke</h3>
            <p><code>Delete Pod</code> stores the Pod ID, certificate fingerprint and device binding in the deny-list. A copied or previously activated executable cannot re-enroll with that identity.</p>
          </article>
          <article id="docs-settings" data-doc-title="Settings appearance colors security password logger">
            <h2>Settings</h2>
            <ul><li><strong>Appearance:</strong> changes dark, light and accent colors and controls Sidebar behavior.</li><li><strong>Security:</strong> changes the direct login password after validating the current password.</li><li><strong>Backup:</strong> creates a complete ZIP or imports a previously created system snapshot.</li><li><strong>Updater:</strong> refreshes Kernel Register and checks the Perimetr GitHub releases selected by its repository URL.</li><li><strong>Logger:</strong> displays UI and API actions with timestamp, responsible actor, target and result.</li></ul>
            <p>Color changes also apply to the login page. Reset Correlation colors independently when the graph should return to the current global light and accent colors.</p>
          </article>
          <article id="docs-backup" data-doc-title="Backup restore recovery zip agents pods denylist">
            <h2>Backup And Restore</h2>
            <h3>Create</h3><p>Select <code>Create Backup</code>. The current snapshot downloads immediately and includes entities, images, shared Properties, correlation state, Agent identity and heartbeat data, Pod credentials and deny-lists, settings, audit data and logs.</p>
            <h3>Restore</h3><ol><li>Start an empty or replacement Perimetr node.</li><li>Keep the same public endpoint whenever existing Agents and Pods must reconnect.</li><li>Select <code>Import Backup</code> and choose the ZIP.</li><li>Confirm that Agent heartbeat and Pod status recover after import.</li></ol>
            <div class="documentation-note">Backup archives contain sensitive network and identity material. Store them encrypted and restrict access like production credentials.</div>
          </article>
          <article id="docs-api" data-doc-title="API REST logger audit retention download">
            <h2>API And Logger</h2>
            <p>Every state-changing operation available in the UI has a corresponding REST operation. The primary contracts are documented in <code>perimetr/.docs/api-contracts.md</code>. Browser actions and API actions both write audit events.</p>
            <p>Logger retention is bounded by count, age, file size and total directory size. Defaults are 240 entries, 30 days, 5 MB per JSONL file and 64 MB for the complete JSONL directory. Use <code>Download Logs Zip</code> before retention expires for long-term storage.</p>
            <pre># Health check
curl http://localhost:18080/v1/health

# Container-side test suite
docker compose exec -T perimetr-api python -m pytest -q</pre>
          </article>
          <article id="docs-troubleshooting" data-doc-title="Troubleshooting Pod unlock containers logs errors service verification trust">
            <h2>Troubleshooting</h2>
            <h3>Perimetr Does Not Open</h3><pre>docker compose ps
docker compose logs --tail=200 perimetr-api</pre>
            <h3>Pod Stays Locked</h3><ul><li>Confirm that the Pod was fully extracted and its <code>state/config/bootstrap.json</code> exists.</li><li>Confirm that <code>PERIMETR_PUBLIC_URL</code> is reachable from the device.</li><li>Check the Pod <code>logs/pod.jsonl</code> file beside the executable.</li><li>Verify the Subject VLESS route independently.</li></ul>
            <h3>A System Tab Cannot Load</h3><p>A website navigation failure is isolated to that tab and no longer revokes a valid Pod session. Proxy verification failures still lock the Pod. Correct the URL in Subject System Tabs and restart the Pod if the page remains unavailable.</p>
            <h3>A Service Requests Extra Verification</h3><p>Use a System Tab for accounts that must keep cookies across restarts. Temporary Tabs intentionally use isolated in-memory storage and look like a new browser after they close. Pod is an embedded Electron user-agent, so some identity providers may require extra verification or reject an authorization flow even when VLESS is healthy. Proxy IP reputation and sudden geography changes are independent signals; do not try to hide the embedded runtime by forging browser identity.</p>
            <h3>Safe Recovery</h3><p>Do not delete database volumes while diagnosing state. Create a backup, preserve the public endpoint and only then rebuild or restore the core.</p>
          </article>
          <div id="documentationEmpty" class="documentation-empty" hidden>No documentation sections match this search.</div>
        </div>
      </div>
    </section>
  </main>
  <div id="fullscreenPanel" class="fullscreen-panel" aria-hidden="true">
    <div class="fullscreen-head">
      <h2 id="fullscreenTitle"></h2>
      <button id="closeFullscreen" class="close-panel" aria-label="close">X</button>
    </div>
    <div id="fullscreenBody" class="fullscreen-body"></div>
  </div>
  <div id="projectCreateModalBackdrop" class="modal-backdrop top" aria-hidden="true">
    <div class="settings-modal" role="dialog" aria-modal="true" aria-labelledby="projectCreateModalTitle">
      <div class="modal-head">
        <h2 id="projectCreateModalTitle">Create Project</h2>
        <button id="closeProjectCreateModal" class="close-panel" aria-label="close">X</button>
      </div>
      <label>project name<input id="newProjectName" autocomplete="off" maxlength="255" placeholder="Project name" /></label>
      <p class="hint">A new workspace Object will be added to Projects.</p>
      <div class="actions">
        <button id="confirmProjectCreate" class="primary">Create Project</button>
        <button id="cancelProjectCreate">Cancel</button>
      </div>
    </div>
  </div>
  <div id="propertyModalBackdrop" class="modal-backdrop" aria-hidden="true">
    <div class="property-modal" role="dialog" aria-modal="true" aria-labelledby="propertyModalTitle">
      <div class="modal-head">
        <h2 id="propertyModalTitle">Create Property</h2>
        <button id="closePropertyModal" class="close-panel" aria-label="close">X</button>
      </div>
      <div class="form-grid">
        <label>type
          <select id="propertyType">
            <option value="plain_text">Plain Text</option>
            <option value="number">Number</option>
            <option value="date">Date</option>
            <option value="geo_location">Geo Location</option>
            <option value="service_id">Service ID</option>
            <option value="document_id">Document ID</option>
            <option value="device_id">Device ID</option>
            <option value="phone_number">Phone Number</option>
            <option value="email_address">Email Address</option>
            <option value="web_address">Web Address</option>
            <option value="network_address">Network Address</option>
            <option value="attachment">Attachment</option>
          </select>
        </label>
        <label>key<input id="propertyKey" placeholder="name" /></label>
        <label class="full">value<input id="propertyValue" placeholder="value" /></label>
        <label id="propertyAttachmentField" class="attachment-field">attachment<input id="propertyAttachment" type="file" accept="image/*,.pdf" /></label>
      </div>
      <div class="actions">
        <button id="saveProperty" class="primary">Create Property</button>
        <button id="deleteProperty">Delete Property</button>
      </div>
      <div>
        <h2>Library</h2>
        <div id="propertyLibrary" class="property-library"></div>
      </div>
    </div>
  </div>
  <div id="passwordModalBackdrop" class="modal-backdrop top" aria-hidden="true">
    <div class="settings-modal" role="dialog" aria-modal="true" aria-labelledby="passwordModalTitle">
      <div class="modal-head">
        <h2 id="passwordModalTitle">Change Password</h2>
        <button id="closePasswordModal" class="close-panel" aria-label="close">X</button>
      </div>
      <div class="form-grid">
        <label class="full">current password<input id="currentPassword" type="password" autocomplete="current-password" /></label>
        <label>new password<input id="newPassword" type="password" autocomplete="new-password" /></label>
        <label>repeat new password<input id="confirmPassword" type="password" autocomplete="new-password" /></label>
      </div>
      <p class="hint">Use at least 12 characters. Changing it revokes every active browser session.</p>
      <div class="actions">
        <button id="changePassword" class="modal-action">Change Password</button>
      </div>
    </div>
  </div>
  <div id="backupImportModalBackdrop" class="modal-backdrop top" aria-hidden="true">
    <div class="settings-modal" role="dialog" aria-modal="true" aria-labelledby="backupImportModalTitle">
      <div class="modal-head">
        <h2 id="backupImportModalTitle">Import Backup</h2>
        <button id="closeBackupImportModal" class="close-panel" aria-label="close">X</button>
      </div>
      <div class="form-grid">
        <label class="full">load backup zip<input id="backupImportFile" type="file" accept=".zip,application/zip" /></label>
      </div>
      <p class="hint">The archive should contain a Perimetr backup manifest and data files.</p>
      <div class="actions">
        <button id="importBackup" class="modal-action">Import Backup</button>
      </div>
    </div>
  </div>
  <div id="updateInstallModalBackdrop" class="modal-backdrop top" aria-hidden="true">
    <div class="settings-modal update-install-modal" role="dialog" aria-modal="true" aria-labelledby="updateInstallModalTitle">
      <div class="modal-head">
        <h2 id="updateInstallModalTitle">Install Perimetr Update</h2>
        <button id="closeUpdateInstallModal" class="close-panel" aria-label="close">X</button>
      </div>
      <h3 id="updateInstallQuestion">Install Perimetr update?</h3>
      <p class="hint">A full backup will be downloaded first. The local updater will verify the signed release, preserve persistent data, run health checks and automatically roll back on failure.</p>
      <div class="actions">
        <button id="cancelInstallUpdate">Cancel</button>
        <button id="confirmInstallUpdate" class="danger">Download backup and install</button>
      </div>
    </div>
  </div>
  <div id="agentLibraryModalBackdrop" class="modal-backdrop top" aria-hidden="true">
    <div class="settings-modal agent-modal" role="dialog" aria-modal="true" aria-labelledby="agentLibraryModalTitle">
      <div class="modal-head">
        <h2 id="agentLibraryModalTitle">Agent Library</h2>
        <button id="closeAgentLibraryModal" class="close-panel" aria-label="close">X</button>
      </div>
      <div class="setting-group">
        <h3>Available Agent Nodes</h3>
        <p class="hint">Agent Nodes already used somewhere in Perimetr can be attached to the currently opened block.</p>
        <label>search<input id="agentLibrarySearch" placeholder="name, status or agent id" /></label>
        <div id="agentLibraryList" class="agent-node-list"></div>
      </div>
      <div class="setting-group">
        <h3>Register New Agent Node</h3>
        <p class="hint">Enter the values printed by <code>agent-node registration</code>. Perimetr completes the enrollment handshake, verifies the identity fingerprint and attaches the Agent to the current block.</p>
        <div class="form-grid">
          <label>display name<input id="agentEnrollName" placeholder="Production Server" /></label>
          <label>agent id<input id="agentEnrollId" placeholder="uuid from agent" /></label>
          <label>domain<input id="agentEnrollDomain" placeholder="node.example.net" /></label>
          <label>port<input id="agentEnrollPort" type="number" value="7443" min="1024" max="65535" /></label>
          <label class="full">identity fingerprint<input id="agentEnrollFingerprint" placeholder="SHA256:..." /></label>
          <label class="full">enrollment token<input id="agentEnrollToken" type="password" autocomplete="off" placeholder="token printed by agent-node registration" /></label>
        </div>
        <div class="actions">
          <button id="registerAgentNode" class="primary">Register Agent Node</button>
        </div>
      </div>
    </div>
  </div>
  <div id="agentRemoveModalBackdrop" class="modal-backdrop top" aria-hidden="true">
    <div class="settings-modal agent-modal" role="dialog" aria-modal="true" aria-labelledby="agentRemoveModalTitle">
      <div class="modal-head">
        <h2 id="agentRemoveModalTitle">Remove Agent Node</h2>
        <button id="closeAgentRemoveModal" class="close-panel" aria-label="close">X</button>
      </div>
      <p class="hint">Permanently delete this Agent Node from Perimetr and remove it from every entity? The Agent Node and Sindri will remain installed on the server, but this identity will be blocked from reconnecting.</p>
      <div class="actions">
        <button id="confirmRemoveAgentNode" class="danger">Remove</button>
        <button id="cancelRemoveAgentNode">Cancel</button>
      </div>
    </div>
  </div>
  <div id="entityDeleteModalBackdrop" class="modal-backdrop top" aria-hidden="true">
    <div class="settings-modal" role="dialog" aria-modal="true" aria-labelledby="entityDeleteModalTitle">
      <div class="modal-head">
        <h2 id="entityDeleteModalTitle">Delete Entity</h2>
        <button id="closeEntityDeleteModal" class="close-panel" aria-label="close">X</button>
      </div>
      <p id="entityDeleteMessage" class="hint"></p>
      <div class="actions">
        <button id="confirmEntityDelete" class="danger">Delete</button>
        <button id="cancelEntityDelete">Cancel</button>
      </div>
    </div>
  </div>
  <div id="agentApprovalModalBackdrop" class="modal-backdrop top" aria-hidden="true">
    <div class="settings-modal agent-modal" role="dialog" aria-modal="true" aria-labelledby="agentApprovalModalTitle">
      <div class="modal-head">
        <h2 id="agentApprovalModalTitle">Approval Required</h2>
        <button id="closeAgentApprovalModal" class="close-panel" aria-label="close">X</button>
      </div>
      <div id="agentApprovalBody" class="stack"></div>
      <div class="actions">
        <button id="approveAgentJob" class="primary">Yes</button>
        <button id="rejectAgentJob" class="danger">No</button>
      </div>
    </div>
  </div>
  <div id="agentCapabilityInputModalBackdrop" class="modal-backdrop top" aria-hidden="true">
    <div class="settings-modal agent-modal" role="dialog" aria-modal="true" aria-labelledby="agentCapabilityInputModalTitle">
      <div class="modal-head">
        <h2 id="agentCapabilityInputModalTitle">Command Inputs</h2>
        <button id="closeAgentCapabilityInputModal" class="close-panel" aria-label="close">X</button>
      </div>
      <p id="agentCapabilityInputDescription" class="hint"></p>
      <div id="agentCapabilityInputFields" class="form-grid"></div>
      <div class="actions">
        <button id="confirmAgentCapabilityInput" class="primary">Run Command</button>
        <button id="cancelAgentCapabilityInput">Cancel</button>
      </div>
    </div>
  </div>
  <div id="podModalBackdrop" class="modal-backdrop top" aria-hidden="true">
    <div class="settings-modal" role="dialog" aria-modal="true" aria-labelledby="podModalTitle">
      <div class="modal-head">
        <h2 id="podModalTitle">Pod</h2>
        <button id="closePodModal" class="close-panel" aria-label="close">X</button>
      </div>
      <div id="podModalBody" class="stack"></div>
    </div>
  </div>

  <script>
    const state = {{ objects: [], subjects: [], pods: [], agents: [], overviewBlocks: [], audit: [], logs: [], metrics: null, backups: [], runtime: null, updateCheck: null, updaterRuntime: null, updateJob: null, pendingUpdateVersion: "", updateInstallPending: false, correlationPercentage: 0 }};
    const uiState = {{
      descriptionsByBlock: {{}},
      propertiesByBlock: {{}},
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
      graphSettings: {{}},
    }};
    const DEFAULT_GRAPH_SETTINGS = {{
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
    }};
    const graphState = {{
      nodes: [], links: [], canvas: null, context: null, width: 0, height: 0,
      transform: {{ x: 0, y: 0, k: 1 }}, draggedNode: null, panning: false,
      pointerX: 0, pointerY: 0, frame: 0, initialized: false,
    }};
    let correlationSyncTimer = null;
    const PERIMETR_BLOCK_ID = "5f0b6d3d90f548a9a2f1d6e9cb7f3412";
    const OVERVIEW_BLOCK_DEFAULTS = {{
      human_general: {{ name: "I as human in general", localBlockId: "human_general" }},
      turkey_global: {{ name: "Turkey / Global sphere", localBlockId: "turkey_global" }},
      russia_sphere: {{ name: "Russia influence sphere", localBlockId: "russia_sphere" }},
      laboratory_block: {{ name: "Laboratory", localBlockId: "laboratory_block", blockType: "laboratory", backendBlockId: "laboratory" }},
      perimetr_block: {{ name: "Perimetr", localBlockId: "perimetr_block", blockType: "perimetr", backendBlockId: PERIMETR_BLOCK_ID }},
    }};
    const agentUiState = {{
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
    }};
    const subjectPodState = {{ subjectId: "", config: null, provisioning: [], instances: [], selected: null }};
    const modalDrag = {{ modal: null, offsetX: 0, offsetY: 0 }};
    const headers = {{ "Content-Type": "application/json" }};
    const subjectConversionInFlight = new Set();
    let pendingApiFeedbackTimer = null;
    let subjectProxyAutosaveTimer = null;
    let subjectProxyAutosaveGeneration = 0;

    async function api(path, options = {{}}) {{
      const {{ feedback = true, ...requestOptions }} = options;
      const requestHeaders = {{ ...headers, ...(requestOptions.headers || {{}}) }};
      if (requestOptions.body instanceof FormData) delete requestHeaders["Content-Type"];
      const response = await fetch(path, {{ ...requestOptions, headers: requestHeaders }});
      const text = await response.text();
      let body = null;
      try {{ body = text ? JSON.parse(text) : null; }} catch (_) {{ body = null; }}
      if (!response.ok) throw new Error(humanizeError(body?.error?.message || body?.detail || response.statusText));
      const method = String(requestOptions.method || "GET").toUpperCase();
      if (feedback !== false && method !== "GET" && path !== "/v1/correlation") {{
        const message = typeof feedback === "string" ? feedback : method === "DELETE" ? "Deleted." : ["PUT", "PATCH"].includes(method) ? "Changes saved." : "Action completed.";
        scheduleApiFeedback(message);
      }}
      return body;
    }}
    function el(id) {{ return document.getElementById(id); }}
    function esc(value) {{ return String(value ?? "").replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c])); }}
    function humanizeError(value) {{
      const code = String(value || "operation_failed");
      const known = {{
        invalid_credentials: "Login or password is incorrect.",
        new_password_confirmation_mismatch: "Passwords do not match.",
        pod_password_confirmation_mismatch: "Passwords do not match.",
        pod_decoy_password_confirmation_required: "Enter and repeat the decoy password, or leave both fields empty.",
        pod_decoy_password_confirmation_mismatch: "Decoy passwords do not match.",
        pod_decoy_password_must_differ: "The decoy password must differ from the primary password.",
        new_password_too_short: "Password must contain at least 12 characters.",
        pod_password_too_short: "Password must contain at least 8 characters.",
        current_password_invalid: "Current password is incorrect.",
        pod_login_required: "Enter a Pod login.",
        invalid_vless_connection: "Enter a valid VLESS connection.",
        entity_image_too_large: "Image is too large. Maximum size is 4 MB.",
        entity_image_must_be_png: "The image could not be converted to PNG.",
      }};
      const translated = known[code] || code.replaceAll("_", " ");
      return translated.charAt(0).toUpperCase() + translated.slice(1);
    }}
    function notify(message, type = "error", timeout = null) {{
      if (pendingApiFeedbackTimer) {{ window.clearTimeout(pendingApiFeedbackTimer); pendingApiFeedbackTimer = null; }}
      const root = el("notificationStack");
      if (!root) return;
      const notice = document.createElement("div");
      notice.className = `system-notice ${{type}}`;
      notice.setAttribute("role", type === "error" ? "alert" : "status");
      notice.innerHTML = `<span>${{esc(humanizeError(message))}}</span><button aria-label="Dismiss notification">X</button>`;
      notice.querySelector("button").addEventListener("click", () => notice.remove());
      root.appendChild(notice);
      while (root.children.length > 5) root.firstElementChild?.remove();
      const lifetime = timeout === null ? (type === "error" ? 8000 : 4500) : timeout;
      if (lifetime) window.setTimeout(() => notice.remove(), lifetime);
      return notice;
    }}
    function scheduleApiFeedback(message) {{
      if (pendingApiFeedbackTimer) window.clearTimeout(pendingApiFeedbackTimer);
      pendingApiFeedbackTimer = window.setTimeout(() => {{
        pendingApiFeedbackTimer = null;
        notify(message, "success");
      }}, 120);
    }}
    window.alert = message => notify(message, "error");
    function fmtBytes(value) {{
      if (!value) return "0 B";
      const units = ["B", "KB", "MB", "GB", "TB"];
      let next = Number(value), idx = 0;
      while (next >= 1024 && idx < units.length - 1) {{ next /= 1024; idx += 1; }}
      return `${{next.toFixed(idx === 0 ? 0 : 1)}} ${{units[idx]}}`;
    }}
    function fmtUptime(value) {{
      const total = Math.max(0, Math.floor(Number(value) || 0));
      const days = Math.floor(total / 86400);
      const hours = Math.floor((total % 86400) / 3600);
      const minutes = Math.floor((total % 3600) / 60);
      return days > 0 ? `${{days}}d ${{hours}}h ${{minutes}}m` : `${{hours}}h ${{minutes}}m`;
    }}
    function statusClass(status) {{
      const normalized = String(status || "").toLowerCase();
      return ["active", "approved", "online", "healthy"].includes(normalized) ? "ok" : ["revoked", "disabled", "expired", "offline", "unreachable", "error"].includes(normalized) ? "bad" : "";
    }}
    function row(title, status, meta, actions = "") {{
      return `<article class="row"><div class="row-head"><div class="title">${{esc(title)}}</div>${{status ? `<span class="pill ${{statusClass(status)}}">${{esc(status)}}</span>` : ""}}</div><div class="meta">${{meta.map(x => `<span>${{esc(x)}}</span>`).join("")}}</div>${{actions ? `<div class="actions">${{actions}}</div>` : ""}}</article>`;
    }}
    function uid() {{
      return `${{Date.now().toString(36)}}-${{Math.random().toString(36).slice(2, 8)}}`;
    }}
    function applySafeHoverScale(target) {{
      if (!(target instanceof HTMLElement)) return;
      const rect = target.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const grow = Math.min(rect.width, rect.height) * 0.05;
      target.style.setProperty("--hover-scale-x", String((rect.width + grow) / rect.width));
      target.style.setProperty("--hover-scale-y", String((rect.height + grow) / rect.height));
      if (target.classList.contains("project-card")) {{
        const grid = target.closest(".project-card-grid");
        const bounds = grid?.getBoundingClientRect();
        if (bounds) {{
          const horizontal = rect.left - bounds.left < grow ? "left" : bounds.right - rect.right < grow ? "right" : "center";
          const vertical = rect.top - bounds.top < grow ? "top" : bounds.bottom - rect.bottom < grow ? "bottom" : "center";
          target.style.transformOrigin = `${{horizontal}} ${{vertical}}`;
        }}
      }}
    }}
    function modalElementFromBackdrop(backdropId) {{
      return el(backdropId)?.querySelector(".property-modal, .settings-modal, .agent-modal");
    }}
    function resetModalPosition(backdropId) {{
      const modal = modalElementFromBackdrop(backdropId);
      if (!modal) return;
      modal.style.position = "fixed";
      modal.style.left = "50%";
      modal.style.top = "50%";
      modal.style.transform = "translate(-50%, -50%)";
    }}
    function correlationPayload() {{
      return {{
        descriptions_by_block: uiState.descriptionsByBlock,
        properties_by_block: uiState.propertiesByBlock,
        property_library: uiState.propertyLibrary,
        graph_settings: {{ ...DEFAULT_GRAPH_SETTINGS, ...uiState.graphSettings }},
      }};
    }}
    function queueCorrelationSync() {{
      window.clearTimeout(correlationSyncTimer);
      correlationSyncTimer = window.setTimeout(async () => {{
        try {{
          const result = await api("/v1/correlation", {{ method: "PUT", body: JSON.stringify(correlationPayload()) }});
          state.correlationPercentage = Number(result.correlation_percentage || 0);
          renderCorrelationMetric();
        }} catch (_) {{}}
      }}, 350);
    }}
    function cleanupUnusedLibraryProperties() {{
      const used = new Set();
      Object.values(uiState.propertiesByBlock || {{}}).forEach(items => {{
        (items || []).forEach(item => {{ if (item.id) used.add(item.id); }});
      }});
      uiState.propertyLibrary = (uiState.propertyLibrary || []).filter(item => used.has(item.id));
    }}
    function loadLocalState() {{
      try {{
        const saved = JSON.parse(localStorage.getItem("perimetr.uiState") || "{{}}");
        uiState.descriptionsByBlock = saved.descriptionsByBlock || {{ human_general: saved.humanDescription || "" }};
        uiState.propertiesByBlock = saved.propertiesByBlock || {{}};
        uiState.propertyLibrary = saved.propertyLibrary || [];
        uiState.graphSettings = {{ ...DEFAULT_GRAPH_SETTINGS, ...(saved.graphSettings || {{}}) }};
      }} catch (_) {{
        uiState.descriptionsByBlock = {{}};
        uiState.propertiesByBlock = {{}};
        uiState.propertyLibrary = [];
        uiState.graphSettings = {{ ...DEFAULT_GRAPH_SETTINGS }};
      }}
      ["human_general", "turkey_global", "russia_sphere"].forEach(blockId => {{
        uiState.descriptionsByBlock[blockId] ||= "";
        uiState.propertiesByBlock[blockId] = (uiState.propertiesByBlock[blockId] || []).filter(item => !(
          item.type === "plain_text" &&
          !item.value &&
          (item.key === ["property", "1"].join(" ") || item.key === ["property", "2"].join(" "))
        ));
      }});
    }}
    function saveLocalState() {{
      localStorage.setItem("perimetr.uiState", JSON.stringify({{
        descriptionsByBlock: uiState.descriptionsByBlock,
        propertiesByBlock: uiState.propertiesByBlock,
        propertyLibrary: uiState.propertyLibrary,
        graphSettings: uiState.graphSettings,
      }}));
      queueCorrelationSync();
    }}
    function recordUiAction(action, targetType = "ui", targetId = "perimetr", payload = {{}}, result = {{}}, feedback = true) {{
      api("/v1/audit/ui", {{ method: "POST", feedback, body: JSON.stringify({{
        action,
        target_type: targetType,
        target_id: targetId,
        payload,
        result,
      }}) }}).catch(() => {{}});
    }}
    function objectById(id) {{
      return state.objects.find(item => item.id === id);
    }}
    function projectItems() {{
      const objectItems = state.objects.map(item => ({{
        id: item.id,
        type: "object",
        title: item.name,
        source: item,
      }}));
      const subjectItems = state.subjects.map(item => ({{
          id: item.id,
          type: "subject",
          title: item.name,
          source: item,
      }}));
      return [...objectItems, ...subjectItems];
    }}
    function overviewBlockById(blockId) {{
      const defaults = OVERVIEW_BLOCK_DEFAULTS[blockId];
      if (!defaults) return null;
      const stored = (state.overviewBlocks || []).find(item => item.id === blockId) || {{}};
      return {{ id: blockId, ...defaults, ...stored }};
    }}
    function renderOverviewBlocks() {{
      document.querySelectorAll("[data-overview-block]").forEach(tile => {{
        const block = overviewBlockById(tile.dataset.overviewBlock);
        if (!block) return;
        const title = tile.querySelector("span");
        if (title) title.textContent = block.name;
        tile.classList.toggle("has-image", Boolean(block.image_url));
        tile.style.backgroundImage = block.image_url ? `url('${{block.image_url}}')` : "";
        tile.setAttribute("aria-label", block.name);
      }});
    }}
    function correlationEntities() {{
      const entities = Object.keys(OVERVIEW_BLOCK_DEFAULTS).map(blockId => ({{
        id: blockId,
        label: overviewBlockById(blockId)?.name || OVERVIEW_BLOCK_DEFAULTS[blockId].name,
      }}));
      state.objects.forEach(item => entities.push({{ id: `object_${{item.id}}`, label: item.name }}));
      state.subjects.forEach(item => entities.push({{ id: `subject_${{item.id}}`, label: item.name }}));
      return entities;
    }}
    function correlationData() {{
      const entities = correlationEntities();
      const validEntities = new Set(entities.map(item => item.id));
      const properties = new Map();
      (uiState.propertyLibrary || []).forEach(item => {{ if (item.id) properties.set(item.id, item); }});
      Object.values(uiState.propertiesByBlock || {{}}).forEach(items => (items || []).forEach(item => {{
        if (item.id && !properties.has(item.id)) properties.set(item.id, item);
      }}));
      const links = [];
      Object.entries(uiState.propertiesByBlock || {{}}).forEach(([blockId, items]) => {{
        if (!validEntities.has(blockId)) return;
        const linked = new Set();
        (items || []).forEach(item => {{
          if (!item.id || linked.has(item.id)) return;
          linked.add(item.id);
          links.push({{ sourceId: `property_${{item.id}}`, targetId: blockId }});
        }});
      }});
      const propertyNodes = [...properties.values()].map(item => ({{
        id: `property_${{item.id}}`, propertyId: item.id, label: item.value || item.key || item.type || "property", type: "property",
      }}));
      const entityNodes = entities.map(item => ({{ ...item, type: "entity" }}));
      return {{ nodes: [...entityNodes, ...propertyNodes], links }};
    }}
    function clientCorrelationPercentage() {{
      const data = correlationData();
      const entityCount = data.nodes.filter(item => item.type === "entity").length;
      const properties = data.nodes.filter(item => item.type === "property");
      if (!properties.length || entityCount < 2) return 0;
      const counts = new Map(properties.map(item => [item.id, 0]));
      data.links.forEach(link => counts.set(link.sourceId, (counts.get(link.sourceId) || 0) + 1));
      const score = [...counts.values()].reduce((sum, count) => sum + Math.max(0, count - 1) / (entityCount - 1), 0) / properties.length;
      return Math.round(score * 10000) / 100;
    }}
    function renderCorrelationMetric() {{
      const percentage = Number.isFinite(state.correlationPercentage) ? state.correlationPercentage : clientCorrelationPercentage();
      if (el("correlationPercent")) el("correlationPercent").textContent = `${{percentage.toFixed(2).replace(/\.00$/, "")}}%`;
      if (el("correlationMapScore")) el("correlationMapScore").textContent = `${{percentage.toFixed(2).replace(/\.00$/, "")}}% correlation`;
      if (el("correlationState")) el("correlationState").textContent = percentage > 0 ? "connected" : "none";
    }}
    function graphColor(name, fallbackVariable) {{
      const configured = uiState.graphSettings?.[name];
      return configured || getComputedStyle(document.documentElement).getPropertyValue(fallbackVariable).trim();
    }}
    function hashPosition(value, axis) {{
      let hash = axis ? 2166136261 : 16777619;
      for (let index = 0; index < value.length; index += 1) hash = Math.imul(hash ^ value.charCodeAt(index), 16777619);
      return ((hash >>> 0) % 1000) / 1000;
    }}
    function rebuildCorrelationGraph() {{
      const previous = new Map(graphState.nodes.map(node => [node.id, node]));
      const data = correlationData();
      graphState.nodes = data.nodes.map((item, index) => {{
        const saved = previous.get(item.id);
        const angle = hashPosition(item.id, false) * Math.PI * 2;
        const radius = 80 + hashPosition(item.id, true) * Math.min(360, 35 * Math.sqrt(data.nodes.length + 1));
        return {{
          ...item,
          x: saved?.x ?? Math.cos(angle) * radius,
          y: saved?.y ?? Math.sin(angle) * radius,
          vx: saved?.vx ?? 0,
          vy: saved?.vy ?? 0,
          fixed: false,
          degree: 0,
        }};
      }});
      const nodesById = new Map(graphState.nodes.map(node => [node.id, node]));
      graphState.links = data.links.map(link => ({{ source: nodesById.get(link.sourceId), target: nodesById.get(link.targetId) }})).filter(link => link.source && link.target);
      graphState.links.forEach(link => {{ link.source.degree += 1; link.target.degree += 1; }});
      state.correlationPercentage = clientCorrelationPercentage();
      renderCorrelationMetric();
      drawCorrelationGraph();
    }}
    function resizeCorrelationCanvas() {{
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
    }}
    function stepCorrelationGraph() {{
      const settings = {{ ...DEFAULT_GRAPH_SETTINGS, ...uiState.graphSettings }};
      const nodes = graphState.nodes;
      const repel = Number(settings.repel_force);
      for (let left = 0; left < nodes.length; left += 1) {{
        const a = nodes[left];
        for (let right = left + 1; right < nodes.length; right += 1) {{
          const b = nodes[right];
          let dx = b.x - a.x, dy = b.y - a.y;
          const distanceSquared = Math.max(64, dx * dx + dy * dy);
          const distance = Math.sqrt(distanceSquared);
          const force = repel / distanceSquared;
          dx /= distance; dy /= distance;
          a.vx -= dx * force; a.vy -= dy * force;
          b.vx += dx * force; b.vy += dy * force;
        }}
      }}
      const desired = Number(settings.link_distance);
      const linkForce = Number(settings.link_force);
      graphState.links.forEach(link => {{
        let dx = link.target.x - link.source.x, dy = link.target.y - link.source.y;
        const distance = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        const force = (distance - desired) * linkForce;
        dx /= distance; dy /= distance;
        link.source.vx += dx * force; link.source.vy += dy * force;
        link.target.vx -= dx * force; link.target.vy -= dy * force;
      }});
      const center = Number(settings.center_force);
      nodes.forEach(node => {{
        if (node !== graphState.draggedNode) {{
          node.vx += -node.x * center;
          node.vy += -node.y * center;
          node.vx *= 0.82;
          node.vy *= 0.82;
          node.x += node.vx;
          node.y += node.vy;
        }}
      }});
    }}
    function graphNodeRadius(node, settings = {{ ...DEFAULT_GRAPH_SETTINGS, ...uiState.graphSettings }}) {{
      const baseRadius = Number(settings.node_size);
      const connectionGrowth = Math.min(0.25, Math.sqrt(Math.max(0, node.degree || 0)) * 0.06);
      return baseRadius * (1 + connectionGrowth);
    }}
    function drawCorrelationGraph() {{
      const context = graphState.context;
      if (!context || !graphState.width || !graphState.height) return;
      const settings = {{ ...DEFAULT_GRAPH_SETTINGS, ...uiState.graphSettings }};
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
      graphState.links.forEach(link => {{
        context.beginPath();
        context.moveTo(link.source.x, link.source.y);
        context.lineTo(link.target.x, link.target.y);
        context.stroke();
      }});
      context.globalAlpha = 1;
      const textFade = Math.max(0, Math.min(1, Number(settings.text_threshold)));
      const textOpacity = 1 - textFade;
      graphState.nodes.forEach(node => {{
        const radius = graphNodeRadius(node, settings);
        context.beginPath();
        context.arc(node.x, node.y, radius, 0, Math.PI * 2);
        context.fillStyle = node.type === "entity" ? graphColor("entity_color", "--accent") : graphColor("property_color", "--light");
        context.fill();
        if (textOpacity > 0) {{
          context.font = `${{11 / graphState.transform.k}}px Consolas, monospace`;
          context.fillStyle = style.getPropertyValue("--light").trim();
          context.globalAlpha = textOpacity;
          context.fillText(node.label, node.x + radius + 5 / graphState.transform.k, node.y + 4 / graphState.transform.k);
          context.globalAlpha = 1;
        }}
      }});
      context.restore();
    }}
    function graphPointerWorld(event) {{
      const rect = graphState.canvas.getBoundingClientRect();
      return {{
        x: (event.clientX - rect.left - graphState.width / 2 - graphState.transform.x) / graphState.transform.k,
        y: (event.clientY - rect.top - graphState.height / 2 - graphState.transform.y) / graphState.transform.k,
      }};
    }}
    function graphNodeAt(event) {{
      const point = graphPointerWorld(event);
      const settings = {{ ...DEFAULT_GRAPH_SETTINGS, ...uiState.graphSettings }};
      return [...graphState.nodes].reverse().find(node => {{
        const hitRadius = Math.max(12 / graphState.transform.k, graphNodeRadius(node, settings));
        return Math.hypot(node.x - point.x, node.y - point.y) <= hitRadius;
      }}) || null;
    }}
    function bindCorrelationCanvas() {{
      const canvas = graphState.canvas;
      if (!canvas || canvas.dataset.ready) return;
      canvas.dataset.ready = "true";
      canvas.addEventListener("pointerdown", event => {{
        canvas.setPointerCapture(event.pointerId);
        graphState.draggedNode = graphNodeAt(event);
        graphState.panning = !graphState.draggedNode;
        graphState.pointerX = event.clientX;
        graphState.pointerY = event.clientY;
        canvas.classList.add("dragging");
      }});
      canvas.addEventListener("pointermove", event => {{
        if (graphState.draggedNode) {{
          const point = graphPointerWorld(event);
          graphState.draggedNode.x = point.x;
          graphState.draggedNode.y = point.y;
          graphState.draggedNode.vx = 0;
          graphState.draggedNode.vy = 0;
        }} else if (graphState.panning) {{
          graphState.transform.x += event.clientX - graphState.pointerX;
          graphState.transform.y += event.clientY - graphState.pointerY;
        }}
        graphState.pointerX = event.clientX;
        graphState.pointerY = event.clientY;
        drawCorrelationGraph();
      }});
      const release = event => {{
        if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
        graphState.draggedNode = null;
        graphState.panning = false;
        canvas.classList.remove("dragging");
      }};
      canvas.addEventListener("pointerup", release);
      canvas.addEventListener("pointercancel", release);
      canvas.addEventListener("wheel", event => {{
        event.preventDefault();
        graphState.transform.k = Math.max(0.25, Math.min(4, graphState.transform.k * Math.exp(-event.deltaY * 0.001)));
        drawCorrelationGraph();
      }}, {{ passive: false }});
      canvas.addEventListener("dblclick", () => {{ graphState.transform = {{ x: 0, y: 0, k: 1 }}; drawCorrelationGraph(); }});
      new ResizeObserver(resizeCorrelationCanvas).observe(canvas);
    }}
    function correlationFrame() {{
      if (uiState.graphSettings.animate !== false && el("correlationMap")?.classList.contains("active")) stepCorrelationGraph();
      drawCorrelationGraph();
      graphState.frame = requestAnimationFrame(correlationFrame);
    }}
    function initCorrelationMap() {{
      const canvas = el("correlationCanvas");
      if (!canvas) return;
      graphState.canvas = canvas;
      graphState.context = canvas.getContext("2d");
      bindCorrelationCanvas();
      syncCorrelationControls();
      rebuildCorrelationGraph();
      resizeCorrelationCanvas();
      if (!graphState.frame) graphState.frame = requestAnimationFrame(correlationFrame);
    }}
    function toggleGraphToolbar() {{
      const toolbar = document.querySelector(".correlation-toolbar");
      if (!toolbar) return;
      const collapsed = toolbar.classList.toggle("collapsed");
      el("graphToolbarToggle").textContent = collapsed ? "Expand Controls" : "Collapse Controls";
      el("graphToolbarToggle").setAttribute("aria-expanded", String(!collapsed));
    }}
    function syncCorrelationControls() {{
      const settings = {{ ...DEFAULT_GRAPH_SETTINGS, ...uiState.graphSettings }};
      const values = {{
        graphTextThreshold: settings.text_threshold,
        graphNodeSize: settings.node_size,
        graphLinkThickness: settings.link_thickness,
        graphCenterForce: settings.center_force,
        graphRepelForce: settings.repel_force,
        graphLinkForce: settings.link_force,
        graphLinkDistance: settings.link_distance,
      }};
      Object.entries(values).forEach(([id, value]) => {{ if (el(id)) el(id).value = value; }});
      if (el("graphPropertyColor")) {{
        el("graphPropertyColor").value = graphColor("property_color", "--light");
        el("graphPropertyColor").dataset.usesTheme = settings.property_color ? "false" : "true";
      }}
      if (el("graphEntityColor")) {{
        el("graphEntityColor").value = graphColor("entity_color", "--accent");
        el("graphEntityColor").dataset.usesTheme = settings.entity_color ? "false" : "true";
      }}
      if (el("graphAnimate")) el("graphAnimate").checked = settings.animate !== false;
      updateCorrelationControlOutputs();
    }}
    function updateCorrelationControlOutputs() {{
      const pairs = {{
        graphTextThresholdValue: `${{Math.round(Number(el("graphTextThreshold")?.value || 0) * 100)}}%`,
        graphNodeSizeValue: el("graphNodeSize")?.value,
        graphLinkThicknessValue: el("graphLinkThickness")?.value,
        graphCenterForceValue: el("graphCenterForce")?.value,
        graphRepelForceValue: el("graphRepelForce")?.value,
        graphLinkForceValue: el("graphLinkForce")?.value,
        graphLinkDistanceValue: el("graphLinkDistance")?.value,
      }};
      Object.entries(pairs).forEach(([id, value]) => {{ if (el(id)) el(id).textContent = value; }});
    }}
    function updateGraphSettingsFromControls() {{
      uiState.graphSettings = {{
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
      }};
      updateCorrelationControlOutputs();
      saveLocalState();
      drawCorrelationGraph();
    }}
    function resetGraphColor(kind) {{
      const key = kind === "entity" ? "entity_color" : "property_color";
      uiState.graphSettings = {{ ...uiState.graphSettings, [key]: "" }};
      syncCorrelationControls();
      saveLocalState();
      drawCorrelationGraph();
    }}
    function renderMetrics() {{
      const metrics = state.metrics || {{}};
      el("cpuPercent").textContent = `${{metrics.cpu_percent ?? 0}}%`;
      el("ramUsed").textContent = fmtBytes(metrics.ram_used_bytes);
      el("ramTotal").textContent = fmtBytes(metrics.ram_total_bytes);
      el("ramPercent").textContent = `${{metrics.ram_percent ?? 0}}%`;
      el("diskUsed").textContent = fmtBytes(metrics.disk_used_bytes);
      el("diskTotal").textContent = fmtBytes(metrics.disk_total_bytes);
      el("diskPercent").textContent = `${{metrics.disk_percent ?? 0}}%`;
      el("systemUptime").textContent = fmtUptime(metrics.uptime_seconds);
      renderCorrelationMetric();
    }}
    function render() {{
      renderMetrics();
      renderOverviewBlocks();
      renderProjectCards();
      renderPodsPage();
      renderObjects();
      renderSubjects();
      if (el("subjectObject")) el("subjectObject").innerHTML = state.objects.map(item => `<option value="${{esc(item.id)}}">${{esc(item.name)}} / ${{esc(item.id)}}</option>`).join("");
      if (el("backupList")) el("backupList").innerHTML = state.backups.map(item => row(item.filename, item.entity_type, [item.created_at], `<a class="button" href="/v1/backups/${{item.id}}">Download</a>`)).join("") || `<div class="muted">no backups yet</div>`;
      const limits = state.runtime?.audit_limits;
      if (el("loggerRetention") && limits) {{
        el("loggerRetention").textContent = `Retention is capped at ${{Number(limits.max_entries).toLocaleString("en-US")}} entries, ${{limits.retention_days}} days, ${{fmtBytes(limits.max_file_bytes)}} per file and ${{fmtBytes(limits.max_total_bytes)}} total; the first reached limit wins.`;
      }}
      renderLogger();
      renderUpdaterRuntime();
      if (el("correlationMap")?.classList.contains("active")) rebuildCorrelationGraph();
    }}
    function fmtLogDate(value) {{
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value || "-");
      const part = number => String(number).padStart(2, "0");
      return `${{part(date.getDate())}}.${{part(date.getMonth() + 1)}}.${{date.getFullYear()}} ${{part(date.getHours())}}:${{part(date.getMinutes())}}:${{part(date.getSeconds())}}`;
    }}
    function logEventStatus(item) {{
      const result = item?.result || {{}};
      const searchable = `${{item?.action || ""}} ${{result.status || ""}} ${{result.error || ""}} ${{result.detail || ""}}`.toLowerCase();
      return /(error|failed|failure|denied|rejected|exception)/.test(searchable) ? "error" : "success";
    }}
    function renderLogger() {{
      const root = el("loggerStream");
      if (!root) return;
      root.innerHTML = (state.logs || []).map(item => {{
        const status = logEventStatus(item);
        return `
          <div class="log-entry">
            <span class="log-status ${{status}}">${{status}}</span>
            <span title="${{esc(item.action)}}">${{esc(item.action)}}</span>
            <span title="${{esc(item.target)}}">${{esc(item.target)}}</span>
            <span title="${{esc(item.actor)}}">${{esc(item.actor)}}</span>
            <time datetime="${{esc(item.created_at)}}">${{esc(fmtLogDate(item.created_at))}}</time>
          </div>
        `;
      }}).join("") || `<span class="muted">no log entries</span>`;
    }}
    function renderProjectCards() {{
      const root = el("projectCards");
      if (!root) return;
      const cards = projectItems().map(item => `
        <button class="project-card ${{item.source.image_url ? "has-image" : ""}}" ${{item.source.image_url ? `style="background-image:url('${{esc(item.source.image_url)}}')"` : ""}} data-project-type="${{esc(item.type)}}" data-project-id="${{esc(item.id)}}">
          <span class="project-card-title">${{esc(item.title)}}</span>
        </button>
      `);
      cards.push(`<button class="project-card plus" data-create-project="true" aria-label="create project">+</button>`);
      root.innerHTML = cards.join("");
    }}
    function propertyLabel(item) {{
      const value = item.value ? ` - ${{item.value}}` : "";
      return `${{item.key || item.type}}${{value}}`;
    }}
    function sharedProperty(item) {{
      return uiState.propertyLibrary.find(entry => entry.id === item.id) || item;
    }}
    function renderProperties(blockId) {{
      const root = el("humanProperties");
      if (!root) return;
      const items = uiState.propertiesByBlock[blockId] || [];
      root.innerHTML = items.map((item, index) => {{
        const property = sharedProperty(item);
        return `
        <div class="property-item" draggable="true" data-property-index="${{index}}">
          <strong>${{esc(property.key || property.type)}}</strong>
          <span>${{esc(property.value || "")}}</span>
        </div>
      `}}).join("") + `<button class="property-add" data-add-property="${{esc(blockId)}}">+</button>`;
    }}
    function renderPropertyLibrary() {{
      const content = uiState.propertyLibrary.map((item, index) => `
        <div class="library-item" draggable="true" data-library-property="${{esc(item.id)}}" data-library-property-index="${{index}}">
          ${{esc(propertyLabel(item))}}
        </div>
      `).join("") || `<div class="muted">library is empty</div>`;
      const root = el("propertyLibrary");
      if (root) root.innerHTML = content;
    }}
    function adjustHumanDescriptionSize() {{
      const field = el("humanDescription");
      if (!field) return;
      const length = field.value.length;
      const size = length > 720 ? 14 : length > 480 ? 16 : length > 280 ? 18 : length > 160 ? 22 : length > 86 ? 26 : 34;
      field.style.fontSize = `${{size}}px`;
      field.scrollTop = 0;
    }}
    function blockInterfaceHtml(localBlockId, blockType = "", backendBlockId = "") {{
      return `
        <div class="block-interface">
          <div class="human-layout">
            <section class="human-column">
              <h2>Description</h2>
              <textarea id="humanDescription" class="human-description" spellcheck="false">${{esc(uiState.descriptionsByBlock[localBlockId] || "")}}</textarea>
            </section>
            <section class="human-column">
              <h2>Properties</h2>
              <div id="humanProperties" class="property-list"></div>
            </section>
          </div>
        </div>
      `;
    }}
    function overviewBlockControlsHtml(blockId) {{
      const block = overviewBlockById(blockId);
      if (!block) return "";
      return `
        <div class="card overview-block-controls">
          <p class="hint">Edit the title directly above or use an image as this Overview card background.</p>
          <div class="actions">
            <button data-choose-overview-image="${{esc(blockId)}}">Upload Image</button>
            ${{block.image_url ? `<button data-remove-overview-image="${{esc(blockId)}}">Remove Image</button>` : ""}}
          </div>
          <input id="overviewBlockImageInput" type="file" accept="image/png,image/jpeg,image/webp" data-overview-block-id="${{esc(blockId)}}" hidden />
        </div>
      `;
    }}
    function openBlockInterface(title, localBlockId, blockType = "", backendBlockId = "", overviewBlockId = "") {{
      uiState.activePropertyBlock = localBlockId;
      uiState.activeDescriptionBlock = localBlockId;
      openFullscreen(title, `${{overviewBlockControlsHtml(overviewBlockId)}}${{blockInterfaceHtml(localBlockId)}}${{agentPanelHtml(blockType, backendBlockId)}}`);
      if (overviewBlockId) {{
        el("fullscreenTitle").contentEditable = "true";
        el("fullscreenTitle").dataset.renameType = "overview_block";
        el("fullscreenTitle").dataset.renameId = overviewBlockId;
      }}
      renderProperties(localBlockId);
      adjustHumanDescriptionSize();
      if (blockType && backendBlockId) loadAgentBlock(blockType, backendBlockId, title);
    }}
    function openInfoPanel(title, blockId) {{
      openBlockInterface(title, blockId, "", "", blockId);
    }}
    function agentStatusPill(status) {{
      const normal = ["online", "healthy", "active", "busy"].includes(String(status || "").toLowerCase());
      return `<span class="pill ${{statusClass(status)}}"><i class="status-spinner ${{normal ? "" : "frozen"}}"></i>${{esc(status || "UNKNOWN")}}</span>`;
    }}
    function agentPanelHtml(blockType, blockId) {{
      if (!blockType || !blockId) {{
        return "";
      }}
      return `
        <section class="agent-surface" data-agent-block-type="${{esc(blockType)}}" data-agent-block-id="${{esc(blockId)}}">
          <div><h2>Agent Nodes</h2><p class="hint">Agents are ordered top to bottom. Drag to reorder or open an Agent Node.</p></div>
          <div id="agentNodesList" class="agent-node-list"><span class="muted">loading agent nodes</span></div>
        </section>
      `;
    }}
    function openAgentManagedBlock(title, blockType, blockId) {{
      const localBlockId = `${{blockType}}_block`;
      const blockTitle = overviewBlockById(localBlockId)?.name || title;
      openBlockInterface(blockTitle, localBlockId, blockType, blockId, localBlockId);
    }}
    function openOverviewBlock(blockId) {{
      const block = overviewBlockById(blockId);
      if (!block) return;
      if (block.blockType) openAgentManagedBlock(block.name, block.blockType, block.backendBlockId);
      else openInfoPanel(block.name, block.localBlockId);
    }}
    async function loadAgentBlock(blockType, blockId, title = "") {{
      agentUiState.activeBlockType = blockType;
      agentUiState.activeBlockId = blockId;
      agentUiState.activeBlockTitle = title;
      const root = el("agentNodesList");
      if (root) root.innerHTML = `<span class="muted">loading agent nodes</span>`;
      try {{
        agentUiState.assignments = await api(`/api/blocks/${{encodeURIComponent(blockId)}}/agents?block_type=${{encodeURIComponent(blockType)}}`);
      }} catch (error) {{
        agentUiState.assignments = [];
        if (root) root.innerHTML = `<span class="muted">${{esc(error.message)}}</span>`;
        return;
      }}
      renderAgentNodes();
    }}
    function renderAgentNodes() {{
      const root = el("agentNodesList");
      if (!root) return;
      const assignments = agentUiState.assignments || [];
      root.innerHTML = assignments.map((item, index) => {{
        const agent = item.agent || {{}};
        return `
          <div class="agent-node-row" data-agent-index="${{index}}" data-agent-assignment-id="${{esc(item.id)}}">
            <div class="agent-node-main" draggable="true" data-agent-drag-index="${{index}}" data-open-agent-node="${{esc(agent.id || item.agent_id)}}">
              <strong>${{esc(agent.display_name || agent.agent_id || item.agent_id)}}</strong>
            </div>
            <div class="agent-node-actions">${{agentStatusPill(agent.status)}}<button class="danger" data-detach-agent-node="${{esc(agent.id || item.agent_id)}}" aria-label="detach agent">X</button></div>
          </div>
        `;
      }}).join("") + `<button id="openAgentLibraryModal" class="agent-add-button primary" aria-label="add agent node">+</button>`;
    }}
    async function openAgentLibraryModal() {{
      resetModalPosition("agentLibraryModalBackdrop");
      el("agentLibraryModalBackdrop").classList.add("open");
      el("agentLibraryModalBackdrop").setAttribute("aria-hidden", "false");
      await renderAgentLibrary();
    }}
    function closeAgentLibraryModal() {{
      el("agentLibraryModalBackdrop").classList.remove("open");
      el("agentLibraryModalBackdrop").setAttribute("aria-hidden", "true");
    }}
    async function renderAgentLibrary() {{
      const root = el("agentLibraryList");
      if (!root) return;
      root.innerHTML = `<span class="muted">loading library</span>`;
      agentUiState.library = await api("/api/agents/library");
      renderAgentLibraryList();
    }}
    function renderAgentLibraryList() {{
      const root = el("agentLibraryList");
      if (!root) return;
      const attached = new Set((agentUiState.assignments || []).map(item => item.agent_id));
      const query = (el("agentLibrarySearch")?.value || "").trim().toLowerCase();
      const filtered = (agentUiState.library || []).filter(agent => {{
        const haystack = `${{agent.display_name || ""}} ${{agent.agent_id || ""}} ${{agent.id || ""}} ${{agent.status || ""}}`.toLowerCase();
        return !query || haystack.includes(query);
      }});
      root.innerHTML = filtered.map(agent => `
          <div class="agent-node-row" data-agent-library-index="${{agentUiState.library.indexOf(agent)}}">
            <div class="agent-node-main" draggable="true" data-agent-library-drag-index="${{agentUiState.library.indexOf(agent)}}">
              <strong>${{esc(agent.display_name || agent.agent_id)}}</strong>
              <small>${{esc(agent.status)}} / attached to ${{esc(agentAssignmentSummary(agent))}}</small>
            </div>
          <button data-attach-agent-node="${{esc(agent.id)}}" ${{attached.has(agent.id) ? "disabled" : ""}}>Attach</button>
        </div>
      `).join("") || `<div class="muted">library is empty</div>`;
    }}
    async function attachAgentNode(agentId) {{
      if (!agentUiState.activeBlockType || !agentUiState.activeBlockId) return;
      await api(`/api/blocks/${{encodeURIComponent(agentUiState.activeBlockId)}}/agents?block_type=${{encodeURIComponent(agentUiState.activeBlockType)}}`, {{
        method: "POST",
        body: JSON.stringify({{ agent_id: agentId, created_by: "operator" }}),
      }});
      closeAgentLibraryModal();
      await loadAgentBlock(agentUiState.activeBlockType, agentUiState.activeBlockId, agentUiState.activeBlockTitle);
    }}
    async function registerAgentNode() {{
      const payload = {{
        agent_id: el("agentEnrollId").value.trim(),
        display_name: el("agentEnrollName").value.trim(),
        domain: el("agentEnrollDomain").value.trim(),
        port: Number(el("agentEnrollPort").value || 7443),
        identity_fingerprint: el("agentEnrollFingerprint").value.trim(),
        enrollment_token: el("agentEnrollToken").value.trim(),
      }};
      if (!payload.agent_id || !payload.display_name || !payload.domain || !payload.identity_fingerprint || !payload.enrollment_token) {{
        return alert("agent id, display name, domain, fingerprint and enrollment token are required");
      }}
      const agent = await api("/api/agents/enroll", {{ method: "POST", body: JSON.stringify(payload) }});
      if (agentUiState.libraryOnly || !agentUiState.activeBlockType || !agentUiState.activeBlockId) {{
        closeAgentLibraryModal();
        await renderAgentsPage();
      }} else {{
        await attachAgentNode(agent.id);
      }}
      ["agentEnrollId", "agentEnrollName", "agentEnrollDomain", "agentEnrollFingerprint", "agentEnrollToken"].forEach(id => {{ el(id).value = ""; }});
      el("agentEnrollPort").value = "7443";
    }}
    async function openAgentNode(agentId) {{
      if (!agentUiState.viewingAgent) {{
        agentUiState.returnContext = agentUiState.activeBlockType === "subject" && agentUiState.activeBlockId
          ? {{ kind: "project", projectType: "subject", projectId: agentUiState.activeBlockId }}
          : agentUiState.activeBlockType && agentUiState.activeBlockId
            ? {{ kind: "block", title: agentUiState.activeBlockTitle, blockType: agentUiState.activeBlockType, blockId: agentUiState.activeBlockId }}
            : {{ kind: "agents" }};
      }}
      agentUiState.viewingAgent = true;
      agentUiState.activeAgentId = agentId;
      agentUiState.activeJobId = "";
      const agent = await api(`/api/agents/${{encodeURIComponent(agentId)}}`);
      const [capabilities, jobs, approvals] = await Promise.all([
        api(`/api/agents/${{encodeURIComponent(agentId)}}/capabilities`),
        api(`/api/agents/${{encodeURIComponent(agentId)}}/jobs`),
        api(`/api/agents/${{encodeURIComponent(agentId)}}/approvals`),
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
                <span>status<br><strong>${{esc(agent.status)}}</strong></span>
                <span>last heartbeat<br><strong>${{esc(agent.last_heartbeat_at || "none")}}</strong></span>
              </div>
              <details class="setting-group">
                <summary>Settings</summary>
                <div class="agent-status-grid">
                  <span>name<br><strong>${{esc(agent.display_name || agent.agent_id)}}</strong></span>
                  <span>agent id<br><strong>${{esc(agent.id)}}</strong></span>
                  <span>domain<br><strong>${{esc(agent.domain || "unknown")}}</strong></span>
                  <span>port<br><strong>${{esc(agent.port || "-")}}</strong></span>
                  <span>fingerprint<br><strong>${{esc(agent.identity_fingerprint || "-")}}</strong></span>
                  <span>certificate<br><strong>${{esc(agent.certificate_serial || "-")}}</strong></span>
                  <span>agent version<br><strong>${{esc(agent.agent_version || "-")}}</strong></span>
                  <span>sindri version<br><strong>${{esc(agent.sindri_version || "-")}}</strong></span>
                </div>
                <div class="actions">
                  <button data-refresh-agent-node="${{esc(agent.id)}}">Refresh</button>
                  <button class="danger" data-request-remove-agent-node="${{esc(agent.id)}}">Delete</button>
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
    }}
    function renderAgentCapabilityCatalog() {{
      const root = el("agentCapabilityList");
      if (!root) return;
      root.innerHTML = (agentUiState.capabilities || []).map(item => `
        <button class="capability-card" data-run-agent-capability="${{esc(item.action)}}" ${{item.available === false ? "disabled" : ""}}>
          <strong>${{esc(item.title || item.action)}}</strong>
          <span>${{esc(item.group || "Agent Node")}} / ${{esc(item.risk || "read")}}</span>
          <small>${{esc(item.description || item.action)}}</small>
        </button>
      `).join("") || `<div class="muted">no capabilities reported</div>`;
    }}
    function renderAgentApprovals() {{
      const root = el("agentApprovalList");
      if (!root) return;
      root.innerHTML = (agentUiState.approvals || []).filter(item => String(item.status).toLowerCase() === "pending").map(item => `
        <button class="approval-card" data-open-agent-approval="${{esc(item.approval_id)}}" data-job-id="${{esc(item.job_id)}}">
          <strong>${{esc(item.risk)}} approval</strong>
          <span>${{esc(item.warning || "Review execution plan")}}</span>
        </button>
      `).join("") || `<div class="muted">no pending approvals</div>`;
    }}
    function renderAgentJobs() {{
      const root = el("agentJobEvents");
      if (!root) return;
      root.innerHTML = (agentUiState.jobs || []).slice(0, 8).map(job => `
        <div class="job-event">
          <strong>${{esc(job.action)}}</strong>
          <span>${{esc(job.status)}} / ${{esc(job.job_id)}}</span>
        </div>
      `).join("") || `<div class="muted">no jobs yet</div>`;
    }}
    function capabilityInputControl(spec) {{
      const name = String(spec.name || "");
      const prompt = String(spec.prompt || name);
      const required = spec.required ? " required" : "";
      const defaultValue = spec.default ?? "";
      const data = `data-capability-input="${{esc(name)}}"`;
      if (spec.type === "choice") {{
        const values = Array.isArray(spec.values) ? spec.values : [];
        return `<label>${{esc(prompt)}}<select ${{data}}${{required}}>${{values.map(value => `<option value="${{esc(value)}}" ${{String(value) === String(defaultValue) ? "selected" : ""}}>${{esc(value)}}</option>`).join("")}}</select></label>`;
      }}
      if (spec.type === "boolean") {{
        const selected = defaultValue === true || String(defaultValue).toLowerCase() === "true";
        return `<label>${{esc(prompt)}}<select ${{data}}><option value="false" ${{selected ? "" : "selected"}}>No</option><option value="true" ${{selected ? "selected" : ""}}>Yes</option></select></label>`;
      }}
      const type = spec.type === "integer" ? "number" : spec.type === "secret" || spec.secret ? "password" : "text";
      const constraints = spec.type === "integer"
        ? `${{spec.minimum ? ` min="${{Number(spec.minimum)}}"` : ""}}${{spec.maximum ? ` max="${{Number(spec.maximum)}}"` : ""}}`
        : "";
      return `<label>${{esc(prompt)}}<input type="${{type}}" ${{data}} value="${{esc(defaultValue)}}" autocomplete="${{type === "password" ? "new-password" : "off"}}"${{constraints}}${{required}} /></label>`;
    }}
    function openAgentCapabilityInput(action) {{
      const capability = (agentUiState.capabilities || []).find(item => item.action === action);
      if (!capability) return;
      agentUiState.pendingCapability = capability;
      el("agentCapabilityInputModalTitle").textContent = capability.title || capability.action;
      el("agentCapabilityInputDescription").textContent = capability.description || capability.action;
      el("agentCapabilityInputFields").innerHTML = (capability.inputs || []).map(capabilityInputControl).join("");
      resetModalPosition("agentCapabilityInputModalBackdrop");
      el("agentCapabilityInputModalBackdrop").classList.add("open");
      el("agentCapabilityInputModalBackdrop").setAttribute("aria-hidden", "false");
    }}
    function closeAgentCapabilityInputModal() {{
      el("agentCapabilityInputModalBackdrop").classList.remove("open");
      el("agentCapabilityInputModalBackdrop").setAttribute("aria-hidden", "true");
      agentUiState.pendingCapability = null;
    }}
    function collectAgentCapabilityInputs() {{
      const capability = agentUiState.pendingCapability;
      const inputs = {{}};
      for (const spec of capability?.inputs || []) {{
        const field = el("agentCapabilityInputFields").querySelector(`[data-capability-input="${{CSS.escape(String(spec.name || ""))}}"]`);
        if (!field) continue;
        const raw = field.value;
        if (spec.required && !String(raw).trim()) throw new Error(`${{spec.prompt || spec.name}} is required`);
        if (spec.type === "integer") {{
          const value = Number(raw);
          if (!Number.isInteger(value)) throw new Error(`${{spec.prompt || spec.name}} must be an integer`);
          inputs[spec.name] = value;
        }} else if (spec.type === "boolean") {{
          inputs[spec.name] = raw === "true";
        }} else if (String(raw).length || spec.required) {{
          inputs[spec.name] = raw;
        }}
      }}
      return inputs;
    }}
    async function dispatchAgentCapability(action, inputs = {{}}) {{
      if (!agentUiState.activeAgentId) return;
      const job = await api(`/api/agents/${{encodeURIComponent(agentUiState.activeAgentId)}}/jobs`, {{
        method: "POST",
        body: JSON.stringify({{ action, inputs, created_by: "operator" }}),
      }});
      agentUiState.activeJobId = job.job_id;
      el("agentActiveJob").textContent = job.status;
      el("agentCommandPreview").textContent = JSON.stringify({{ job_id: job.job_id, action: job.action, status: job.status }}, null, 2);
      agentUiState.jobs = [job, ...(agentUiState.jobs || [])];
      await refreshAgentJobEvents();
    }}
    async function runAgentCapability(action) {{
      const capability = (agentUiState.capabilities || []).find(item => item.action === action);
      if (!capability || !agentUiState.activeAgentId) return;
      if ((capability.inputs || []).length) {{
        openAgentCapabilityInput(action);
        return;
      }}
      await dispatchAgentCapability(action);
    }}
    async function confirmAgentCapabilityInput() {{
      const capability = agentUiState.pendingCapability;
      if (!capability) return;
      const inputs = collectAgentCapabilityInputs();
      closeAgentCapabilityInputModal();
      await dispatchAgentCapability(capability.action, inputs);
    }}
    async function refreshAgentJobEvents() {{
      if (!agentUiState.activeAgentId || !agentUiState.activeJobId) return;
      agentUiState.events = await api(`/api/agents/${{encodeURIComponent(agentUiState.activeAgentId)}}/jobs/${{encodeURIComponent(agentUiState.activeJobId)}}/events`);
      const root = el("agentJobEvents");
      if (root) root.innerHTML = agentUiState.events.map(item => `
        <div class="job-event">
          <strong>#${{item.sequence}} ${{esc(item.event_type)}}</strong>
          <span>${{esc(item.status)}} ${{esc(item.message || "")}}</span>
        </div>
      `).join("") || `<div class="muted">job created, waiting for Agent Node events</div>`;
    }}
    function openAgentApproval(approvalId, jobId) {{
      const approval = (agentUiState.approvals || []).find(item => item.approval_id === approvalId && item.job_id === jobId);
      if (!approval) return;
      agentUiState.activeApproval = approval;
      agentUiState.activeJobId = approval.job_id;
      const exterminatusConfirmation = approval.action === "system.exterminatus"
        ? `<div class="form-grid">
            <label>confirmation phrase<input id="agentApprovalConfirmationPhrase" autocomplete="off" placeholder="EXTERMINATUS" /></label>
            <label>agent hostname<input id="agentApprovalHostname" autocomplete="off" placeholder="${{esc(approval.hostname || "exact agent hostname")}}" /></label>
          </div>
          <p class="hint">This command requires the exact phrase <code>EXTERMINATUS</code> and the Agent hostname${{approval.hostname ? ` (<code>${{esc(approval.hostname)}}</code>)` : ""}}.</p>`
        : "";
      el("agentApprovalBody").innerHTML = `
        <div><strong>command</strong><br>${{esc(approval.action || "agent command")}}</div>
        <div><strong>risk</strong><br>${{esc(approval.risk)}}</div>
        <div><strong>warning</strong><br>${{esc(approval.warning || "Review execution plan")}}</div>
        <div class="agent-command-preview">${{esc(JSON.stringify(approval.plan || [], null, 2))}}</div>
        ${{exterminatusConfirmation}}
      `;
      resetModalPosition("agentApprovalModalBackdrop");
      el("agentApprovalModalBackdrop").classList.add("open");
      el("agentApprovalModalBackdrop").setAttribute("aria-hidden", "false");
    }}
    async function refreshPendingApprovals() {{
      if (document.querySelector(".modal-backdrop.open")) return;
      const approvals = await api("/api/approvals/pending");
      const next = (approvals || []).find(item => !agentUiState.presentedApprovalIds.has(item.approval_id));
      if (!next) return;
      agentUiState.presentedApprovalIds.add(next.approval_id);
      agentUiState.activeAgentId = next.agent_id;
      agentUiState.approvals = approvals;
      openAgentApproval(next.approval_id, next.job_id);
    }}
    function closeAgentApprovalModal() {{
      el("agentApprovalModalBackdrop").classList.remove("open");
      el("agentApprovalModalBackdrop").setAttribute("aria-hidden", "true");
      agentUiState.activeApproval = null;
    }}
    function requestRemoveAgentNode(agentId) {{
      agentUiState.pendingRemoveAgentId = agentId;
      resetModalPosition("agentRemoveModalBackdrop");
      el("agentRemoveModalBackdrop").classList.add("open");
      el("agentRemoveModalBackdrop").setAttribute("aria-hidden", "false");
    }}
    function closeAgentRemoveModal() {{
      el("agentRemoveModalBackdrop").classList.remove("open");
      el("agentRemoveModalBackdrop").setAttribute("aria-hidden", "true");
      agentUiState.pendingRemoveAgentId = "";
    }}
    async function decideAgentApproval(decision) {{
      const approval = agentUiState.activeApproval;
      if (!approval || !agentUiState.activeAgentId) return;
      const confirmationPhrase = el("agentApprovalConfirmationPhrase")?.value || "";
      const hostnameConfirmation = el("agentApprovalHostname")?.value || "";
      if (decision === "approve" && approval.action === "system.exterminatus") {{
        if (confirmationPhrase !== "EXTERMINATUS") throw new Error("Enter the exact confirmation phrase EXTERMINATUS");
        if (!hostnameConfirmation.trim()) throw new Error("Enter the exact Agent hostname");
      }}
      await api(`/api/agents/${{encodeURIComponent(agentUiState.activeAgentId)}}/jobs/${{encodeURIComponent(approval.job_id)}}/${{decision}}`, {{
        method: "POST",
        body: JSON.stringify({{
          approval_id: approval.approval_id,
          plan_hash: approval.plan_hash,
          decided_by: "operator",
          confirmation_phrase: confirmationPhrase,
          hostname_confirmation: hostnameConfirmation,
        }}),
      }});
      closeAgentApprovalModal();
      if (el("agentApprovalList")) await openAgentNode(agentUiState.activeAgentId);
      await refreshPendingApprovals();
    }}
    async function removeAgentNode(agentId) {{
      await api(`/api/agents/${{encodeURIComponent(agentId)}}`, {{ method: "DELETE" }});
      closeAgentRemoveModal();
      agentUiState.viewingAgent = false;
      await refresh();
      closeFullscreen();
      showView("agents");
    }}
    async function detachAgentNode(agentId) {{
      if (!agentUiState.activeBlockType || !agentUiState.activeBlockId) return;
      await api(`/api/blocks/${{encodeURIComponent(agentUiState.activeBlockId)}}/agents/${{encodeURIComponent(agentId)}}?block_type=${{encodeURIComponent(agentUiState.activeBlockType)}}`, {{ method: "DELETE" }});
      await loadAgentBlock(agentUiState.activeBlockType, agentUiState.activeBlockId, agentUiState.activeBlockTitle);
    }}
    function moveOrderedItem(items, from, to, after = false) {{
      if (from === null || to === null || from < 0 || to < 0 || !items[from] || !items[to]) return items;
      let insertion = to + (after ? 1 : 0);
      const next = [...items];
      const [moved] = next.splice(from, 1);
      if (from < insertion) insertion -= 1;
      next.splice(Math.max(0, Math.min(next.length, insertion)), 0, moved);
      return next;
    }}
    function isDropAfter(event, item) {{
      const rect = item.getBoundingClientRect();
      return event.clientY >= rect.top + rect.height / 2;
    }}
    function isMetricDropAfter(event, item) {{
      const rect = item.getBoundingClientRect();
      if (event.clientY >= rect.top && event.clientY <= rect.bottom) return event.clientX >= rect.left + rect.width / 2;
      return event.clientY >= rect.top + rect.height / 2;
    }}
    function clearDropIndicators() {{
      document.querySelectorAll(".drop-before, .drop-after").forEach(item => item.classList.remove("drop-before", "drop-after"));
    }}
    function showDropIndicator(item, after) {{
      clearDropIndicators();
      item.classList.add(after ? "drop-after" : "drop-before");
    }}
    async function reorderAgentNodes(from, to, after = false) {{
      if (from === null || to === null) return;
      const assignments = [...(agentUiState.assignments || [])];
      const reordered = moveOrderedItem(assignments, from, to, after);
      if (reordered.every((item, index) => item === assignments[index])) return;
      agentUiState.assignments = reordered;
      renderAgentNodes();
      await api(`/api/blocks/${{encodeURIComponent(agentUiState.activeBlockId)}}/agents/reorder?block_type=${{encodeURIComponent(agentUiState.activeBlockType)}}`, {{
        method: "POST",
        body: JSON.stringify({{ ordered_agent_ids: reordered.map(item => item.agent_id) }}),
      }});
      await loadAgentBlock(agentUiState.activeBlockType, agentUiState.activeBlockId, agentUiState.activeBlockTitle);
    }}
    async function reorderAgentLibrary(from, to, after = false) {{
      const current = [...(agentUiState.library || [])];
      const reordered = moveOrderedItem(current, from, to, after);
      if (reordered.every((item, index) => item === current[index])) return;
      agentUiState.library = reordered;
      renderAgentLibraryList();
      renderAgentsPageList();
      await api("/api/agents/reorder", {{
        method: "POST",
        body: JSON.stringify({{ ordered_agent_ids: reordered.map(item => item.id) }}),
      }});
    }}
    function reorderPropertyLibrary(from, to, after = false) {{
      const current = [...(uiState.propertyLibrary || [])];
      const reordered = moveOrderedItem(current, from, to, after);
      if (reordered.every((item, index) => item === current[index])) return;
      uiState.propertyLibrary = reordered;
      saveLocalState();
      renderPropertyLibrary();
      renderPropertiesPage();
    }}
    function updatePropertyModalMode() {{
      const type = el("propertyType").value;
      const isAttachment = type === "attachment";
      const input = el("propertyValue");
      const inputTypes = {{ number: "number", date: "date", phone_number: "tel", email_address: "email", web_address: "url" }};
      const placeholders = {{
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
      }};
      input.type = inputTypes[type] || "text";
      input.inputMode = type === "number" ? "decimal" : type === "phone_number" ? "tel" : type === "email_address" ? "email" : type === "web_address" ? "url" : "text";
      input.placeholder = placeholders[type] || "Enter a value";
      el("propertyAttachmentField").classList.toggle("visible", isAttachment);
      input.closest("label").style.display = isAttachment ? "none" : "block";
    }}
    function openPropertyModal(blockId, index = null) {{
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
    }}
    function closePropertyModal() {{
      el("propertyModalBackdrop").classList.remove("open");
      el("propertyModalBackdrop").setAttribute("aria-hidden", "true");
      uiState.editingPropertyIndex = null;
    }}
    function openPasswordModal() {{
      resetModalPosition("passwordModalBackdrop");
      el("passwordModalBackdrop").classList.add("open");
      el("passwordModalBackdrop").setAttribute("aria-hidden", "false");
    }}
    function closePasswordModal() {{
      el("passwordModalBackdrop").classList.remove("open");
      el("passwordModalBackdrop").setAttribute("aria-hidden", "true");
    }}
    function openBackupImportModal() {{
      resetModalPosition("backupImportModalBackdrop");
      el("backupImportModalBackdrop").classList.add("open");
      el("backupImportModalBackdrop").setAttribute("aria-hidden", "false");
    }}
    function closeBackupImportModal() {{
      el("backupImportModalBackdrop").classList.remove("open");
      el("backupImportModalBackdrop").setAttribute("aria-hidden", "true");
    }}
    function openUpdateInstallModal() {{
      const version = state.updateCheck?.available_version;
      if (!version || !state.updaterRuntime?.available) return;
      state.pendingUpdateVersion = version;
      el("updateInstallQuestion").textContent = `Install Perimetr ${{version}}?`;
      el("confirmInstallUpdate").textContent = "Download backup and install";
      el("confirmInstallUpdate").disabled = false;
      el("cancelInstallUpdate").disabled = false;
      el("closeUpdateInstallModal").disabled = false;
      resetModalPosition("updateInstallModalBackdrop");
      el("updateInstallModalBackdrop").classList.add("open");
      el("updateInstallModalBackdrop").setAttribute("aria-hidden", "false");
    }}
    function closeUpdateInstallModal(force = false) {{
      if (state.updateInstallPending && !force) return;
      el("updateInstallModalBackdrop").classList.remove("open");
      el("updateInstallModalBackdrop").setAttribute("aria-hidden", "true");
      state.pendingUpdateVersion = "";
    }}
    function addPropertyToBlock(blockId, property, insertionIndex = null) {{
      const next = {{ ...property, id: property.id || uid() }};
      if ((uiState.propertiesByBlock[blockId] || []).some(item => item.id === next.id)) {{
        renderProperties(blockId);
        return;
      }}
      const items = [...(uiState.propertiesByBlock[blockId] || [])];
      items.splice(insertionIndex === null ? items.length : Math.max(0, Math.min(items.length, insertionIndex)), 0, next);
      uiState.propertiesByBlock[blockId] = items;
      saveLocalState();
      renderProperties(blockId);
    }}
    function propagateSharedProperty(property) {{
      uiState.propertyLibrary = uiState.propertyLibrary.some(item => item.id === property.id)
        ? uiState.propertyLibrary.map(item => item.id === property.id ? property : item)
        : [...uiState.propertyLibrary, property];
      Object.keys(uiState.propertiesByBlock).forEach(blockId => {{
        uiState.propertiesByBlock[blockId] = (uiState.propertiesByBlock[blockId] || []).map(item => item.id === property.id ? {{ ...property }} : item);
      }});
    }}
    function savePropertyFromModal() {{
      const file = el("propertyAttachment").files?.[0];
      const type = el("propertyType").value;
      const currentBlock = uiState.activePropertyBlock || "human_general";
      const libraryMode = currentBlock === "__library__";
      const currentItems = libraryMode ? uiState.propertyLibrary : (uiState.propertiesByBlock[currentBlock] || []);
      const previous = uiState.editingPropertyIndex === null ? null : (libraryMode ? currentItems[uiState.editingPropertyIndex] : sharedProperty(currentItems[uiState.editingPropertyIndex]));
      const property = {{
        id: previous?.id || uid(),
        type,
        key: el("propertyKey").value.trim() || el("propertyType").selectedOptions[0].textContent,
        value: type === "attachment" ? (file?.name || previous?.value || "") : el("propertyValue").value.trim(),
      }};
      if (libraryMode) {{
        propagateSharedProperty(property);
        saveLocalState();
        renderPropertiesPage();
        recordUiAction(previous ? "property.updated" : "property.created", "property_library", property.id, {{ key: property.key, type: property.type }});
      }} else if (uiState.editingPropertyIndex === null) {{
        uiState.propertyLibrary = [...uiState.propertyLibrary, property];
        addPropertyToBlock(currentBlock, property);
        recordUiAction("property.created", "overview_block", currentBlock, {{ key: property.key, type: property.type }});
      }} else {{
        currentItems[uiState.editingPropertyIndex] = property;
        uiState.propertiesByBlock[currentBlock] = currentItems;
        propagateSharedProperty(property);
        saveLocalState();
        renderProperties(currentBlock);
        renderPropertyLibrary();
        recordUiAction("property.updated", "overview_block", currentBlock, {{ property_id: property.id, key: property.key, type: property.type }});
      }}
      closePropertyModal();
    }}
    function deletePropertyFromModal() {{
      if (uiState.editingPropertyIndex === null) return;
      const currentBlock = uiState.activePropertyBlock || "human_general";
      if (currentBlock === "__library__") {{
        const property = uiState.propertyLibrary[uiState.editingPropertyIndex];
        uiState.propertyLibrary = uiState.propertyLibrary.filter(item => item.id !== property?.id);
        Object.keys(uiState.propertiesByBlock).forEach(blockId => {{
          uiState.propertiesByBlock[blockId] = (uiState.propertiesByBlock[blockId] || []).filter(item => item.id !== property?.id);
        }});
        saveLocalState();
        renderPropertiesPage();
        closePropertyModal();
        return;
      }}
      const items = [...(uiState.propertiesByBlock[currentBlock] || [])];
      items.splice(uiState.editingPropertyIndex, 1);
      uiState.propertiesByBlock[currentBlock] = items;
      saveLocalState();
      renderProperties(currentBlock);
      recordUiAction("property.deleted", "overview_block", currentBlock);
      closePropertyModal();
    }}
    function renderObjects() {{
      if (!el("objectsList")) return;
      el("objectsList").innerHTML = state.objects.map(item => row(item.name, "", [`id ${{item.id}}`, `kind ${{item.kind}}`], `<button data-object-subject="${{item.id}}">Create Subject</button><button class="danger" data-request-entity-delete="object" data-entity-id="${{item.id}}" data-entity-name="${{esc(item.name)}}">Delete Object</button>`)).join("") || `<div class="muted">no objects</div>`;
    }}
    function renderSubjects() {{
      if (!el("subjectsList")) return;
      el("subjectsList").innerHTML = state.subjects.map(item => row(
        item.name,
        "",
        [`id ${{item.id}}`, `runtime ${{item.runtime_type}}`, `route ${{item.primary_route || "none"}}`],
        `<button data-create-pod="${{item.id}}">Create Pod</button><button class="danger" data-request-entity-delete="subject" data-entity-id="${{item.id}}" data-entity-name="${{esc(item.name)}}">Delete Subject</button>`
      )).join("") || `<div class="muted">no subjects</div>`;
    }}
    async function renderAgentsPage() {{
      const root = el("agentsPageList");
      if (!root) return;
      const agents = await api("/api/agents/library");
      agentUiState.library = agents;
      renderAgentsPageList();
    }}
    function agentAssignmentSummary(agent) {{
      const assignments = agent.assignments || [];
      if (!assignments.length) return "not attached";
      return assignments.map(item => `${{item.name}} (${{item.block_type}})`).join(", ");
    }}
    function renderAgentsPageList() {{
      const root = el("agentsPageList");
      if (!root) return;
      const query = String(el("agentsPageSearch")?.value || "").trim().toLowerCase();
      const agents = (agentUiState.library || [])
        .map((agent, index) => ({{ agent, index }}))
        .filter(({{ agent }}) => !query || `${{agent.display_name || ""}} ${{agent.agent_id || ""}} ${{agent.id || ""}} ${{agent.status || ""}} ${{agentAssignmentSummary(agent)}}`.toLowerCase().includes(query));
      root.innerHTML = agents.map(({{ agent, index }}) => `
        <div class="agent-node-row" data-agent-library-index="${{index}}" data-open-library-agent="${{esc(agent.id)}}">
          <div class="agent-node-main" draggable="true" data-agent-library-drag-index="${{index}}"><strong>${{esc(agent.display_name || agent.agent_id)}}</strong><small>id ${{esc(agent.id)}} / attached to ${{esc(agentAssignmentSummary(agent))}}</small></div>
          ${{agentStatusPill(agent.status)}}
        </div>
      `).join("") || `<div class="muted">${{query ? "No agents match this search." : "No agents registered."}}</div>`;
    }}
    function renderPodsPage() {{
      const root = el("podsPageList");
      if (!root) return;
      const query = String(el("podsPageSearch")?.value || "").trim().toLowerCase();
      const pods = (state.pods || []).filter(item => !query || `${{item.login || ""}} ${{item.name || ""}} ${{item.id || ""}} ${{item.subject_name || ""}} ${{item.subject_id || ""}} ${{item.kind || ""}} ${{item.status || ""}}`.toLowerCase().includes(query));
      root.innerHTML = pods.map(item => {{
        const active = String(item.status || "").toLowerCase() === "active";
        const status = item.kind === "instance" ? (active ? "Online" : "Offline") : humanizeError(item.status || "Pending");
        return `
          <div class="agent-node-row" data-open-global-pod="${{esc(item.id)}}">
            <div class="agent-node-main">
              <strong>${{esc(item.login || item.name)}}</strong>
              <small>subject ${{esc(item.subject_name || item.subject_id)}} / id ${{esc(item.subject_id)}} / ${{esc(item.kind)}}</small>
            </div>
            <span class="pill ${{active ? "ok" : ""}}"><i class="status-spinner ${{active ? "" : "frozen"}}"></i>${{esc(status)}}</span>
          </div>`;
      }}).join("") || `<div class="muted">${{query ? "No pods match this search." : "No pods registered."}}</div>`;
    }}
    async function loadPodsPage() {{
      state.pods = await api("/v1/pods");
      renderPodsPage();
    }}
    function openGlobalPodItem(id) {{
      const item = (state.pods || []).find(entry => entry.id === id);
      if (!item) return;
      if (item.kind === "instance") {{
        openPodModal(item.login || item.name, `${{podSettingsHtml(item)}}<p class="hint">Manage or delete this Pod from its Subject workspace.</p>`);
        return;
      }}
      openPodModal(item.login || item.name, `<div class="pod-settings-grid"><div class="pod-setting"><small>Subject</small><strong>${{esc(item.subject_name || item.subject_id)}}</strong></div><div class="pod-setting"><small>Status</small><strong>${{esc(item.status)}}</strong></div><div class="pod-setting"><small>Bundle version</small><strong>${{esc(item.bundle_version)}}</strong></div><div class="pod-setting"><small>Created</small><strong>${{esc(item.created_at)}}</strong></div></div><p class="hint">Pending Pod bundles are managed from their Subject workspace.</p>`);
    }}
    function renderPropertiesPage() {{
      const root = el("propertiesPageList");
      if (!root) return;
      const query = String(el("propertiesPageSearch")?.value || "").trim().toLowerCase();
      const properties = (uiState.propertyLibrary || [])
        .map((property, index) => ({{ property, index }}))
        .filter(({{ property }}) => !query || `${{property.key || ""}} ${{property.value || ""}} ${{property.type || ""}} ${{property.id || ""}}`.toLowerCase().includes(query));
      root.innerHTML = properties.map(({{ property, index }}) => `
        <div class="library-property-row" draggable="true" data-library-property-index="${{index}}" data-edit-library-property="${{index}}">
          <strong>${{esc(property.key || property.type)}}</strong><span>${{esc(property.value || "")}}</span>
        </div>
      `).join("") || `<div class="muted">${{query ? "No properties match this search." : "No properties registered."}}</div>`;
    }}
    function subjectPodWorkspaceHtml(subjectId) {{
      return `
        <div class="subject-pod-workspace" data-subject-pod-workspace="${{esc(subjectId)}}">
          <div class="subject-pod-head">
            <h2>Pods Settings</h2>
            <button class="primary" data-open-create-pod="${{esc(subjectId)}}">Create Pod</button>
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
            <div class="actions"><button data-add-system-tab="true">Add System Tab</button><button class="primary" data-save-subject-pod-config="${{esc(subjectId)}}">Save Pod Settings</button></div>
          </section>
          <section class="subject-pod-section">
            <h3>Pods List</h3>
            <div id="subjectPodsList" class="pod-list"><div class="pod-empty">loading pods</div></div>
          </section>
        </div>`;
    }}
    function renderSubjectSystemTabs(tabs = []) {{
      const root = el("subjectSystemTabs");
      if (!root) return;
      root.innerHTML = tabs.map((tab, index) => `
        <div class="subject-tab-row" data-system-tab-index="${{index}}">
          <input data-system-tab-title value="${{esc(tab.title || "")}}" placeholder="Site" />
          <input data-system-tab-url value="${{esc(tab.url || "")}}" placeholder="https://example.com" />
          <label class="check"><input data-system-tab-required type="checkbox" ${{tab.required !== false ? "checked" : ""}} /> Required</label>
          <button data-remove-system-tab="${{index}}" aria-label="remove system tab">X</button>
          <input data-system-tab-id type="hidden" value="${{esc(tab.id || uid())}}" />
        </div>`).join("") || `<div class="pod-empty">no system tabs configured</div>`;
    }}
    function podLastSeen(value) {{
      if (!value) return "Not activated";
      const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
      if (seconds < 60) return `${{seconds}} sec ago`;
      if (seconds < 3600) return `${{Math.floor(seconds / 60)}} min ago`;
      if (seconds < 86400) return `${{Math.floor(seconds / 3600)}} hours ago`;
      return `${{Math.floor(seconds / 86400)}} days ago`;
    }}
    function renderSubjectPods() {{
      const root = el("subjectPodsList");
      if (!root) return;
      const active = subjectPodState.instances.map(item => ({{ ...item, kind: "instance" }}));
      root.innerHTML = active.map(item => {{
        const online = String(item.status || "").toLowerCase() === "active";
        return `
        <button class="pod-row" data-open-pod-kind="${{item.kind}}" data-open-pod-id="${{esc(item.id)}}">
          <strong>${{esc(item.login || item.name)}}</strong><span class="pod-status"><i class="status-spinner ${{online ? "" : "frozen"}}"></i>${{online ? "Online" : "Offline"}}</span><span>Last seen: ${{esc(podLastSeen(item.last_seen_at))}}</span>
        </button>`;
      }}).join("") || `<div class="pod-empty">no activated pods</div>`;
    }}
    async function loadSubjectWorkspace(subjectId) {{
      window.clearTimeout(subjectProxyAutosaveTimer);
      subjectProxyAutosaveGeneration += 1;
      const [config, pods] = await Promise.all([api(`/v1/subjects/${{encodeURIComponent(subjectId)}}/pod-config`), api(`/v1/subjects/${{encodeURIComponent(subjectId)}}/pods`)]);
      subjectPodState.subjectId = subjectId;
      subjectPodState.config = config;
      subjectPodState.provisioning = pods.provisioning || [];
      subjectPodState.instances = pods.instances || [];
      if (!el("subjectVlessConnection")) return;
      el("subjectVlessConnection").value = config.vless_connection || "";
      el("subjectUpdateChannel").value = config.update_channel || "stable";
      renderSubjectSystemTabs(config.system_tabs || []);
      renderSubjectPods();
    }}
    function collectSubjectSystemTabs() {{
      return [...document.querySelectorAll("[data-system-tab-index]")].map((row, position) => ({{
        id: row.querySelector("[data-system-tab-id]").value || uid(), title: row.querySelector("[data-system-tab-title]").value.trim(),
        url: row.querySelector("[data-system-tab-url]").value.trim(), required: row.querySelector("[data-system-tab-required]").checked, position,
      }})).filter(tab => tab.title || tab.url);
    }}
    async function saveSubjectPodConfig(subjectId) {{
      window.clearTimeout(subjectProxyAutosaveTimer);
      subjectProxyAutosaveGeneration += 1;
      await api(`/v1/subjects/${{encodeURIComponent(subjectId)}}/pod-config`, {{ method: "PUT", body: JSON.stringify({{
        vless_connection: el("subjectVlessConnection").value.trim(), system_tabs: collectSubjectSystemTabs(),
        update_channel: el("subjectUpdateChannel").value,
      }}) }});
      await loadSubjectWorkspace(subjectId);
      recordUiAction("subject.pod_config.updated", "subject", subjectId);
    }}
    function scheduleSubjectProxyAutosave(subjectId, value) {{
      window.clearTimeout(subjectProxyAutosaveTimer);
      const generation = ++subjectProxyAutosaveGeneration;
      subjectProxyAutosaveTimer = window.setTimeout(async () => {{
        if (subjectPodState.subjectId !== subjectId || generation !== subjectProxyAutosaveGeneration) return;
        try {{
          const saved = await api(`/v1/subjects/${{encodeURIComponent(subjectId)}}/pod-config`, {{
            method: "PUT",
            feedback: false,
            body: JSON.stringify({{ vless_connection: value.trim() }}),
          }});
          if (generation !== subjectProxyAutosaveGeneration) return;
          subjectPodState.config = saved;
          notify("Proxy connection saved automatically.", "success");
        }} catch (error) {{
          if (generation === subjectProxyAutosaveGeneration) notify(error.message, "error");
        }}
      }}, 850);
    }}
    function openPodModal(title, body) {{
      el("podModalTitle").textContent = title; el("podModalBody").innerHTML = body; resetModalPosition("podModalBackdrop");
      el("podModalBackdrop").classList.add("open"); el("podModalBackdrop").setAttribute("aria-hidden", "false");
    }}
    function closePodModal() {{ el("podModalBackdrop").classList.remove("open"); el("podModalBackdrop").setAttribute("aria-hidden", "true"); subjectPodState.selected = null; }}
    function closeBackdrop(backdrop) {{
      const closers = {{
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
      }};
      closers[backdrop?.id]?.();
    }}
    function openCreatePodModal(subjectId) {{
      subjectPodState.subjectId = subjectId;
      openPodModal("Create Pod", `<div class="form-grid"><label class="full">Login<input id="newPodLogin" autocomplete="username" /></label><label>Password<input id="newPodPassword" type="password" autocomplete="new-password" /></label><label>Repeat Password<input id="newPodPasswordConfirm" type="password" autocomplete="new-password" /></label><label>Decoy Password <small>(optional)</small><input id="newPodDecoyPassword" type="password" autocomplete="new-password" /></label><label>Repeat Decoy Password<input id="newPodDecoyPasswordConfirm" type="password" autocomplete="new-password" /></label></div><p class="hint">The primary password opens the Subject. The optional decoy password opens a clean Pod with only the default Google search in an isolated temporary profile. Passwords are stored only as salted hashes.</p><div class="actions"><button class="primary" data-confirm-create-pod="true">Create Pod</button></div>`);
    }}
    async function createPodProvisioning() {{
      const login = el("newPodLogin").value.trim();
      const password = el("newPodPassword").value;
      const confirmPassword = el("newPodPasswordConfirm").value;
      const decoyPassword = el("newPodDecoyPassword").value;
      const confirmDecoyPassword = el("newPodDecoyPasswordConfirm").value;
      const progress = notify("Checking the latest verified Pod release...", "info", 0);
      let record;
      try {{
        record = await api(`/v1/subjects/${{encodeURIComponent(subjectPodState.subjectId)}}/pods`, {{ method: "POST", body: JSON.stringify({{ login, password, confirm_password: confirmPassword, decoy_password: decoyPassword || null, confirm_decoy_password: confirmDecoyPassword || null }}) }});
      }} finally {{
        progress?.remove();
      }}
      notify(
        record.runtime_warning
          ? `Pod ${{record.bundle_version}} created from last-known-good runtime. ${{record.runtime_warning}}`
          : `Verified Pod ${{record.bundle_version}} selected.`,
        record.runtime_warning ? "info" : "success",
        record.runtime_warning ? 8000 : null,
      );
      const download = document.createElement("a");
      download.href = record.download_url;
      download.download = `${{login || "perimetr-pod"}}.zip`;
      document.body.appendChild(download); download.click(); download.remove();
      closePodModal();
      await loadSubjectWorkspace(subjectPodState.subjectId);
    }}
    function podSettingsHtml(item) {{
      const online = String(item.status || "").toLowerCase() === "active";
      const values = [["Login", item.login || item.name], ["Password", "Stored securely; use the form below to replace it"], ["Pod ID", item.id], ["Subject ID", item.subject_id], ["Certificate fingerprint", item.certificate_fingerprint], ["Device binding fingerprint", item.device_binding_fingerprint], ["Status", online ? "Online" : "Offline"], ["Pod version", item.pod_version], ["Last seen", item.last_seen_at || "never"], ["Last heartbeat", item.last_heartbeat_at || "never"], ["Device binding", item.device_binding_status], ["xray-core", item.xray_version], ["VLESS profile version", item.network_profile_version], ["System Tabs version", item.system_tabs_profile_version]];
      return `<div class="pod-settings-grid">${{values.map(([label, value]) => `<div class="pod-setting"><small>${{esc(label)}}</small><strong>${{esc(value ?? "")}}</strong></div>`).join("")}}</div>`;
    }}
    function openPodItem(kind, id) {{
      const item = kind === "instance" ? subjectPodState.instances.find(entry => entry.id === id) : subjectPodState.provisioning.find(entry => entry.id === id);
      if (!item) return;
      subjectPodState.selected = {{ kind, item }};
      if (kind !== "instance") return;
      openPodModal(item.login || item.name, `${{podSettingsHtml(item)}}<section class="setting-group"><h3>Change Password</h3><div class="form-grid"><label>New Password<input id="podNewPassword" type="password" autocomplete="new-password" /></label><label>Repeat Password<input id="podNewPasswordConfirm" type="password" autocomplete="new-password" /></label></div><div class="actions"><button data-change-pod-password="${{esc(item.id)}}">Change Password</button></div></section><div class="actions"><button class="danger" data-request-revoke-pod="${{esc(item.id)}}">Delete Pod</button></div>`);
    }}
    function requestRevokePod(id) {{
      const item = subjectPodState.instances.find(entry => entry.id === id); if (!item) return;
      subjectPodState.selected = {{ kind: "instance", item }};
      el("podModalBody").innerHTML = `<div class="pod-confirm">Delete ${{esc(item.name)}} from Perimetr? Its Pod ID, certificate fingerprint and device binding will be blacklisted. The local copy will stop opening after its next heartbeat.</div><div class="actions"><button class="danger" data-confirm-revoke-pod="${{esc(id)}}">Delete Pod</button><button data-cancel-pod-delete="true">Cancel</button></div>`;
    }}
    async function refreshSubjectPodsAndModal(close = true) {{ if (close) closePodModal(); await loadSubjectWorkspace(subjectPodState.subjectId); }}
    async function changePodPassword(id) {{
      await api(`/v1/pods/${{encodeURIComponent(id)}}/password`, {{ method: "PUT", body: JSON.stringify({{
        new_password: el("podNewPassword").value,
        confirm_password: el("podNewPasswordConfirm").value,
      }}) }});
      await refreshSubjectPodsAndModal();
    }}
    function openFullscreen(title, body = "") {{
      el("fullscreenTitle").textContent = title;
      el("fullscreenTitle").contentEditable = "false";
      delete el("fullscreenTitle").dataset.renameType;
      delete el("fullscreenTitle").dataset.renameId;
      el("fullscreenBody").innerHTML = body;
      el("fullscreenBody").classList.remove("entity-detail");
      el("fullscreenPanel").classList.add("open");
      el("fullscreenPanel").setAttribute("aria-hidden", "false");
      render();
    }}
    function openProjectDetail(type, id) {{
      const item = type === "object" ? state.objects.find(entry => entry.id === id) : type === "subject" ? state.subjects.find(entry => entry.id === id) : agentUiState.library.find(entry => entry.id === id);
      if (!item) return;
      const title = item.name;
      const actions = type === "object"
        ? `<button data-object-subject="${{item.id}}">Create Subject</button><button data-choose-entity-image="object" data-entity-id="${{item.id}}">Upload Image</button>${{item.image_url ? `<button data-remove-entity-image="object" data-entity-id="${{item.id}}">Remove Image</button>` : ""}}<button class="danger" data-request-entity-delete="object" data-entity-id="${{item.id}}" data-entity-name="${{esc(item.name)}}">Delete Object</button>`
        : `<button data-choose-entity-image="subject" data-entity-id="${{item.id}}">Upload Image</button>${{item.image_url ? `<button data-remove-entity-image="subject" data-entity-id="${{item.id}}">Remove Image</button>` : ""}}<button class="danger" data-request-entity-delete="subject" data-entity-id="${{item.id}}" data-entity-name="${{esc(item.name)}}">Delete Subject</button>`;
      const localBlockId = `${{type}}_${{id}}`;
      const agentBlock = type === "subject" ? {{ blockType: "subject", blockId: item.id }} : {{ blockType: "", blockId: "" }};
      uiState.activePropertyBlock = localBlockId;
      uiState.activeDescriptionBlock = localBlockId;
      openFullscreen(title, `
        <div class="card">
          <div class="stack">
            <div>type: <strong>${{esc(type)}}</strong></div>
            <div>id: <strong>${{esc(item.id)}}</strong></div>
          </div>
          <div class="actions" style="margin-top:14px">${{actions}}</div>
          <input id="entityImageInput" type="file" accept="image/png,image/jpeg,image/webp" hidden />
         </div>
         ${{blockInterfaceHtml(localBlockId)}}
         ${{agentPanelHtml(agentBlock.blockType, agentBlock.blockId)}}
         ${{type === "subject" ? subjectPodWorkspaceHtml(item.id) : ""}}
       `);
      el("fullscreenBody").classList.add("entity-detail");
      el("fullscreenTitle").contentEditable = "true";
      el("fullscreenTitle").dataset.renameType = type;
      el("fullscreenTitle").dataset.renameId = item.id;
      renderProperties(localBlockId);
      adjustHumanDescriptionSize();
      if (type === "subject") {{
        loadAgentBlock("subject", item.id, title);
        loadSubjectWorkspace(item.id).catch(error => alert(error.message));
      }}
    }}
    async function normalizeEntityImage(file) {{
      if (!file) throw new Error("Select an image.");
      if (file.size > 12 * 1024 * 1024) throw new Error("Image is too large. Maximum source size is 12 MB.");
      const bitmap = await createImageBitmap(file);
      const side = Math.min(bitmap.width, bitmap.height);
      const canvas = document.createElement("canvas");
      canvas.width = 256; canvas.height = 256;
      canvas.getContext("2d").drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, 256, 256);
      bitmap.close();
      return new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error("Image conversion failed.")), "image/png"));
    }}
    async function uploadEntityImage(type, id, file) {{
      const image = await normalizeEntityImage(file);
      const form = new FormData();
      form.append("image", image, "entity.png");
      await api(`/v1/${{type === "object" ? "objects" : "subjects"}}/${{encodeURIComponent(id)}}/image`, {{ method: "PUT", body: form }});
      await refresh();
      notify("Image updated.", "success");
      openProjectDetail(type, id);
    }}
    async function removeEntityImage(type, id) {{
      await api(`/v1/${{type === "object" ? "objects" : "subjects"}}/${{encodeURIComponent(id)}}/image`, {{ method: "DELETE" }});
      await refresh();
      notify("Image removed.", "success");
      openProjectDetail(type, id);
    }}
    async function uploadOverviewBlockImage(blockId, file) {{
      const image = await normalizeEntityImage(file);
      const form = new FormData();
      form.append("image", image, "overview-block.png");
      await api(`/v1/overview-blocks/${{encodeURIComponent(blockId)}}/image`, {{ method: "PUT", body: form }});
      await refresh();
      notify("Image updated.", "success");
      openOverviewBlock(blockId);
    }}
    async function removeOverviewBlockImage(blockId) {{
      await api(`/v1/overview-blocks/${{encodeURIComponent(blockId)}}/image`, {{ method: "DELETE" }});
      await refresh();
      notify("Image removed.", "success");
      openOverviewBlock(blockId);
    }}
    function openProjectCreateModal() {{
      resetModalPosition("projectCreateModalBackdrop");
      el("newProjectName").value = "";
      el("projectCreateModalBackdrop").classList.add("open");
      el("projectCreateModalBackdrop").setAttribute("aria-hidden", "false");
      window.setTimeout(() => el("newProjectName").focus(), 0);
    }}
    function closeProjectCreateModal() {{
      el("projectCreateModalBackdrop").classList.remove("open");
      el("projectCreateModalBackdrop").setAttribute("aria-hidden", "true");
    }}
    async function createQuickProject() {{
      const name = el("newProjectName").value.trim();
      if (!name) {{
        notify("Enter a project name.", "error");
        el("newProjectName").focus();
        return;
      }}
      const button = el("confirmProjectCreate");
      button.disabled = true;
      try {{
        await api("/v1/objects", {{ method: "POST", feedback: "Project created.", body: JSON.stringify({{
          name,
          kind: "workspace",
          description: "",
          tags: [],
        }}) }});
        closeProjectCreateModal();
        await refresh();
      }} finally {{
        button.disabled = false;
      }}
    }}
    function closeFullscreen() {{
      if (agentUiState.viewingAgent) {{
        const destination = agentUiState.returnContext;
        agentUiState.viewingAgent = false;
        agentUiState.activeAgentId = "";
        if (destination?.kind === "block") {{
          openAgentManagedBlock(destination.title || "Agent Nodes", destination.blockType, destination.blockId);
          return;
        }}
        if (destination?.kind === "project") {{
          openProjectDetail(destination.projectType, destination.projectId);
          return;
        }}
        agentUiState.activeBlockType = "";
        agentUiState.activeBlockId = "";
        showView("agents");
      }}
      el("fullscreenPanel").classList.remove("open");
      el("fullscreenPanel").setAttribute("aria-hidden", "true");
      el("fullscreenTitle").textContent = "";
      el("fullscreenTitle").contentEditable = "false";
      el("fullscreenBody").innerHTML = "";
    }}
    async function refresh() {{
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
      Object.assign(state, {{ objects, subjects, pods, agents, overviewBlocks, audit, logs: logs.entries || [], metrics, backups, runtime, updaterRuntime }});
      const serverHasProperties = (correlation.property_library || []).length > 0 || Object.keys(correlation.properties_by_block || {{}}).length > 0;
      if (serverHasProperties || !(uiState.propertyLibrary || []).length) {{
        uiState.descriptionsByBlock = correlation.descriptions_by_block || {{}};
        uiState.propertiesByBlock = correlation.properties_by_block || {{}};
        uiState.propertyLibrary = correlation.property_library || [];
        uiState.graphSettings = {{ ...DEFAULT_GRAPH_SETTINGS, ...(correlation.graph_settings || {{}}) }};
        localStorage.setItem("perimetr.uiState", JSON.stringify({{
          descriptionsByBlock: uiState.descriptionsByBlock,
          propertiesByBlock: uiState.propertiesByBlock,
          propertyLibrary: uiState.propertyLibrary,
          graphSettings: uiState.graphSettings,
        }}));
      }} else {{
        queueCorrelationSync();
      }}
      state.correlationPercentage = Number(correlation.correlation_percentage || clientCorrelationPercentage());
      render();
    }}
    async function createObject() {{
      const name = el("objectName").value.trim();
      if (!name) return alert("name is required");
      await api("/v1/objects", {{ method: "POST", body: JSON.stringify({{
        name,
        kind: el("objectKind").value,
        description: el("objectDescription").value,
        tags: el("objectTags").value.split(",").map(x => x.trim()).filter(Boolean),
      }}) }});
      el("objectName").value = ""; el("objectDescription").value = ""; el("objectTags").value = "";
      await refresh();
    }}
    async function createSubject(objectId = null) {{
      const selectedObjectId = objectId || el("subjectObject")?.value;
      if (!selectedObjectId) return alert("create an object first");
      if (subjectConversionInFlight.has(selectedObjectId)) return;
      subjectConversionInFlight.add(selectedObjectId);
      document.querySelectorAll(`[data-object-subject="${{CSS.escape(selectedObjectId)}}"]`).forEach(button => button.disabled = true);
      let transformed;
      try {{
        transformed = await api("/v1/subjects", {{ method: "POST", body: JSON.stringify({{ object_id: selectedObjectId, runtime_type: "web" }}) }});
      }} finally {{
        subjectConversionInFlight.delete(selectedObjectId);
      }}
      const objectBlock = `object_${{selectedObjectId}}`;
      const subjectBlock = `subject_${{transformed.id}}`;
      if (Object.hasOwn(uiState.descriptionsByBlock, objectBlock)) {{
        uiState.descriptionsByBlock[subjectBlock] = uiState.descriptionsByBlock[objectBlock];
        delete uiState.descriptionsByBlock[objectBlock];
      }}
      if (Object.hasOwn(uiState.propertiesByBlock, objectBlock)) {{
        uiState.propertiesByBlock[subjectBlock] = uiState.propertiesByBlock[objectBlock];
        delete uiState.propertiesByBlock[objectBlock];
      }}
      saveLocalState();
      await refresh();
      openProjectDetail("subject", transformed.id);
    }}
    async function renameProjectFromTitle(titleElement) {{
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
      if (!name) {{
        titleElement.textContent = item?.name || item?.display_name || "Untitled";
        return;
      }}
      const previousName = item?.name || item?.display_name;
      if (name === previousName) return;
      const path = type === "agent"
        ? `/api/agents/${{encodeURIComponent(id)}}`
        : type === "overview_block"
          ? `/v1/overview-blocks/${{encodeURIComponent(id)}}`
          : `/v1/${{type === "object" ? "objects" : "subjects"}}/${{encodeURIComponent(id)}}`;
      await api(path, {{
        method: "PATCH",
        body: JSON.stringify(type === "agent" ? {{ display_name: name }} : {{ name }}),
      }});
      await refresh();
      titleElement.textContent = name;
      recordUiAction(`${{type}}.renamed`, type, id, {{ name }});
    }}
    function requestEntityDelete(type, id, name) {{
      uiState.pendingEntityDelete = {{ type, id, name }};
      el("entityDeleteModalTitle").textContent = `Delete ${{type === "subject" ? "Subject" : "Object"}}`;
      el("entityDeleteMessage").textContent = `Permanently delete ${{name || id}} from Perimetr? This action cannot be undone.`;
      resetModalPosition("entityDeleteModalBackdrop");
      el("entityDeleteModalBackdrop").classList.add("open");
      el("entityDeleteModalBackdrop").setAttribute("aria-hidden", "false");
    }}
    function closeEntityDeleteModal() {{
      el("entityDeleteModalBackdrop").classList.remove("open");
      el("entityDeleteModalBackdrop").setAttribute("aria-hidden", "true");
      uiState.pendingEntityDelete = null;
    }}
    async function confirmEntityDelete() {{
      const pending = uiState.pendingEntityDelete;
      if (!pending) return;
      await api(`/v1/${{pending.type === "subject" ? "subjects" : "objects"}}/${{encodeURIComponent(pending.id)}}`, {{ method: "DELETE" }});
      closeEntityDeleteModal();
      closeFullscreen();
      await refresh();
    }}
    function loadUiSettings() {{
      const theme = JSON.parse(localStorage.getItem("perimetr.theme") || "{{}}");
      el("colorDark").value = theme.dark || "#000000";
      el("colorLight").value = theme.light || "#ffffff";
      el("colorAccent").value = theme.accent || "#00a8ff";
      const auto = localStorage.getItem("perimetr.sidebarAuto") !== "false";
      el("sidebarAuto").checked = auto;
      document.body.classList.toggle("sidebar-auto", auto);
      document.body.classList.toggle("sidebar-fixed", !auto);
      applyTheme(false);
    }}
    function applyTheme(save = true) {{
      const theme = {{ dark: el("colorDark").value, light: el("colorLight").value, accent: el("colorAccent").value }};
      document.documentElement.style.setProperty("--dark", theme.dark);
      document.documentElement.style.setProperty("--light", theme.light);
      document.documentElement.style.setProperty("--accent", theme.accent);
      if (graphState.canvas) {{ syncCorrelationControls(); drawCorrelationGraph(); }}
      if (save) {{
        const serialized = JSON.stringify(theme);
        localStorage.setItem("perimetr.theme", serialized);
        document.cookie = `perimetr_theme=${{encodeURIComponent(serialized)}}; path=/; max-age=31536000; samesite=lax`;
      }}
    }}
    async function createBackup() {{
      const backup = await api("/v1/backups", {{ method: "POST", body: JSON.stringify({{ entity_type: "system" }}) }});
      const response = await fetch(`/v1/backups/${{backup.id}}`, {{ credentials: "same-origin" }});
      if (!response.ok) throw new Error(`Backup download failed with HTTP ${{response.status}}`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = backup.filename || "perimetr-backup.zip";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      await refresh();
      return backup;
    }}
    async function checkForUpdates() {{
      const button = el("checkForUpdates");
      button.disabled = true;
      button.textContent = "Checking...";
      try {{
        const result = await api("/v1/updater/check", {{ method: "POST" }});
        state.updateCheck = result;
        el("updaterInstalled").textContent = result.installed_version;
        el("updaterAvailable").textContent = result.available_version || "No published release";
        el("updaterStatus").textContent = result.update_available ? "UPDATE AVAILABLE" : "UP TO DATE";
        const releaseLink = el("updaterReleaseLink");
        releaseLink.hidden = !result.release_url;
        if (result.release_url) releaseLink.href = result.release_url;
        el("updaterResult").hidden = false;
        el("installUpdate").hidden = !result.update_available;
        el("installUpdate").disabled = !result.update_available || !state.updaterRuntime?.available;
        notify(result.update_available ? "Perimetr update is available." : "Perimetr is up to date.", "success");
        await refresh();
      }} finally {{
        button.disabled = false;
        button.textContent = "Check for Updates";
      }}
    }}
    function renderUpdaterRuntime() {{
      const runtime = state.updaterRuntime;
      const root = el("updaterAvailability");
      if (!root) return;
      root.classList.toggle("is-unavailable", !runtime?.available);
      root.textContent = runtime?.available
        ? `UPDATER AVAILABLE · ${{runtime.version || "version unknown"}}`
        : runtime?.message || "Updater is not installed or is unavailable on this VPS.";
      if (el("installUpdate")) {{
        el("installUpdate").disabled = !runtime?.available || !state.updateCheck?.update_available;
      }}
    }}
    function renderUpdateJob(job) {{
      state.updateJob = job;
      el("updaterJob").hidden = false;
      el("updaterJobId").textContent = job.id || "-";
      el("updaterJobState").textContent = job.state || "-";
      el("updaterJobMessage").textContent = job.message || "-";
    }}
    async function pollUpdateJob(jobId) {{
      const terminal = new Set(["COMPLETED", "ROLLED_BACK", "FAILED", "ROLLBACK_FAILED"]);
      for (let attempt = 0; attempt < 240; attempt += 1) {{
        const job = await api(`/v1/updater/jobs/${{encodeURIComponent(jobId)}}`);
        renderUpdateJob(job);
        if (terminal.has(job.state)) {{
          notify(`Update job ${{job.state.toLowerCase().replaceAll("_", " ")}}.`, job.state === "COMPLETED" ? "success" : "error");
          return;
        }}
        await new Promise(resolve => window.setTimeout(resolve, 1500));
      }}
      notify("Update job is still running. Refresh Settings to continue monitoring.", "info");
    }}
    async function installUpdate() {{
      const version = state.pendingUpdateVersion;
      if (!version || !state.updaterRuntime?.available) return;
      const button = el("installUpdate");
      const confirmButton = el("confirmInstallUpdate");
      state.updateInstallPending = true;
      button.disabled = true;
      confirmButton.disabled = true;
      el("cancelInstallUpdate").disabled = true;
      el("closeUpdateInstallModal").disabled = true;
      confirmButton.textContent = "Preparing backup...";
      try {{
        const backup = await createBackup();
        confirmButton.textContent = "Starting update...";
        const job = await api("/v1/updater/install", {{
          method: "POST",
          body: JSON.stringify({{ version, backup_id: backup.id }}),
        }});
        renderUpdateJob(job);
        closeUpdateInstallModal(true);
        notify("Backup downloaded and Perimetr update job started.", "success");
        pollUpdateJob(job.id).catch(error => notify(error.message, "error"));
      }} catch (error) {{
        notify(error.message, "error");
      }} finally {{
        state.updateInstallPending = false;
        confirmButton.textContent = "Download backup and install";
        confirmButton.disabled = false;
        el("cancelInstallUpdate").disabled = false;
        el("closeUpdateInstallModal").disabled = false;
        button.disabled = !state.updaterRuntime?.available || !state.updateCheck?.update_available;
      }}
    }}
    async function importBackup() {{
      const file = el("backupImportFile").files?.[0];
      if (!file) return alert("select backup zip first");
      const form = new FormData();
      form.append("archive", file);
      await api("/v1/backups/import", {{ method: "POST", body: form }});
      el("backupImportFile").value = "";
      closeBackupImportModal();
      await refresh();
    }}
    async function changePassword() {{
      const currentPassword = el("currentPassword").value;
      const newPassword = el("newPassword").value;
      const confirmPassword = el("confirmPassword").value;
      await api("/v1/settings/password", {{ method: "POST", body: JSON.stringify({{
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      }}) }});
      el("currentPassword").value = "";
      el("newPassword").value = "";
      el("confirmPassword").value = "";
      closePasswordModal();
      notify("Password changed.", "success");
      await refresh();
    }}
    function showView(viewName) {{
      const button = document.querySelector(`.sidebar button[data-view="${{viewName}}"]`);
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
    }}
    function filterDocumentation(query) {{
      const normalized = String(query || "").trim().toLowerCase();
      let visible = 0;
      document.querySelectorAll(".documentation-content article").forEach(article => {{
        const searchable = `${{article.dataset.docTitle || ""}} ${{article.textContent || ""}}`.toLowerCase();
        article.hidden = Boolean(normalized) && !searchable.includes(normalized);
        if (!article.hidden) visible += 1;
      }});
      document.querySelectorAll(".documentation-nav a").forEach(link => {{
        const target = document.querySelector(link.getAttribute("href"));
        link.hidden = Boolean(target?.hidden);
      }});
      el("documentationEmpty").hidden = visible !== 0;
    }}
    function restoreNavOrder() {{
      const nav = document.querySelector(".nav");
      if (!nav) return;
      let order = [];
      try {{ order = JSON.parse(localStorage.getItem("perimetr.navOrder") || "[]"); }} catch (_) {{}}
      order.forEach(view => {{ const button = nav.querySelector(`[data-view="${{view}}"]`); if (button) nav.appendChild(button); }});
      updateNavNumbers();
    }}
    function updateNavNumbers() {{
      document.querySelectorAll(".nav button[data-view]").forEach((button, index) => {{
        const marker = button.querySelector("small");
        if (marker) marker.textContent = String(index + 1).padStart(2, "0");
      }});
    }}
    function restoreMetricOrder() {{
      const grid = document.querySelector(".dashboard-metrics");
      if (!grid) return;
      let order = [];
      try {{ order = JSON.parse(localStorage.getItem("perimetr.metricOrder") || "[]"); }} catch (_) {{}}
      order.forEach(metricId => {{ const metric = grid.querySelector(`[data-metric-id="${{metricId}}"]`); if (metric) grid.appendChild(metric); }});
    }}
    restoreNavOrder();
    restoreMetricOrder();
    document.querySelectorAll(".nav button").forEach(button => button.addEventListener("click", () => {{
      showView(button.dataset.view);
    }}));
    document.querySelectorAll(".sidebar-footer button[data-view]").forEach(button => button.addEventListener("click", () => {{
      showView(button.dataset.view);
    }}));
    el("documentationSearch")?.addEventListener("input", event => filterDocumentation(event.currentTarget.value));
    ["graphPropertyColor", "graphEntityColor"].forEach(id => {{
      el(id)?.addEventListener("input", event => {{
        event.currentTarget.dataset.usesTheme = "false";
        updateGraphSettingsFromControls();
      }});
    }});
    [
      "graphTextThreshold", "graphNodeSize", "graphLinkThickness",
      "graphCenterForce", "graphRepelForce", "graphLinkForce", "graphLinkDistance", "graphAnimate",
    ].forEach(id => {{
      el(id)?.addEventListener(id === "graphAnimate" ? "change" : "input", updateGraphSettingsFromControls);
    }});
    document.addEventListener("click", async event => {{
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      try {{
        if (target.matches(".modal-backdrop.open")) {{ closeBackdrop(target); return; }}
        if (target.dataset.chooseEntityImage && target.dataset.entityId) {{
          const input = el("entityImageInput");
          input.dataset.entityType = target.dataset.chooseEntityImage;
          input.dataset.entityId = target.dataset.entityId;
          input.value = "";
          input.click();
          return;
        }}
        if (target.dataset.removeEntityImage && target.dataset.entityId) {{
          await removeEntityImage(target.dataset.removeEntityImage, target.dataset.entityId);
          return;
        }}
        if (target.dataset.chooseOverviewImage) {{
          const input = el("overviewBlockImageInput");
          input.dataset.overviewBlockId = target.dataset.chooseOverviewImage;
          input.value = "";
          input.click();
          return;
        }}
        if (target.dataset.removeOverviewImage) {{
          await removeOverviewBlockImage(target.dataset.removeOverviewImage);
          return;
        }}
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
        if (target.id === "openAgentLibraryModal") {{ agentUiState.libraryOnly = false; await openAgentLibraryModal(); }}
        if (target.dataset.addAgentLibrary) {{
          agentUiState.libraryOnly = true;
          agentUiState.activeBlockType = "";
          agentUiState.activeBlockId = "";
          await openAgentLibraryModal();
        }}
        if (target.dataset.addLibraryProperty) openPropertyModal("__library__");
        const libraryProperty = target.closest("[data-edit-library-property]");
        if (libraryProperty?.dataset.editLibraryProperty !== undefined) openPropertyModal("__library__", Number(libraryProperty.dataset.editLibraryProperty));
        if (target.id === "closeAgentLibraryModal") closeAgentLibraryModal();
        if (target.id === "closeAgentApprovalModal") closeAgentApprovalModal();
        if (target.id === "closeAgentCapabilityInputModal" || target.id === "cancelAgentCapabilityInput") closeAgentCapabilityInputModal();
        if (target.id === "closeAgentRemoveModal" || target.id === "cancelRemoveAgentNode") closeAgentRemoveModal();
        if (target.id === "closeEntityDeleteModal" || target.id === "cancelEntityDelete") closeEntityDeleteModal();
        if (target.id === "closePodModal" || target.dataset.closePodAfterCreate) closePodModal();
        if (target.dataset.addSystemTab) renderSubjectSystemTabs([...collectSubjectSystemTabs(), {{ id: uid(), title: "", url: "", required: true, position: collectSubjectSystemTabs().length }}]);
        if (target.dataset.removeSystemTab !== undefined) {{
          const tabs = collectSubjectSystemTabs(); tabs.splice(Number(target.dataset.removeSystemTab), 1); renderSubjectSystemTabs(tabs);
        }}
        if (target.dataset.saveSubjectPodConfig) await saveSubjectPodConfig(target.dataset.saveSubjectPodConfig);
        if (target.dataset.openCreatePod || target.dataset.createPod) openCreatePodModal(target.dataset.openCreatePod || target.dataset.createPod);
        if (target.dataset.confirmCreatePod) await createPodProvisioning();
        const podItem = target.closest("[data-open-pod-id]");
        if (podItem?.dataset.openPodId) openPodItem(podItem.dataset.openPodKind, podItem.dataset.openPodId);
        const globalPodItem = target.closest("[data-open-global-pod]");
        if (globalPodItem?.dataset.openGlobalPod) openGlobalPodItem(globalPodItem.dataset.openGlobalPod);
        if (target.dataset.savePodName) {{
          await api(`/v1/pods/${{encodeURIComponent(target.dataset.savePodName)}}`, {{ method: "PATCH", body: JSON.stringify({{ name: el("podInstanceName").value.trim() }}) }});
          await refreshSubjectPodsAndModal();
        }}
        if (target.dataset.changePodPassword) await changePodPassword(target.dataset.changePodPassword);
        if (target.dataset.removePodProvisioning) {{
          await api(`/v1/subjects/${{encodeURIComponent(subjectPodState.subjectId)}}/pods/provisioning/${{encodeURIComponent(target.dataset.removePodProvisioning)}}`, {{ method: "DELETE" }});
          await refreshSubjectPodsAndModal();
        }}
        if (target.dataset.requestRevokePod) requestRevokePod(target.dataset.requestRevokePod);
        if (target.dataset.cancelPodDelete && subjectPodState.selected) openPodItem(subjectPodState.selected.kind, subjectPodState.selected.item.id);
        if (target.dataset.confirmRevokePod) {{ await api(`/v1/pods/${{encodeURIComponent(target.dataset.confirmRevokePod)}}`, {{ method: "DELETE" }}); await refreshSubjectPodsAndModal(); }}
        if (target.id === "confirmEntityDelete") await confirmEntityDelete();
        if (target.id === "registerAgentNode") await registerAgentNode();
        if (target.id === "approveAgentJob") await decideAgentApproval("approve");
        if (target.id === "rejectAgentJob") await decideAgentApproval("reject");
        if (target.id === "confirmAgentCapabilityInput") await confirmAgentCapabilityInput();
        if (target.id === "confirmRemoveAgentNode" && agentUiState.pendingRemoveAgentId) await removeAgentNode(agentUiState.pendingRemoveAgentId);
        if (target.id === "saveProperty") savePropertyFromModal();
        if (target.id === "deleteProperty") deletePropertyFromModal();
        const propertyItem = target.closest(".property-item");
        if (propertyItem?.dataset.propertyIndex) {{
          openPropertyModal(uiState.activePropertyBlock || "human_general", Number(propertyItem.dataset.propertyIndex));
          return;
        }}
        if (target.dataset.addProperty) openPropertyModal(target.dataset.addProperty);
        if (target.dataset.libraryProperty) {{
          const property = uiState.propertyLibrary.find(item => item.id === target.dataset.libraryProperty);
          if (property) {{
            addPropertyToBlock(uiState.activePropertyBlock || "human_general", property);
            recordUiAction("property.attached", "overview_block", uiState.activePropertyBlock || "human_general", {{ property_id: property.id, key: property.key }});
            closePropertyModal();
          }}
        }}
        const overviewTile = target.closest("[data-overview-block]");
        if (overviewTile?.dataset.overviewBlock) {{
          openOverviewBlock(overviewTile.dataset.overviewBlock);
          return;
        }}
        const expandable = target.closest("[data-expand]");
        if (expandable?.dataset.expand) {{
          const panelName = expandable.dataset.expand;
          if (panelName === "I as human in general") openInfoPanel("I as human in general", "human_general");
          else if (panelName === "Turkey / Global sphere") openInfoPanel("Turkey / Global sphere", "turkey_global");
          else if (panelName === "Russia influence sphere") openInfoPanel("Russia influence sphere", "russia_sphere");
          else if (panelName === "Laboratory") openAgentManagedBlock("Laboratory", "laboratory", "laboratory");
          else if (panelName === "Perimetr") openAgentManagedBlock("Perimetr", "perimetr", PERIMETR_BLOCK_ID);
          else openFullscreen(panelName);
        }}
        const projectCard = target.closest("[data-project-type][data-project-id]");
        if (projectCard?.dataset.projectType && projectCard.dataset.projectId) openProjectDetail(projectCard.dataset.projectType, projectCard.dataset.projectId);
        if (target.dataset.attachAgentNode) await attachAgentNode(target.dataset.attachAgentNode);
        const agentNodeItem = target.closest("[data-open-agent-node]");
        if (agentNodeItem?.dataset.openAgentNode) await openAgentNode(agentNodeItem.dataset.openAgentNode);
        const libraryAgent = target.closest("[data-open-library-agent]");
        if (libraryAgent?.dataset.openLibraryAgent) {{
          agentUiState.activeBlockType = "";
          agentUiState.activeBlockId = "";
          agentUiState.activeBlockTitle = "";
          await openAgentNode(libraryAgent.dataset.openLibraryAgent);
        }}
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
        if (target.id === "applyTheme") {{ applyTheme(true); recordUiAction("appearance.theme.updated", "settings", "appearance"); }}
        if (target.id === "resetTheme") {{ localStorage.removeItem("perimetr.theme"); loadUiSettings(); recordUiAction("appearance.theme.reset", "settings", "appearance"); }}
        if (target.id === "createBackup") await createBackup();
        if (target.id === "checkForUpdates") await checkForUpdates();
        if (target.id === "installUpdate") openUpdateInstallModal();
        if (target.id === "importBackup") await importBackup();
        if (target.id === "changePassword") await changePassword();
        if (target.dataset.objectSubject) await createSubject(target.dataset.objectSubject);
        if (target.dataset.requestEntityDelete && target.dataset.entityId) requestEntityDelete(target.dataset.requestEntityDelete, target.dataset.entityId, target.dataset.entityName);
      }} catch (error) {{
        alert(error.message);
      }}
    }});
    document.addEventListener("keydown", event => {{
      const target = event.target;
      if (target instanceof HTMLElement && target.id === "newProjectName" && event.key === "Enter") {{
        event.preventDefault();
        createQuickProject().catch(error => notify(error.message, "error"));
        return;
      }}
      if (target instanceof HTMLElement && target.id === "fullscreenTitle" && event.key === "Enter") {{
        event.preventDefault();
        target.blur();
      }}
    }});
    document.addEventListener("focusout", event => {{
      const target = event.target;
      if (!(target instanceof HTMLElement) || target.id !== "fullscreenTitle" || !target.dataset.renameType) return;
      renameProjectFromTitle(target).catch(error => alert(error.message));
    }});
    document.addEventListener("pointerover", event => {{
      const target = event.target instanceof HTMLElement
        ? event.target.closest("button, a.button, input, select, textarea, .overview-tile, .project-card, .property-item, .library-item, .agent-node-row, .capability-card, .approval-card")
        : null;
      if (target instanceof HTMLElement && !target.classList.contains("human-description")) {{
        applySafeHoverScale(target);
      }}
    }});
    document.addEventListener("mousedown", event => {{
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.closest("button, input, select, textarea, a")) return;
      const head = target.closest(".modal-head");
      if (!head) return;
      const modal = head.closest(".property-modal, .settings-modal, .agent-modal");
      if (!(modal instanceof HTMLElement)) return;
      const rect = modal.getBoundingClientRect();
      modal.style.position = "fixed";
      modal.style.left = `${{rect.left}}px`;
      modal.style.top = `${{rect.top}}px`;
      modal.style.transform = "none";
      modalDrag.modal = modal;
      modalDrag.offsetX = event.clientX - rect.left;
      modalDrag.offsetY = event.clientY - rect.top;
      event.preventDefault();
    }});
    document.addEventListener("mousemove", event => {{
      const modal = modalDrag.modal;
      if (!modal) return;
      const rect = modal.getBoundingClientRect();
      const left = Math.max(8, Math.min(window.innerWidth - rect.width - 8, event.clientX - modalDrag.offsetX));
      const top = Math.max(8, Math.min(window.innerHeight - rect.height - 8, event.clientY - modalDrag.offsetY));
      modal.style.left = `${{left}}px`;
      modal.style.top = `${{top}}px`;
    }});
    document.addEventListener("mouseup", () => {{
      modalDrag.modal = null;
    }});
    document.addEventListener("input", event => {{
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.id === "humanDescription") {{
        uiState.descriptionsByBlock[uiState.activeDescriptionBlock || "human_general"] = target.value;
        adjustHumanDescriptionSize();
        saveLocalState();
      }}
      if (target.id === "subjectVlessConnection" && subjectPodState.subjectId) {{
        scheduleSubjectProxyAutosave(subjectPodState.subjectId, target.value);
      }}
      if (target.id === "agentLibrarySearch") renderAgentLibraryList();
      if (target.id === "agentsPageSearch") renderAgentsPageList();
      if (target.id === "podsPageSearch") renderPodsPage();
      if (target.id === "propertiesPageSearch") renderPropertiesPage();
      if (target.id === "propertyType") updatePropertyModalMode();
    }});
    document.addEventListener("dragstart", event => {{
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.matches(".nav button[data-view]")) {{
        uiState.draggedNavView = target.dataset.view || "";
        target.classList.add("dragging");
        event.dataTransfer?.setData("application/x-perimetr-nav", uiState.draggedNavView);
      }}
      if (target.matches(".metric[data-metric-id]")) {{
        uiState.draggedMetricId = target.dataset.metricId || "";
        target.classList.add("dragging");
        event.dataTransfer?.setData("application/x-perimetr-metric", uiState.draggedMetricId);
      }}
      if (target.dataset.propertyIndex !== undefined) {{
        uiState.draggedPropertyIndex = Number(target.dataset.propertyIndex);
        target.classList.add("dragging");
        event.dataTransfer?.setData("text/plain", target.dataset.propertyIndex);
      }}
      if (target.dataset.agentDragIndex !== undefined) {{
        agentUiState.draggedAgentIndex = Number(target.dataset.agentDragIndex);
        target.classList.add("dragging");
        event.dataTransfer?.setData("application/x-perimetr-agent-index", target.dataset.agentDragIndex);
      }}
      if (target.dataset.agentLibraryDragIndex !== undefined) {{
        agentUiState.draggedLibraryAgentIndex = Number(target.dataset.agentLibraryDragIndex);
        target.classList.add("dragging");
        event.dataTransfer?.setData("application/x-perimetr-agent-library-index", target.dataset.agentLibraryDragIndex);
      }}
      if (target.dataset.libraryPropertyIndex !== undefined) {{
        uiState.draggedLibraryPropertyIndex = Number(target.dataset.libraryPropertyIndex);
        target.classList.add("dragging");
        event.dataTransfer?.setData("application/x-perimetr-property-library-index", target.dataset.libraryPropertyIndex);
      }}
      if (target.dataset.libraryProperty) {{
        event.dataTransfer?.setData("application/x-perimetr-library-property", target.dataset.libraryProperty);
      }}
    }});
    document.addEventListener("dragend", event => {{
      const target = event.target;
      if (target instanceof HTMLElement) target.classList.remove("dragging");
      uiState.draggedPropertyIndex = null;
      uiState.draggedNavView = "";
      uiState.draggedMetricId = "";
      uiState.draggedLibraryPropertyIndex = null;
      agentUiState.draggedAgentIndex = null;
      agentUiState.draggedLibraryAgentIndex = null;
      clearDropIndicators();
    }});
    document.addEventListener("dragover", event => {{
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const navTarget = target.closest(".nav button[data-view]");
      if (navTarget && uiState.draggedNavView) {{ event.preventDefault(); showDropIndicator(navTarget, isDropAfter(event, navTarget)); return; }}
      const metricTarget = target.closest(".metric[data-metric-id]");
      if (metricTarget && uiState.draggedMetricId) {{ event.preventDefault(); showDropIndicator(metricTarget, isMetricDropAfter(event, metricTarget)); return; }}
      const agentTarget = target.closest("[data-agent-index]");
      if (agentTarget && agentUiState.draggedAgentIndex !== null) {{ event.preventDefault(); showDropIndicator(agentTarget, isDropAfter(event, agentTarget)); return; }}
      const agentLibraryTarget = target.closest("[data-agent-library-index]");
      if (agentLibraryTarget && agentUiState.draggedLibraryAgentIndex !== null) {{ event.preventDefault(); showDropIndicator(agentLibraryTarget, isDropAfter(event, agentLibraryTarget)); return; }}
      const propertyTarget = target.closest("[data-property-index]");
      if (propertyTarget && (uiState.draggedPropertyIndex !== null || uiState.draggedLibraryPropertyIndex !== null)) {{ event.preventDefault(); showDropIndicator(propertyTarget, isDropAfter(event, propertyTarget)); return; }}
      const propertyLibraryTarget = target.closest("[data-library-property-index]");
      if (propertyLibraryTarget && uiState.draggedLibraryPropertyIndex !== null) {{ event.preventDefault(); showDropIndicator(propertyLibraryTarget, isDropAfter(event, propertyLibraryTarget)); return; }}
      const propertyList = target.closest(".property-list");
      if (propertyList && (uiState.draggedPropertyIndex !== null || uiState.draggedLibraryPropertyIndex !== null)) {{ event.preventDefault(); showDropIndicator(propertyList, false); return; }}
      if (target.closest(".agent-node-list")) event.preventDefault();
    }});
    document.addEventListener("drop", event => {{
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const navTarget = target.closest(".nav button[data-view]");
      const draggedView = event.dataTransfer?.getData("application/x-perimetr-nav") || uiState.draggedNavView;
      if (navTarget && draggedView) {{
        const dragged = document.querySelector(`.nav button[data-view="${{draggedView}}"]`);
        if (dragged && dragged !== navTarget) {{
          navTarget.parentElement?.insertBefore(dragged, isDropAfter(event, navTarget) ? navTarget.nextSibling : navTarget);
          localStorage.setItem("perimetr.navOrder", JSON.stringify([...document.querySelectorAll(".nav button[data-view]")].map(item => item.dataset.view)));
          updateNavNumbers();
          recordUiAction("navigation.reordered", "sidebar", "navigation", {{}}, {{}}, false);
          notify("Navigation order saved.", "success");
        }}
        clearDropIndicators();
        event.preventDefault();
        return;
      }}
      const metricTarget = target.closest(".metric[data-metric-id]");
      const draggedMetricId = event.dataTransfer?.getData("application/x-perimetr-metric") || uiState.draggedMetricId;
      if (metricTarget && draggedMetricId) {{
        const dragged = document.querySelector(`.metric[data-metric-id="${{draggedMetricId}}"]`);
        if (dragged && dragged !== metricTarget) {{
          metricTarget.parentElement?.insertBefore(dragged, isMetricDropAfter(event, metricTarget) ? metricTarget.nextSibling : metricTarget);
          localStorage.setItem("perimetr.metricOrder", JSON.stringify([...document.querySelectorAll(".dashboard-metrics .metric[data-metric-id]")].map(item => item.dataset.metricId)));
          recordUiAction("dashboard.metrics.reordered", "dashboard", "metrics");
        }}
        clearDropIndicators(); event.preventDefault(); return;
      }}
      const agentLibraryItem = target.closest("[data-agent-library-index]");
      if (agentLibraryItem && agentUiState.draggedLibraryAgentIndex !== null) {{
        event.preventDefault();
        const after = isDropAfter(event, agentLibraryItem);
        clearDropIndicators();
        reorderAgentLibrary(agentUiState.draggedLibraryAgentIndex, Number(agentLibraryItem.dataset.agentLibraryIndex), after).catch(error => alert(error.message));
        return;
      }}
      const agentItem = target.closest("[data-agent-index]");
      if (agentItem && agentUiState.draggedAgentIndex !== null) {{
        event.preventDefault();
        const after = isDropAfter(event, agentItem);
        clearDropIndicators();
        reorderAgentNodes(agentUiState.draggedAgentIndex, Number(agentItem.dataset.agentIndex), after).catch(error => alert(error.message));
        return;
      }}
      const propertyLibraryItem = target.closest("[data-library-property-index]");
      if (propertyLibraryItem && uiState.draggedLibraryPropertyIndex !== null) {{
        event.preventDefault();
        const after = isDropAfter(event, propertyLibraryItem);
        clearDropIndicators();
        reorderPropertyLibrary(uiState.draggedLibraryPropertyIndex, Number(propertyLibraryItem.dataset.libraryPropertyIndex), after);
        return;
      }}
      const list = target.closest(".property-list");
      if (!list) return;
      event.preventDefault();
      const blockId = uiState.activePropertyBlock || "human_general";
      const libraryId = event.dataTransfer?.getData("application/x-perimetr-library-property");
      if (libraryId) {{
        const property = uiState.propertyLibrary.find(item => item.id === libraryId);
        if (property) {{
          const destination = target.closest(".property-item");
          const destinationIndex = destination
            ? Number(destination.dataset.propertyIndex) + (isDropAfter(event, destination) ? 1 : 0)
            : null;
          addPropertyToBlock(blockId, property, destinationIndex);
          recordUiAction("property.attached", "overview_block", blockId, {{ property_id: property.id, key: property.key }});
        }}
        clearDropIndicators();
        return;
      }}
      const from = uiState.draggedPropertyIndex;
      const item = target.closest(".property-item");
      if (from === null || item?.dataset.propertyIndex === undefined) return;
      const to = Number(item.dataset.propertyIndex);
      const items = [...(uiState.propertiesByBlock[blockId] || [])];
      uiState.propertiesByBlock[blockId] = moveOrderedItem(items, from, to, isDropAfter(event, item));
      clearDropIndicators();
      saveLocalState();
      renderProperties(blockId);
    }});
    el("sidebarAuto").addEventListener("change", () => {{
      const auto = el("sidebarAuto").checked;
      localStorage.setItem("perimetr.sidebarAuto", String(auto));
      document.body.classList.toggle("sidebar-auto", auto);
      document.body.classList.toggle("sidebar-fixed", !auto);
      recordUiAction("appearance.sidebar.updated", "settings", "appearance", {{ auto_hide: auto }});
    }});
    document.addEventListener("change", async event => {{
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.id === "entityImageInput") {{
        try {{
          await uploadEntityImage(target.dataset.entityType, target.dataset.entityId, target.files?.[0]);
        }} catch (error) {{
          notify(error.message, "error");
        }}
        return;
      }}
      if (target.id === "overviewBlockImageInput") {{
        try {{
          await uploadOverviewBlockImage(target.dataset.overviewBlockId, target.files?.[0]);
        }} catch (error) {{
          notify(error.message, "error");
        }}
        return;
      }}
      if (target.id === "humanDescription") {{
        recordUiAction("description.updated", "overview_block", uiState.activeDescriptionBlock || "human_general");
      }}
    }});
    loadLocalState();
    loadUiSettings();
    refresh();
    setInterval(() => api("/v1/system/metrics").then(metrics => {{ state.metrics = metrics; renderMetrics(); }}).catch(() => {{}}), 1000);
    setInterval(() => refreshPendingApprovals().catch(() => {{}}), 2000);
    refreshPendingApprovals().catch(() => {{}});
  </script>
</body>
</html>"""
    return (
        template
        .replace("{{", "{")
        .replace("}}", "}")
    )
