const frame = document.querySelector('#app');
const save = document.querySelector('#save');
const refresh = document.querySelector('#refresh');
const status = document.querySelector('#status');
const params = new URLSearchParams(location.search);
const terminal = params.get('terminal_id'), path = params.get('path'), chat = params.get('chat_id');
const name = path?.split('/').at(-1);
const app = {docx: 'wordcraft', pptx: 'deckcraft', xlsx: 'gridcraft'}[name?.split('.').at(-1)?.toLowerCase()];
const token = localStorage.token || '';
const headers = {Authorization: `Bearer ${token}`};
const limit = 32 * 1024 * 1024;
let route, busy = false, ready = false;

function message(text) { status.textContent = text; }
function controls() { save.disabled = !ready || busy; refresh.disabled = busy; }
function session() {
  if (!token || localStorage.token !== token) throw Error('Session changed. Reopen the editor.');
}
async function request(url, options = {}) {
  session();
  const response = await fetch(url, {...options, headers, cache: 'no-store', redirect: 'error'});
  if (!response.ok) throw Error(response.status === 401 || response.status === 403 ? 'Access denied' : `Request failed (${response.status})`);
  return response;
}
async function open() {
  const response = await request(route + '/view?path=' + encodeURIComponent(path));
  if (Number(response.headers.get('content-length')) > limit) throw Error('File exceeds 32 MiB');
  const reader = response.body.getReader(), chunks = [];
  let length = 0;
  try {
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > limit) throw Error('File exceeds 32 MiB');
      chunks.push(value);
    }
  } finally { await reader.cancel(); }
  const bytes = await new Blob(chunks).arrayBuffer();
  session();
  frame.contentWindow.postMessage({type: app + ':open', name, bytes}, location.origin, [bytes]);
  ready = true;
  message('Opened from Terminal');
}

window.addEventListener('message', async event => {
  if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
  const data = event.data;
  if (data?.type === app + ':dirty') {
    if (data.dirty && !busy) message('Unsaved changes');
    return;
  }
  if (data?.type === app + ':failed') { message(data.error || 'Editor failed'); return; }
  if (data?.type !== app + ':ready' && data?.type !== app + ':save') return;
  if (busy) return;
  busy = true;
  controls();
  try {
    if (data.type === app + ':ready') await open();
    else {
      if (!ready || data.name !== name || data.saveAs) throw Error('Only Save to the original file is supported.');
      if (!(data.bytes instanceof ArrayBuffer) && !(data.bytes instanceof Uint8Array)) throw Error('Invalid save data');
      if (data.bytes.byteLength > limit) throw Error('File exceeds 32 MiB');
      message('Saving…');
      const form = new FormData();
      form.append('file', new File([data.bytes], name));
      const response = await request(route + '/upload?directory=' + encodeURIComponent(path.slice(0, path.lastIndexOf('/'))),
        {method: 'POST', body: form});
      await response.json();
      session();
      if (data.id != null) frame.contentWindow.postMessage({type: app + ':saved', id: data.id}, location.origin);
      message('Saved');
    }
  } catch (error) {
    message('Failed: ' + error.message);
    if (data?.id != null) frame.contentWindow.postMessage({type: app + ':failed', id: data.id, error: error.message}, location.origin);
  } finally { busy = false; controls(); }
});

refresh.onclick = async () => {
  busy = true;
  controls();
  message('Refreshing…');
  try { await open(); }
  catch (error) { message('Failed: ' + error.message); }
  finally { busy = false; controls(); }
};
save.onclick = async () => {
  try {
    session();
    message('Saving…');
    const result = await frame.contentWindow[app].execute('file.save', {});
    if (result?.ok === false) throw Error(result.error || 'Editor could not save');
  } catch (error) { message('Failed: ' + error.message); }
};

try {
  if (!app || !terminal || !/^[\w-]+$/.test(terminal) || !path?.startsWith('/home/user/') || path.includes('\0') ||
      (chat && !/^[\w-]+$/.test(chat))) throw Error('Invalid workspace document');
  const user = await (await request('/api/v1/auths/')).json();
  if (!user.id) throw Error('Sign in required');
  route = `/api/v1/terminals/${encodeURIComponent(terminal)}${chat ? '/chats/' + encodeURIComponent(chat) : ''}/files`;
  const apps = await (await fetch('/document-editor/apps.json', {cache: 'no-store'})).json();
  if (!apps[app]?.startsWith('/craft/' + app + '/')) throw Error('Editor unavailable');
  document.querySelector('#name').textContent = name;
  document.title = name + ' · Craft editor';
  refresh.disabled = false;
  frame.src = apps[app] + '?host=parent&webgl';
} catch (error) { message('Failed: ' + error.message); refresh.disabled = false; }
