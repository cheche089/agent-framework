// ============================================================
// OpenAgent Web UI - Main Application
// ============================================================

const App = {
  // State
  config: null,
  providers: [],
  currentConvId: null,
  isStreaming: false,
  conversations: [],

  // DOM refs
  els: {},

  async init() {
    this.els = {
      providerSelect: document.getElementById('provider-select'),
      modelSelect: document.getElementById('model-select'),
      chatMessages: document.getElementById('chat-messages'),
      chatInput: document.getElementById('chat-input'),
      sendBtn: document.getElementById('send-btn'),
      convList: document.getElementById('conversation-list'),
      newChatBtn: document.getElementById('new-chat-btn'),
      settingsBtn: document.getElementById('settings-btn'),
      settingsOverlay: document.getElementById('settings-overlay'),
      settingsClose: document.getElementById('settings-close'),
      settingsSave: document.getElementById('settings-save'),
      clearChatBtn: document.getElementById('clear-chat-btn'),
      inputHint: document.getElementById('input-hint'),
      settingTemp: document.getElementById('setting-temp'),
      settingTempVal: document.getElementById('setting-temp-val'),
      settingMaxTokens: document.getElementById('setting-max-tokens'),
      settingSystemPrompt: document.getElementById('setting-system-prompt'),
      apiKeysList: document.getElementById('api-keys-list'),
      toolsBtn: document.getElementById('tools-btn'),
      toolsOverlay: document.getElementById('tools-overlay'),
      toolsClose: document.getElementById('tools-close'),
    };

    await this.loadProviders();
    await this.loadConfig();
    await this.loadConversations();
    this.bindEvents();
    this.els.chatInput.addEventListener('input', () => this.autoResizeInput());
    this.updateSendButton();
  },

  // ---- Data Loading ----

  async loadProviders() {
    const res = await fetch('/api/providers');
    this.providers = await res.json();
    this.renderProviders();
  },

  async loadConfig() {
    const res = await fetch('/api/config');
    this.config = await res.json();
    this.applyConfig();
  },

  async saveConfig() {
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(this.config),
    });
  },

  async loadConversations() {
    const res = await fetch('/api/conversations');
    this.conversations = await res.json();
    this.renderConversations();
  },

  async createConversation() {
    const conv = {
      id: crypto.randomUUID(),
      title: '新对话',
      messages: [],
      created_at: new Date().toISOString(),
    };
    const res = await fetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(conv),
    });
    const saved = await res.json();
    this.conversations.unshift(saved);
    this.renderConversations();
    this.selectConversation(saved.id);
  },

  async deleteConversation(id, event) {
    event.stopPropagation();
    await fetch('/api/conversations/' + id, { method: 'DELETE' });
    this.conversations = this.conversations.filter(c => c.id !== id);
    this.renderConversations();
    if (this.currentConvId === id) {
      this.currentConvId = null;
      this.clearMessages();
    }
  },

  selectConversation(id) {
    this.currentConvId = id;
    const conv = this.conversations.find(c => c.id === id);
    if (!conv) return;
    this.renderConversations();
    this.renderMessages(conv.messages || []);
    this.els.chatInput.focus();
  },

  // ---- Rendering ----

  renderProviders() {
    const sel = this.els.providerSelect;
    sel.innerHTML = this.providers.map(p =>
      `<option value="${p.id}">${p.name}</option>`
    ).join('');
    sel.value = this.config?.provider || 'openai';
    this.renderModels();
  },

  renderModels() {
    const provider = this.providers.find(p => p.id === this.els.providerSelect.value);
    if (!provider) return;
    const sel = this.els.modelSelect;
    sel.innerHTML = provider.models.map(m =>
      `<option value="${m}">${m}</option>`
    ).join('');
    if (provider.models.includes(this.config?.model)) {
      sel.value = this.config.model;
    }
  },

  renderConversations() {
    const list = this.els.convList;
    list.innerHTML = this.conversations.map(c => {
      const time = new Date(c.updated_at || c.created_at);
      const timeStr = time.toLocaleDateString() + ' ' + time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const title = c.title || '新对话';
      return '<div class="conv-item' + (c.id === this.currentConvId ? ' active' : '') + '" data-id="' + c.id + '">' +
        '<span>' + this.escapeHtml(title) + '</span>' +
        '<span class="conv-time">' + timeStr + '</span>' +
        '<button class="conv-del" data-id="' + c.id + '" title="删除">✕</button>' +
        '</div>';
    }).join('');

    list.querySelectorAll('.conv-item').forEach(el => {
      el.addEventListener('click', (e) => {
        if (e.target.closest('.conv-del')) return;
        this.selectConversation(el.dataset.id);
      });
    });
    list.querySelectorAll('.conv-del').forEach(el => {
      el.addEventListener('click', (e) => this.deleteConversation(el.dataset.id, e));
    });
  },

  renderMessages(messages) {
    const container = this.els.chatMessages;
    container.innerHTML = '';
    if (!messages || messages.length === 0) {
      this.showWelcome();
      return;
    }
    messages.forEach(msg => this.appendMessage(msg.role, msg.content, false));
    container.scrollTop = container.scrollHeight;
  },

  showWelcome() {
    this.els.chatMessages.innerHTML = '<div class="welcome">' +
      '<div class="welcome-icon">◆</div>' +
      '<h2>OpenAgent</h2>' +
      '<p>选择一个模型并开始对话。支持多厂商 LLM，流式输出。</p>' +
      '</div>';
  },

  clearMessages() {
    this.els.chatMessages.innerHTML = '';
    this.showWelcome();
  },

  appendMessage(role, content, scroll = true) {
    const container = this.els.chatMessages;
    const div = document.createElement('div');
    div.className = 'message ' + role;
    const header = document.createElement('div');
    header.className = 'msg-header';
    header.textContent = role === 'user' ? '👤 你' : '◆ OpenAgent';
    div.appendChild(header);
    const body = document.createElement('div');
    body.className = 'msg-body';
    body.innerHTML = this.renderMarkdown(content);
    div.appendChild(body);
    container.appendChild(div);
    if (scroll) container.scrollTop = container.scrollHeight;
    return div;
  },

  renderMarkdown(text) {
    if (!text) return '';
    let html = this.escapeHtml(text);
    // Code blocks
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
      return '<pre><code class="language-' + lang + '">' + this.escapeHtml(code) + '</code></pre>';
    });
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    return html;
  },

  escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return String(text).replace(/[&<>"']/g, c => map[c]);
  },

  autoResizeInput() {
    const el = this.els.chatInput;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    this.updateSendButton();
  },

  updateSendButton() {
    const hasText = this.els.chatInput.value.trim().length > 0;
    const hasKey = this.hasActiveKey();
    this.els.sendBtn.disabled = !(hasText && hasKey && !this.isStreaming);
  },

  hasActiveKey() {
    if (!this.config || !this.config.api_keys) return false;
    const pid = this.els.providerSelect.value;
    return !!this.config.api_keys[pid];
  },

  // ---- Events ----

  bindEvents() {
    this.els.providerSelect.addEventListener('change', () => {
      this.renderModels();
      this.updateSendButton();
    });
    this.els.modelSelect.addEventListener('change', () => {
      this.config.model = this.els.modelSelect.value;
      this.saveConfig();
    });

    this.els.sendBtn.addEventListener('click', () => this.sendMessage());
    this.els.chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });
    this.els.chatInput.addEventListener('input', () => this.updateSendButton());

    this.els.newChatBtn.addEventListener('click', () => this.createConversation());

    this.els.toolsBtn.addEventListener('click', () => this.openTools());
    this.els.settingsBtn.addEventListener('click', () => this.openSettings());
    this.els.settingsClose.addEventListener('click', () => this.closeSettings());
    this.els.toolsClose.addEventListener('click', () => this.closeTools());
    this.els.toolsOverlay.addEventListener('click', (e) => {
      if (e.target === this.els.toolsOverlay) this.closeTools();
    });

    // Tools tab switching
    document.querySelectorAll('.tools-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.tools-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tools-tab-content').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const target = document.getElementById('tab-' + tab.dataset.tab);
        if (target) target.classList.add('active');
      });
    });

    // Web search
    document.getElementById('web-search-btn').addEventListener('click', () => {
      const q = document.getElementById('web-search-input').value;
      this.webSearch(q);
    });
    document.getElementById('web-search-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const q = document.getElementById('web-search-input').value;
        this.webSearch(q);
      }
    });
    this.els.settingsOverlay.addEventListener('click', (e) => {
      if (e.target === this.els.settingsOverlay) this.closeSettings();
    });
    this.els.settingsSave.addEventListener('click', () => this.saveSettings());

    this.els.settingTemp.addEventListener('input', () => {
      this.els.settingTempVal.textContent = this.els.settingTemp.value;
    });

    this.els.clearChatBtn.addEventListener('click', () => {
      if (this.currentConvId) {
        const conv = this.conversations.find(c => c.id === this.currentConvId);
        if (conv) {
          conv.messages = [];
          fetch('/api/conversations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(conv),
          });
          this.renderMessages([]);
        }
      } else {
        this.clearMessages();
      }
    });

    
  // ---- Tools & Skills ----

  async openTools() {
    this.els.toolsOverlay.classList.remove('hidden');
    await this.loadTools();
    await this.loadSkills();
    await this.loadCuratedSkills();
  },

  closeTools() {
    this.els.toolsOverlay.classList.add('hidden');
  },

  async loadTools() {
    const res = await fetch('/api/tools');
    const tools = await res.json();
    const list = document.getElementById('tool-list');
    list.innerHTML = tools.map(t =>
      '<div class="tool-item">' +
        '<div class="tool-info">' +
          '<div class="tool-name">' + t.name + '</div>' +
          '<div class="tool-desc">' + t.description + '</div>' +
        '</div>' +
        '<span class="tool-cat">' + t.category + '</span>' +
      '</div>'
    ).join('');
  },

  async loadSkills() {
    const res = await fetch('/api/skills');
    const skills = await res.json();
    const list = document.getElementById('installed-skills-list');
    if (skills.length === 0) {
      list.innerHTML = '<p style="color:var(--text-muted);font-size:13px;">暂无已安装的 Skill。切换到"安装"页签添加。</p>';
      return;
    }
    list.innerHTML = skills.map(s =>
      '<div class="skill-card">' +
        '<div class="skill-name">' + s.name + '<span class="skill-badge">' + (s.category || '通用') + '</span></div>' +
        '<div class="skill-desc">' + s.description + '</div>' +
        '<div class="skill-req">需要工具: ' +
          (s.requires && s.requires.length
            ? s.requires.map(r => '<span>' + r + '</span>').join(' ')
            : '<span>无</span>') +
        '</div>' +
        '<div class="skill-actions">' +
          '<button class="btn-uninstall" onclick="App.uninstallSkill(' + "'" + s.id + "'" + ')">卸载</button>' +
        '</div>' +
      '</div>'
    ).join('');
  },

  async loadCuratedSkills() {
    const res = await fetch('/api/skills/curated');
    const skills = await res.json();
    const installedRes = await fetch('/api/skills');
    const installed = await installedRes.json();
    const installedIds = installed.map(s => s.id);

    const list = document.getElementById('curated-skills-list');
    list.innerHTML = skills.map(s => {
      const isInstalled = installedIds.includes(s.id);
      return '<div class="skill-card">' +
        '<div class="skill-name">' + s.name + '<span class="skill-badge">' + (s.category || '通用') + '</span></div>' +
        '<div class="skill-desc">' + s.description + '</div>' +
        '<div class="skill-req">需要工具: ' +
          (s.requires && s.requires.length
            ? s.requires.map(r => '<span>' + r + '</span>').join(' ')
            : '<span>无</span>') +
        '</div>' +
        '<div class="skill-actions">' +
          (isInstalled
            ? '<button class="btn-uninstall" onclick="App.uninstallSkill(' + "'" + s.id + "'" + ')">已安装 - 卸载</button>'
            : '<button class="btn-install" onclick="App.installSkill(' + "'" + s.id + "'" + ')">安装</button>'
          ) +
        '</div>' +
      '</div>';
    }).join('');
  },

  async installSkill(skillId) {
    const btn = document.querySelector('#curated-skills-list .btn-install');
    const res = await fetch('/api/skills/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill_id: skillId }),
    });
    const data = await res.json();
    if (data.status === 'ok') {
      this.showToast('Skill "' + data.skill.name + '" 安装成功!');
      await this.loadCuratedSkills();
      await this.loadSkills();
    } else {
      this.showToast('安装失败: ' + (data.detail || '未知错误'), 'error');
    }
  },

  async uninstallSkill(skillId) {
    const res = await fetch('/api/skills/uninstall/' + skillId, { method: 'POST' });
    const data = await res.json();
    if (data.status === 'ok') {
      this.showToast('Skill 已卸载');
      await this.loadCuratedSkills();
      await this.loadSkills();
    }
  },

  async webSearch(query) {
    if (!query.trim()) return;
    const btn = document.getElementById('web-search-btn');
    const resultsDiv = document.getElementById('web-search-results');
    btn.disabled = true;
    btn.textContent = '搜索中...';
    resultsDiv.innerHTML = '<p style="color:var(--text-muted);">搜索中...</p>';

    try {
      const res = await fetch('/api/web/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query, num_results: 5 }),
      });
      const data = await res.json();

      if (data.results && data.results.length > 0) {
        resultsDiv.innerHTML = data.results.map(r =>
          '<div class="search-result">' +
            '<div class="sr-title" onclick="window.open(' + "'" + r.url + "'" + ','_blank')">' + this.escapeHtml(r.title) + '</div>' +
            '<div class="sr-url">' + this.escapeHtml(r.url) + '</div>' +
            '<div class="sr-snippet">' + this.escapeHtml(r.snippet) + '</div>' +
          '</div>'
        ).join('');
      } else {
        resultsDiv.innerHTML = '<p style="color:var(--text-muted);">未找到结果。</p>';
      }
    } catch (e) {
      resultsDiv.innerHTML = '<p style="color:var(--danger);">搜索失败: ' + e.message + '</p>';
    }

    btn.disabled = false;
    btn.textContent = '\u641c\u7d22';
  },

  showToast(msg, type) {
    // Simple toast notification
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = msg;
    toast.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);padding:10px 24px;border-radius:8px;font-size:13px;z-index:200;animation:slideUp 0.3s ease;background:' + (type === 'error' ? 'var(--danger)' : 'var(--accent)') + ';color:#fff;box-shadow:0 4px 20px rgba(0,0,0,0.4);';
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.3s'; setTimeout(() => toast.remove(), 300); }, 3000);
  },

