"""Extract the upstream renderer; leave the independent Open WebUI tool intact."""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
tree = ast.parse((ROOT.parent / "frontier_ui.py").read_text(encoding="utf-8-sig"))
html = ""
description = ""
def literal(node):
    if isinstance(node, ast.Name) and node.id == "_HTML":
        return html
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "replace":
        return literal(node.func.value).replace(*(ast.literal_eval(arg) for arg in node.args))
    return ast.literal_eval(node)

for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_HTML" for t in node.targets):
        html = literal(node.value)
    elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == "_HTML":
        html += ast.literal_eval(node.value)
    elif isinstance(node, ast.ClassDef) and node.name == "Tools":
        method = next(n for n in node.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "render_frontier_ui")
        description = ast.get_docstring(method)

scripts = re.findall(r'<script nonce="__NONCE__">(.*?)</script>', html, re.S)
assert len(scripts) == 3, "Upstream renderer layout changed; review extraction"
js = "\n".join(scripts)

def replace_once(old, new):
    global js
    assert js.count(old) == 1, f"Upstream bridge changed: {old[:60]}"
    js = js.replace(old, new)

replace_once("function sendPrompt(t){post({type:'input:prompt:submit',text:String(t)});}",
             "function sendPrompt(t){bridge.sendPrompt(String(t));}")
start = js.index("function openLink(u){")
end = js.index("var lastH=", start)
js = js[:start] + "function openLink(u){bridge.openLink(String(u));}\n" + js[end:]
# Content bounds allow shrinking after a host has expanded the iframe viewport.
replace_once("function reportHeight(){var h=Math.ceil(Math.max(document.body.scrollHeight,document.documentElement.scrollHeight));",
             "function reportHeight(){var h=Math.ceil(document.body.getBoundingClientRect().height);")
replace_once("post({type:'iframe:height',height:h});", "bridge.resize(h);")
start = js.index("try{var pr=parent.document.documentElement;")
end = js.index("function isDark()", start)
js = js[:start] + js[end:]
replace_once("box.dataset.base=useLocal?'local':'openfreemap';", "bridge.trackMap(map);box.dataset.base=useLocal?'local':'openfreemap';")
replace_once("function saveFile(name,text,mime){", "function saveFile(name,text,mime){if(bridge.download(name,text,mime))return;")
replace_once("function download(name,text,mime){", "function download(name,text,mime){if(bridge.download(name,text,mime))return;")
replace_once("if(UI.craft_desktop&&b.app){",
             "if(b.preview_url){var pv=h('button','btn',[icon('ext'),txt('span','','Open preview')]);"
             "pv.onclick=function(){I.openLink(b.preview_url);};bt.appendChild(pv);}if(UI.craft_desktop&&b.app){")
replace_once(" CDN:'__CDN__'", " CDN:(S._ui&&S._ui.cdn)||'__CDN__'")
replace_once(".then(function(r){var lib=r[0],useLocal=r[1];", ".then(function(r){if(!lifecycle.isActive())return;var lib=r[0],useLocal=r[1];")
replace_once("window.addEventListener('load',", "lifecycle.onLoad(")
js = js.replace("__NONCE__", "frontier-mcp").replace("__CDN__", "https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1")

dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
(dist / "renderer.js").write_text("export function renderOriginal(bridge, lifecycle) {\n" +
    "const {document, ResizeObserver, setTimeout, setInterval} = lifecycle;\n" + js + "\n}\n")
(dist / "style.css").write_text("\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)))
(dist / "description.json").write_text(json.dumps(description))
