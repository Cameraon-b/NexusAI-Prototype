const API = '/api';

const riskLevels = [
  'SAFE / READ-ONLY',
  'DOCUMENTATION ONLY',
  'BACKUP WRITE OPERATION',
  'STATE-CHANGING / APPROVAL REQUIRED',
  'RESTORE-ONLY / HIGH RISK',
  'DESTRUCTIVE / EXPLICIT APPROVAL REQUIRED',
  'UNKNOWN / NEEDS REVIEW'
];

const agents = ['Cameron', 'Nova', 'Mira', 'Hermes', 'OpenClaw', 'System'];

async function api(path, options = {}) {
  const headers = {'Content-Type': 'application/json', ...(options.headers || {})};
  const res = await fetch(API + path, {...options, headers});
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  return res.json();
}

function esc(value) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

function riskClass(risk) {
  if (!risk) return 'unknown';
  if (risk.includes('SAFE')) return 'safe';
  if (risk.includes('DOCUMENTATION')) return 'doc';
  if (risk.includes('BACKUP')) return 'backup';
  if (risk.includes('STATE')) return 'state';
  if (risk.includes('RESTORE')) return 'restore';
  if (risk.includes('DESTRUCTIVE')) return 'destructive';
  return 'unknown';
}

function riskBadge(risk) {
  return `<span class="risk ${riskClass(risk)}">${esc(risk || 'UNKNOWN / NEEDS REVIEW')}</span>`;
}

function layout(title, body) {
  document.querySelector('#app').innerHTML = `
    <section class="panel">
      <div class="page-heading">
        <p class="eyebrow">AETHER internal operations</p>
        <h1>${esc(title)}</h1>
      </div>
      ${body}
    </section>`;
}

function card(title, value, link, tone = '') {
  return `<a class="metric ${tone}" href="${link}"><span>${esc(value)}</span><strong>${esc(title)}</strong></a>`;
}