document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (!this.els.settingsOverlay.classList.contains('hidden')) {
          this.closeSettings();
        }
      }
    });
  },

  async sendMessage() {
    const text = this.els.chatInput.value.trim();
    if (!text || this.isStreaming) return;

    if (!this.currentConvId) {
      await this.createConversation();
    }

    this.isStreaming = true;
    this.els.sendBtn.disabled = true;
    this.els.chatInput.value = '';
    this.autoResizeInput();

    this.appendMessage('user', text);

    // Typing indicator
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message assistant';
    typingDiv.innerHTML = '<div class="msg-header">◆ OpenAgent</div><div class="typing-indicator"><span></span><span></span><span></span></div>';
    this.els.chatMessages.appendChild(typingDiv);
    this.els.chatMessages.scrollTop = this.els.chatMessages.scrollHeight;

    const conv = this.conversations.find(c => c.id === this.currentConvId);
    const existingMessages = conv ? (conv.messages || []).map(m => ({ role: m.role, content: m.content })) : [];

    const providerId = this.els.providerSelect.value;
    const model = this.els.modelSelect.value;

    try {
      const ws = new WebSocket('ws://' + window.location.host + '/ws/chat');

      const payload = {
        provider_id: providerId,
        model: model,
        messages: [...existingMessages, { role: 'user', content: text }],
        temperature: parseFloat(this.config.temperature || 0.3),
        max_tokens: parseInt(this.config.max_tokens || 4096),
        system_prompt: this.config.system_prompt || '',
        conversation_id: this.currentConvId,
      };

      typingDiv.remove();

      const msgDiv = this.appendMessage('assistant', '', true);
      const bodyEl = msgDiv.querySelector('.msg-body');
      bodyEl.innerHTML = '';
      bodyEl.classList.add('streaming-cursor');

      let fullContent = '';

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'chunk') {
          fullContent += data.content;
          bodyEl.innerHTML = this.renderMarkdown(fullContent);
          this.els.chatMessages.scrollTop = this.els.chatMessages.scrollHeight;
        } else if (data.type === 'done') {
          bodyEl.classList.remove('streaming-cursor');
          bodyEl.innerHTML = this.renderMarkdown(data.content || fullContent);
          this.isStreaming = false;
          this.updateSendButton();
          this.els.chatInput.focus();
          this.loadConversations();
        } else if (data.type === 'error') {
          bodyEl.classList.remove('streaming-cursor');
          bodyEl.innerHTML = '<span style="color: var(--danger);">⚠️ ' + this.escapeHtml(data.content) + '</span>';
          this.isStreaming = false;
          this.updateSendButton();
        }
      };

      ws.onerror = () => {
        if (bodyEl) {
          bodyEl.classList.remove('streaming-cursor');
          bodyEl.innerHTML = '<span style="color: var(--danger);">⚠️ 连接错误</span>';
        }
        this.isStreaming = false;
        this.updateSendButton();
      };

      ws.onclose = () => {
        if (this.isStreaming) {
          if (bodyEl) bodyEl.classList.remove('streaming-cursor');
          this.isStreaming = false;
          this.updateSendButton();
        }
      };

      ws.onopen = () => {
        ws.send(JSON.stringify(payload));
      };

    } catch (e) {
      typingDiv.remove();
      this.appendMessage('assistant', '⚠️ 发送失败: ' + e.message);
      this.isStreaming = false;
      this.updateSendButton();
    }
  },

  // ---- Settings ----

  openSettings() {
    this.renderApiKeys();
    this.els.settingTemp.value = this.config.temperature || 0.3;
    this.els.settingTempVal.textContent = this.config.temperature || 0.3;
    this.els.settingMaxTokens.value = this.config.max_tokens || 4096;
    this.els.settingSystemPrompt.value = this.config.system_prompt || '';
    this.els.settingsOverlay.classList.remove('hidden');
  },

  closeSettings() {
    this.els.settingsOverlay.classList.add('hidden');
  },

  renderApiKeys() {
    const container = this.els.apiKeysList;
    const keys = this.config.api_keys || {};
    container.innerHTML = this.providers.map(p => {
      const val = keys[p.id] || '';
      const statusText = val ? '✓ 已配置' : '未配置';
      const stCls = val ? 'valid' : 'invalid';
      return '<div class="api-key-row">' +
        '<label>' + p.name + '</label>' +
        '<input type="password" data-provider="' + p.id + '" value="' + this.escapeHtml(val) + '" placeholder="' + p.env_key + '">' +
        '<span class="key-status ' + stCls + '">' + statusText + '</span>' +
        '</div>';
    }).join('');
  },

  saveSettings() {
    const keys = {};
    this.els.apiKeysList.querySelectorAll('input[data-provider]').forEach(input => {
      const val = input.value.trim();
      if (val) keys[input.dataset.provider] = val;
    });
    this.config.api_keys = keys;
    this.config.temperature = parseFloat(this.els.settingTemp.value);
    this.config.max_tokens = parseInt(this.els.settingMaxTokens.value);
    this.config.system_prompt = this.els.settingSystemPrompt.value.trim();
    this.config.provider = this.els.providerSelect.value;
    this.config.model = this.els.modelSelect.value;

    this.saveConfig();
    this.closeSettings();
    this.updateSendButton();
  },

  applyConfig() {
    if (!this.config) return;
    if (this.config.provider) {
      this.els.providerSelect.value = this.config.provider;
      this.renderModels();
    }
    this.updateSendButton();
  },
};

document.addEventListener('DOMContentLoaded', () => App.init());
