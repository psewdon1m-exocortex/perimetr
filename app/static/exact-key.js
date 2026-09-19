/* Preserve pasted line breaks: HTML password controls normally discard them. */
const opaqueKeys = new WeakMap();
function bindOpaqueKey(input) {
  if (!input || opaqueKeys.has(input)) return;
  const state = {text: input.value}; opaqueKeys.set(input, state);
  const display = value => value.replace(/[\r\n]/g, "␤");
  state.sync = () => {
    const before = display(state.text), after = input.value;
    if (before === after) return;
    let prefix = 0, suffix = 0;
    while (prefix < Math.min(before.length, after.length) && before[prefix] === after[prefix]) prefix++;
    while (suffix < Math.min(before.length, after.length) - prefix && before[before.length-1-suffix] === after[after.length-1-suffix]) suffix++;
    state.text = state.text.slice(0,prefix) + after.slice(prefix,after.length-suffix) + (suffix ? state.text.slice(-suffix) : "");
  };
  input.addEventListener("input", state.sync);
  input.addEventListener("paste", event => {
    if (!event.clipboardData) return;
    event.preventDefault(); state.sync();
    const pasted = event.clipboardData.getData("text/plain"), start = input.selectionStart ?? 0, end = input.selectionEnd ?? input.value.length;
    state.text = state.text.slice(0,start) + pasted + state.text.slice(end);
    input.value = display(state.text); input.setSelectionRange(start+pasted.length,start+pasted.length);
    input.dispatchEvent(new Event("input", {bubbles:true}));
  });
}
function readOpaqueKey(input) { const state=opaqueKeys.get(input); if(!state) return input.value; state.sync(); return state.text; }
function clearOpaqueKey(input) { const state=opaqueKeys.get(input); if(state) state.text=""; input.value=""; }