function renderRows(items, columns) {
  if (!items.length) return '<p class="empty-state">No records yet.</p>';
  return `<div class="table-wrap"><table><thead><tr>${columns.map(c => `<th>${esc(c.label)}</th>`).join('')}</tr></thead><tbody>${items.map(item => `<tr>${columns.map(c => `<td>${c.render ? c.render(item) : esc(item[c.key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

function select(name, values, selected) {
  return `<select name="${name}">${values.map(v => `<option value="${esc(v)}" ${v===selected?'selected':''}>${esc(v)}</option>`).join('')}</select>`;
}

function viewButton(kind, id, label = 'Open') {
  return `<button class="secondary compact" type="button" onclick="open${kind}(${Number(id)})">${esc(label)}</button>`;
}

function truncate(value, max = 90) {
  const text = String(value ?? '');
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

async function dashboard() {
  const data = await api('/dashboard');
  layout('NexusAI Dashboard', `
    <p class="notice"><strong>AETHER policy:</strong> No agent shall chown the kingdom. NexusAI records coordination and approvals only; it does not execute commands.</p>
    <div class="metrics">
      ${card('Open Messages', data.open_messages.length, '/messages', 'blue')}
      ${card('Open / Active Tasks', data.open_tasks.length, '/tasks', 'green')}
      ${card('Pending Approvals', data.pending_approvals.length, '/approvals', 'amber')}
      ${card('Recent Logs', data.recent_logs.length, '/logs', 'slate')}
    </div>
    <div class="dashboard-grid">
      <section class="section-card"><h2>Pending Approvals</h2>${renderRows(data.pending_approvals, approvalColumns(false))}</section>
      <section class="section-card"><h2>Open / Active Tasks</h2>${renderRows(data.open_tasks, taskColumns(false))}</section>
      <section class="section-card"><h2>Open Messages</h2>${renderRows(data.open_messages, messageColumns(false))}</section>
      <section class="section-card"><h2>Recent Action Logs</h2>${renderRows(data.recent_logs, logColumns())}</section>
    </div>
  `);
}

function messageColumns(actions = true) {
  return [
    {label:'Open', render: i => viewButton('Message', i.id)},
    {label:'ID', key:'id'},
    {label:'From', key:'from'},
    {label:'To', key:'to'},
    {label:'Subject', render: i => `<strong>${esc(i.subject)}</strong>`},
    {label:'Preview', render: i => `<span class="muted">${esc(truncate(i.body))}</span>`},
    {label:'Risk', render: i => riskBadge(i.risk_level)},
    {label:'Status', render: i => statusPill(i.status)},
    ...(actions ? [{label:'Update', render: i => statusForm('messages', i.id, ['open','acknowledged','completed','archived'], i.status)}] : [])
  ];
}

function taskColumns(actions = true) {
  return [
    {label:'Open', render: i => viewButton('Task', i.id)},
    {label:'ID', key:'id'},
    {label:'Title', render: i => `<strong>${esc(i.title)}</strong>`},
    {label:'By', key:'created_by'},
    {label:'Assigned', key:'assigned_to'},
    {label:'Description', render: i => `<span class="muted">${esc(truncate(i.description))}</span>`},
    {label:'Risk', render: i => riskBadge(i.risk_level)},
    {label:'Status', render: i => statusPill(i.status)},
    ...(actions ? [{label:'Update', render: i => statusForm('tasks', i.id, ['open','in_progress','blocked','completed','cancelled'], i.status, true)}] : [])
  ];
}

function approvalColumns(actions = true) {
  return [
    {label:'Open', render: i => viewButton('Approval', i.id)},
    {label:'ID', key:'id'},
    {label:'Requested By', key:'requested_by'},
    {label:'For', key:'requested_for'},
    {label:'Action', render: i => `<strong>${esc(i.action_summary)}</strong>`},
    {label:'Risk', render: i => riskBadge(i.risk_level)},
    {label:'Status', render: i => statusPill(i.status)},
    ...(actions ? [{label:'Update', render: i => approvalForm(i)}] : [])
  ];
}

function logColumns() {
  return [
    {label:'Time', key:'timestamp'},
    {label:'Actor', key:'actor'},
    {label:'Action', key:'action_type'},
    {label:'Target', render: i => `${esc(i.target_type)} #${esc(i.target_id)}`},
    {label:'Summary', key:'summary'}
  ];
}

function statusPill(status) {
  return `<span class="status ${esc(status)}">${esc(status)}</span>`;
}

function statusForm(type, id, statuses, current, notes = false) {
  return `<form class="inline" onsubmit="patchStatus(event, '${type}', ${id})">
    ${select('status', statuses, current)}
    ${notes ? '<input name="completion_notes" placeholder="completion notes">' : ''}
    <button>Save</button>
  </form>`;
}

function approvalForm(item) {
  return `<form class="inline" onsubmit="patchApproval(event, ${item.id})">
    ${select('status', ['pending','approved','rejected','cancelled'], item.status)}
    <input name="approved_by" placeholder="approved by" value="${item.status === 'approved' ? esc(item.approved_by) : ''}">
    <input name="rejection_reason" placeholder="rejection reason">
    <button>Save</button>
  </form>`;
}

async function patchStatus(event, type, id) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target).entries());
  Object.keys(data).forEach(k => data[k] === '' && delete data[k]);
  await api(`/${type}/${id}`, {method:'PATCH', body: JSON.stringify(data)});
  closeModal();
  route();
}

async function patchApproval(event, id) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target).entries());
  Object.keys(data).forEach(k => data[k] === '' && delete data[k]);
  await api(`/approvals/${id}`, {method:'PATCH', body: JSON.stringify(data)});
  closeModal();
  route();
}

function field(label, value, mode = 'text') {
  const display = value || '—';
  const className = mode === 'long' ? 'detail-value long-text' : mode === 'code' ? 'detail-value command-text' : 'detail-value';
  const tag = mode === 'code' ? 'pre' : 'div';
  return `<div class="detail-field"><dt>${esc(label)}</dt><dd><${tag} class="${className}">${esc(display)}</${tag}></dd></div>`;
}

function modal(title, body) {
  closeModal();
  const wrapper = document.createElement('div');
  wrapper.className = 'modal-backdrop';
  wrapper.id = 'detail-modal';
  wrapper.innerHTML = `
    <section class="modal-card" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <header class="modal-header">
        <div><p class="eyebrow">Record detail</p><h2>${esc(title)}</h2></div>
        <button class="icon-button" type="button" onclick="closeModal()" aria-label="Close detail view">×</button>
      </header>
      <div class="modal-body">${body}</div>
    </section>`;
  wrapper.addEventListener('click', event => {
    if (event.target === wrapper) closeModal();
  });
  document.body.appendChild(wrapper);
}

