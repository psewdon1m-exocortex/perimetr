from __future__ import annotations

import html


def render(error: str | None = None, accent: str = "#00A8FF") -> str:
    return r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive,nosnippet"><title>perimetr</title>
<link rel="icon" type="image/png" sizes="1254x1254" href="/assets/perimetr-icon.png?v=7e7edac3">
<link rel="stylesheet" href="/assets/unified.css"><style>
:root{--accent:__ACCENT__} body{min-height:100vh;display:grid;place-items:center;margin:0;padding:24px}
.login-shell{width:min(560px,100%)} .login-brand{height:100px;display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.login-brand h1{font:700 clamp(48px,8vw,72px)/1 "Space Grotesk","Segoe UI",sans-serif;color:var(--accent);margin:0}
.login-mark{width:100px;height:100px;object-fit:contain;flex:none} .login-panel{border:1px solid var(--white);padding:21px 24px 25px;min-height:268px}
.reachability{display:flex;align-items:center;justify-content:space-between;gap:12px;width:min(255px,100%);min-height:50px;border:1px solid var(--line-inner);padding:12px;margin-bottom:55px}
.status-square{width:18px;height:18px;background:currentColor;flex:none}.reachable{color:var(--success);border-color:color-mix(in srgb,var(--success) 80%,transparent)}
.reachable .status-square{animation:reachability 2s ease-in-out infinite}.unreachable{color:var(--danger)}
@keyframes reachability{50%{opacity:.45}} .access-key-wrapper{min-height:44px;display:flex;align-items:center}
#accessKey{height:31px;min-height:31px;width:100%} .login-panel button{width:100%;min-height:50px;margin-top:20px}
.login-error:empty{display:none}.login-error{color:var(--danger);margin-top:12px;overflow-wrap:anywhere}.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
@media(prefers-reduced-motion:reduce){.reachable .status-square{animation:reachability 2s ease-in-out infinite}}
</style></head><body><main class="login-shell">
<header class="login-brand"><h1 class="login-wordmark">perimetr</h1><img class="login-mark" src="/assets/perimetr-icon.png?v=7e7edac3" width="100" height="100" alt="" draggable="false"></header>
<form class="login-panel" id="loginForm">
<div id="reachability" class="reachability" role="status"><span id="reachabilityText">Checking service…</span><span class="status-square" aria-hidden="true"></span></div>
<label class="visually-hidden" for="accessKey">Access Key</label><div class="access-key-wrapper"><input id="accessKey" type="password" name="access_key" placeholder="Access Key…" autocomplete="current-password" autocapitalize="none" spellcheck="false" required></div>
<button id="enterService" type="submit">Enter perimetr</button><div id="loginError" class="login-error" role="alert">__ERROR__</div>
</form></main><script src="/assets/exact-key.js"></script><script>
const form=document.getElementById('loginForm'), key=document.getElementById('accessKey'), button=document.getElementById('enterService'), error=document.getElementById('loginError');
bindOpaqueKey(key);
let pending=false;
form.addEventListener('submit',async event=>{event.preventDefault();if(pending)return;pending=true;button.disabled=true;button.textContent='Signing in…';error.textContent='';
try{const response=await fetch('/v1/auth/direct',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({access_key:readOpaqueKey(key),target:'perimetr'}),cache:'no-store'});
if(!response.ok)throw new Error(response.status===429?'Too many attempts. Wait before trying again.':'Access Key was not accepted.');clearOpaqueKey(key);location.replace('/');}
catch(exc){error.textContent=exc.message;key.focus();}finally{pending=false;button.disabled=false;button.textContent='Enter perimetr';}});
async function checkReachability(){if(document.hidden)return;const status=document.getElementById('reachability');try{const response=await fetch('/v1/reachability',{cache:'no-store'});if(!response.ok)throw new Error();status.className='reachability reachable';document.getElementById('reachabilityText').textContent='Perimetr is reachable';}catch{status.className='reachability unreachable';document.getElementById('reachabilityText').textContent='Perimetr is unreachable';}}
checkReachability();setInterval(checkReachability,15000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)checkReachability();});
</script></body></html>'''.replace("__ACCENT__", html.escape(accent, quote=True)).replace("__ERROR__", "Unable to sign in." if error else "")
