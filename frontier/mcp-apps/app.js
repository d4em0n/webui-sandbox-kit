import { App, applyDocumentTheme, applyHostStyleVariables, applyHostFonts } from '@modelcontextprotocol/ext-apps';
import { renderOriginal } from './dist/renderer.js';

const app = new App({name: 'Frontier UI', version: '0.1.0'}, {}, {autoResize: false});
let dispose = () => {};
let currentSpec;
let contextTimer;
const values = new Map();

function notice(message, text) {
  const box = document.getElementById('host-notice');
  box.replaceChildren(document.createTextNode(message));
  if (text) {
    const field = document.createElement('textarea');
    field.readOnly = true;
    field.value = text;
    field.setAttribute('aria-label', 'Text to copy');
    field.onclick = () => field.select();
    box.append(field);
  }
}

function theme(context) {
  if (context?.theme) {
    applyDocumentTheme(context.theme);
    // Frontier's CSS and map renderer use classes; the SDK sets data-theme/color-scheme.
    document.documentElement.classList.toggle('dark', context.theme === 'dark');
    document.documentElement.classList.toggle('light', context.theme === 'light');
  }
  if (context?.styles?.variables) applyHostStyleVariables(context.styles.variables);
  if (context?.styles?.css?.fonts) applyHostFonts(context.styles.css.fonts);
  document.dispatchEvent(new Event('iui-theme'));
}

const bridge = {
  async sendPrompt(text) {
    if (app.getHostCapabilities()?.serverTools && currentSpec?._ui?.card) {
      const exportAction = text.match(/^Export the Frontier UI card .* as a (Word|PDF|Excel|PowerPoint)(?: \(\.\w+\))? file/);
      const saveAction = text.startsWith('Save the Frontier UI card ');
      if (saveAction || exportAction) {
        const name = saveAction ? 'save_note' : 'craft_file';
        const args = {card: currentSpec._ui.card};
        if (exportAction) args.format = {Word:'docx',PDF:'pdf',Excel:'xlsx',PowerPoint:'pptx'}[exportAction[1]];
        if (exportAction) args.open_in_desktop = text.includes('and open it in the Craft desktop');
        try {
          const result = await app.callServerTool({name, arguments: args});
          if (result.structuredContent?.spec) render(result);
          else notice(result.content?.find(x => x.type === 'text')?.text ?? 'The action returned no result.');
        } catch { notice('The host could not complete this action. You can retry.'); }
        return;
      }
    }
    if (!app.getHostCapabilities()?.message?.text) {
      notice('This host cannot send follow-ups. Copy this into the chat:', text);
      return;
    }
    try {
      const result = await app.sendMessage({role: 'user', content: [{type: 'text', text}]});
      if (result.isError) throw new Error('Host declined the message');
    } catch {
      notice('The host could not send this follow-up. Copy it into the chat:', text);
    }
  },
  async openLink(url) {
    try {
      const link = new URL(url);
      if (!['https:', 'http:'].includes(link.protocol)) throw new Error('Unsupported link');
      if (!app.getHostCapabilities()?.openLinks) throw new Error('Links unavailable');
      const result = await app.openLink({url: link.href});
      if (result.isError) throw new Error('Link declined');
    } catch {
      notice('The host could not open this link. Copy it to your browser:', url);
    }
  },
  resize(height) { app.sendSizeChanged({height: Math.min(height, app.getHostContext()?.containerDimensions?.maxHeight ?? height)}); },
  download(name, text, mime) {
    if (app.getHostCapabilities()?.downloadFile) {
      const bytes = new TextEncoder().encode(text);
      const blob = btoa(Array.from(bytes, byte => String.fromCharCode(byte)).join(''));
      app.downloadFile({contents:[{type:'resource',resource:{uri:'file:///'+encodeURIComponent(name),mimeType:mime,blob}}]})
        .catch(() => notice('The host could not download '+name+'. Copy its contents:',text));
      return true;
    }
    if (app.getHostContext()?.platform === 'mobile') {
      notice('This host cannot download '+name+'. Copy its contents to save it:',text);
      return true;
    }
    return false;
  },
  trackMap() {},
};

