class App {
  constructor() {
    this.config = null;
    this.providers = [];
    this.convs = [];
    this.curId = null;
    this.streaming = false;
  }
  async init() {
    this.el = {
      p: document.getElementById('sel-provider'),
      m: document.getElementById('sel-model'),
      msgs: document.getElementById('chat-msgs'),
      inp: document.getElementById('input-msg'),
      send: document.getElementById('btn-send'),
      cl: document.getElementById('conv-list'),
      nc: document.getElementById('btn-new'),
      set: document.getElementById('btn-settings'),
    };
    try {
      await this.loadProv();
      await this.loadCfg();
      await this.loadConvs();
      this.bind();
      this.updBtn();
    } catch(e) { this.err(e.message); }
  }
  async loadProv() {
    var r = await fetch('/api/providers');
    this.providers = await r.json();
    this.el.p.innerHTML = '';
    for (var i = 0; i < this.providers.length; i++) {
      var o = document.createElement('option');
      o.value = this.providers[i].id;
      o.text = this.providers[i].name;
      this.el.p.appendChild(o);
    }
    this.renderModels();
  }
  renderModels() {
    var pid = this.el.p.value;
    var p = null;
    for (var i = 0; i < this.providers.length; i++) {
      if (this.providers[i].id === pid) { p = this.providers[i]; break; }
    }
    if (!p) return;
    this.el.m.innerHTML = '';
    for (var i = 0; i < p.models.length; i++) {
      var o = document.createElement('option');
      o.value = p.models[i];
      o.text = p.models[i];
      this.el.m.appendChild(o);
    }
    if (this.config && p.models.indexOf(this.config.model) >= 0) {
      this.el.m.value = this.config.model;
    }
  }
  async loadCfg() {
    var r = await fetch('/api/config');
    this.config = await r.json();
    if (this.config.provider) {
      this.el.p.value = this.config.provider;
      this.renderModels();
    }
    this.updBtn();
  }
  async saveCfg(d) {
    await fetch('/api/config', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
  }
  async loadConvs() {
    var r = await fetch('/api/conversations');
    this.convs = await r.json();
    this.renderConvs();
  }
  renderConvs() {
    var self = this;
    var list = this.el.cl;
    list.innerHTML = '';
    for (var i = 0; i < this.convs.length; i++) {
      var c = this.convs[i];
      var cls = c.id === this.curId ? ' cv-item on' : ' cv-item';
      var t = c.title || '新对话';
      var d = document.createElement('div');
      d.className = cls;
      d.dataset.id = c.id;
      d.innerHTML = '<div>' + self.esc(t) + '</div><div class="tm">' + (c.updated_at||c.created_at||'').slice(0,10) + '</div>';
      d.addEventListener('click', function() { self.select(this.dataset.id); });
      list.appendChild(d);
    }
  }
  select(id) {
    this.curId = id;
    this.renderConvs();
    for (var i = 0; i < this.convs.length; i++) {
      if (this.convs[i].id === id) {
        this.renderMsgs(this.convs[i].messages || []);
        return;
      }
    }
  }
  renderMsgs(msgs) {
    var el = this.el.msgs;
    el.innerHTML = '';
    if (!msgs || msgs.length === 0) {
      el.innerHTML = '<div class="welcome"><h1>OpenAgent</h1><p>开始新对话</p></div>';
      return;
    }
    for (var i = 0; i < msgs.length; i++) {
      this.addMsg(msgs[i].role, msgs[i].content, false);
    }
    el.scrollTop = el.scrollHeight;
  }
  addMsg(role, content, scroll) {
    var el = this.el.msgs;
    var d = document.createElement('div');
    d.className = 'msg ' + role;
    var rl = role === 'user' ? '你' : 'OpenAgent';
    d.innerHTML = '<div class="rl">' + rl + '</div><div class="ct">' + this.fmt(content) + '</div>';
    el.appendChild(d);
    if (scroll !== false) el.scrollTop = el.scrollHeight;
    return d;
  }
  fmt(t) {
    if (!t) return '';
    var h = this.esc(t);
    h = h.replace(/\`\`\`(\w*)\n([\s\S]*?)\`\`\`/g, '<pre><code>$2</code></pre>');
    h = h.replace(/\`([^\`]+)\`/g, '<code>$1</code>');
    h = h.replace(/\n/g, '<br>');
    return h;
  }
  esc(t) { return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  hasKey() {
    if (!this.config) return false;
    var pid = this.el.p.value;
    if (this.config.api_keys && this.config.api_keys[pid]) return true;
    if (this.config._env_keys && this.config._env_keys[pid]) return true;
    for (var i = 0; i < this.providers.length; i++) {
      if (this.providers[i].id === pid && this.providers[i].has_env_key) return true;
    }
    return false;
  }
  updBtn() {
    var hasText = this.el.inp.value.trim().length > 0;
    var hasKey = this.hasKey();
    this.el.send.disabled = !(hasText && hasKey && !this.streaming);
  }
  bind() {
    var self = this;
    this.el.p.onchange = function() { self.renderModels(); self.updBtn(); };
    this.el.m.onchange = function() {
      self.config.model = self.el.m.value;
      self.saveCfg(self.config);
    };
    this.el.send.onclick = function() { self.send(); };
    this.el.inp.onkeydown = function(e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); self.send(); }
    };
    this.el.inp.oninput = function() { self.updBtn(); };
    this.el.nc.onclick = function() { self.newConv(); };
    this.el.set.onclick = function() { self.openSet(); };
    document.getElementById('modal-close').onclick = function() {
      document.getElementById('modal').classList.add('hide');
    };
    document.getElementById('btn-save').onclick = function() { self.saveSet(); };
    document.getElementById('st-temp').oninput = function(e) {
      document.getElementById('st-temp-v').textContent = e.target.value;
    };
  }
  async newConv() {
    var conv = {id:crypto.randomUUID(),title:'新对话',messages:[],created_at:new Date().toISOString()};
    var r = await fetch('/api/conversations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(conv)});
    var saved = await r.json();
    this.convs.unshift(saved);
    this.renderConvs();
    this.select(saved.id);
  }
  async send() {
    var self = this;
    var text = this.el.inp.value.trim();
    if (!text || this.streaming) return;
    if (!this.curId) await this.newConv();
    this.streaming = true;
    this.el.send.disabled = true;
    this.el.inp.value = '';
    this.updBtn();
    this.addMsg('user', text);
    var msgs = [];
    for (var i = 0; i < this.convs.length; i++) {
      if (this.convs[i].id === this.curId) {
        var conv = this.convs[i];
        if (conv.messages) {
          for (var j = 0; j < conv.messages.length; j++) {
            msgs.push({role: conv.messages[j].role, content: conv.messages[j].content});
          }
        }
        break;
      }
    }
    var td = document.createElement('div');
    td.className = 'msg assistant';
    td.innerHTML = '<div class="rl">OpenAgent</div><div class="ct"><div class="typing"><span></span><span></span><span></span></div></div>';
    this.el.msgs.appendChild(td);
    this.el.msgs.scrollTop = this.el.msgs.scrollHeight;
    try {
      var ws = new WebSocket('ws://' + location.host + '/ws/agent');
      var payload = {
        provider_id: this.el.p.value,
        model: this.el.m.value,
        messages: msgs.concat([{role:'user',content:text}]),
        temperature: parseFloat(this.config.temperature || 0.3),
        max_tokens: parseInt(this.config.max_tokens || 4096),
        system_prompt: this.config.system_prompt || '',
        conversation_id: this.curId,
      };
      td.remove();
      var md = this.addMsg('assistant', '');
      var ce = md.querySelector('.ct');
      ce.innerHTML = '';
      var full = '';
      ws.onmessage = function(e) {
        var d = JSON.parse(e.data);
        if (d.type === 'chunk') { full += d.content; ce.innerHTML = self.fmt(full); self.el.msgs.scrollTop = self.el.msgs.scrollHeight; }
        else if (d.type === 'status') { ce.innerHTML = '<em>' + self.esc(d.content) + '</em>'; } else if (d.type === 'progress') { ce.innerHTML = '<pre style=color:#888;font-size:12px>' + self.esc(d.content) + '</pre>'; } else if (d.type === 'done') { ce.innerHTML = self.fmt(d.content || full); self.streaming = false; self.updBtn(); self.el.inp.focus(); self.loadConvs(); }
        else if (d.type === 'error') { ce.innerHTML = '<span style=color:red>' + self.esc(d.content) + '</span>'; self.streaming = false; self.updBtn(); }
      };
      ws.onerror = function() { ce.innerHTML = '<span style=color:red>连接错误</span>'; self.streaming = false; self.updBtn(); };
      ws.onclose = function() { if (self.streaming) { self.streaming = false; self.updBtn(); } };
      ws.onopen = function() { ws.send(JSON.stringify(payload)); };
    } catch(e) {
      td.remove();
      this.addMsg('assistant', '发送失败: ' + e.message);
      this.streaming = false;
      this.updBtn();
    }
  }
  openSet() {
    this.renderKeys();
    document.getElementById('st-temp').value = this.config.temperature || 0.3;
    document.getElementById('st-temp-v').textContent = this.config.temperature || 0.3;
    document.getElementById('st-mt').value = this.config.max_tokens || 4096;
    document.getElementById('st-sp').value = this.config.system_prompt || '';
    document.getElementById('modal').classList.remove('hide');
  }
  renderKeys() {
    var c = document.getElementById('api-key-list');
    var keys = (this.config.api_keys) || {};
    var ek = (this.config._env_keys) || {};
    c.innerHTML = '';
    for (var i = 0; i < this.providers.length; i++) {
      var p = this.providers[i];
      var v = keys[p.id] || '';
      var he = ek[p.id] || p.has_env_key;
      var st, cls;
      if (v) { st = 'OK 已配置'; cls = 'ok'; }
      else if (he) { st = 'OK 环境变量'; cls = 'ok'; }
      else { st = '未配置'; cls = 'no'; }
      var row = document.createElement('div');
      row.className = 'api-row';
      row.innerHTML = '<label>' + this.esc(p.name) + '</label><input type=password data-p="' + p.id + '" value="' + this.esc(v) + '" placeholder="' + this.esc(p.env_key) + '"><span class="st ' + cls + '">' + st + '</span>';
      c.appendChild(row);
    }
  }
  saveSet() {
    var keys = {};
    var inputs = document.querySelectorAll('#api-key-list input[data-p]');
    for (var i = 0; i < inputs.length; i++) {
      var v = inputs[i].value.trim();
      if (v) keys[inputs[i].dataset.p] = v;
    }
    this.config.api_keys = keys;
    this.config.temperature = parseFloat(document.getElementById('st-temp').value);
    this.config.max_tokens = parseInt(document.getElementById('st-mt').value);
    this.config.system_prompt = document.getElementById('st-sp').value.trim();
    this.config.provider = this.el.p.value;
    this.config.model = this.el.m.value;
    this.saveCfg(this.config);
    document.getElementById('modal').classList.add('hide');
    this.updBtn();
  }
  err(msg) {
    var el = this.el.msgs || document.body;
    el.innerHTML = '<div style=color:red;padding:40px;text-align:center><h2>错误</h2><p>' + this.esc(msg) + '</p></div>';
  }
}
var app = new App();
document.addEventListener('DOMContentLoaded', function() { app.init(); });