function closeModal() {
  document.querySelector('#detail-modal')?.remove();
}

async function findById(path, id) {
  const items = await api(path);
  const item = items.find(record => Number(record.id) === Number(id));
  if (!item) throw new Error(`Record #${id} not found`);
  return item;
}

async function openMessage(id) {
  try {
    const item = await findById('/messages', id);
    modal(`Message #${item.id}: ${item.subject}`, `
      <dl class="detail-grid">
        ${field('ID', item.id)}
        ${field('From', item.from)}
        ${field('To', item.to)}
        ${field('Subject', item.subject)}
        <div class="detail-field full"><dt>Full body</dt><dd><div class="detail-value long-text">${esc(item.body)}</div></dd></div>
        <div class="detail-field"><dt>Risk level</dt><dd>${riskBadge(item.risk_level)}</dd></div>
        <div class="detail-field"><dt>Status</dt><dd>${statusPill(item.status)}</dd></div>
        ${field('Created at', item.created_at)}
        ${field('Updated at', item.updated_at)}
      </dl>
      <div class="detail-actions">
        <h3>Update status</h3>
        ${statusForm('messages', item.id, ['open','acknowledged','completed','archived'], item.status)}
      </div>`);
  } catch (err) {
    layout('Error', `<pre>${esc(err.stack || err.message || err)}</pre>`);
  }
}

async function openTask(id) {
  try {
    const item = await findById('/tasks', id);
    modal(`Task #${item.id}: ${item.title}`, `
      <dl class="detail-grid">
        ${field('ID', item.id)}
        ${field('Title', item.title)}
        <div class="detail-field full"><dt>Full description</dt><dd><div class="detail-value long-text">${esc(item.description)}</div></dd></div>
        ${field('Created by', item.created_by)}
        ${field('Assigned to', item.assigned_to)}
        <div class="detail-field"><dt>Risk level</dt><dd>${riskBadge(item.risk_level)}</dd></div>
        <div class="detail-field"><dt>Status</dt><dd>${statusPill(item.status)}</dd></div>
        ${field('Completion notes', item.completion_notes, 'long')}
        ${field('Created at', item.created_at)}
        ${field('Updated at', item.updated_at)}
      </dl>
      <div class="detail-actions">
        <h3>Update status</h3>
        ${statusForm('tasks', item.id, ['open','in_progress','blocked','completed','cancelled'], item.status, true)}
      </div>`);
  } catch (err) {
    layout('Error', `<pre>${esc(err.stack || err.message || err)}</pre>`);
  }
}

async function openApproval(id) {
  try {
    const item = await findById('/approvals', id);
    modal(`Approval #${item.id}: ${item.action_summary}`, `
      <p class="notice subtle"><strong>Safety:</strong> Proposed commands are displayed as inert text only. NexusAI has no run button and does not execute commands.</p>
      <dl class="detail-grid">
        ${field('ID', item.id)}
        ${field('Requested by', item.requested_by)}
        ${field('Requested for', item.requested_for)}
        ${field('Action summary', item.action_summary)}
        <div class="detail-field full"><dt>Proposed command / action text</dt><dd>
          <pre class="detail-value command-text">${esc(item.proposed_command || '—')}</pre>
          <button class="secondary compact" type="button" data-copy="${esc(item.proposed_command || '')}">Copy text</button>
        </dd></div>
        <div class="detail-field"><dt>Risk level</dt><dd>${riskBadge(item.risk_level)}</dd></div>
        <div class="detail-field full"><dt>Reason</dt><dd><div class="detail-value long-text">${esc(item.reason)}</div></dd></div>
        <div class="detail-field"><dt>Status</dt><dd>${statusPill(item.status)}</dd></div>
        ${field('Approved by', item.approved_by)}
        ${field('Approved at', item.approved_at)}
        ${field('Rejection reason', item.rejection_reason, 'long')}
        ${field('Created at', item.created_at)}
        ${field('Updated at', item.updated_at)}
      </dl>
      <div class="detail-actions">
        <h3>Record approval status</h3>
        ${approvalForm(item)}
      </div>`);
  } catch (err) {
    layout('Error', `<pre>${esc(err.stack || err.message || err)}</pre>`);
  }
}