// Dispose upstream listeners, observers, timers and maps when a host delivers a new card.
function lifecycle() {
  const cleanups = [];
  let active = true;
  const doc = new Proxy(document, {get(target, key) {
    if (key === 'addEventListener') return (name, fn, options) => {
      target.addEventListener(name, fn, options);
      cleanups.push(() => target.removeEventListener(name, fn, options));
    };
    const value = Reflect.get(target, key, target);
    return typeof value === 'function' ? value.bind(target) : value;
  }});
  class Observer extends ResizeObserver {
    constructor(fn) { super(fn); cleanups.push(() => this.disconnect()); }
  }
  const timeout = (fn, delay, ...args) => {
    const id = setTimeout(() => { if (active) fn(...args); }, delay);
    cleanups.push(() => clearTimeout(id));
    return id;
  };
  const interval = (fn, delay, ...args) => {
    const id = setInterval(fn, delay, ...args);
    cleanups.push(() => clearInterval(id));
    return id;
  };
  const trackMap = map => {
    if (!active) { map.remove(); return; }
    cleanups.push(() => map.remove());
  };
  return {document: doc, ResizeObserver: Observer, setTimeout: timeout, setInterval: interval, trackMap,
    isActive: () => active,
    onLoad(fn) { window.addEventListener('load', fn); cleanups.push(() => window.removeEventListener('load', fn)); },
    dispose() { active = false; cleanups.splice(0).reverse().forEach(fn => fn()); }};
}

function controls() { return [...document.querySelectorAll('#app input, #app select, #app textarea')]; }
function snapshot() {
  return controls().map((el, index) => ({index, type: el.type, value: el.value, checked: el.checked}));
}
function restore(saved) {
  const nodes = controls();
  for (const item of saved ?? []) {
    const el = nodes[item.index];
    if (!el || el.type !== item.type) continue;
    el.value = item.value;
    el.checked = item.checked;
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
  }
}

function render(result) {
  const spec = result?.structuredContent?.spec;
  if (!spec) {
    if (result?.isError) notice(result.content?.find(x => x.type === 'text')?.text ?? 'The tool failed.');
    return;
  }
  if (currentSpec) values.set(JSON.stringify(currentSpec), snapshot());
  dispose();
  currentSpec = spec;
  document.getElementById('app').replaceChildren();
  document.getElementById('spec').textContent = JSON.stringify(spec);
  if (spec._ui?.cdn) document.querySelector('link[rel=stylesheet]').href = spec._ui.cdn+'/dist/maplibre-gl.css';
  const life = lifecycle();
  renderOriginal({...bridge, trackMap: life.trackMap}, life);
  dispose = life.dispose;
  restore(values.get(JSON.stringify(spec)));
  if (values.size > 20) values.delete(values.keys().next().value);
  theme(app.getHostContext());
  if (app.getHostCapabilities()?.serverTools) {
    const refresh = document.createElement('button');
    refresh.className = 'btn';
    refresh.textContent = 'Refresh data';
    refresh.onclick = async () => {
      refresh.disabled = true;
      try {
        const saved = snapshot();
        const { _ui, ...input } = currentSpec;
        render(await app.callServerTool({name: 'render_frontier_ui', arguments: {spec: input}}));
        restore(saved);
      } catch {
        notice('The host could not refresh this card. You can retry.');
      } finally { refresh.disabled = false; }
    };
    document.getElementById('app').append(refresh);
  }
  document.documentElement.dataset.frontierReady = 'true';
}

document.addEventListener('input', () => {
  clearTimeout(contextTimer);
  if (!app.getHostCapabilities()?.updateModelContext?.text) return;
  contextTimer = setTimeout(() => app.updateModelContext({content: [{type: 'text', text: JSON.stringify({title: currentSpec?.title, controls: snapshot()})}]}).catch(() => {}), 300);
});
app.ontoolresult = render;
app.ontoolinput = () => {};
app.onhostcontextchanged = theme;
app.onerror = error => {
  console.error('Frontier MCP host error:', error);
  notice('The MCP host connection reported an error.');
};
app.onteardown = async () => { dispose(); clearTimeout(contextTimer); return {}; };
app.connect().then(() => theme(app.getHostContext())).catch(() => notice('Open this widget from an MCP Apps host.'));