async function pageMessages() {
  const items = await api('/messages');
  layout('Messages', `
    <form class="grid record-form" onsubmit="createMessage(event)">
      ${select('from', agents, 'Mira')}${select('to', agents, 'Nova')}
      <input name="subject" placeholder="Subject" required>
      ${select('risk_level', riskLevels, 'DOCUMENTATION ONLY')}
      <textarea name="body" placeholder="Message body" required></textarea>
      ${select('status', ['open','acknowledged','completed','archived'], 'open')}
      <button>Create Message</button>
    </form>
    ${renderRows(items, messageColumns())}
  `);
}

async function createMessage(event) {
  event.preventDefault();
  await api('/messages', {method:'POST', body: JSON.stringify(Object.fromEntries(new FormData(event.target).entries()))});
  route();
}

async function pageTasks() {
  const items = await api('/tasks');
  layout('Tasks', `
    <form class="grid record-form" onsubmit="createTask(event)">
      <input name="title" placeholder="Title" required>
      <textarea name="description" placeholder="Description" required></textarea>
      ${select('created_by', agents, 'Hermes')}${select('assigned_to', agents, 'Mira')}
      ${select('risk_level', riskLevels, 'UNKNOWN / NEEDS REVIEW')}${select('status', ['open','in_progress','blocked','completed','cancelled'], 'open')}
      <button>Create Task</button>
    </form>
    ${renderRows(items, taskColumns())}
  `);
}

async function createTask(event) {
  event.preventDefault();
  await api('/tasks', {method:'POST', body: JSON.stringify(Object.fromEntries(new FormData(event.target).entries()))});
  route();
}

async function pageApprovals() {
  const items = await api('/approvals');
  layout('Approval Requests', `
    <p class="notice subtle"><strong>Reminder:</strong> Approval records are coordination notes only. They never execute proposed commands.</p>
    <form class="grid record-form" onsubmit="createApproval(event)">
      ${select('requested_by', agents, 'Hermes')}${select('requested_for', agents, 'Cameron')}
      <input name="action_summary" placeholder="Action summary" required>
      ${select('risk_level', riskLevels, 'STATE-CHANGING / APPROVAL REQUIRED')}
      <textarea name="proposed_command" placeholder="Proposed command or action. Recorded only; never executed." required></textarea>
      <textarea name="reason" placeholder="Reason" required></textarea>
      ${select('status', ['pending','approved','rejected','cancelled'], 'pending')}
      <button>Create Approval Request</button>
    </form>
    ${renderRows(items, approvalColumns())}
  `);
}

async function createApproval(event) {
  event.preventDefault();
  await api('/approvals', {method:'POST', body: JSON.stringify(Object.fromEntries(new FormData(event.target).entries()))});
  route();
}

async function pageAgents() {
  const items = await api('/agents');
  layout('Agents', renderRows(items, [
    {label:'ID', key:'id'}, {label:'Name', key:'name'}, {label:'Description', key:'description'}, {label:'Created', key:'created_at'}
  ]));
}

async function pageLogs() {
  const items = await api('/logs');
  layout('Action Log', renderRows(items, logColumns()));
}

async function route() {
  try {
    const path = window.location.pathname;
    if (path === '/messages') return pageMessages();
    if (path === '/tasks') return pageTasks();
    if (path === '/approvals') return pageApprovals();
    if (path === '/agents') return pageAgents();
    if (path === '/logs') return pageLogs();
    return dashboard();
  } catch (err) {
    layout('Error', `<pre>${esc(err.stack || err.message || err)}</pre>`);
  }
}

document.addEventListener('click', async event => {
  const copyButton = event.target.closest('[data-copy]');
  if (!copyButton) return;
  try {
    await navigator.clipboard.writeText(copyButton.dataset.copy || '');
    copyButton.textContent = 'Copied';
    setTimeout(() => { copyButton.textContent = 'Copy text'; }, 1200);
  } catch (_) {
    copyButton.textContent = 'Copy unavailable';
  }
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape') closeModal();
});

route();
