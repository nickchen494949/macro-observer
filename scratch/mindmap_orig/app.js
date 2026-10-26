/* ── State ── */
// Workspaces (Tabs) state
let workspaces = [];
let activeWorkspaceId = null;
let tabTree = []; // [{type:'ws',wsId} | {type:'group',id,name,children:[...]}]
let _tabDragSrcId = null;
let _dragGroupId = null;
console.log('APP.JS VERSION: 20260820-3 LOADED');
let _tabDragOverEl = null;
let _tabDragNestMode = false;
let _tabDragStartY = 0;

const state = {
  nodes: [],
  arrows: [],
  mode: 'add-node', // add-node | add-arrow | select
  selectedNode: null,
  selectedNodes: [],  // multi-select for area selection
  selectedArrow: null,
  arrowStart: null,  // {nodeId, port}
  dragNode: null,
  dragOffset: { x: 0, y: 0 },
  didDrag: false,
  nextId: 1,
  // Zoom & Pan
  zoom: 1,
  panX: 0,
  panY: 0,
  isPanning: false,
  panStart: { x: 0, y: 0 },
  spaceHeld: false,
  panMoved: false,
  wasPanning: false,
  arrowStyle: 'curve',
  arrowDirection: 'single', // 'single' | 'double'
  arrowCurve: 80,
  arrowDashed: false,
  dragMode: 'branch', // 'node' | 'branch'
};

/* ── DOM refs ── */
const tabsContainer = document.getElementById('tabs-container');
const btnAddTab = document.getElementById('btn-add-tab');
const nodeLayer = document.getElementById('node-layer');
const arrowLayer = document.getElementById('arrow-layer');
const anchorLayer = document.getElementById('anchor-layer');
const canvas = document.getElementById('canvas-container');
const transformGroup = document.getElementById('transform-group');
const statusText = document.getElementById('status-text');
const editorPanel = document.getElementById('node-editor');
const zoomInfo = document.getElementById('zoom-info');

/* ── SVG defs (arrowhead markers) ── */
function initSVG() {
  const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
  const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
  marker.setAttribute('id', 'arrowhead');
  marker.setAttribute('markerWidth', '12');
  marker.setAttribute('markerHeight', '8');
  marker.setAttribute('refX', '11');
  marker.setAttribute('refY', '4');
  marker.setAttribute('orient', 'auto');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M0,0 L12,4 L0,8 L3,4 Z');
  path.setAttribute('fill', '#6366f1');
  marker.appendChild(path);
  defs.appendChild(marker);

  // Reverse arrowhead for bidirectional arrows
  const marker2 = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
  marker2.setAttribute('id', 'arrowhead-start');
  marker2.setAttribute('markerWidth', '12');
  marker2.setAttribute('markerHeight', '8');
  marker2.setAttribute('refX', '1');
  marker2.setAttribute('refY', '4');
  marker2.setAttribute('orient', 'auto');
  const path2 = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path2.setAttribute('d', 'M12,0 L0,4 L12,8 L9,4 Z');
  path2.setAttribute('fill', '#6366f1');
  marker2.appendChild(path2);
  defs.appendChild(marker2);

  arrowLayer.appendChild(defs);
}
initSVG();

/* ── Workspace & Tabs Logic ── */
function generateId() { return Math.random().toString(36).substr(2, 9); }

function saveCurrentWorkspaceState() {
  if (!activeWorkspaceId) return;
  const ws = workspaces.find(w => w.id === activeWorkspaceId);
  if (ws) {
    ws.state = {
      nodes: JSON.parse(JSON.stringify(state.nodes.filter(n => !n.isArrowLabel))),
      arrows: JSON.parse(JSON.stringify(state.arrows)),
      nextId: state.nextId,
      zoom: state.zoom,
      panX: state.panX,
      panY: state.panY
    };
  }
}

function loadWorkspaceState(ws) {
  state.nodes = JSON.parse(JSON.stringify(ws.state.nodes || []));
  state.arrows = JSON.parse(JSON.stringify(ws.state.arrows || []));
  state.nextId = ws.state.nextId || 1;
  state.zoom = ws.state.zoom || 1;
  state.panX = ws.state.panX || 0;
  state.panY = ws.state.panY || 0;
  
  // Clear selection state
  state.selectedNode = null;
  state.selectedArrow = null;
  state.dragNode = null;
  editorPanel.classList.add('hidden');
  
  // Safety: if any node lacks x/y, run autoLayout before rendering
  var needsLayout = state.nodes.some(function(n) {
    return n.x === undefined || n.y === undefined;
  });
  if (needsLayout && typeof autoLayout === 'function') {
    autoLayout(state.nodes, state.arrows);
  }

  refreshNodes();
  refreshArrows();
  transformGroup.style.transform = `scale(${state.zoom}) translate(${state.panX}px, ${state.panY}px)`;
  zoomInfo.textContent = Math.round(state.zoom * 100) + '%';
  saveToLocalStorage();
}

/* ── Tab Tree Helpers ── */
function tabTreeRemove(nodes, pred) {
  for (let i = 0; i < nodes.length; i++) {
    if (pred(nodes[i])) return nodes.splice(i, 1)[0];
    if (nodes[i].type === 'group') {
      const found = tabTreeRemove(nodes[i].children, pred);
      if (found) return found;
    }
  }
  return null;
}
function tabTreeRemoveWs(wsId) { tabTreeRemove(tabTree, n => n.type === 'ws' && n.wsId === wsId); }
function tabTreeGetGroups(nodes, result = []) {
  nodes.forEach(n => { if (n.type === 'group') { result.push(n); tabTreeGetGroups(n.children, result); } });
  return result;
}
function tabTreeFindParentArr(nodes, groupId) {
  for (const n of nodes) {
    if (n.type === 'group') {
      if (n.id === groupId) return nodes;
      const found = tabTreeFindParentArr(n.children, groupId);
      if (found) return found;
    }
  }
  return null;
}
function getAllWsIdsFromTree(nodes, result = new Set()) {
  nodes.forEach(n => {
    if (n.type === 'ws') result.add(n.wsId);
    if (n.type === 'group') {
      if (n.wsId) result.add(n.wsId);
      getAllWsIdsFromTree(n.children, result);
    }
  });
  return result;
}

/* ── Context Menu ── */
function hideTabContextMenu() {
  const m = document.getElementById('tab-context-menu');
  if (m) m.classList.add('hidden');
}
function buildContextMenu(menu, items, e) {
  items.forEach(item => {
    if (item.label === '---') {
      const sep = document.createElement('div'); sep.className = 'ctx-sep'; menu.appendChild(sep);
    } else {
      const btn = document.createElement('button');
      btn.className = 'ctx-item' + (item.danger ? ' ctx-danger' : '');
      btn.textContent = item.label;
      btn.onclick = () => { item.action(); hideTabContextMenu(); };
      menu.appendChild(btn);
    }
  });
  const x = Math.min(e.clientX, window.innerWidth - 200);
  const y = Math.min(e.clientY, window.innerHeight - items.length * 34 - 16);
  menu.style.left = x + 'px';
  menu.style.top = y + 'px';
  menu.classList.remove('hidden');
  setTimeout(() => document.addEventListener('click', hideTabContextMenu, { once: true }), 10);
}
function showTabContextMenu(e, ws, siblings) {
  e.preventDefault(); e.stopPropagation();
  hideTabContextMenu();
  const menu = document.getElementById('tab-context-menu');
  menu.innerHTML = '';
  const atRoot = siblings === tabTree;
  const groups = tabTreeGetGroups(tabTree);
  const items = [];
  items.push({ label: '📁 新建分组（以此开始）', action: () => {
    const name = prompt('分组名称:', '新分组'); if (!name || !name.trim()) return;
    const idx = siblings.findIndex(n => n.type === 'ws' && n.wsId === ws.id); if (idx < 0) return;
    const wsNode = siblings[idx];
    siblings[idx] = { type: 'group', id: generateId(), name: name.trim(), children: [wsNode] };
    renderTabs(); saveToLocalStorage();
  }});
  if (groups.length > 0) {
    items.push({ label: '---' });
    groups.forEach(g => {
      items.push({ label: `↳ 加入「${g.name}」`, action: () => {
        const node = tabTreeRemove(tabTree, n => n.type === 'ws' && n.wsId === ws.id);
        if (node) { g.children.push(node); renderTabs(); saveToLocalStorage(); }
      }});
    });
  }
  if (!atRoot) {
    items.push({ label: '---' });
    items.push({ label: '↑ 移出分组', action: () => {
      const node = tabTreeRemove(tabTree, n => n.type === 'ws' && n.wsId === ws.id);
      if (node) { tabTree.push(node); renderTabs(); saveToLocalStorage(); }
    }});
  }
  items.push({ label: '---' });
  items.push({ label: '✕ 关闭标签页', danger: true, action: () => closeWorkspace(ws.id) });
  buildContextMenu(menu, items, e);
}
function showGroupContextMenu(e, group) {
  e.preventDefault(); e.stopPropagation();
  hideTabContextMenu();
  const menu = document.getElementById('tab-context-menu');
  menu.innerHTML = '';
  const items = [];
  items.push({ label: '＋ 新建子标签页', action: () => {
    const name = prompt('标签页名称:', '画布 ' + (workspaces.length + 1)); if (!name || !name.trim()) return;
    const id = generateId();
    const newWs = { id, name: name.trim(), state: { nodes: [], arrows: [], nextId: 1, zoom: 1, panX: 0, panY: 0 } };
    workspaces.push(newWs); group.children.push({ type: 'ws', wsId: id });
    activeWorkspaceId = id; loadWorkspaceState(newWs); renderTabs(); saveToLocalStorage();
  }});
  items.push({ label: '📁 新建子分组', action: () => {
    const name = prompt('子分组名称:', '新子分组'); if (!name || !name.trim()) return;
    group.children.push({ type: 'group', id: generateId(), name: name.trim(), children: [] });
    renderTabs(); saveToLocalStorage();
  }});
  items.push({ label: '---' });
  items.push({ label: '✎ 重命名分组', action: () => {
    const name = prompt('重命名分组:', group.name); if (name && name.trim()) { group.name = name.trim(); renderTabs(); saveToLocalStorage(); }
  }});
  const parentArr = tabTreeFindParentArr(tabTree, group.id);
  if (parentArr && parentArr !== tabTree) {
    items.push({ label: '↑ 移出上层分组', action: () => {
      const node = tabTreeRemove(tabTree, n => n.type === 'group' && n.id === group.id);
      if (node) { tabTree.push(node); renderTabs(); saveToLocalStorage(); }
    }});
  }
  // 移入其他分组 — list all other groups as targets
  const allGroups = []; tabTreeGetGroups(tabTree, allGroups);
  // Exclude self and any descendants of self
  const selfDescendants = new Set();
  const descArr = []; tabTreeGetGroups(group.children, descArr);
  descArr.forEach(g => selfDescendants.add(g.id));
  selfDescendants.add(group.id);
  const otherGroups = allGroups.filter(g => !selfDescendants.has(g.id));
  if (otherGroups.length > 0) {
    items.push({ label: '---' });
    otherGroups.forEach(target => {
      const targetWs = target.wsId ? workspaces.find(w => w.id === target.wsId) : null;
      const targetName = targetWs ? targetWs.name : target.name;
      items.push({ label: '📂 移入「' + targetName + '」', action: () => {
        const node = tabTreeRemove(tabTree, n => n.type === 'group' && n.id === group.id);
        if (node) { target.children.push(node); renderTabs(); saveToLocalStorage(); }
      }});
    });
  }
  items.push({ label: '---' });
  items.push({ label: '🗑 删除分组（子项移至上层）', danger: true, action: () => {
    if (!confirm(`删除分组「${group.name}」？子标签页将移至上层。`)) return;
    const arr = tabTreeFindParentArr(tabTree, group.id) || tabTree;
    const idx = arr.findIndex(n => n.type === 'group' && n.id === group.id);
    if (idx >= 0) arr.splice(idx, 1, ...group.children);
    renderTabs(); saveToLocalStorage();
  }});
  buildContextMenu(menu, items, e);
}

/* ── Tab Rendering (recursive tree) ── */
function startInlineTabRename(nameEl, currentName, onSave) {
  if (!nameEl || nameEl.dataset.renaming === 'true') return;
  nameEl.dataset.renaming = 'true';

  const input = document.createElement('input');
  input.type = 'text';
  input.value = currentName;
  input.setAttribute('aria-label', '重命名标签页');
  input.style.cssText = `
    width:${Math.min(180, Math.max(90, currentName.length * 14 + 24))}px;
    min-width:70px;
    height:26px;
    padding:2px 6px;
    border:1px solid #6366f1;
    border-radius:4px;
    outline:none;
    background:#fff;
    color:#111827;
    font:inherit;
  `;

  nameEl.replaceWith(input);
  input.focus();
  input.select();

  let finished = false;
  const finish = save => {
    if (finished) return;
    finished = true;
    const nextName = input.value.trim();
    if (save && nextName) onSave(nextName);
    else renderTabs();
  };

  input.addEventListener('click', e => e.stopPropagation());
  input.addEventListener('dblclick', e => e.stopPropagation());
  input.addEventListener('keydown', e => {
    e.stopPropagation();
    if (e.key === 'Enter') { e.preventDefault(); finish(true); }
    if (e.key === 'Escape') { e.preventDefault(); finish(false); }
  });
  input.addEventListener('blur', () => finish(true), { once: true });
}

function renderTabs() {
  tabsContainer.innerHTML = '';
  _tabDragSrcId = null; _tabDragOverEl = null;
  tabTree.forEach(node => tabsContainer.appendChild(renderTabNode(node, tabTree)));
}
function renderTabNode(node, siblings) {
  if (node.type === 'ws') return renderLeafTab(node, siblings);
  if (node.type === 'group') return renderGroupCol(node);
  return document.createElement('div');
}
function renderGroupCol(group) {
  const col = document.createElement('div');
  col.className = 'tab-group-col'; col.dataset.groupId = group.id;
  const ws = group.wsId ? workspaces.find(w => w.id === group.wsId) : null;
  const header = document.createElement('div');
  header.className = 'tab-group-header' + (ws && ws.id === activeWorkspaceId ? ' active' : '');
  const nameEl = document.createElement('span'); nameEl.className = 'tab-group-name'; nameEl.textContent = ws ? ws.name : group.name;
  const arrow = document.createElement('span'); arrow.textContent = ' ▾'; arrow.style.cssText = 'font-size:9px;opacity:0.5;flex-shrink:0;';
  // + add child tab button
  const addBtn = document.createElement('div'); addBtn.className = 'tab-group-add'; addBtn.textContent = '+'; addBtn.title = '新建子标签页';
  addBtn.onclick = e => {
    e.stopPropagation();
    const name = '画布 ' + (workspaces.length + 1);
    const id = generateId();
    const newWs = { id, name, state: { nodes: [], arrows: [], nextId: 1, zoom: 1, panX: 0, panY: 0 } };
    workspaces.push(newWs); group.children.push({ type: 'ws', wsId: id });
    activeWorkspaceId = id; loadWorkspaceState(newWs); renderTabs(); saveToLocalStorage();
  };
  // × delete group button — ungroups: parent becomes standalone tab, children move up
  const delBtn = document.createElement('div'); delBtn.className = 'tab-group-del'; delBtn.textContent = '×'; delBtn.title = '解散分组';
  delBtn.onclick = e => {
    e.stopPropagation();
    const arr = tabTreeFindParentArr(tabTree, group.id) || tabTree;
    const idx = arr.findIndex(n => n.type === 'group' && n.id === group.id);
    if (idx >= 0) {
      const items = [];
      if (group.wsId) items.push({ type: 'ws', wsId: group.wsId });
      items.push(...group.children);
      arr.splice(idx, 1, ...items);
    }
    renderTabs(); saveToLocalStorage();
  };
  // ◀ move group left
  const moveLeftBtn = document.createElement('div'); moveLeftBtn.className = 'tab-group-add'; moveLeftBtn.textContent = '◀'; moveLeftBtn.title = '向左移动';
  moveLeftBtn.onclick = e => {
    e.stopPropagation();
    const arr = tabTreeFindParentArr(tabTree, group.id) || tabTree;
    const idx = arr.findIndex(n => n.type === 'group' && n.id === group.id);
    if (idx > 0) { [arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]]; renderTabs(); saveToLocalStorage(); }
  };
  // ▶ move group right
  const moveRightBtn = document.createElement('div'); moveRightBtn.className = 'tab-group-add'; moveRightBtn.textContent = '▶'; moveRightBtn.title = '向右移动';
  moveRightBtn.onclick = e => {
    e.stopPropagation();
    const arr = tabTreeFindParentArr(tabTree, group.id) || tabTree;
    const idx = arr.findIndex(n => n.type === 'group' && n.id === group.id);
    if (idx >= 0 && idx < arr.length - 1) { [arr[idx], arr[idx + 1]] = [arr[idx + 1], arr[idx]]; renderTabs(); saveToLocalStorage(); }
  };
  // ↓ move group into another group
  const moveIntoBtn = document.createElement('div'); moveIntoBtn.className = 'tab-group-add'; moveIntoBtn.textContent = '↓'; moveIntoBtn.title = '移入其他分组';
  moveIntoBtn.onclick = e => {
    e.stopPropagation();
    hideTabContextMenu();
    const menu = document.getElementById('tab-context-menu');
    menu.innerHTML = '';
    const menuItems = [];
    const allGrps = []; tabTreeGetGroups(tabTree, allGrps);
    const selfDesc = new Set(); const dArr = []; tabTreeGetGroups(group.children, dArr); dArr.forEach(g => selfDesc.add(g.id)); selfDesc.add(group.id);
    const targets = allGrps.filter(g => !selfDesc.has(g.id));
    if (targets.length === 0) {
      menuItems.push({ label: '（没有其他分组）' });
    } else {
      targets.forEach(target => {
        const tWs = target.wsId ? workspaces.find(w => w.id === target.wsId) : null;
        const tName = tWs ? tWs.name : target.name;
        menuItems.push({ label: '📂 移入「' + tName + '」', action: () => {
          const node = tabTreeRemove(tabTree, n => n.type === 'group' && n.id === group.id);
          if (node) { target.children.push(node); renderTabs(); saveToLocalStorage(); }
        }});
      });
    }
    buildContextMenu(menu, menuItems, e);
  };
  header.appendChild(nameEl); header.appendChild(arrow); header.appendChild(moveLeftBtn); header.appendChild(moveRightBtn); header.appendChild(moveIntoBtn); header.appendChild(addBtn); header.appendChild(delBtn);
  // Click header = switch to parent workspace
  if (ws) {
    header.onclick = () => switchWorkspace(ws.id);
  }
  header.addEventListener('dblclick', e => {
    e.stopPropagation();
    const currentName = ws ? ws.name : group.name;
    startInlineTabRename(nameEl, currentName, nextName => {
      if (ws) ws.name = nextName;
      else group.name = nextName;
      renderTabs();
      saveToLocalStorage();
    });
  });
  header.addEventListener('contextmenu', e => showGroupContextMenu(e, group));

  // Make group header draggable — drags the whole group
  header.draggable = true;
  header.addEventListener('dragstart', e => {
    _dragGroupId = group.id;
    _tabDragSrcId = null;
    e.dataTransfer.setData('text/plain', group.id);
    e.dataTransfer.effectAllowed = 'move';
    header.style.opacity = '0.4';
    console.log('GROUP DRAG START:', group.id, group.name);
    setTimeout(() => {
      document.querySelectorAll('.tab-nest-zone').forEach(z => z.classList.add('visible'));

    }, 0);
  });
  header.addEventListener('dragend', () => {
    header.style.opacity = '';
    _dragGroupId = null;
    document.querySelectorAll('.tab-nest-zone').forEach(z => z.classList.remove('visible', 'drag-over-nest'));

    if (_tabDragOverEl) { _tabDragOverEl.classList.remove('drag-over', 'drag-over-nest'); _tabDragOverEl = null; }
  });

  // Drop another group or tab onto this header = reorder
  header.addEventListener('dragover', e => {
    if (!_dragGroupId && !_tabDragSrcId) return;
    if (_dragGroupId === group.id) return;
    e.preventDefault();
    if (_tabDragOverEl !== header) {
      if (_tabDragOverEl) _tabDragOverEl.classList.remove('drag-over');
      _tabDragOverEl = header; header.classList.add('drag-over');
    }
  });
  header.addEventListener('dragleave', () => { header.classList.remove('drag-over'); if (_tabDragOverEl === header) _tabDragOverEl = null; });
  header.addEventListener('drop', e => {
    if (!_dragGroupId && !_tabDragSrcId) return;
    if (_dragGroupId === group.id) return;
    e.preventDefault(); e.stopPropagation();
    header.classList.remove('drag-over');
    
    const toParentArr = tabTreeFindParentArr(tabTree, group.id) || tabTree;
    const toIdx = toParentArr.findIndex(n => n.type === 'group' && n.id === group.id);

    if (_dragGroupId) {
      // Move dragged group next to this group
      const moved = tabTreeRemove(tabTree, n => n.type === 'group' && n.id === _dragGroupId);
      if (moved) {
        const newToIdx = toParentArr.findIndex(n => n.type === 'group' && n.id === group.id);
        toParentArr.splice(newToIdx, 0, moved);
      }
    } else if (_tabDragSrcId) {
      // Move dragged tab next to this group
      const moved = tabTreeRemove(tabTree, n => n.type === 'ws' && n.wsId === _tabDragSrcId);
      if (moved) {
        const newToIdx = toParentArr.findIndex(n => n.type === 'group' && n.id === group.id);
        toParentArr.splice(newToIdx, 0, moved);
      }
    }
    renderTabs(); saveToLocalStorage();
  });

  col.appendChild(header);

  // Visible ▼ nest zone below group header — drop here to add child to this group
  const groupNestZone = document.createElement('div');
  groupNestZone.className = 'tab-nest-zone';
  groupNestZone.textContent = '▼ 放入此分组';
  groupNestZone.addEventListener('dragover', e => {
    e.preventDefault(); e.stopPropagation();
    if (!_tabDragSrcId) return;
    if (ws && _tabDragSrcId === ws.id) return;
    groupNestZone.classList.add('drag-over-nest');
  });
  groupNestZone.addEventListener('dragleave', () => groupNestZone.classList.remove('drag-over-nest'));
  groupNestZone.addEventListener('drop', e => {
    e.preventDefault(); e.stopPropagation();
    groupNestZone.classList.remove('drag-over-nest');
    if (!_tabDragSrcId) return;
    if (ws && _tabDragSrcId === ws.id) return;
    const node = tabTreeRemove(tabTree, n => n.type === 'ws' && n.wsId === _tabDragSrcId);
    if (node) { group.children.push(node); renderTabs(); saveToLocalStorage(); }
  });
  col.appendChild(groupNestZone);

  const childRow = document.createElement('div'); childRow.className = 'tab-children-row';
  group.children.forEach(child => childRow.appendChild(renderTabNode(child, group.children)));
  col.appendChild(childRow);
  return col;
}
function renderLeafTab(node, siblings) {
  const ws = workspaces.find(w => w.id === node.wsId);
  if (!ws) return document.createElement('div');

  // Wrapper column: tab on top, nest-zone below
  const wrapper = document.createElement('div');
  wrapper.className = 'tab-wrapper';
  wrapper.dataset.wsId = ws.id;

  const tab = document.createElement('div');
  tab.className = `tab ${ws.id === activeWorkspaceId ? 'active' : ''}`;
  tab.draggable = true; tab.dataset.wsId = ws.id;
  if (ws.parentWorkspaceId) {
    const ind = document.createElement('span'); ind.textContent = '🔗 '; ind.style.cssText = 'font-size:10px;opacity:0.7;'; tab.appendChild(ind);
  }
  const nameSpan = document.createElement('span'); nameSpan.className = 'tab-name'; nameSpan.textContent = ws.name; nameSpan.title = ws.name;
  nameSpan.ondblclick = e => {
    e.stopPropagation();
    startInlineTabRename(nameSpan, ws.name, nextName => {
      ws.name = nextName;
      renderTabs();
      saveToLocalStorage();
    });
  };
  const closeBtn = document.createElement('div'); closeBtn.className = 'tab-close';
  closeBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
  closeBtn.onclick = e => { e.stopPropagation(); closeWorkspace(ws.id); };
  tab.onclick = () => switchWorkspace(ws.id);
  tab.addEventListener('contextmenu', e => showTabContextMenu(e, ws, siblings));

  // Drag start
  tab.addEventListener('dragstart', e => {
    _tabDragSrcId = ws.id;
    _dragGroupId = null;
    e.dataTransfer.setData('text/plain', ws.id);
    e.dataTransfer.effectAllowed = 'move';
    tab.style.opacity = '0.4';
    console.log('TAB DRAG START:', ws.id, ws.name);
    // Show all nest zones
    // Show all nest zones + pull-out zone
    setTimeout(() => {
      document.querySelectorAll('.tab-nest-zone').forEach(z => z.classList.add('visible'));

    }, 0);
  });
  tab.addEventListener('dragend', () => {
    tab.style.opacity = '';
    if (_tabDragOverEl) { _tabDragOverEl.classList.remove('drag-over'); _tabDragOverEl = null; }
    // Hide all nest zones + pull-out zone
    document.querySelectorAll('.tab-nest-zone').forEach(z => z.classList.remove('visible', 'drag-over-nest'));

  });

  // Drop on tab itself = REORDER
  tab.addEventListener('dragover', e => {
    e.preventDefault();
    if (!_tabDragSrcId && !_dragGroupId) return;
    if (_tabDragSrcId === ws.id) return;
    if (_tabDragOverEl !== tab) {
      if (_tabDragOverEl) _tabDragOverEl.classList.remove('drag-over');
      _tabDragOverEl = tab; tab.classList.add('drag-over');
    }
  });
  tab.addEventListener('dragleave', () => { tab.classList.remove('drag-over'); if (_tabDragOverEl === tab) _tabDragOverEl = null; });
  tab.addEventListener('drop', e => {
    e.preventDefault(); e.stopPropagation();
    tab.classList.remove('drag-over');
    if (!_tabDragSrcId && !_dragGroupId) return;
    if (_tabDragSrcId === ws.id) return;

    if (_tabDragSrcId) {
      // Move tab: same level reorder OR cross-level move
      const fromIdx = siblings.findIndex(n => n.type === 'ws' && n.wsId === _tabDragSrcId);
      const toIdx = siblings.findIndex(n => n.type === 'ws' && n.wsId === ws.id);
      if (fromIdx >= 0 && toIdx >= 0) {
        const [moved] = siblings.splice(fromIdx, 1);
        siblings.splice(toIdx, 0, moved);
      } else if (toIdx >= 0) {
        const moved = tabTreeRemove(tabTree, n => n.type === 'ws' && n.wsId === _tabDragSrcId);
        if (moved) {
          const newToIdx = siblings.findIndex(n => n.type === 'ws' && n.wsId === ws.id);
          siblings.splice(newToIdx, 0, moved);
        }
      }
    } else if (_dragGroupId) {
      // Move dragged group next to this tab
      const toIdx = siblings.findIndex(n => n.type === 'ws' && n.wsId === ws.id);
      if (toIdx >= 0) {
        const moved = tabTreeRemove(tabTree, n => n.type === 'group' && n.id === _dragGroupId);
        if (moved) {
          const newToIdx = siblings.findIndex(n => n.type === 'ws' && n.wsId === ws.id);
          siblings.splice(newToIdx, 0, moved);
        }
      }
    }
    renderTabs(); saveToLocalStorage();
  });

  tab.appendChild(nameSpan); tab.appendChild(closeBtn);
  wrapper.appendChild(tab);

  // Nest zone below the tab
  const nestZone = document.createElement('div');
  nestZone.className = 'tab-nest-zone';
  nestZone.textContent = '▼';
  nestZone.addEventListener('dragover', e => {
    e.preventDefault(); e.stopPropagation();
    if (!_tabDragSrcId || _tabDragSrcId === ws.id) return;
    nestZone.classList.add('drag-over-nest');
  });
  nestZone.addEventListener('dragleave', () => nestZone.classList.remove('drag-over-nest'));
  nestZone.addEventListener('drop', e => {
    e.preventDefault(); e.stopPropagation();
    nestZone.classList.remove('drag-over-nest');
    if (!_tabDragSrcId || _tabDragSrcId === ws.id) return;
    // NEST: target tab (ws) becomes the PARENT, dragged tab becomes the CHILD
    const targetNode = siblings.find(n => n.type === 'ws' && n.wsId === ws.id);
    if (!targetNode) return;
    const draggedNode = tabTreeRemove(tabTree, n => n.type === 'ws' && n.wsId === _tabDragSrcId);
    if (!draggedNode) return;
    const newTargetIdx = siblings.indexOf(targetNode);
    if (newTargetIdx >= 0) {
      // Target tab becomes the group header (wsId), dragged tab is the only child
      siblings[newTargetIdx] = { type: 'group', id: generateId(), name: ws.name, wsId: ws.id, children: [draggedNode] };
    }
    renderTabs(); saveToLocalStorage();
  });
  wrapper.appendChild(nestZone);

  return wrapper;
}

function createWorkspace(name = '画布 ' + (workspaces.length + 1), data = null) {
  saveCurrentWorkspaceState();
  const id = generateId();
  const newWs = {
    id,
    name,
    state: data || { nodes: [], arrows: [], nextId: 1, zoom: 1, panX: 0, panY: 0 }
  };
  workspaces.push(newWs);
  tabTree.push({ type: 'ws', wsId: id });
  activeWorkspaceId = id;
  loadWorkspaceState(newWs);
  renderTabs();
}

function switchWorkspace(id) {
  if (id === activeWorkspaceId) return;
  saveCurrentWorkspaceState();
  activeWorkspaceId = id;
  const ws = workspaces.find(w => w.id === id);
  if (ws) {
    loadWorkspaceState(ws);
    renderTabs();
  }
}

function closeWorkspace(id) {
  if (workspaces.length === 1) {
    if (confirm('确定要清空唯一的画布吗？')) {
      workspaces[0].state = { nodes: [], arrows: [], nextId: 1, zoom: 1, panX: 0, panY: 0 };
      loadWorkspaceState(workspaces[0]);
    }
    return;
  }

  const ws = workspaces.find(w => w.id === id);

  // Clean up: clear linkedWorkspaceId on parent node
  if (ws && ws.parentWorkspaceId && ws.parentNodeId) {
    const parentWs = workspaces.find(w => w.id === ws.parentWorkspaceId);
    if (parentWs && parentWs.state && parentWs.state.nodes) {
      const parentNode = parentWs.state.nodes.find(n => n.id === ws.parentNodeId);
      if (parentNode) parentNode.linkedWorkspaceId = null;
    }
    // Also clean live state if parent is the active workspace
    if (ws.parentWorkspaceId === activeWorkspaceId) {
      const liveNode = state.nodes.find(n => n.id === ws.parentNodeId);
      if (liveNode) {
        liveNode.linkedWorkspaceId = null;
        refreshNodes();
      }
    }
  }

  // Also recursively close any child sub-maps of this workspace
  const childWsIds = [];
  if (ws && ws.state && ws.state.nodes) {
    ws.state.nodes.forEach(n => {
      if (n.linkedWorkspaceId) childWsIds.push(n.linkedWorkspaceId);
    });
  }
  
  const idx = workspaces.findIndex(w => w.id === id);
  workspaces.splice(idx, 1);
  tabTreeRemoveWs(id);

  // Remove orphaned children
  childWsIds.forEach(cid => {
    const ci = workspaces.findIndex(w => w.id === cid);
    if (ci >= 0) workspaces.splice(ci, 1);
    tabTreeRemoveWs(cid);
  });
  
  if (id === activeWorkspaceId) {
    const nextWs = workspaces[Math.max(0, idx - 1)];
    activeWorkspaceId = nextWs.id;
    loadWorkspaceState(nextWs);
  }
  renderTabs();
  saveToLocalStorage();
}

// Attach Add Tab event
if (btnAddTab) btnAddTab.onclick = () => createWorkspace();

/* ── Hyperlink Sub-Map (Drill Into Node) ── */
function drillIntoNode(nodeId) {
  const n = state.nodes.find(nd => nd.id === nodeId);
  if (!n) return;

  // If this node already has a linked workspace, navigate to it
  if (n.linkedWorkspaceId) {
    const existing = workspaces.find(w => w.id === n.linkedWorkspaceId);
    if (existing) {
      switchWorkspace(existing.id);
      return;
    }
    // Linked workspace was deleted, clear the stale reference
    n.linkedWorkspaceId = null;
  }

  // Create a new workspace linked to this node
  const id = generateId();
  n.linkedWorkspaceId = id; // Set link BEFORE saving parent state
  saveCurrentWorkspaceState(); // Now parent state includes the linkedWorkspaceId
  const newWs = {
    id,
    name: n.label + ' (子图)',
    parentWorkspaceId: activeWorkspaceId,
    parentNodeId: nodeId,
    state: { nodes: [], arrows: [], nextId: 1, zoom: 1, panX: 0, panY: 0 }
  };
  workspaces.push(newWs);
  tabTree.push({ type: 'ws', wsId: id });
  activeWorkspaceId = id;
  loadWorkspaceState(newWs);
  renderTabs();

  triggerAutoSave();
  statusText.textContent = `已进入 "${n.label}" 的子图，可以在此继续展开分支`;
}

/* ── LocalStorage Auto-Save ── */
function saveToLocalStorage() {
  saveCurrentWorkspaceState();
  localStorage.setItem('sysMapWorkspaces', JSON.stringify(workspaces));
  localStorage.setItem('sysMapActiveId', activeWorkspaceId);
  localStorage.setItem('sysMapTabTree', JSON.stringify(tabTree));
}

function loadFromLocalStorage() {
  try {
    const savedWs = localStorage.getItem('sysMapWorkspaces');
    const savedActiveId = localStorage.getItem('sysMapActiveId');
    const savedTree = localStorage.getItem('sysMapTabTree');
    if (savedWs) {
      workspaces = JSON.parse(savedWs);
      activeWorkspaceId = savedActiveId || workspaces[0].id;
      if (savedTree) {
        tabTree = JSON.parse(savedTree);
        // Migrate old-format groups: if a group has no wsId but has a child
        // whose workspace name matches the group name, convert it
        migrateTabTree(tabTree);
        // Ensure any workspace not yet in the tree gets added (migration safety)
        const treeIds = getAllWsIdsFromTree(tabTree);
        workspaces.forEach(ws => { if (!treeIds.has(ws.id)) tabTree.push({ type: 'ws', wsId: ws.id }); });
      } else {
        tabTree = workspaces.map(ws => ({ type: 'ws', wsId: ws.id }));
      }
      const ws = workspaces.find(w => w.id === activeWorkspaceId) || workspaces[0];
      activeWorkspaceId = ws.id;
      loadWorkspaceState(ws);
      renderTabs();
      return true;
    }
  } catch(e) { console.error('Failed to load from local storage', e); }
  return false;
}

// Migrate old groups where both parent+child were stored as children
function migrateTabTree(nodes) {
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    if (n.type === 'group') {
      // Old format: group has no wsId, and one child matches the group name
      if (!n.wsId && n.children && n.children.length > 0) {
        const matchIdx = n.children.findIndex(c => {
          if (c.type !== 'ws') return false;
          const cws = workspaces.find(w => w.id === c.wsId);
          return cws && cws.name === n.name;
        });
        if (matchIdx >= 0) {
          // Promote matching child to be the group's wsId
          n.wsId = n.children[matchIdx].wsId;
          n.children.splice(matchIdx, 1);
        }
      }
      // Recurse into children
      migrateTabTree(n.children);
    }
  }
}

// Auto-save triggers are hooked up to state modification functions.
// We will intercept changes and call saveToLocalStorage().
// To keep it simple, we just hook saveToLocalStorage() into functions that mutate state.
function triggerAutoSave() {
  saveToLocalStorage();
}

/* ── Toolbar ── */
document.getElementById('btn-add-node').onclick = () => setMode('add-node');
document.getElementById('btn-add-arrow').onclick = () => setMode('add-arrow');
document.getElementById('btn-select').onclick = () => setMode('select');
document.getElementById('btn-add-group').onclick = () => setMode('add-group');
document.getElementById('btn-add-label').onclick = () => setMode('add-label');
document.getElementById('btn-add-free-arrow').onclick = () => setMode('add-free-arrow');
document.getElementById('btn-delete').onclick = deleteSelected;
document.getElementById('btn-clear').onclick = clearAll;
document.getElementById('btn-export').onclick = exportPNG;
document.getElementById('btn-save').onclick = saveJSON;
document.getElementById('btn-load').onclick = loadJSON;
document.getElementById('edit-apply').onclick = applyEdit;
document.getElementById('edit-drill').onclick = () => {
  if (state.selectedNode !== null) {
    applyEdit(); // save any pending edits first
    drillIntoNode(state.selectedNode);
  }
};
document.getElementById('btn-toggle-line').onclick = () => {
  if (state.selectedArrow) {
    // Toggle only selected arrow
    const a = state.arrows.find(ar => ar.id === state.selectedArrow);
    if (a) {
      a.isStraight = !a.isStraight;
      refreshArrows();
      statusText.textContent = a.isStraight ? '✅ 所选箭头已切换为直线' : '✅ 所选箭头已切换为曲线';
      triggerAutoSave();
    }
  } else {
    // Change default for NEW arrows only (don't overwrite all existing ones)
    state.arrowStyle = state.arrowStyle === 'curve' ? 'straight' : 'curve';
    var isStraight = state.arrowStyle === 'straight';
    document.querySelector('#btn-toggle-line').textContent = isStraight ? '直线连线' : '曲线连线';
    statusText.textContent = isStraight ? '✏️ 之后画的新箭头将是直线' : '✏️ 之后画的新箭头将是曲线';
  }
};

document.getElementById('btn-toggle-dir').onclick = () => {
  if (state.selectedArrow) {
    // Toggle only selected arrow
    const a = state.arrows.find(ar => ar.id === state.selectedArrow);
    if (a) {
      a.bidir = !a.bidir;
      refreshArrows();
      statusText.textContent = a.bidir ? '✅ 所选箭头已切换为双向' : '✅ 所选箭头已切换为单向';
      triggerAutoSave();
    }
  } else {
    // Change default for NEW arrows only
    state.arrowDirection = state.arrowDirection === 'single' ? 'double' : 'single';
    var isDouble = state.arrowDirection === 'double';
    document.querySelector('#btn-toggle-dir').textContent = isDouble ? '↔ 双向' : '→ 单向';
    statusText.textContent = isDouble ? '✏️ 之后画的新箭头将是双向' : '✏️ 之后画的新箭头将是单向';
  }
};

document.getElementById('btn-toggle-dash').onclick = () => {
  if (state.selectedArrow) {
    const a = state.arrows.find(ar => ar.id === state.selectedArrow);
    if (a) {
      a.isDashed = !a.isDashed;
      refreshArrows();
      statusText.textContent = a.isDashed ? '✅ 所选箭头已切换为虚线' : '✅ 所选箭头已切换为实线';
      triggerAutoSave();
    }
  } else {
    state.arrowDashed = !state.arrowDashed;
    document.querySelector('#btn-toggle-dash').textContent = state.arrowDashed ? '虚线连线' : '实线连线';
    statusText.textContent = state.arrowDashed ? '✏️ 之后画的新箭头将是虚线' : '✏️ 之后画的新箭头将是实线';
  }
};

document.getElementById('arrow-curve').addEventListener('input', (e) => {
  const val = parseInt(e.target.value, 10);
  state.arrowCurve = val;
  if (state.selectedArrow) {
    const a = state.arrows.find(ar => ar.id === state.selectedArrow);
    if (a) {
      a.curveOffset = val;
      refreshArrows();
      statusText.textContent = `✅ 所选曲线弧度已调整为 ${val}`;
      triggerAutoSave();
    }
  } else {
    statusText.textContent = `✏️ 之后画的新曲线弧度将是 ${val}`;
  }
});

document.getElementById('btn-drag-mode').onclick = () => {
  state.dragMode = state.dragMode === 'branch' ? 'node' : 'branch';
  const btn = document.getElementById('btn-drag-mode');
  const isBranch = state.dragMode === 'branch';
  btn.querySelector('span').textContent = isBranch ? '整支移动' : '单节点';
  btn.classList.toggle('active', isBranch);
  statusText.textContent = isBranch ? '拖动时将移动整个分支' : '拖动时只移动单个节点';
};
document.getElementById('btn-zoom-in').onclick = () => zoomBy(0.15);
document.getElementById('btn-zoom-out').onclick = () => zoomBy(-0.15);
document.getElementById('zoom-info').onclick = resetView;

// Make zoom controls draggable
(function() {
  const zc = document.getElementById('zoom-controls');
  let drag = false, didDrag = false, sx, sy, sl, st;
  zc.addEventListener('mousedown', (e) => {
    if (e.target.closest('.zoom-btn')) return; // let buttons work
    drag = true; didDrag = false;
    const r = zc.getBoundingClientRect();
    sx = e.clientX; sy = e.clientY; sl = r.left; st = r.top;
    e.preventDefault();
  });
  document.addEventListener('mousemove', (e) => {
    if (!drag) return;
    if (Math.abs(e.clientX-sx)>3||Math.abs(e.clientY-sy)>3) didDrag = true;
    if (didDrag) {
      zc.style.left = (sl + e.clientX - sx) + 'px';
      zc.style.top = (st + e.clientY - sy) + 'px';
      zc.style.right = 'auto'; zc.style.bottom = 'auto';
    }
  });
  document.addEventListener('mouseup', () => { drag = false; });
})();

/* ── Zoom & Pan ── */
function applyTransform() {
  transformGroup.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
  zoomInfo.textContent = Math.round(state.zoom * 100) + '%';
}

function zoomBy(delta) {
  const oldZoom = state.zoom;
  state.zoom = Math.min(3, Math.max(0.2, state.zoom + delta));
  // Zoom toward center of canvas
  const cr = canvas.getBoundingClientRect();
  const cx = cr.width / 2, cy = cr.height / 2;
  state.panX = cx - (cx - state.panX) * (state.zoom / oldZoom);
  state.panY = cy - (cy - state.panY) * (state.zoom / oldZoom);
  applyTransform();
  refreshArrows();
}

function zoomAtPoint(delta, px, py) {
  const oldZoom = state.zoom;
  state.zoom = Math.min(3, Math.max(0.2, state.zoom + delta));
  state.panX = px - (px - state.panX) * (state.zoom / oldZoom);
  state.panY = py - (py - state.panY) * (state.zoom / oldZoom);
  applyTransform();
  refreshArrows();
  triggerAutoSave();
}

function resetView() {
  state.zoom = 1; state.panX = 0; state.panY = 0;
  applyTransform();
  refreshArrows();
  triggerAutoSave();
}

/* ── Locate & Highlight (for AI) ── */
function highlightNodes(labels) {
  const found = [];
  labels.forEach(label => {
    const n = state.nodes.find(nd => nd.label === label);
    if (!n) return;
    const el = nodeLayer.querySelector(`[data-id="${n.id}"]`);
    if (el) { el.classList.add('ai-highlight'); found.push(n); }
  });
  return found;
}

// Trace full branch: ancestors (up) + descendants (down) + highlight arrows
function highlightBranch(label) {
  const n = state.nodes.find(nd => nd.label === label);
  if (!n) return [];

  const visited = new Set();
  const arrowIds = new Set();

  // Walk UP (find ancestors via incoming arrows)
  function walkUp(id) {
    if (visited.has(id)) return;
    visited.add(id);
    state.arrows.forEach(a => {
      if (a.to === id && !visited.has(a.from)) {
        arrowIds.add(a.id);
        walkUp(a.from);
      }
    });
  }

  // Walk DOWN (find descendants via outgoing arrows)
  function walkDown(id) {
    if (visited.has(id)) return;
    visited.add(id);
    state.arrows.forEach(a => {
      if (a.from === id && !visited.has(a.to)) {
        arrowIds.add(a.id);
        walkDown(a.to);
      }
    });
  }

  walkUp(n.id);
  visited.delete(n.id); // reset so walkDown includes it
  walkDown(n.id);

  // Highlight all nodes in the branch
  const found = [];
  visited.forEach(id => {
    const nd = state.nodes.find(x => x.id === id);
    if (!nd) return;
    const el = nodeLayer.querySelector(`[data-id="${id}"]`);
    if (el) { el.classList.add('ai-highlight'); found.push(nd); }
  });

  // Highlight arrows
  arrowIds.forEach(aid => {
    const g = arrowLayer.querySelector(`[data-id="${aid}"]`);
    if (g) g.classList.add('arrow-highlight');
  });

  return found;
}

function unhighlightAll() {
  nodeLayer.querySelectorAll('.node.ai-highlight').forEach(el => el.classList.remove('ai-highlight'));
  arrowLayer.querySelectorAll('.arrow-highlight').forEach(el => el.classList.remove('arrow-highlight'));
}
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') unhighlightAll(); });

function locateNode(label) {
  const n = state.nodes.find(nd => nd.label === label);
  if (!n) return false;
  const el = nodeLayer.querySelector(`[data-id="${n.id}"]`);
  if (!el) return false;
  // Pan to center the node on screen
  const cr = canvas.getBoundingClientRect();
  const nw = el.offsetWidth, nh = el.offsetHeight;
  const targetX = cr.width / 2 - (n.x + nw / 2) * state.zoom;
  const targetY = cr.height / 2 - (n.y + nh / 2) * state.zoom;
  // Smooth transition
  transformGroup.style.transition = 'transform 0.5s ease';
  state.panX = targetX;
  state.panY = targetY;
  applyTransform();
  setTimeout(() => { transformGroup.style.transition = ''; refreshArrows(); }, 550);
  // Highlight it
  highlightNodes([label]);
  return true;
}

/* ── Map API (for AI) ── */
window.mapAPI = {
  // Query
  getNodes() { return state.nodes.map(n => ({ id: n.id, label: n.label, desc: n.desc || '', x: n.x, y: n.y })); },
  getEdges() { return state.arrows.map(a => { const f = state.nodes.find(n=>n.id===a.from); const t = state.nodes.find(n=>n.id===a.to); return { from: f?.label, to: t?.label, label: a.label || '' }; }); },
  findNode(label) { return state.nodes.find(n => n.label === label); },

  // Create
  addNode(label, desc, nearLabel, color) {
    let x = 300 + Math.random()*200, y = 200 + Math.random()*200;
    if (nearLabel) { const ref = state.nodes.find(n=>n.label===nearLabel); if(ref){x=ref.x+160;y=ref.y+30;} }
    return createNode(x, y, label, desc||'', color||'#ffffff', '#6366f1');
  },
  addEdge(fromLabel, toLabel, label) {
    const f = state.nodes.find(n=>n.label===fromLabel), t = state.nodes.find(n=>n.label===toLabel);
    if(!f||!t) return null;
    const bp = bestPorts(f,t); return createArrow(f.id, bp.fromPort, t.id, bp.toPort, label||'');
  },

  // Modify
  editNode(label, props) {
    const n = state.nodes.find(nd=>nd.label===label); if(!n) return false;
    if(props.label) n.label = props.label;
    if(props.desc !== undefined) n.desc = props.desc;
    if(props.color) n.bg = props.color;
    if(props.border) n.border = props.border;
    const el = nodeLayer.querySelector(`[data-id="${n.id}"]`);
    if(el){ el.querySelector('.label').textContent=n.label; if(props.color)el.style.background=n.bg; if(props.border)el.style.borderColor=n.border; }
    return true;
  },

  // Delete
  deleteNode(label) {
    const n = state.nodes.find(nd=>nd.label===label); if(!n) return false;
    state.arrows = state.arrows.filter(a=>a.from!==n.id&&a.to!==n.id);
    state.nodes = state.nodes.filter(nd=>nd.id!==n.id);
    nodeLayer.querySelector(`[data-id="${n.id}"]`)?.remove();
    refreshArrows(); return true;
  },
  deleteEdge(fromLabel, toLabel) {
    const idx = state.arrows.findIndex(a=>{ const f=state.nodes.find(n=>n.id===a.from); const t=state.nodes.find(n=>n.id===a.to); return f?.label===fromLabel&&t?.label===toLabel; });
    if(idx<0) return false;
    const aid=state.arrows[idx].id; state.arrows.splice(idx,1); arrowLayer.querySelector(`[data-id="${aid}"]`)?.remove(); return true;
  },

  // Visual
  highlight(labels) { return highlightNodes(Array.isArray(labels)?labels:[labels]); },
  highlightBranch(label) { return highlightBranch(label); },
  unhighlight() { unhighlightAll(); },
  locate(label) { return locateNode(label); },

  // Bulk
  clear() { state.nodes=[]; state.arrows=[]; nodeLayer.innerHTML=''; arrowLayer.querySelectorAll('g').forEach(g=>g.remove()); },
  resetView() { resetView(); },
  refreshArrows() { refreshArrows(); },

  // Log (shows result in status bar)
  log(msg) { statusText.textContent = msg; }
};

// Convert screen coords to canvas coords (accounting for zoom+pan)
function screenToCanvas(clientX, clientY) {
  const cr = canvas.getBoundingClientRect();
  return {
    x: (clientX - cr.left - state.panX) / state.zoom,
    y: (clientY - cr.top - state.panY) / state.zoom
  };
}

// Convert screen coords to SVG coords using SVG's native matrix (most accurate for arrows)
function screenToSvg(clientX, clientY) {
  const ctm = arrowLayer.getScreenCTM();
  if (ctm) {
    const inv = ctm.inverse();
    return {
      x: inv.a * clientX + inv.c * clientY + inv.e,
      y: inv.b * clientX + inv.d * clientY + inv.f
    };
  }
  // Fallback
  return screenToCanvas(clientX, clientY);
}

function setMode(m) {
  state.mode = m;
  document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
  const map = { 'add-node': 'btn-add-node', 'add-arrow': 'btn-add-arrow', 'select': 'btn-select', 'add-group': 'btn-add-group', 'add-label': 'btn-add-label', 'add-free-arrow': 'btn-add-free-arrow' };
  if (map[m]) document.getElementById(map[m]).classList.add('active');
  document.body.classList.toggle('arrow-mode', m === 'add-arrow');
  canvas.style.cursor = m === 'select' ? 'default' : 'crosshair';
  const msgs = { 'add-node': '点击画布添加节点', 'add-arrow': '点击第一个节点开始连线', 'select': '点击选择节点或箭头', 'add-group': '点击画布添加分组容器', 'add-label': '点击画布添加文字标注', 'add-free-arrow': '点击画布放置独立箭头（可拖动端点）' };
  statusText.textContent = msgs[m] || '就绪';
  deselectAll();
  state.arrowStart = null;
  removeTempArrow();
}

function bestPorts(fromNode, toNode) {
  const fEl = document.querySelector(`[data-id="${fromNode.id}"]`);
  const tEl = document.querySelector(`[data-id="${toNode.id}"]`);
  const fCx = fromNode.x + fEl.offsetWidth / 2, fCy = fromNode.y + fEl.offsetHeight / 2;
  const tCx = toNode.x + tEl.offsetWidth / 2, tCy = toNode.y + tEl.offsetHeight / 2;
  const dx = tCx - fCx, dy = tCy - fCy;
  let fromPort, toPort;
  
  const hasExisting = state.arrows.some(a => 
    (a.from === fromNode.id && a.to === toNode.id) ||
    (a.from === toNode.id && a.to === fromNode.id)
  );

  const isVertical = Math.abs(dy) > 30;

  if (hasExisting) {
    // Only apply alternate ports if the nodes are roughly aligned on an axis.
    // Otherwise, picking alternate ports on diagonal nodes causes lines to cross in an X shape!
    if (Math.abs(dx) < 60) {
      fromPort = dx > 0 ? 'right' : 'left';
      toPort = dx > 0 ? 'right' : 'left';
      return { fromPort, toPort };
    } else if (Math.abs(dy) < 60) {
      fromPort = dy > 0 ? 'bottom' : 'top';
      toPort = dy > 0 ? 'bottom' : 'top';
      return { fromPort, toPort };
    }
  }

  // Normal single-connection layout (or fallback for diagonal nodes)
  if (isVertical) {
    fromPort = dy > 0 ? 'bottom' : 'top';
    toPort = dy > 0 ? 'top' : 'bottom';
  } else {
    fromPort = dx > 0 ? 'right' : 'left';
    toPort = dx > 0 ? 'left' : 'right';
  }
  return { fromPort, toPort };
}

/* ── Create Node ── */
function createNode(x, y, label, desc, bg, border, id, isGroup, gw, gh, nw, nh) {
  const nid = id || state.nextId++;
  if (!id && nid >= state.nextId) state.nextId = nid + 1;
  const n = { id: nid, x, y, label: label || '新节点', desc: desc || '', bg: bg || '#ffffff', border: border || '#6366f1', isGroup: isGroup || false, gw: gw || 300, gh: gh || 200, nw: nw || 0, nh: nh || 0 };
  state.nodes.push(n);
  renderNode(n);
  return n;
}

function createGroup(x, y, label) {
  return createNode(x, y, label || '分组', '', 'rgba(99,102,241,0.04)', '#a5b4fc', null, true);
}

function createLabel(x, y, label) {
  const n = createNode(x, y, label || '标注', '', 'transparent', 'transparent');
  n.isLabel = true;
  // Re-render with label class
  const old = nodeLayer.querySelector(`[data-id="${n.id}"]`);
  if (old) old.remove();
  renderNode(n);
  return n;
}

// Create a free-standing arrow: two tiny invisible anchor nodes + a labeled arrow between them.
// Fully compatible with save/load, zoom/pan, and double-click-to-edit-label.
function createFreeArrow(x, y, label) {
  const arrowLen = 120;
  // Create two invisible anchor points (tiny transparent nodes)
  const anchorFrom = createNode(x, y - 2, '●', '', 'transparent', 'transparent');
  anchorFrom.isFreeAnchor = true;
  anchorFrom.isLabel = true; // renders as label (no box)
  const oldFrom = nodeLayer.querySelector(`[data-id="${anchorFrom.id}"]`);
  if (oldFrom) { oldFrom.remove(); }
  renderNode(anchorFrom);
  // Make anchor dot tiny
  const fromEl = nodeLayer.querySelector(`[data-id="${anchorFrom.id}"]`);
  if (fromEl) { fromEl.style.minWidth = '8px'; fromEl.style.minHeight = '8px'; fromEl.style.padding = '0'; fromEl.style.opacity = '0.3'; fromEl.style.fontSize = '8px'; }

  const anchorTo = createNode(x + arrowLen, y - 2, '●', '', 'transparent', 'transparent');
  anchorTo.isFreeAnchor = true;
  anchorTo.isLabel = true;
  const oldTo = nodeLayer.querySelector(`[data-id="${anchorTo.id}"]`);
  if (oldTo) { oldTo.remove(); }
  renderNode(anchorTo);
  const toEl = nodeLayer.querySelector(`[data-id="${anchorTo.id}"]`);
  if (toEl) { toEl.style.minWidth = '8px'; toEl.style.minHeight = '8px'; toEl.style.padding = '0'; toEl.style.opacity = '0.3'; toEl.style.fontSize = '8px'; }

  // Create the arrow between anchors
  const arrowColor = document.getElementById('arrow-color').value || '#6366f1';
  const a = createArrow(anchorFrom.id, 'right', anchorTo.id, 'left', label || '', arrowColor, null, true, false, null, false);
  a.isFreeArrow = true;
  a._anchorFromId = anchorFrom.id;
  a._anchorToId = anchorTo.id;

  return a;
}

// Find nodes whose center is inside a group's bounds
function getChildrenOfGroup(group) {
  const el = nodeLayer.querySelector(`[data-id="${group.id}"]`);
  if (!el) return [];
  const gw = group.gw || el.offsetWidth;
  const gh = group.gh || el.offsetHeight;
  // Collect ALL nodes whose center is inside this group (including nested groups)
  // BUT exclude groups that contain/enclose this group (parent groups)
  return state.nodes.filter(n => {
    if (n.id === group.id) return false;
    const nel = nodeLayer.querySelector(`[data-id="${n.id}"]`);
    if (!nel) return false;
    var nw = n.isGroup ? (n.gw || nel.offsetWidth) : nel.offsetWidth;
    var nh = n.isGroup ? (n.gh || nel.offsetHeight) : nel.offsetHeight;
    // Skip groups that are bigger than or equal size — they are parents, not children
    if (n.isGroup && nw * nh >= gw * gh) return false;
    const cx = n.x + nw / 2;
    const cy = n.y + nh / 2;
    return cx >= group.x && cx <= group.x + gw && cy >= group.y && cy <= group.y + gh;
  });
}

/* ── Find all descendants of a node via outgoing arrows (recursive) ── */
function getDescendants(nodeId) {
  const result = [];
  const visited = new Set();
  function walk(id) {
    if (visited.has(id)) return;
    visited.add(id);
    state.arrows.forEach(a => {
      if (a.from === id && !visited.has(a.to)) {
        result.push(a.to);
        walk(a.to);
      }
    });
  }
  walk(nodeId);
  return state.nodes.filter(n => result.includes(n.id));
}

function renderNode(n) {
  const el = document.createElement('div');
  el.className = n.isLabel ? 'node label-node' : (n.isGroup ? 'node group-node' : 'node');
  el.dataset.id = n.id;
  el.style.left = n.x + 'px';
  el.style.top = n.y + 'px';
  if (n.isGroup) {
    el.style.width = (n.gw || 300) + 'px';
    el.style.height = (n.gh || 200) + 'px';
    el.style.background = n.bg;
    el.style.borderColor = n.border;
  } else {
    el.style.background = n.bg;
    el.style.borderColor = n.border;
    if (n.nw) el.style.width = n.nw + 'px';
    if (n.nh) el.style.minHeight = n.nh + 'px';
    // Apply custom font size (set by resize-to-scale)
    if (n.fontSize) {
      el.style.fontSize = n.fontSize + 'px';
    }
  }
  const hasDesc = n.desc && n.desc.trim().length > 0;
  const descToggleHtml = (!n.isGroup && !n.isLabel && !n.isArrowLabel && hasDesc)
    ? `<div class="desc-toggle" title="${n.showDesc ? '隐藏描述' : '显示描述'}">${n.showDesc ? '▼' : '▶'}</div>`
    : '';
  el.innerHTML = `<span class="label">${n.label}</span>${descToggleHtml}${n.desc && n.showDesc ? '<div class="desc">' + n.desc + '</div>' : ''}
    <div class="port top" data-port="top"></div>
    <div class="port bottom" data-port="bottom"></div>
    <div class="port left" data-port="left"></div>
    <div class="port right" data-port="right"></div>
    <div class="rh rh-n" data-rh="n"></div>
    <div class="rh rh-s" data-rh="s"></div>
    <div class="rh rh-e" data-rh="e"></div>
    <div class="rh rh-w" data-rh="w"></div>
    <div class="rh rh-ne" data-rh="ne"></div>
    <div class="rh rh-nw" data-rh="nw"></div>
    <div class="rh rh-se" data-rh="se"></div>
    <div class="rh rh-sw" data-rh="sw"></div>
    ${n.isGroup ? '<div class="resize-handle"></div>' : ''}
    ${n.linkedWorkspaceId ? '<div class="submap-badge" data-action="drill" title="点击进入子图">🔗</div>' : ''}`;

  // Click on submap badge to drill in
  const badge = el.querySelector('.submap-badge');
  if (badge) {
    badge.addEventListener('click', (e) => {
      e.stopPropagation();
      drillIntoNode(n.id);
    });
  }

  // Click node
  el.addEventListener('click', (e) => {
    // If we are in add-node mode and click on a group, we want to create a node inside it!
    // So we don't stop propagation, and we don't select the group.
    if (state.mode === 'add-node' && n.isGroup) {
      return; // Let it bubble to canvas
    }
    
    e.stopPropagation();
    if (state.didDrag) { state.didDrag = false; return; }
    
    // In these modes, clicking a node selects it
    if (state.mode === 'select' || state.mode === 'add-node' || state.mode === 'add-group') {
      selectNode(n.id);
      return;
    }
    if (state.mode !== 'add-arrow') return;
    const clickedPort = e.target.dataset.port;
    if (!state.arrowStart) {
      // First click — start arrow from this node
      state.arrowStart = { nodeId: n.id, port: clickedPort };
      el.classList.add('selected');
      statusText.textContent = `从 "${n.label}" 开始 → 点击目标节点或连接点完成连线`;
      // Compute start position in canvas coordinates (matching getArrowPoints logic)
      const elW = el.offsetWidth, elH = el.offsetHeight;
      const portOffsets = {
        top:    [elW / 2, 0],
        bottom: [elW / 2, elH],
        left:   [0, elH / 2],
        right:  [elW, elH / 2]
      };
      let canvasX, canvasY;
      if (clickedPort && portOffsets[clickedPort]) {
        canvasX = n.x + portOffsets[clickedPort][0];
        canvasY = n.y + portOffsets[clickedPort][1];
      } else {
        canvasX = n.x + elW / 2;
        canvasY = n.y + elH / 2;
      }
      startTempArrowAt(canvasX, canvasY);
    } else if (state.arrowStart.nodeId !== n.id) {
      // Second click — finish arrow to this node
      const fromNode = state.nodes.find(nd => nd.id === state.arrowStart.nodeId);
      const autoPorts = bestPorts(fromNode, n);
      const fromPort = state.arrowStart.port || autoPorts.fromPort;
      const toPort = clickedPort || autoPorts.toPort;
      createArrow(state.arrowStart.nodeId, fromPort, n.id, toPort, '', document.getElementById('arrow-color').value, null, state.arrowStyle === 'straight', state.arrowDirection === 'double', null, state.arrowDashed);
      // Reset for next arrow
      nodeLayer.querySelectorAll('.node.selected').forEach(e => e.classList.remove('selected'));
      state.arrowStart = null;
      removeTempArrow();
      statusText.textContent = '连线完成！点击下一个节点继续连线';
      triggerAutoSave();
    }
  });

  // Node drag (works in select and add-node modes)
  el.addEventListener('mousedown', (e) => {
    if (state.mode === 'add-arrow') return;
    if (e.target.classList.contains('port')) return;
    
    // Resize handles (8-point directional)
    if (e.target.dataset.rh) {
      state.resizingGroup = n.id;
      state.resizeDir = e.target.dataset.rh;
      state.resizeStart = screenToCanvas(e.clientX, e.clientY);
      const rel = nodeLayer.querySelector(`[data-id="${n.id}"]`);
      if (n.isGroup) {
        state.resizeOrigRect = { x: n.x, y: n.y, w: n.gw || 300, h: n.gh || 200 };
      } else {
        state.resizeOrigRect = { x: n.x, y: n.y, w: n.nw || (rel ? rel.offsetWidth : 100), h: n.nh || (rel ? rel.offsetHeight : 50) };
      }
      // Save original font size for proportional scaling
      state.resizeOrigFontSize = n.fontSize || 13;
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    // Legacy resize handle for groups
    if (e.target.classList.contains('resize-handle') && n.isGroup) {
      state.resizingGroup = n.id;
      state.resizeDir = 'se';
      state.resizeStart = screenToCanvas(e.clientX, e.clientY);
      state.resizeOrigRect = { x: n.x, y: n.y, w: n.gw || 300, h: n.gh || 200 };
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    
    // If in add-node mode and clicking on a group, don't drag the group, let the canvas click handle it
    if (state.mode === 'add-node' && n.isGroup) {
      return;
    }
    
    state.dragNode = n.id;
    state.didDrag = false;
    const pt = screenToCanvas(e.clientX, e.clientY);
    state.dragOffset = { x: pt.x - n.x, y: pt.y - n.y };
    
    // Capture children before dragging (group: spatial children, regular: arrow descendants)
    if (n.isGroup) {
      state.dragGroupChildren = getChildrenOfGroup(n).map(c => ({ id: c.id, ox: c.x - n.x, oy: c.y - n.y }));
    } else if (state.dragMode === 'branch') {
      let descendants = getDescendants(n.id);
      // If any descendant is a group, also include its spatial children
      const extra = [];
      descendants.forEach(d => {
        if (d.isGroup) {
          getChildrenOfGroup(d).forEach(c => {
            if (!descendants.find(dd => dd.id === c.id) && c.id !== n.id && !extra.find(ee => ee.id === c.id)) {
              extra.push(c);
            }
          });
        }
      });
      descendants = descendants.concat(extra);
      state.dragGroupChildren = descendants.length > 0
        ? descendants.map(c => ({ id: c.id, ox: c.x - n.x, oy: c.y - n.y }))
        : null;
    } else {
      state.dragGroupChildren = null;
    }
    
    el.style.cursor = 'grabbing';
    e.preventDefault();
  });

  // Double-click to edit inline on node
  el.addEventListener('dblclick', (e) => {
    e.stopPropagation();
    if (state.mode === 'add-arrow') return;
    if (n.isArrowLabel) return;
    
    // Groups: open the side editor panel (has width/height controls)
    if (n.isGroup) {
      selectNode(n.id);
      showEditor(n);
      return;
    }
    
    // If clicked on the label text, edit label inline
    if (e.target.classList.contains('label')) {
      showInlineLabelEditor(n, el);
      return;
    }
    
    // If clicked on the desc toggle, ignore (handled separately)
    if (e.target.closest('.desc-toggle')) return;
    
    // Otherwise, edit desc inline on the node
    showInlineDescEditor(n, el);
  });

  // Desc show/hide toggle button
  const toggleBtn = el.querySelector('.desc-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      n.showDesc = !n.showDesc;
      rerenderNode(n);
      refreshArrows();
      triggerAutoSave();
    });
  }

  nodeLayer.appendChild(el);
}

function refreshNodes() {
  nodeLayer.innerHTML = '';
  state.nodes.filter(n => !n.isArrowLabel).forEach(n => renderNode(n));
  // Re-apply tiny-dot styling for free arrow anchor nodes
  state.nodes.filter(n => n.isFreeAnchor).forEach(n => {
    const el = nodeLayer.querySelector(`[data-id="${n.id}"]`);
    if (el) { el.style.minWidth = '8px'; el.style.minHeight = '8px'; el.style.padding = '0'; el.style.opacity = '0.3'; el.style.fontSize = '8px'; }
  });
}

function rerenderNode(n) {
  const old = nodeLayer.querySelector(`[data-id="${n.id}"]`);
  if (old) old.remove();
  renderNode(n);
  if (state.selectedNode === n.id) {
    const el = nodeLayer.querySelector(`[data-id="${n.id}"]`);
    if (el) el.classList.add('selected');
  }
}

/* ── Arrow ── */
function createArrow(fromId, fromPort, toId, toPort, label, color, id, isStraight, bidir, mark, isDashed) {
  const aid = id || 'a' + state.nextId++;
  const col = color || '#6366f1';
  const a = { id: aid, from: fromId, fromPort, to: toId, toPort, label: label || '', color: col, isStraight: isStraight || false, bidir: bidir || false, mark: mark || null, isDashed: isDashed || false };
  state.arrows.push(a);
  renderArrow(a);
  return a;
}

function renderArrow(a) {
  const pts = getArrowPoints(a);
  if (!pts) return;

  const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  g.dataset.id = a.id;

  const curveOffset = getArrowCurveOffset(a, pts);
  const curvePath = buildCurvePath(pts.x1, pts.y1, pts.x2, pts.y2, a.fromPort, a.toPort, a.isStraight, a.from, a.to, curveOffset);

  // Invisible wide hit-area for easy clicking
  const hitArea = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  hitArea.setAttribute('d', curvePath);
  hitArea.setAttribute('stroke', 'transparent');
  hitArea.setAttribute('stroke-width', '24');
  hitArea.setAttribute('fill', 'none');
  hitArea.style.cursor = a.isFreeArrow ? 'grab' : 'pointer';
  hitArea.style.pointerEvents = 'all';
  hitArea.addEventListener('mousedown', (e) => {
    e.stopPropagation();
    // Free arrow: start dragging both anchor nodes
    if (a.isFreeArrow) {
      const fromNode = state.nodes.find(n => n.id === a.from);
      const toNode = state.nodes.find(n => n.id === a.to);
      if (fromNode && toNode) {
        const pt = screenToCanvas(e.clientX, e.clientY);
        state.dragFreeArrow = {
          arrowId: a.id,
          fromId: a.from, toId: a.to,
          startX: pt.x, startY: pt.y,
          fromOrigX: fromNode.x, fromOrigY: fromNode.y,
          toOrigX: toNode.x, toOrigY: toNode.y
        };
        hitArea.style.cursor = 'grabbing';
      }
    }
  });
  hitArea.addEventListener('click', (e) => { e.stopPropagation(); selectArrow(a.id); });
  hitArea.addEventListener('dblclick', (e) => {
    e.stopPropagation();
    e.preventDefault();
    const pts2 = getArrowPoints(a);
    if (pts2) {
      const mid = getArrowMidpoint(a, pts2);
      showArrowLabelEditor(a, mid.x, mid.y);
    }
  });
  hitArea.addEventListener('mouseenter', () => {
    const p = g.querySelector('.arrow-line');
    if (p && !p.classList.contains('selected')) p.classList.add('hover-highlight');
  });
  hitArea.addEventListener('mouseleave', () => {
    const p = g.querySelector('.arrow-line');
    if (p) p.classList.remove('hover-highlight');
  });
  g.appendChild(hitArea);

  // Visible arrow
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', curvePath);
  path.setAttribute('class', 'arrow-line');
  path.setAttribute('stroke', a.color);
  if (a.isDashed) path.setAttribute('stroke-dasharray', '8,6');
  path.setAttribute('marker-end', 'url(#arrowhead)');
  if (a.bidir) {
    path.setAttribute('marker-start', 'url(#arrowhead-start)');
  }
  g.appendChild(path);

  // Label — above the arrow, follows direction
  const { x: mx, y: my } = getArrowMidpoint(a, pts);
  const labelText = a.label || '';

  // Calculate true tangent vector at midpoint for accurate rotation and offset
  var tdx = pts.x2 - pts.x1;
  var tdy = pts.y2 - pts.y1;
  
  if (!a.isStraight) {
    const curve = getArrowCurveOffset(a, pts);
    const offsets = { top: [0, -curve], bottom: [0, curve], left: [-curve, 0], right: [curve, 0] };
    const cx1 = pts.x1 + (offsets[a.fromPort]?.[0] || 0);
    const cy1 = pts.y1 + (offsets[a.fromPort]?.[1] || 0);
    const cx2 = pts.x2 + (offsets[a.toPort]?.[0] || 0);
    const cy2 = pts.y2 + (offsets[a.toPort]?.[1] || 0);
    // B'(0.5) tangent vector of cubic bezier
    tdx = 0.75 * (pts.x2 + cx2 - cx1 - pts.x1);
    tdy = 0.75 * (pts.y2 + cy2 - cy1 - pts.y1);
  }

  var angle = Math.atan2(tdy, tdx) * 180 / Math.PI;
  var absAngle = Math.abs(angle);
  var isVertical = (absAngle > 60 && absAngle < 120);

  const descText = a.desc || '';

  const textGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  textGroup.setAttribute('class', 'arrow-label-group');
  textGroup.style.cursor = 'pointer';

  const createTextNode = (text, isDesc) => {
    const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    txt.setAttribute('class', 'arrow-label');
    txt.setAttribute('text-anchor', 'middle');
    txt.setAttribute('dominant-baseline', 'central');
    if (isDesc) {
      txt.setAttribute('fill', '#6b7280');
      txt.setAttribute('font-size', '11');
      txt.setAttribute('font-weight', 'normal');
    }
    // Support multi-line text: split by newline and create tspan for each line
    const lines = text.split('\n');
    if (lines.length <= 1) {
      txt.textContent = text;
    } else {
      const lineHeight = isDesc ? 13 : 16;
      lines.forEach((line, i) => {
        const tspan = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
        tspan.textContent = line;
        tspan.setAttribute('x', '0');
        tspan.setAttribute('dy', i === 0 ? `${-(lines.length - 1) * lineHeight / 2}` : `${lineHeight}`);
        txt.appendChild(tspan);
      });
    }
    txt._lineCount = lines.length;
    return txt;
  };

  const labelNode = labelText ? createTextNode(labelText, false) : null;
  const descNode = descText ? createTextNode(descText, true) : null;

  if (isVertical) {
    let offsetX = 16;
    if (!a.isStraight) {
      const midStraightX = (pts.x1 + pts.x2) / 2;
      if (mx < midStraightX) {
        offsetX = -16;
      }
    }
    
    // For vertical text, offset desc to the left if bowing left, right if bowing right or straight
    const descOffsetX = offsetX < 0 ? offsetX - 14 : offsetX + 14;

    if (labelNode) {
      // For multi-line vertical text: each line becomes a separate vertical column
      const labelLines = (a.label || '').split('\n');
      if (labelLines.length > 1) {
        // Remove the tspan-based node and create individual vertical text nodes for each line
        while (labelNode.firstChild) labelNode.removeChild(labelNode.firstChild);
        labelNode.textContent = '';
        const colSpacing = 16;
        const totalWidth = (labelLines.length - 1) * colSpacing;
        labelLines.forEach((line, i) => {
          const colText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          colText.setAttribute('class', 'arrow-label');
          colText.setAttribute('text-anchor', 'middle');
          colText.setAttribute('dominant-baseline', 'central');
          colText.style.writingMode = 'vertical-rl';
          colText.style.textOrientation = 'upright';
          // Lines go left-to-right (first line on the left)
          colText.setAttribute('x', mx + offsetX - totalWidth / 2 + i * colSpacing);
          colText.setAttribute('y', my);
          colText.textContent = line;
          textGroup.appendChild(colText);
        });
      } else {
        labelNode.style.writingMode = 'vertical-rl';
        labelNode.style.textOrientation = 'upright';
        labelNode.setAttribute('x', mx + offsetX);
        labelNode.setAttribute('y', my);
        textGroup.appendChild(labelNode);
      }
    }
    if (descNode) {
      const descLines = (a.desc || '').split('\n');
      if (descLines.length > 1) {
        while (descNode.firstChild) descNode.removeChild(descNode.firstChild);
        descNode.textContent = '';
        const colSpacing = 14;
        const totalWidth = (descLines.length - 1) * colSpacing;
        const baseX = labelNode ? (mx + descOffsetX) : (mx + offsetX);
        descLines.forEach((line, i) => {
          const colText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          colText.setAttribute('class', 'arrow-label');
          colText.setAttribute('text-anchor', 'middle');
          colText.setAttribute('dominant-baseline', 'central');
          colText.setAttribute('fill', '#6b7280');
          colText.setAttribute('font-size', '11');
          colText.setAttribute('font-weight', 'normal');
          colText.style.writingMode = 'vertical-rl';
          colText.style.textOrientation = 'upright';
          colText.setAttribute('x', baseX - totalWidth / 2 + i * colSpacing);
          colText.setAttribute('y', my);
          colText.textContent = line;
          textGroup.appendChild(colText);
        });
      } else {
        descNode.style.writingMode = 'vertical-rl';
        descNode.style.textOrientation = 'upright';
        descNode.setAttribute('x', mx + (labelNode ? descOffsetX : offsetX));
        descNode.setAttribute('y', my);
        textGroup.appendChild(descNode);
      }
    }
  } else {
    var perpAngle = angle;
    if (perpAngle > 90 || perpAngle < -90) perpAngle += 180;
    var rad = angle * Math.PI / 180;
    var perpX = -Math.sin(rad) * 14;
    var perpY = Math.cos(rad) * 14;
    
    // We rotate the group, so local coordinates are X=along the line, Y=perpendicular
    textGroup.setAttribute('transform', `translate(${mx + perpX}, ${my - perpY}) rotate(${perpAngle > 180 ? perpAngle - 360 : perpAngle})`);
    
    if (labelNode) {
      // For multi-line horizontal text: update tspan x attributes for the rotated group
      const tspans = labelNode.querySelectorAll('tspan');
      tspans.forEach(ts => ts.setAttribute('x', '0'));
      labelNode.setAttribute('x', 0);
      labelNode.setAttribute('y', descNode ? -6 : 0);
      textGroup.appendChild(labelNode);
    }
    if (descNode) {
      const tspans = descNode.querySelectorAll('tspan');
      tspans.forEach(ts => ts.setAttribute('x', '0'));
      descNode.setAttribute('x', 0);
      // For multi-line, push desc further down to account for label's line count
      const labelLineCount = labelNode ? (labelNode._lineCount || 1) : 0;
      const extraOffset = labelLineCount > 1 ? (labelLineCount - 1) * 8 : 0;
      descNode.setAttribute('y', labelNode ? 8 + extraOffset : 0);
      textGroup.appendChild(descNode);
    }
  }

  textGroup.addEventListener('click', () => selectArrow(a.id));
  textGroup.addEventListener('dblclick', (e) => {
    e.stopPropagation();
    showArrowLabelEditor(a, mx, my);
  });
  // Free arrow: text label is also draggable
  if (a.isFreeArrow) {
    textGroup.style.cursor = 'grab';
    textGroup.addEventListener('mousedown', (e) => {
      e.stopPropagation();
      const fromNode = state.nodes.find(n => n.id === a.from);
      const toNode = state.nodes.find(n => n.id === a.to);
      if (fromNode && toNode) {
        const pt = screenToCanvas(e.clientX, e.clientY);
        state.dragFreeArrow = {
          arrowId: a.id,
          fromId: a.from, toId: a.to,
          startX: pt.x, startY: pt.y,
          fromOrigX: fromNode.x, fromOrigY: fromNode.y,
          toOrigX: toNode.x, toOrigY: toNode.y
        };
        textGroup.style.cursor = 'grabbing';
      }
    });
  }
  g.appendChild(textGroup);

  // Mark icon (✓ or ✗)
  if (a.mark) {
    const markG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    markG.setAttribute('class', 'arrow-mark');
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', mx);
    circle.setAttribute('cy', my + 10);
    circle.setAttribute('r', '10');
    circle.setAttribute('fill', a.mark === 'tick' ? '#10b981' : '#ef4444');
    circle.setAttribute('stroke', '#fff');
    circle.setAttribute('stroke-width', '2');
    markG.appendChild(circle);
    const markTxt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    markTxt.setAttribute('x', mx);
    markTxt.setAttribute('y', my + 15);
    markTxt.setAttribute('text-anchor', 'middle');
    markTxt.setAttribute('fill', '#fff');
    markTxt.setAttribute('font-size', '13');
    markTxt.setAttribute('font-weight', 'bold');
    markTxt.style.pointerEvents = 'none';
    markTxt.textContent = a.mark === 'tick' ? '✓' : '✗';
    markG.appendChild(markTxt);
    g.appendChild(markG);
  }

  arrowLayer.appendChild(g);

  // Keep all text labels on top
  arrowLayer.querySelectorAll('.arrow-label-group').forEach(el => arrowLayer.appendChild(el));
}

function getArrowCurveOffset(a, pts) {
  if (a.curveOffset !== undefined) return a.curveOffset;
  const dist = Math.hypot(pts.x2 - pts.x1, pts.y2 - pts.y1);
  return Math.min(dist * 0.4, 80);
}

function buildCurvePath(x1, y1, x2, y2, fp, tp, isStraight, arrowFrom, arrowTo, curveOffset) {
  if (isStraight) {
    return `M${x1},${y1} L${x2},${y2}`;
  }
  let curve = curveOffset !== undefined ? curveOffset : Math.min(Math.hypot(x2 - x1, y2 - y1) * 0.4, 80);

  // Check if the basic curve would pass through any node and increase offset if so
  // Skip collision if user manually set a curve value
  if (curveOffset === undefined) {
    const padding = 20;
    for (const n of state.nodes) {
      if (n.id === arrowFrom || n.id === arrowTo) continue;
      const el = nodeLayer.querySelector(`[data-id="${n.id}"]`);
      if (!el) continue;
      const nw = el.offsetWidth, nh = el.offsetHeight;
      const nx1 = n.x - padding, ny1 = n.y - padding;
      const nx2 = n.x + nw + padding, ny2 = n.y + nh + padding;
      // Sample 10 points along the basic bezier and check collision
      const offsets = { top: [0, -curve], bottom: [0, curve], left: [-curve, 0], right: [curve, 0] };
      const cx1t = x1 + (offsets[fp]?.[0] || 0), cy1t = y1 + (offsets[fp]?.[1] || 0);
      const cx2t = x2 + (offsets[tp]?.[0] || 0), cy2t = y2 + (offsets[tp]?.[1] || 0);
      let hit = false;
      for (let t = 0.1; t <= 0.9; t += 0.1) {
        const it = 1 - t;
        const px = it*it*it*x1 + 3*it*it*t*cx1t + 3*it*t*t*cx2t + t*t*t*x2;
        const py = it*it*it*y1 + 3*it*it*t*cy1t + 3*it*t*t*cy2t + t*t*t*y2;
        if (px > nx1 && px < nx2 && py > ny1 && py < ny2) { hit = true; break; }
      }
      if (hit) {
        curve = Math.min(curve * 2.5, 300);
        break;
      }
    }
  }

  const offsets = { top: [0, -curve], bottom: [0, curve], left: [-curve, 0], right: [curve, 0] };
  const [cx1, cy1] = [x1 + (offsets[fp]?.[0] || 0), y1 + (offsets[fp]?.[1] || 0)];
  const [cx2, cy2] = [x2 + (offsets[tp]?.[0] || 0), y2 + (offsets[tp]?.[1] || 0)];
  return `M${x1},${y1} C${cx1},${cy1} ${cx2},${cy2} ${x2},${y2}`;
}

function getArrowPoints(a) {
  const fromNode = state.nodes.find(n => n.id === a.from);
  const toNode = state.nodes.find(n => n.id === a.to);
  if (!fromNode || !toNode) return null;
  const fromEl = document.querySelector(`[data-id="${a.from}"]`);
  const toEl = document.querySelector(`[data-id="${a.to}"]`);
  if (!fromEl || !toEl) return null;
  const fw = fromEl.offsetWidth, fh = fromEl.offsetHeight;
  const tw = toEl.offsetWidth, th = toEl.offsetHeight;
  const portOffsets = {
    top:    (w, h) => [w / 2, 0],
    bottom: (w, h) => [w / 2, h],
    left:   (w, h) => [0, h / 2],
    right:  (w, h) => [w, h / 2]
  };
  const [fox, foy] = portOffsets[a.fromPort](fw, fh);
  const [tox, toy] = portOffsets[a.toPort](tw, th);
  return {
    x1: fromNode.x + fox,
    y1: fromNode.y + foy,
    x2: toNode.x + tox,
    y2: toNode.y + toy
  };
}

function getArrowMidpoint(a, pts) {
  if (a.isStraight) {
    return { x: (pts.x1 + pts.x2) / 2, y: (pts.y1 + pts.y2) / 2 };
  }
  const curve = getArrowCurveOffset(a, pts);
  const offsets = { top: [0, -curve], bottom: [0, curve], left: [-curve, 0], right: [curve, 0] };
  const cx1 = pts.x1 + (offsets[a.fromPort]?.[0] || 0);
  const cy1 = pts.y1 + (offsets[a.fromPort]?.[1] || 0);
  const cx2 = pts.x2 + (offsets[a.toPort]?.[0] || 0);
  const cy2 = pts.y2 + (offsets[a.toPort]?.[1] || 0);
  
  const mx = 0.125 * pts.x1 + 0.375 * cx1 + 0.375 * cx2 + 0.125 * pts.x2;
  const my = 0.125 * pts.y1 + 0.375 * cy1 + 0.375 * cy2 + 0.125 * pts.y2;
  return { x: mx, y: my };
}

function refreshArrows() {
  arrowLayer.querySelectorAll('g').forEach(g => g.remove());
  refreshArrowLabelAnchors(); // Must run FIRST so virtual label nodes exist for arrows that connect to them!
  state.arrows.forEach(a => renderArrow(a));
  
  // Re-order SVG elements: move all text labels to the very end so they sit on top of all lines
  // This ensures the CSS paint-order halo perfectly masks crossing lines
  arrowLayer.querySelectorAll('.arrow-label-group').forEach(g => {
    arrowLayer.appendChild(g);
  });
}

/* ── Arrow Label Anchors: treat arrow text as connectable nodes ── */
function refreshArrowLabelAnchors() {
  // Remove old anchors
  anchorLayer.innerHTML = '';

  state.arrows.forEach(a => {
    const labelText = a.label || a.desc || '';
    if (!labelText) return;

    const pts = getArrowPoints(a);
    if (!pts) return;
    const mid = getArrowMidpoint(a, pts);

    // Ensure a corresponding node exists for this arrow label
    let labelNode = state.nodes.find(n => n.isArrowLabel && n.parentArrowId === a.id);
    if (!labelNode) {
      labelNode = {
        id: 'al_' + a.id,
        label: '',
        desc: '',
        x: mid.x - 20,
        y: mid.y - 12,
        bg: 'transparent',
        border: 'transparent',
        isArrowLabel: true,
        parentArrowId: a.id,
        nw: 40,
        nh: 24
      };
      state.nodes.push(labelNode);
    }
    // Update position to follow arrow midpoint
    labelNode.x = mid.x - 20;
    labelNode.y = mid.y - 12;

    // Create the anchor div
    const el = document.createElement('div');
    el.className = 'node arrow-label-anchor';
    el.dataset.id = labelNode.id;
    el.style.left = labelNode.x + 'px';
    el.style.top = labelNode.y + 'px';
    el.style.width = '40px';
    el.style.height = '24px';

    // Ports for connections
    el.innerHTML = `
      <div class="port top" data-port="top"></div>
      <div class="port bottom" data-port="bottom"></div>
      <div class="port left" data-port="left"></div>
      <div class="port right" data-port="right"></div>
    `;

    // Click handler for arrow mode connections
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      if (state.mode !== 'add-arrow') return;

      const clickedPort = e.target.dataset.port;
      if (!state.arrowStart) {
        state.arrowStart = { nodeId: labelNode.id, port: clickedPort };
        el.classList.add('selected');
        statusText.textContent = `从箭头标签开始 → 点击目标节点完成连线`;
        const elW = 40, elH = 24;
        const portOffsets = {
          top: [elW / 2, 0], bottom: [elW / 2, elH],
          left: [0, elH / 2], right: [elW, elH / 2]
        };
        let cx, cy;
        if (clickedPort && portOffsets[clickedPort]) {
          cx = labelNode.x + portOffsets[clickedPort][0];
          cy = labelNode.y + portOffsets[clickedPort][1];
        } else {
          cx = labelNode.x + elW / 2;
          cy = labelNode.y + elH / 2;
        }
        startTempArrowAt(cx, cy);
      } else if (state.arrowStart.nodeId !== labelNode.id) {
        const fromNode = state.nodes.find(nd => nd.id === state.arrowStart.nodeId);
        const autoPorts = bestPorts(fromNode, labelNode);
        const fromPort = state.arrowStart.port || autoPorts.fromPort;
        const toPort = clickedPort || autoPorts.toPort;
        createArrow(state.arrowStart.nodeId, fromPort, labelNode.id, toPort, '',
          document.getElementById('arrow-color').value, null,
          state.arrowStyle === 'straight', state.arrowDirection === 'double',
          null, state.arrowDashed);
        document.querySelectorAll('.node.selected, .arrow-label-anchor.selected').forEach(e => e.classList.remove('selected'));
        state.arrowStart = null;
        removeTempArrow();
        statusText.textContent = '连线完成！';
        triggerAutoSave();
      }
    });

    anchorLayer.appendChild(el);
  });
}

/* ── Temp arrow for drawing ── */
let tempLine = null;
function startTempArrow(e) {
  tempLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  tempLine.setAttribute('class', 'temp-arrow');
  const pt = screenToSvg(e.clientX, e.clientY);
  tempLine.setAttribute('x1', pt.x);
  tempLine.setAttribute('y1', pt.y);
  tempLine.setAttribute('x2', pt.x);
  tempLine.setAttribute('y2', pt.y);
  arrowLayer.appendChild(tempLine);
}
function startTempArrowAt(canvasX, canvasY) {
  tempLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  tempLine.setAttribute('class', 'temp-arrow');
  tempLine.setAttribute('x1', canvasX);
  tempLine.setAttribute('y1', canvasY);
  tempLine.setAttribute('x2', canvasX);
  tempLine.setAttribute('y2', canvasY);
  arrowLayer.appendChild(tempLine);
}
function removeTempArrow() {
  if (tempLine) { tempLine.remove(); tempLine = null; }
}

/* ── Canvas events ── */
// Hit-test: find arrow near a canvas point
function findArrowAtPoint(canvasX, canvasY, threshold) {
  const thr = threshold || 15;
  let bestArrow = null, bestDist = Infinity;
  for (const a of state.arrows) {
    const pts = getArrowPoints(a);
    if (!pts) continue;
    // Compute bezier control points (same as buildCurvePath)
    if (a.isStraight) {
       // Simple distance from line segment
       const d = distToSegment(canvasX, canvasY, pts.x1, pts.y1, pts.x2, pts.y2);
       if (d < bestDist) { bestDist = d; bestArrow = a; }
    } else {
      const curve = getArrowCurveOffset(a, pts);
      const offsets = { top: [0, -curve], bottom: [0, curve], left: [-curve, 0], right: [curve, 0] };
      const cx1 = pts.x1 + (offsets[a.fromPort]?.[0] || 0);
      const cy1 = pts.y1 + (offsets[a.fromPort]?.[1] || 0);
      const cx2 = pts.x2 + (offsets[a.toPort]?.[0] || 0);
      const cy2 = pts.y2 + (offsets[a.toPort]?.[1] || 0);
      // Sample cubic bezier
      for (let i = 0; i <= 40; i++) {
        const t = i / 40;
        const u = 1 - t;
        const bx = u*u*u*pts.x1 + 3*u*u*t*cx1 + 3*u*t*t*cx2 + t*t*t*pts.x2;
        const by = u*u*u*pts.y1 + 3*u*u*t*cy1 + 3*u*t*t*cy2 + t*t*t*pts.y2;
        const d = Math.hypot(canvasX - bx, canvasY - by);
        if (d < bestDist) { bestDist = d; bestArrow = a; }
      }
    }
  }
  return bestDist < thr ? bestArrow : null;
}

function distToSegment(px, py, x1, y1, x2, y2) {
  const l2 = (x2-x1)**2 + (y2-y1)**2;
  if (l2 === 0) return Math.hypot(px-x1, py-y1);
  let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (x1 + t * (x2 - x1)), py - (y1 + t * (y2 - y1)));
}

canvas.addEventListener('click', (e) => {
  if (e.detail >= 2) return; // ignore double-click (handled by dblclick event)
  if (state.wasPanning) { state.wasPanning = false; return; }
  if (state.wasMarquee) { state.wasMarquee = false; return; }
  
  // Handle arrow-label-anchor clicks in arrow mode
  const closestAnchor = e.target.closest('.arrow-label-anchor');
  if (closestAnchor && state.mode === 'add-arrow') {
    e.stopPropagation();
    const labelNodeId = closestAnchor.dataset.id;
    const labelNode = state.nodes.find(n => n.id === labelNodeId);
    if (!labelNode) return;
    const clickedPort = e.target.dataset.port;
    if (!state.arrowStart) {
      state.arrowStart = { nodeId: labelNode.id, port: clickedPort };
      closestAnchor.classList.add('selected');
      statusText.textContent = '从箭头标签开始 → 点击目标节点完成连线';
      const elW = closestAnchor.offsetWidth || 40, elH = closestAnchor.offsetHeight || 24;
      const portOffsets = {
        top: [elW / 2, 0], bottom: [elW / 2, elH],
        left: [0, elH / 2], right: [elW, elH / 2]
      };
      let cx, cy;
      if (clickedPort && portOffsets[clickedPort]) {
        cx = labelNode.x + portOffsets[clickedPort][0];
        cy = labelNode.y + portOffsets[clickedPort][1];
      } else {
        cx = labelNode.x + elW / 2;
        cy = labelNode.y + elH / 2;
      }
      startTempArrowAt(cx, cy);
    } else if (state.arrowStart.nodeId !== labelNode.id) {
      const fromNode = state.nodes.find(nd => nd.id === state.arrowStart.nodeId);
      const autoPorts = bestPorts(fromNode, labelNode);
      const fromPort = state.arrowStart.port || autoPorts.fromPort;
      const toPort = clickedPort || autoPorts.toPort;
      createArrow(state.arrowStart.nodeId, fromPort, labelNode.id, toPort, '',
        document.getElementById('arrow-color').value, null,
        state.arrowStyle === 'straight', state.arrowDirection === 'double',
        null, state.arrowDashed);
      document.querySelectorAll('.node.selected, .arrow-label-anchor.selected').forEach(el => el.classList.remove('selected'));
      state.arrowStart = null;
      removeTempArrow();
      statusText.textContent = '连线完成！';
      triggerAutoSave();
    }
    return;
  }
  if (closestAnchor) return; // don't process anchor clicks in non-arrow modes

  const closestNode = e.target.closest('.node');
  const isGroupNodeClick = closestNode && closestNode.classList.contains('group-node');
  
  if ((closestNode && !isGroupNodeClick) || e.target.closest('.port')) return;
  if (e.target.closest('#zoom-controls')) return;
  if (e.target.closest('#toolbar')) return;

  const pt = screenToCanvas(e.clientX, e.clientY);

  // Check if clicking near an arrow
  if (state.mode === 'select' || state.mode === 'add-node') {
    const hitArrow = findArrowAtPoint(pt.x, pt.y, 20);
    if (hitArrow) {
      selectArrow(hitArrow.id);
      return;
    }
  }

  // If we clicked a group node but we are in select mode, we just want to select it, not create a node inside it
  if (isGroupNodeClick && state.mode === 'select') {
    return; // The node's own click handler already took care of selecting it
  }

  if (state.mode === 'add-node') {
    const n = createNode(pt.x - 50, pt.y - 20, '新节点');
    selectNode(n.id);
    showEditor(n);
    setTimeout(() => {
      const inp = document.getElementById('edit-label');
      inp.focus();
      inp.select();
    }, 50);
    triggerAutoSave();
  } else if (state.mode === 'add-group') {
    const g = createGroup(pt.x - 150, pt.y - 20);
    selectNode(g.id);
    showEditor(g);
    setTimeout(() => {
      const inp = document.getElementById('edit-label');
      inp.focus();
      inp.select();
    }, 50);
    triggerAutoSave();
  } else if (state.mode === 'add-label') {
    showCanvasTextInput(pt.x, pt.y, '', (text) => {
      if (!text.trim()) return;
      const lb = createLabel(pt.x - 10, pt.y - 10, text.trim());
      selectNode(lb.id);
      triggerAutoSave();
    });
  } else if (state.mode === 'add-free-arrow') {
    const fa = createFreeArrow(pt.x, pt.y, '');
    selectArrow(fa.id);
    // Open label editor at the arrow midpoint
    const midX = pt.x + 60; // center of 120px arrow
    const midY = pt.y;
    showArrowLabelEditor(fa, midX, midY);
    statusText.textContent = '独立箭头已创建 — 输入文字，拖动端点调整位置';
    triggerAutoSave();
  } else {
    deselectAll();
  }
});

// Double-click on empty canvas → inline text input (works in any mode)
canvas.addEventListener('dblclick', (e) => {
  // Skip if clicking on a node, arrow, toolbar, or editor
  if (e.target.closest('.node') || e.target.closest('#toolbar') ||
      e.target.closest('#arrow-label-editor') || e.target.closest('#canvas-text-input') ||
      e.target.closest('.arrow-label-anchor')) return;
  // Skip if we hit an arrow's SVG element (text or path)
  if (e.target.closest('g[data-id]')) return;

  const pt = screenToCanvas(e.clientX, e.clientY);
  showCanvasTextInput(pt.x, pt.y, '', (text) => {
    if (!text.trim()) return;
    const lb = createLabel(pt.x - 10, pt.y - 10, text.trim());
    selectNode(lb.id);
    triggerAutoSave();
    statusText.textContent = '文字已添加';
  });
});

canvas.addEventListener('mousedown', (e) => {
  if (e.target.closest('.node') || e.target.closest('#zoom-controls') || e.target.closest('#toolbar') || e.target.closest('#arrow-label-editor') || e.target.closest('.arrow-label-anchor') || e.target.closest('#canvas-text-input')) return;
  // Don't start panning when clicking on arrow elements
  if (e.target.closest('#arrow-layer g')) return;
  if (e.button === 2) return; // ignore right-click
  e.preventDefault();

  // Space + drag: start marquee area selection (works in any mode)
  if (state.spaceHeld) {
    const cr = canvas.getBoundingClientRect();
    state.marquee = {
      active: true,
      startScreenX: e.clientX,
      startScreenY: e.clientY,
      originX: e.clientX - cr.left,
      originY: e.clientY - cr.top
    };
    let mq = document.getElementById('marquee-rect');
    if (!mq) {
      mq = document.createElement('div');
      mq.id = 'marquee-rect';
      mq.style.cssText = 'position:absolute;border:2px dashed #6366f1;background:rgba(99,102,241,0.08);pointer-events:none;z-index:400;display:none;border-radius:3px;';
      canvas.appendChild(mq);
    }
    mq.style.display = 'none';
    statusText.textContent = '框选中...松手完成选择';
    return;
  }

  // Default: pan canvas
  state.isPanning = true;
  state.panMoved = false;
  state.panStart = { x: e.clientX - state.panX, y: e.clientY - state.panY };
  canvas.classList.add('panning');
});

document.addEventListener('mousemove', (e) => {
  // Track mouse position for paste-at-cursor
  state._lastMouseX = e.clientX;
  state._lastMouseY = e.clientY;
  // Panning
  if (state.isPanning) {
    const dx = e.clientX - state.panStart.x - state.panX;
    const dy = e.clientY - state.panStart.y - state.panY;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) state.panMoved = true;
    state.panX = e.clientX - state.panStart.x;
    state.panY = e.clientY - state.panStart.y;
    applyTransform();
    refreshArrows();
    return;
  }
  // Marquee selection
  if (state.marquee && state.marquee.active) {
    const cr = canvas.getBoundingClientRect();
    const curX = e.clientX - cr.left;
    const curY = e.clientY - cr.top;
    const ox = state.marquee.originX;
    const oy = state.marquee.originY;
    const left = Math.min(ox, curX);
    const top = Math.min(oy, curY);
    const w = Math.abs(curX - ox);
    const h = Math.abs(curY - oy);
    const mq = document.getElementById('marquee-rect');
    if (mq) {
      mq.style.display = 'block';
      mq.style.left = left + 'px';
      mq.style.top = top + 'px';
      mq.style.width = w + 'px';
      mq.style.height = h + 'px';
    }
    // Live highlight nodes inside marquee
    const selRect = {
      x1: (left - state.panX) / state.zoom,
      y1: (top - state.panY) / state.zoom,
      x2: ((left + w) - state.panX) / state.zoom,
      y2: ((top + h) - state.panY) / state.zoom
    };
    nodeLayer.querySelectorAll('.node').forEach(nel => {
      const nid = nel.dataset.id;
      const nd = state.nodes.find(n => n.id === nid);
      if (!nd || nd.isArrowLabel) return;
      const nw = nel.offsetWidth, nh = nel.offsetHeight;
      const cx = nd.x + nw / 2, cy = nd.y + nh / 2;
      if (cx >= selRect.x1 && cx <= selRect.x2 && cy >= selRect.y1 && cy <= selRect.y2) {
        nel.classList.add('selected');
      } else {
        nel.classList.remove('selected');
      }
    });
    return;
  }
  // Temp arrow
  if (tempLine) {
    const pt = screenToSvg(e.clientX, e.clientY);
    tempLine.setAttribute('x2', pt.x);
    tempLine.setAttribute('y2', pt.y);
  }
  // Resize node (directional)
  if (state.resizingGroup) {
    const pt = screenToCanvas(e.clientX, e.clientY);
    const gn = state.nodes.find(n => n.id === state.resizingGroup);
    if (gn) {
      const dx = pt.x - state.resizeStart.x;
      const dy = pt.y - state.resizeStart.y;
      const orig = state.resizeOrigRect;
      const dir = state.resizeDir || 'se';
      let newX = orig.x, newY = orig.y, newW = orig.w, newH = orig.h;
      const minW = gn.isGroup ? 40 : 60;
      const minH = gn.isGroup ? 30 : 30;

      if (dir.includes('e')) newW = orig.w + dx;
      if (dir.includes('w')) { newW = orig.w - dx; newX = orig.x + dx; }
      if (dir.includes('s')) newH = orig.h + dy;
      if (dir.includes('n')) { newH = orig.h - dy; newY = orig.y + dy; }

      // Enforce minimums and fix position
      if (newW < minW) { if (dir.includes('w')) newX = orig.x + orig.w - minW; newW = minW; }
      if (newH < minH) { if (dir.includes('n')) newY = orig.y + orig.h - minH; newH = minH; }

      gn.x = newX;
      gn.y = newY;
      const gel = nodeLayer.querySelector(`[data-id="${gn.id}"]`);
      if (gn.isGroup) {
        gn.gw = newW; gn.gh = newH;
        if (gel) { gel.style.left = gn.x + 'px'; gel.style.top = gn.y + 'px'; gel.style.width = gn.gw + 'px'; gel.style.height = gn.gh + 'px'; }
      } else {
        gn.nw = newW; gn.nh = newH;
        if (gel) { gel.style.left = gn.x + 'px'; gel.style.top = gn.y + 'px'; gel.style.width = gn.nw + 'px'; gel.style.minHeight = gn.nh + 'px'; }
        // Scale font size proportionally for label / regular nodes
        const origFontSize = state.resizeOrigFontSize || 13;
        const scale = newW / orig.w;
        const newFontSize = Math.max(8, Math.min(72, Math.round(origFontSize * scale)));
        gn.fontSize = newFontSize;
        if (gel) { gel.style.fontSize = newFontSize + 'px'; }
      }
      refreshArrows();
    }
    return;
  }
  // Drag node
  if (state.dragNode !== null) {
    const pt = screenToCanvas(e.clientX, e.clientY);
    const n = state.nodes.find(n => n.id === state.dragNode);
    if (!n) return;
    n.x = pt.x - state.dragOffset.x;
    n.y = pt.y - state.dragOffset.y;
    state.didDrag = true;
    const el = nodeLayer.querySelector(`[data-id="${n.id}"]`);
    if (el) { el.style.left = n.x + 'px'; el.style.top = n.y + 'px'; }
    
    // Move group children
    if (state.dragGroupChildren) {
      state.dragGroupChildren.forEach(c => {
        const child = state.nodes.find(nd => nd.id === c.id);
        if (!child) return;
        child.x = n.x + c.ox;
        child.y = n.y + c.oy;
        const cel = nodeLayer.querySelector(`[data-id="${child.id}"]`);
        if (cel) { cel.style.left = child.x + 'px'; cel.style.top = child.y + 'px'; }
      });
    }
    
    refreshArrows();
  }
  // Drag free arrow (both anchor nodes move together)
  if (state.dragFreeArrow) {
    const pt = screenToCanvas(e.clientX, e.clientY);
    const d = state.dragFreeArrow;
    const dx = pt.x - d.startX;
    const dy = pt.y - d.startY;
    const fromNode = state.nodes.find(n => n.id === d.fromId);
    const toNode = state.nodes.find(n => n.id === d.toId);
    if (fromNode) {
      fromNode.x = d.fromOrigX + dx;
      fromNode.y = d.fromOrigY + dy;
      const el = nodeLayer.querySelector(`[data-id="${fromNode.id}"]`);
      if (el) { el.style.left = fromNode.x + 'px'; el.style.top = fromNode.y + 'px'; }
    }
    if (toNode) {
      toNode.x = d.toOrigX + dx;
      toNode.y = d.toOrigY + dy;
      const el = nodeLayer.querySelector(`[data-id="${toNode.id}"]`);
      if (el) { el.style.left = toNode.x + 'px'; el.style.top = toNode.y + 'px'; }
    }
    refreshArrows();
  }
});

document.addEventListener('mouseup', (e) => {
  if (state.isPanning) {
    state.isPanning = false;
    state.wasPanning = state.panMoved;
    canvas.classList.remove('panning');
    return;
  }
  // Finalize marquee selection
  if (state.marquee && state.marquee.active) {
    state.marquee.active = false;
    state.wasMarquee = true;  // prevent click handler from deselecting
    const mq = document.getElementById('marquee-rect');
    if (mq) mq.style.display = 'none';
    // Collect all selected nodes
    const selected = [];
    nodeLayer.querySelectorAll('.node.selected').forEach(nel => {
      const nid = nel.dataset.id;
      if (nid && !state.nodes.find(n => n.id === nid)?.isArrowLabel) selected.push(nid);
    });
    state.selectedNodes = selected;
    if (selected.length > 0) {
      state.selectedNode = selected[0];
      statusText.textContent = '已框选 ' + selected.length + ' 个节点';
    } else {
      deselectAll();
    }
    return;
  }
  if (state.resizingGroup) {
    state.resizingGroup = null;
    return;
  }
  if (state.dragNode !== null) {
    const el = nodeLayer.querySelector(`[data-id="${state.dragNode}"]`);
    if (el) el.style.cursor = 'grab';
    // Mark node as pinned — user manually dragged it, auto-layout won't move it
    if (state.didDrag) {
      const draggedNode = state.nodes.find(n => n.id === state.dragNode);
      if (draggedNode) draggedNode.pinned = true;
      // Also pin branch children if in branch mode
      if (state.dragGroupChildren) {
        state.dragGroupChildren.forEach(c => {
          const child = state.nodes.find(n => n.id === c.id);
          if (child) child.pinned = true;
        });
      }
    }
    state.dragNode = null;
    state.dragGroupChildren = null;
  }
  if (state.dragFreeArrow) {
    state.dragFreeArrow = null;
    triggerAutoSave();
  }
});

// Mouse wheel zoom
canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const cr = canvas.getBoundingClientRect();
  const px = e.clientX - cr.left;
  const py = e.clientY - cr.top;
  const delta = e.deltaY > 0 ? -0.08 : 0.08;
  zoomAtPoint(delta, px, py);
}, { passive: false });

/* ── Selection ── */
function selectNode(id) {
  deselectAll();
  state.selectedNode = id;
  state.selectedNodes = [id];
  const el = nodeLayer.querySelector(`[data-id="${id}"]`);
  if (el) el.classList.add('selected');
  statusText.textContent = `已选择节点: ${state.nodes.find(n => n.id === id)?.label || id}`;
}

function selectArrow(id) {
  deselectAll();
  state.selectedArrow = id;
  const g = arrowLayer.querySelector(`[data-id="${id}"]`);
  if (g) g.querySelector('path')?.classList.add('selected');
  const a = state.arrows.find(ar => ar.id === id);
  if (a) {
    document.getElementById('arrow-curve').value = a.curveOffset !== undefined ? a.curveOffset : state.arrowCurve;
  }
  // Show mark buttons in status bar
  statusText.innerHTML = `已选择箭头 &nbsp;
    <button class="mark-btn mark-tick" title="标记 ✓">✓</button>
    <button class="mark-btn mark-x" title="标记 ✗">✗</button>
    <button class="mark-btn mark-clear" title="清除标记">○</button>`;
  statusText.querySelector('.mark-tick').onclick = () => { setArrowMark(id, 'tick'); };
  statusText.querySelector('.mark-x').onclick = () => { setArrowMark(id, 'x'); };
  statusText.querySelector('.mark-clear').onclick = () => { setArrowMark(id, null); };
}

function setArrowMark(id, mark) {
  const a = state.arrows.find(ar => ar.id === id);
  if (!a) return;
  a.mark = mark;
  refreshArrows();
  selectArrow(id);
}

function deselectAll() {
  state.selectedNode = null;
  state.selectedNodes = [];
  state.selectedArrow = null;
  nodeLayer.querySelectorAll('.node.selected').forEach(e => e.classList.remove('selected'));
  arrowLayer.querySelectorAll('.selected').forEach(e => e.classList.remove('selected'));
  editorPanel.classList.add('hidden');
  document.getElementById('arrow-curve').value = state.arrowCurve;
  if (state.arrowStart) {
    state.arrowStart = null;
    removeTempArrow();
    if (state.mode === 'add-arrow') statusText.textContent = '点击第一个节点开始连线';
  }
}

/* ── Delete ── */
function deleteSelected() {
  // Multi-select delete
  if (state.selectedNodes.length > 1) {
    const ids = new Set(state.selectedNodes);
    state.arrows = state.arrows.filter(a => !ids.has(a.from) && !ids.has(a.to));
    state.nodes = state.nodes.filter(n => !ids.has(n.id));
    ids.forEach(id => nodeLayer.querySelector(`[data-id="${id}"]`)?.remove());
    refreshArrows();
    deselectAll();
    statusText.textContent = '已删除 ' + ids.size + ' 个节点';
  } else if (state.selectedNode !== null) {
    const id = state.selectedNode;
    state.arrows = state.arrows.filter(a => a.from !== id && a.to !== id);
    state.nodes = state.nodes.filter(n => n.id !== id);
    nodeLayer.querySelector(`[data-id="${id}"]`)?.remove();
    refreshArrows();
    deselectAll();
    statusText.textContent = '节点已删除';
  } else if (state.selectedArrow) {
    const id = state.selectedArrow;
    // Also remove arrow-label node and its connections
    const labelNodeId = 'al_' + id;
    state.arrows = state.arrows.filter(a => a.from !== labelNodeId && a.to !== labelNodeId);
    state.nodes = state.nodes.filter(n => n.id !== labelNodeId);
    state.arrows = state.arrows.filter(a => a.id !== id);
    arrowLayer.querySelector(`[data-id="${id}"]`)?.remove();
    deselectAll();
    refreshArrows();
    statusText.textContent = '箭头已删除';
  }
  triggerAutoSave();
}

let clearPending = false;
function clearAll() {
  if (!clearPending) {
    clearPending = true;
    statusText.textContent = '⚠️ 再次点击"清空"确认清除所有内容';
    setTimeout(() => { clearPending = false; statusText.textContent = '已取消清空'; }, 3000);
    return;
  }
  clearPending = false;
  state.nodes = []; state.arrows = [];
  nodeLayer.innerHTML = '';
  arrowLayer.querySelectorAll('g').forEach(g => g.remove());
  deselectAll();
  statusText.textContent = '画布已清空';
  triggerAutoSave();
}

/* ── Editor Panel (Popup Window) ── */
// Drag popup by header
(function() {
  const header = document.getElementById('editor-header');
  let isDragging = false, startX, startY, startLeft, startTop;
  header.addEventListener('mousedown', (e) => {
    if (e.target.id === 'editor-close') return;
    isDragging = true;
    const rect = editorPanel.getBoundingClientRect();
    startX = e.clientX;
    startY = e.clientY;
    startLeft = rect.left;
    startTop = rect.top;
    e.preventDefault();
  });
  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    editorPanel.style.left = (startLeft + dx) + 'px';
    editorPanel.style.top = (startTop + dy) + 'px';
    editorPanel.style.right = 'auto';
  });
  document.addEventListener('mouseup', () => { isDragging = false; });
})();

// Close button
document.getElementById('editor-close').onclick = () => {
  editorPanel.classList.add('hidden');
};

// ── Inline canvas text input: type directly on the canvas ──
function showCanvasTextInput(canvasX, canvasY, initialText, onCommit) {
  // Remove any existing inline input
  const old = document.getElementById('canvas-text-input');
  if (old) old.remove();

  // Convert canvas coords to screen coords
  const screenX = canvasX * state.zoom + state.panX;
  const screenY = canvasY * state.zoom + state.panY;

  const inp = document.createElement('textarea');
  inp.id = 'canvas-text-input';
  inp.value = initialText || '';
  inp.placeholder = '输入文字...';
  inp.style.cssText = `
    position: absolute;
    left: ${screenX}px;
    top: ${screenY}px;
    min-width: 120px;
    max-width: 400px;
    min-height: 28px;
    padding: 6px 10px;
    font-size: ${13 * state.zoom}px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-weight: 500;
    color: #1e293b;
    background: #fff;
    border: 2px solid #6366f1;
    border-radius: 6px;
    outline: none;
    box-shadow: 0 4px 16px rgba(99,102,241,0.25);
    resize: none;
    overflow: hidden;
    z-index: 500;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
  `;

  // Auto-resize height as user types
  function autoResize() {
    inp.style.height = 'auto';
    inp.style.height = inp.scrollHeight + 'px';
    // Auto-widen based on content
    const lines = inp.value.split('\n');
    const maxLen = Math.max(...lines.map(l => l.length));
    inp.style.width = Math.max(120, Math.min(400, maxLen * 9 * state.zoom + 24)) + 'px';
  }

  function commit() {
    const text = inp.value;
    inp.remove();
    if (onCommit) onCommit(text);
  }

  function cancel() {
    inp.remove();
  }

  inp.addEventListener('input', autoResize);

  inp.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      commit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      cancel();
    }
    e.stopPropagation(); // Don't let keyboard shortcuts (Delete etc.) fire
  });

  // Commit on click-away
  inp.addEventListener('blur', () => {
    // Small delay to let click events process first
    setTimeout(() => {
      if (document.getElementById('canvas-text-input')) {
        commit();
      }
    }, 150);
  });

  // Prevent canvas click from immediately removing input
  inp.addEventListener('mousedown', (e) => e.stopPropagation());
  inp.addEventListener('click', (e) => e.stopPropagation());

  canvas.appendChild(inp);
  setTimeout(() => { inp.focus(); autoResize(); }, 30);
}

function showInlineDescEditor(n, el) {
  // Find or create the desc div
  let descDiv = el.querySelector('.desc');
  if (!descDiv) {
    // No desc div yet — create one
    descDiv = document.createElement('div');
    descDiv.className = 'desc';
    // A hidden description is not empty. Restore its saved text before editing
    // so a double-click cannot accidentally overwrite it with an empty string.
    descDiv.textContent = n.desc || '';
    // Insert after the label span, before the ports
    const labelSpan = el.querySelector('.label');
    if (labelSpan && labelSpan.nextSibling) {
      el.insertBefore(descDiv, labelSpan.nextSibling);
    } else {
      el.appendChild(descDiv);
    }
  }

  // Make it contenteditable — edit directly in place
  descDiv.setAttribute('contenteditable', 'true');
  descDiv.style.outline = '1.5px solid #6366f1';
  descDiv.style.borderRadius = '3px';
  descDiv.style.padding = '2px 4px';
  descDiv.style.minHeight = '1.5em';
  descDiv.style.cursor = 'text';
  descDiv.focus();

  // Place cursor at end
  const range = document.createRange();
  range.selectNodeContents(descDiv);
  range.collapse(false);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);

  const saveAndClose = () => {
    descDiv.removeAttribute('contenteditable');
    descDiv.style.outline = '';
    descDiv.style.padding = '';
    descDiv.style.minHeight = '';
    descDiv.style.cursor = '';

    // Convert innerHTML (with <br> and <div>) back to plain text with \n
    // Use innerText which preserves line breaks
    n.desc = descDiv.innerText;
    if (n.desc && !n.showDesc) n.showDesc = true;
    // Rebuild the whole node so the description toggle is added/removed too.
    rerenderNode(n);
    refreshArrows();
    triggerAutoSave();
  };

  descDiv.onkeydown = (e) => {
    if (e.key === 'Escape') {
      saveAndClose();
      return;
    }
    e.stopPropagation();
  };

  descDiv.onblur = () => {
    if (descDiv.getAttribute('contenteditable') === 'true') {
      saveAndClose();
    }
  };

  descDiv.onmousedown = (e) => {
    if (descDiv.getAttribute('contenteditable') === 'true') e.stopPropagation();
  };
}

function showInlineLabelEditor(n, el) {
  const labelSpan = el.querySelector('.label');
  if (!labelSpan) return;

  labelSpan.setAttribute('contenteditable', 'true');
  labelSpan.style.outline = '1.5px solid #6366f1';
  labelSpan.style.borderRadius = '3px';
  labelSpan.style.padding = '0 4px';
  labelSpan.style.cursor = 'text';
  labelSpan.focus();

  const range = document.createRange();
  range.selectNodeContents(labelSpan);
  range.collapse(false);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);

  const saveAndClose = () => {
    labelSpan.removeAttribute('contenteditable');
    labelSpan.style.outline = '';
    labelSpan.style.padding = '';
    labelSpan.style.cursor = '';
    n.label = labelSpan.innerText.trim() || n.label;
    refreshArrows();
    triggerAutoSave();
  };

  labelSpan.onkeydown = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); saveAndClose(); }
    if (e.key === 'Escape') {
      saveAndClose();
      return;
    }
    e.stopPropagation();
  };

  labelSpan.onblur = () => {
    if (labelSpan.getAttribute('contenteditable') === 'true') {
      saveAndClose();
    }
  };
  
  labelSpan.onmousedown = (e) => {
    if (labelSpan.getAttribute('contenteditable') === 'true') e.stopPropagation();
  };
}

function showEditor(n) {
  editorPanel.classList.remove('hidden');
  document.getElementById('edit-label').value = n.label;
  document.getElementById('edit-desc').value = n.desc || '';
  document.getElementById('edit-show-desc').checked = !!n.showDesc;
  
  const colorRow = document.getElementById('edit-color-row');
  const sizeRow = document.getElementById('edit-size-row');
  if (n.isGroup) {
    colorRow.style.display = 'none';
    sizeRow.style.display = 'flex';
    document.getElementById('edit-width').value = Math.round(n.gw || 300);
    document.getElementById('edit-height').value = Math.round(n.gh || 200);
  } else {
    colorRow.style.display = 'block';
    sizeRow.style.display = 'flex';
    document.getElementById('edit-bg').value = n.bg;
    document.getElementById('edit-border').value = n.border;
    // Highlight active swatches
    document.querySelectorAll('#bg-swatches .swatch').forEach(s => {
      s.classList.toggle('active', s.dataset.color === n.bg);
    });
    document.querySelectorAll('#border-swatches .swatch').forEach(s => {
      s.classList.toggle('active', s.dataset.color === n.border);
    });
    const el = nodeLayer.querySelector(`[data-id="${n.id}"]`);
    document.getElementById('edit-width').value = Math.round(n.nw || (el ? el.offsetWidth : 100));
    document.getElementById('edit-height').value = Math.round(n.nh || (el ? el.offsetHeight : 50));
  }

  // Font size
  const curFs = n.fontSize || 13;
  document.getElementById('edit-fontsize').value = curFs;
  document.getElementById('edit-fontsize-val').textContent = curFs + 'px';

  // Update drill button
  const drillBtn = document.getElementById('edit-drill');
  if (n.linkedWorkspaceId && workspaces.find(w => w.id === n.linkedWorkspaceId)) {
    drillBtn.textContent = '🔗 进入子图 →';
    drillBtn.style.background = 'rgba(16,185,129,0.12)';
    drillBtn.style.borderColor = '#10b981';
    drillBtn.style.color = '#059669';
  } else {
    drillBtn.textContent = '🔗 创建子图';
    drillBtn.style.background = 'rgba(99,102,241,0.1)';
    drillBtn.style.borderColor = '#6366f1';
    drillBtn.style.color = '#6366f1';
  }
}

// Color swatch click handlers
document.querySelectorAll('#bg-swatches .swatch').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('#bg-swatches .swatch').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('edit-bg').value = btn.dataset.color;
  };
});
document.querySelectorAll('#border-swatches .swatch').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('#border-swatches .swatch').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('edit-border').value = btn.dataset.color;
  };
});

// Reset size button
document.getElementById('edit-reset-size').onclick = () => {
  const n = state.nodes.find(n => n.id === state.selectedNode);
  if (!n || n.isGroup) return;
  n.nw = 0;
  n.nh = 0;
  const el = nodeLayer.querySelector(`[data-id="${n.id}"]`);
  if (el) {
    el.style.width = '';
    el.style.minHeight = '';
  }
  refreshArrows();
  // Update the inputs to show actual size
  setTimeout(() => {
    const el2 = nodeLayer.querySelector(`[data-id="${n.id}"]`);
    if (el2) {
      document.getElementById('edit-width').value = el2.offsetWidth;
      document.getElementById('edit-height').value = el2.offsetHeight;
    }
  }, 50);
  statusText.textContent = '已重置为自动大小';
};

// Font size slider live preview
document.getElementById('edit-fontsize').oninput = (e) => {
  const val = e.target.value;
  document.getElementById('edit-fontsize-val').textContent = val + 'px';
  const n = state.nodes.find(n => n.id === state.selectedNode);
  if (!n) return;
  const el = nodeLayer.querySelector(`[data-id="${n.id}"]`);
  if (el) el.style.fontSize = val + 'px';
};

function applyEdit() {
  const n = state.nodes.find(n => n.id === state.selectedNode);
  if (!n) return;
  n.label = document.getElementById('edit-label').value;
  n.desc = document.getElementById('edit-desc').value;
  n.showDesc = document.getElementById('edit-show-desc').checked;
  
  if (!n.isGroup) {
    n.bg = document.getElementById('edit-bg').value;
    n.border = document.getElementById('edit-border').value;
  }

  // Apply size
  const newW = parseInt(document.getElementById('edit-width').value) || 0;
  const newH = parseInt(document.getElementById('edit-height').value) || 0;
  if (n.isGroup) {
    n.gw = Math.max(40, newW);
    n.gh = Math.max(30, newH);
  } else {
    n.nw = Math.max(60, newW);
    n.nh = Math.max(30, newH);
  }

  // Apply font size
  const newFs = parseInt(document.getElementById('edit-fontsize').value) || 13;
  n.fontSize = newFs;
  
  // Rebuild the node after editing. Updating only the description element left
  // the expand/collapse button stale when a description was added or hidden.
  rerenderNode(n);
  editorPanel.classList.add('hidden');
  refreshArrows();
  statusText.textContent = '节点已更新';
  triggerAutoSave();
}

/* ── Save / Load ── */
function saveJSON() {
  saveCurrentWorkspaceState();
  const projectData = {
    version: 2,
    activeWorkspaceId: activeWorkspaceId,
    workspaces: workspaces
  };
  const data = JSON.stringify(projectData, null, 2);
  const blob = new Blob([data], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '动力图工程_' + new Date().toISOString().slice(0, 10) + '.json';
  a.click();
  statusText.textContent = '已保存全部 ' + workspaces.length + ' 个标签页';
}

function loadJSON() {
  const input = document.createElement('input');
  input.type = 'file'; input.accept = '.json';
  input.onchange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result);
        
        if (data.version === 2 && data.workspaces) {
          // Ask user: replace all or append?
          const doReplace = confirm('检测到多标签页工程文件（' + data.workspaces.length + ' 个标签页）。\n\n确定 = 替换当前所有标签页\n取消 = 追加到现有标签页');
          if (doReplace) {
            workspaces = data.workspaces;
          } else {
            data.workspaces.forEach(ws => { workspaces.push(ws); });
          }
          const targetId = data.activeWorkspaceId || data.workspaces[0].id;
          activeWorkspaceId = targetId;
          const ws = workspaces.find(w => w.id === targetId) || workspaces[workspaces.length - 1];
          activeWorkspaceId = ws.id;
          loadWorkspaceState(ws);
          renderTabs();
          statusText.textContent = '已加载 ' + data.workspaces.length + ' 个标签页（' + (doReplace ? '替换' : '追加') + '模式）';
        } else {
          // Old single-workspace format (backward compatible)
          let maxId = 0;
          (data.nodes || []).forEach(n => {
            if (n.id > maxId) maxId = n.id;
          });
          
          let tabName = file.name.replace('.json', '');
          if (tabName.includes('_')) tabName = tabName.split('_')[0];
          
          createWorkspace(tabName, {
            nodes: data.nodes || [],
            arrows: data.arrows || [],
            nextId: maxId + 1,
            zoom: 1,
            panX: 0,
            panY: 0
          });
          statusText.textContent = '加载成功，已在新标签页打开！';
        }
      } catch (err) { alert('文件格式错误: ' + err.message); }
    };
    reader.readAsText(file);
  };
  input.click();
}

/* ── Export PNG ── */
function exportPNG() {
  // Use html2canvas-like approach via SVG foreignObject
  const nodes = nodeLayer.querySelectorAll('.node');
  if (nodes.length === 0) { alert('画布为空'); return; }

  // Calculate bounds
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  state.nodes.filter(n => !n.isArrowLabel).forEach(n => {
    const el = nodeLayer.querySelector(`[data-id="${n.id}"]`);
    if (!el) return;
    minX = Math.min(minX, n.x);
    minY = Math.min(minY, n.y);
    maxX = Math.max(maxX, n.x + el.offsetWidth);
    maxY = Math.max(maxY, n.y + el.offsetHeight);
  });
  const pad = 60;
  const w = maxX - minX + pad * 2;
  const h = maxY - minY + pad * 2;

  // Dynamically calculate scale to avoid browser canvas limits (max area ~268MP, max dim ~32767)
  let scale = 2; // preferred high-DPI
  const maxArea = 200_000_000;
  const maxDim = 32000;
  
  if (w * scale > maxDim || h * scale > maxDim || (w * scale * h * scale) > maxArea) {
    // reduce scale to fit
    const scaleDim = Math.min(maxDim / w, maxDim / h);
    const scaleArea = Math.sqrt(maxArea / (w * h));
    scale = Math.min(scale, scaleDim, scaleArea);
  }
  
  // Also, if scale ends up very small, at least try to give them something (though quality drops)
  scale = Math.max(scale, 0.1);

  const c = document.createElement('canvas');
  c.width = w * scale; c.height = h * scale;
  const ctx = c.getContext('2d');
  ctx.scale(scale, scale);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, w, h);

  // Draw arrows
  state.arrows.forEach(a => {
    const pts = getArrowPoints(a);
    if (!pts) return;
    ctx.strokeStyle = a.color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    const cr = canvas.getBoundingClientRect();
    const x1 = pts.x1 - minX + pad, y1 = pts.y1 - minY + pad;
    const x2 = pts.x2 - minX + pad, y2 = pts.y2 - minY + pad;
    ctx.moveTo(x1, y1);
    
    // Draw line or curve
    const curveOffset = getArrowCurveOffset(a, {x1: pts.x1, y1: pts.y1, x2: pts.x2, y2: pts.y2});
    const pathData = buildCurvePath(x1, y1, x2, y2, a.fromPort, a.toPort, a.isStraight, a.from, a.to, curveOffset);
    const p2d = new Path2D(pathData);
    ctx.stroke(p2d);
    
    // Arrowhead
    let headAngle = Math.atan2(y2 - y1, x2 - x1);
    if (!a.isStraight) {
      const offsets = { top: [0, -curveOffset], bottom: [0, curveOffset], left: [-curveOffset, 0], right: [curveOffset, 0] };
      const cx2 = x2 + (offsets[a.toPort]?.[0] || 0);
      const cy2 = y2 + (offsets[a.toPort]?.[1] || 0);
      headAngle = Math.atan2(y2 - cy2, x2 - cx2);
    }
    
    ctx.fillStyle = a.color;
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - 12 * Math.cos(headAngle - 0.4), y2 - 12 * Math.sin(headAngle - 0.4));
    ctx.lineTo(x2 - 12 * Math.cos(headAngle + 0.4), y2 - 12 * Math.sin(headAngle + 0.4));
    ctx.closePath(); ctx.fill();
    
    if (a.bidir) {
      let startAngle = Math.atan2(y1 - y2, x1 - x2);
      if (!a.isStraight) {
        const offsets = { top: [0, -curveOffset], bottom: [0, curveOffset], left: [-curveOffset, 0], right: [curveOffset, 0] };
        const cx1 = x1 + (offsets[a.fromPort]?.[0] || 0);
        const cy1 = y1 + (offsets[a.fromPort]?.[1] || 0);
        startAngle = Math.atan2(y1 - cy1, x1 - cx1);
      }
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x1 - 12 * Math.cos(startAngle - 0.4), y1 - 12 * Math.sin(startAngle - 0.4));
      ctx.lineTo(x1 - 12 * Math.cos(startAngle + 0.4), y1 - 12 * Math.sin(startAngle + 0.4));
      ctx.closePath(); ctx.fill();
    }
    
    // Arrow Label — above the line, rotated parallel
    if (a.label || a.desc) {
      const midX = (x1 + x2) / 2;
      const midY = (y1 + y2) / 2;
      
      var tdx = x2 - x1, tdy = y2 - y1;
      if (!a.isStraight) {
        // Find canvas scale distance logic roughly matching buildCurvePath
        const dist = Math.hypot(tdx, tdy);
        const curve = Math.min(dist * 0.4, 80);
        const offsets = { top: [0, -curve], bottom: [0, curve], left: [-curve, 0], right: [curve, 0] };
        // We need original node logic to perfectly match curve. Fortunately we can just use the DOM midpoints
        // since we didn't save the exact points. But wait, we can just grab them from getArrowPoints.
      }
      
      // Let's get exact midpoint and tangent directly from getArrowPoints logic
      const pts = getArrowPoints(a);
      if (pts) {
        const { x: mx0, y: my0 } = getArrowMidpoint(a, pts);
        // Transform to canvas coordinates
        const mx = mx0 - minX + pad;
        const my = my0 - minY + pad;
        
        var adx = pts.x2 - pts.x1;
        var ady = pts.y2 - pts.y1;
        if (!a.isStraight) {
          const curve = getArrowCurveOffset(a, pts);
          const offsets = { top: [0, -curve], bottom: [0, curve], left: [-curve, 0], right: [curve, 0] };
          const cx1 = pts.x1 + (offsets[a.fromPort]?.[0] || 0);
          const cy1 = pts.y1 + (offsets[a.fromPort]?.[1] || 0);
          const cx2 = pts.x2 + (offsets[a.toPort]?.[0] || 0);
          const cy2 = pts.y2 + (offsets[a.toPort]?.[1] || 0);
          adx = 0.75 * (pts.x2 + cx2 - cx1 - pts.x1);
          ady = 0.75 * (pts.y2 + cy2 - cy1 - pts.y1);
        }
        
        var labelAngle = Math.atan2(ady, adx) * 180 / Math.PI;
        var absAngle = Math.abs(labelAngle);
        var isVertical = (absAngle > 60 && absAngle < 120);
        
        ctx.save();
        ctx.fillStyle = '#1f2937';
        
        if (isVertical) {
          ctx.font = '500 13px "Noto Sans SC", sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 4;
          
          let offsetX = 16;
          if (!a.isStraight) {
            const midStraightX = (pts.x1 + pts.x2) / 2;
            if (mx0 < midStraightX) {
              offsetX = -16;
            }
          }
          const descOffsetX = offsetX < 0 ? offsetX - 14 : offsetX + 14;
          
          if (a.label) {
            var totalH = a.label.length * 14;
            var startY = my - totalH / 2 + 7;
            for (var i=0; i<a.label.length; i++) {
               ctx.strokeText(a.label[i], mx + offsetX, startY + i*14);
               ctx.fillText(a.label[i], mx + offsetX, startY + i*14);
            }
          }
          if (a.desc) {
            ctx.font = '400 11px "Noto Sans SC", sans-serif';
            ctx.fillStyle = '#6b7280';
            var totalHDesc = a.desc.length * 12;
            var startYDesc = my - totalHDesc / 2 + 6;
            for (var i=0; i<a.desc.length; i++) {
               ctx.strokeText(a.desc[i], mx + (a.label ? descOffsetX : offsetX), startYDesc + i*12);
               ctx.fillText(a.desc[i], mx + (a.label ? descOffsetX : offsetX), startYDesc + i*12);
            }
          }
        } else {
          ctx.font = '500 13px "Noto Sans SC", sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          var perpAngle = labelAngle;
          if (perpAngle > 90 || perpAngle < -90) perpAngle += 180;
          
          var rad = labelAngle * Math.PI / 180;
          var perpX = -Math.sin(rad) * 14;
          var perpY = Math.cos(rad) * 14;
          
          ctx.translate(mx + perpX, my - perpY);
          ctx.rotate(perpAngle * Math.PI / 180);
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 4;
          
          if (a.label) {
            ctx.strokeText(a.label, 0, a.desc ? -6 : 0);
            ctx.fillText(a.label, 0, a.desc ? -6 : 0);
          }
          if (a.desc) {
            ctx.font = '400 11px "Noto Sans SC", sans-serif';
            ctx.fillStyle = '#6b7280';
            ctx.strokeText(a.desc, 0, a.label ? 8 : 0);
            ctx.fillText(a.desc, 0, a.label ? 8 : 0);
          }
        }
        ctx.restore();
      }
    }
  });

  function wrapText(context, text, x, y, maxWidth, lineHeight) {
    let words = text.split('');
    let line = '';
    let lines = [];
    for (let n = 0; n < words.length; n++) {
      let testLine = line + words[n];
      let metrics = context.measureText(testLine);
      let testWidth = metrics.width;
      if (testWidth > maxWidth && n > 0) {
        lines.push(line);
        line = words[n];
      } else {
        line = testLine;
      }
    }
    lines.push(line);
    let startY = y - (lines.length - 1) * lineHeight / 2;
    for (let i = 0; i < lines.length; i++) {
      context.fillText(lines[i], x, startY + (i * lineHeight));
    }
  }

  // Draw nodes
  state.nodes.filter(n => !n.isArrowLabel).forEach(n => {
    const el = document.querySelector(`[data-id="${n.id}"]`);
    if (!el) return;
    const nx = n.x - minX + pad, ny = n.y - minY + pad;
    const nw = el.offsetWidth, nh = el.offsetHeight;
    
    if (n.isLabel) {
      // Label node: just text, no box
      ctx.fillStyle = '#1e293b';
      ctx.font = 'bold 18px "Noto Sans SC", sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText(n.label, nx, ny);
    } else {
      ctx.fillStyle = n.bg;
      ctx.strokeStyle = n.border;
      ctx.lineWidth = 2;
      if (n.isGroup) ctx.setLineDash([6, 6]);
      else ctx.setLineDash([]);
      
      roundRect(ctx, nx, ny, nw, nh, 12);
      ctx.fill(); ctx.stroke();
      ctx.setLineDash([]); // Reset
      
      if (n.isGroup) {
        // Group title: top-left corner
        ctx.fillStyle = '#6366f1';
        ctx.font = 'bold 16px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillText(n.label, nx + 12, ny + 8);
      } else {
        // Regular node: centered
        ctx.fillStyle = '#111827';
        ctx.font = '500 15px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        wrapText(ctx, n.label, nx + nw / 2, ny + nh / 2, nw - 20, 20);
      }
    }
  });

  const link = document.createElement('a');
  link.download = '动力图_' + new Date().toISOString().slice(0, 10) + '.png';
  link.href = c.toDataURL();
  link.click();
  
  statusText.textContent = '已导出PNG图片。源文件请点击“保存工程”。';
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

/* ── Keyboard ── */
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') e.target.blur();
    deselectAll();
    return;
  }
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;

  // ── Copy: Ctrl+C ──
  if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
    e.preventDefault();
    // Use multi-select if available, otherwise single selected node
    let selIds = state.selectedNodes.length > 0 ? [...state.selectedNodes] : (state.selectedNode ? [state.selectedNode] : []);

    // If an arrow is selected (e.g. user clicked a free arrow), include its endpoints
    if (state.selectedArrow) {
      const sa = state.arrows.find(a => a.id === state.selectedArrow);
      if (sa) {
        if (!selIds.includes(sa.from)) selIds.push(sa.from);
        if (!selIds.includes(sa.to)) selIds.push(sa.to);
      }
    }

    if (selIds.length === 0) return;

    // Expand selection: include children of any group nodes
    const expandedIds = new Set(selIds);
    selIds.forEach(id => {
      const n = state.nodes.find(nd => nd.id === id);
      if (n && n.isGroup) {
        const children = getChildrenOfGroup(n);
        children.forEach(c => expandedIds.add(c.id));
      }
    });

    // Expand selection: include free arrow anchors
    // If an arrow has one endpoint selected, include the other + the arrow
    state.arrows.forEach(a => {
      if (expandedIds.has(a.from) || expandedIds.has(a.to)) {
        expandedIds.add(a.from);
        expandedIds.add(a.to);
      }
    });

    const selNodes = state.nodes.filter(n => expandedIds.has(n.id));
    // Collect all arrows where BOTH endpoints are in expanded set
    const selArrows = state.arrows.filter(a => expandedIds.has(a.from) && expandedIds.has(a.to));

    state._clipboard = {
      nodes: JSON.parse(JSON.stringify(selNodes)),
      arrows: JSON.parse(JSON.stringify(selArrows))
    };
    statusText.textContent = '已复制 ' + selNodes.length + ' 个节点, ' + selArrows.length + ' 条箭头';
    return;
  }

  // ── Paste: Ctrl+V ──
  if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
    e.preventDefault();
    if (!state._clipboard || !state._clipboard.nodes.length) return;

    // Calculate bounding box center of copied nodes
    const clipNodes = state._clipboard.nodes;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    clipNodes.forEach(n => {
      minX = Math.min(minX, n.x);
      minY = Math.min(minY, n.y);
      maxX = Math.max(maxX, n.x + (n.isGroup ? (n.gw || 300) : (n.nw || 100)));
      maxY = Math.max(maxY, n.y + (n.isGroup ? (n.gh || 200) : (n.nh || 40)));
    });
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    // Paste at mouse position (convert screen to canvas coords)
    const mouseCanvas = screenToCanvas(state._lastMouseX || 0, state._lastMouseY || 0);
    const offsetX = mouseCanvas.x - centerX;
    const offsetY = mouseCanvas.y - centerY;

    const idMap = {}; // old id → new id
    const newNodes = [];
    clipNodes.forEach(orig => {
      const newId = String(state.nextId++);
      idMap[orig.id] = newId;
      const nn = JSON.parse(JSON.stringify(orig));
      nn.id = newId;
      nn.x += offsetX;
      nn.y += offsetY;
      state.nodes.push(nn);
      renderNode(nn);
      // Apply font size and anchor styling
      const el = nodeLayer.querySelector(`[data-id="${nn.id}"]`);
      if (nn.fontSize && el) el.style.fontSize = nn.fontSize + 'px';
      if (nn.isFreeAnchor && el) {
        el.style.minWidth = '8px'; el.style.minHeight = '8px';
        el.style.padding = '0'; el.style.opacity = '0.3'; el.style.fontSize = '8px';
      }
      newNodes.push(nn);
    });
    // Paste arrows between copied nodes
    if (state._clipboard.arrows) {
      state._clipboard.arrows.forEach(orig => {
        if (idMap[orig.from] && idMap[orig.to]) {
          const na = JSON.parse(JSON.stringify(orig));
          na.id = 'a' + state.nextId++;
          na.from = idMap[orig.from];
          na.to = idMap[orig.to];
          // Update free arrow anchor references
          if (na._anchorFromId && idMap[na._anchorFromId]) na._anchorFromId = idMap[na._anchorFromId];
          if (na._anchorToId && idMap[na._anchorToId]) na._anchorToId = idMap[na._anchorToId];
          state.arrows.push(na);
          renderArrow(na);
        }
      });
    }
    // Select all pasted nodes
    deselectAll();
    state.selectedNodes = newNodes.map(n => n.id);
    state.selectedNode = newNodes[0]?.id || null;
    newNodes.forEach(nn => {
      const el = nodeLayer.querySelector(`[data-id="${nn.id}"]`);
      if (el) el.classList.add('selected');
    });
    statusText.textContent = '已粘贴 ' + newNodes.length + ' 个节点';
    triggerAutoSave();
    return;
  }

  if (e.key === 'Delete' || e.key === 'Backspace') deleteSelected();
  if (e.key === '1') setMode('add-node');
  if (e.key === '2') setMode('add-arrow');
  if (e.key === '3') setMode('select');
  if (e.key === '+' || e.key === '=') { e.preventDefault(); zoomBy(0.15); }
  if (e.key === '-' || e.key === '_') { e.preventDefault(); zoomBy(-0.15); }
  if (e.key === '0') { e.preventDefault(); resetView(); }
  if (e.key === ' ') { e.preventDefault(); state.spaceHeld = true; document.body.classList.add('space-held'); }
});
document.addEventListener('keyup', (e) => {
  if (e.key === ' ') { state.spaceHeld = false; document.body.classList.remove('space-held'); }
});

/* ── Helpers ── */
function adjustColor(hex, amount) {
  let c = hex.replace('#', '');
  if (c.length === 3) c = c[0]+c[0]+c[1]+c[1]+c[2]+c[2];
  const num = parseInt(c, 16);
  let r = Math.min(255, Math.max(0, (num >> 16) + amount));
  let g = Math.min(255, Math.max(0, ((num >> 8) & 0xff) + amount));
  let b = Math.min(255, Math.max(0, (num & 0xff) + amount));
  return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
}

/* ── Inline Arrow Label Editor ── */
function showArrowLabelEditor(a, svgX, svgY) {
  // Remove any existing inline editor
  const old = document.getElementById('arrow-label-editor');
  if (old) old.remove();

  const inpContainer = document.createElement('div');
  inpContainer.id = 'arrow-label-editor';
  
  const inpLabel = document.createElement('textarea');
  inpLabel.value = a.label || '';
  inpLabel.placeholder = '输入主标签（可多行）...';
  inpLabel.rows = Math.max(2, (a.label || '').split('\n').length);
  
  const inpDesc = document.createElement('textarea');
  inpDesc.value = a.desc || '';
  inpDesc.placeholder = '输入备注/副标签（可多行）...';
  inpDesc.rows = Math.max(2, (a.desc || '').split('\n').length);

  // Calculate actual screen coordinates
  const screenX = svgX * state.zoom + state.panX;
  const screenY = svgY * state.zoom + state.panY;

  inpContainer.style.cssText = `
    position:absolute; left:${screenX - 90}px; top:${screenY - 40}px;
    width:180px; padding:8px; background:#ffffff;
    border:1px solid #6366f1; border-radius:6px; z-index:300;
    box-shadow:0 4px 12px rgba(0,0,0,0.15); display:flex; flex-direction:column; gap:4px;
  `;
  
  const textareaStyle = `
    width: 100%; border: 1px solid #e5e7eb; outline: none; background: #f9fafb;
    text-align: center; font-family: inherit; resize: vertical;
    border-radius: 4px; padding: 4px;
  `;
  inpLabel.style.cssText = textareaStyle + 'font-size: 13px; color: #111827; font-weight: 500;';
  inpDesc.style.cssText = textareaStyle + 'font-size: 11px; color: #6b7280;';

  // Hint text
  const hint = document.createElement('div');
  hint.textContent = 'Ctrl+Enter 保存 / Esc 取消';
  hint.style.cssText = 'font-size:10px; color:#9ca3af; text-align:center; margin-top:2px;';

  inpContainer.appendChild(inpLabel);
  inpContainer.appendChild(inpDesc);
  inpContainer.appendChild(hint);
  
  const saveAndClose = () => {
    a.label = inpLabel.value;
    a.desc = inpDesc.value;
    inpContainer.remove();
    refreshArrows();
    triggerAutoSave();
  };

  inpContainer.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) saveAndClose();
    if (e.key === 'Escape') inpContainer.remove();
  });
  
  // Need to handle blur carefully since there are two inputs
  inpContainer.addEventListener('focusout', (e) => {
    if (!inpContainer.contains(e.relatedTarget)) {
      saveAndClose();
    }
  });

  canvas.appendChild(inpContainer);
  inpLabel.focus();
  inpLabel.select();
}

/* ── Demo: recreate screenshot diagram ── */
function loadDemo() {
  createWorkspace('默认画布');
  const n1 = createNode(200, 120, '政府');
  const n2 = createNode(450, 120, '央行');
  const n3 = createNode(420, 280, '银行');
  const n4 = createNode(420, 420, '企业');
  const n5 = createNode(300, 540, '员工');
  createArrow(n2.id, 'left', n1.id, 'right', '', '#0f3460');
  createArrow(n1.id, 'bottom', n5.id, 'top', '', '#0f3460');
  createArrow(n3.id, 'bottom', n4.id, 'top', '', '#0f3460');
  setMode('select');
  triggerAutoSave();
}

// One-time migration: clear stale cache so v4 loads fresh
(function migrateV4() {
  if (localStorage.getItem('sysMapMigration') === 'v6') return;
  localStorage.removeItem('sysMapWorkspaces');
  localStorage.removeItem('sysMapActiveId');
  localStorage.removeItem('sysMapGeneratedHash');
  // Also clear new-format hash keys
  for (var i = localStorage.length - 1; i >= 0; i--) {
    var k = localStorage.key(i);
    if (k && k.startsWith('sysMapAutoHash:')) localStorage.removeItem(k);
  }
  console.log('Migration v4b: cleared stale localStorage cache');
  localStorage.setItem('sysMapMigration', 'v6');
})();

// Always check generated JSON — if it changed since last cache, reload fresh
(function autoLoadGenerated() {
  var GENERATED_URL = 'generated/macro-economy-system-v3-auto-draw.json';
  var HASH_KEY = 'sysMapAutoHash:' + GENERATED_URL; // hash key includes filename
  fetch(GENERATED_URL)
    .then(function(r) { return r.text(); })
    .then(function(text) {
      // Simple hash to detect changes
      var hash = 0;
      for (var i = 0; i < text.length; i++) {
        hash = ((hash << 5) - hash) + text.charCodeAt(i);
        hash |= 0;
      }
      var cachedHash = localStorage.getItem(HASH_KEY);
      var hasLocalData = !!localStorage.getItem('sysMapWorkspaces');

      // If generated file hasn't changed AND we have local data, use cache
      if (hasLocalData && cachedHash === String(hash)) {
        loadFromLocalStorage();
        return;
      }

      // Generated file is new or changed — load it fresh
      console.log('Auto-load: file changed (hash: ' + hash + ' vs cached: ' + cachedHash + '), reloading fresh data');
      var data = JSON.parse(text);

      // Clear ONLY app-specific stale state (not all localStorage)
      workspaces = [];
      nodeLayer.innerHTML = '';
      arrowLayer.querySelectorAll('g').forEach(function(g) { g.remove(); });
      localStorage.removeItem('sysMapWorkspaces');
      localStorage.removeItem('sysMapActiveId');

      if (data.version === 2 && data.workspaces && data.workspaces.length > 0) {
        workspaces = data.workspaces;
        // Run auto-layout on each workspace if nodes have level/lane hints or no valid coords
        workspaces.forEach(function(wsItem) {
          var nodes = wsItem.state.nodes || [];
          var arrows = wsItem.state.arrows || [];
          var hasHints = nodes.some(function(n) { return n.level !== undefined; });
          var hasCoords = nodes.every(function(n) { return n.x !== undefined && n.y !== undefined && (n.x !== 0 || n.y !== 0); });
          if (hasHints || !hasCoords) {
            console.log('Auto-layout workspace: ' + wsItem.name);
            autoLayout(nodes, arrows);
          }
        });
        activeWorkspaceId = data.activeWorkspaceId || workspaces[0].id;
        var ws = workspaces.find(function(w) { return w.id === activeWorkspaceId; }) || workspaces[0];
        activeWorkspaceId = ws.id;
        loadWorkspaceState(ws);
        renderTabs();
      } else {
        var maxId = 0;
        (data.nodes || []).forEach(function(n) { if (n.id > maxId) maxId = n.id; });
        createWorkspace('默认画布', {
          nodes: data.nodes || [],
          arrows: data.arrows || [],
          nextId: maxId + 1,
          zoom: 1,
          panX: 0,
          panY: 0
        });
      }

      // Save hash with filename so switching files works correctly
      localStorage.setItem(HASH_KEY, String(hash));
      setMode('select');
      triggerAutoSave();
    })
    .catch(function(err) {
      console.warn('Failed to fetch generated file, falling back to localStorage/demo:', err);
      if (!loadFromLocalStorage()) {
        loadDemo();
      }
    });
})();
document.getElementById('btn-drag-mode').classList.add('active');

// ── Auto-Layout Button Handlers ──
document.getElementById('btn-auto-layout').addEventListener('click', function() {
  if (typeof autoLayout !== 'function') { statusText.textContent = '⚠️ autoLayout.js 未加载'; return; }
  autoLayout(state.nodes, state.arrows);
  refreshNodes();
  refreshArrows();
  triggerAutoSave();
  var pinnedCount = state.nodes.filter(function(n) { return n.pinned; }).length;
  statusText.textContent = '✅ 自动排版完成！' + (pinnedCount > 0 ? ' (' + pinnedCount + ' 个锁定节点已跳过)' : '');
});

document.getElementById('btn-unlock-all').addEventListener('click', function() {
  var count = 0;
  state.nodes.forEach(function(n) { if (n.pinned) { n.pinned = false; count++; } });
  triggerAutoSave();
  statusText.textContent = count > 0 ? '🔓 已解锁 ' + count + ' 个节点' : '没有锁定的节点';
});

document.getElementById('btn-check-collision').addEventListener('click', function() {
  if (typeof checkArrowCollisions !== 'function') { statusText.textContent = '⚠️ autoLayout.js 未加载'; return; }
  // Clear old warnings
  arrowLayer.querySelectorAll('.collision-warning').forEach(function(el) { el.classList.remove('collision-warning'); });
  var collisions = checkArrowCollisions(state.nodes, state.arrows);
  if (collisions.length === 0) {
    statusText.textContent = '✅ 没有箭头穿过节点，布局干净！';
    return;
  }
  // Highlight colliding arrows
  var arrowIds = new Set();
  collisions.forEach(function(c) { arrowIds.add(c.arrowId); });
  arrowIds.forEach(function(aid) {
    var g = arrowLayer.querySelector('g[data-id="' + aid + '"]');
    if (g) {
      var line = g.querySelector('.arrow-line');
      if (line) line.classList.add('collision-warning');
    }
  });
  statusText.textContent = '⚠️ 发现 ' + arrowIds.size + ' 条箭头穿过节点（已标红）';
});

/* ── Presentation / Slideshow Mode ── */
let presMode = false;
let presOrder = [];   // ordered list of node IDs to present
let presIndex = -1;
let presSrtData = []; // for SRT export
let presAutoTimer = null; // auto-play timer
let presAutoPlaying = true; // auto-play state

function buildPresOrder() {
  const childSet = new Set(state.arrows.map(a => a.to));
  const parentSet = new Set(state.arrows.map(a => a.from));

  // Root = nodes that are parents but not children, or if none, the topmost node
  let roots = state.nodes.filter(n => parentSet.has(n.id) && !childSet.has(n.id));
  if (roots.length === 0 && state.nodes.length > 0) {
    roots = [state.nodes.reduce((a, b) => a.y < b.y ? a : b)];
  }

  const order = [];
  const visited = new Set();

  function dfs(nodeId) {
    if (visited.has(nodeId)) return;
    visited.add(nodeId);
    order.push(nodeId);
    // Find children (nodes this connects TO)
    const children = state.arrows.filter(a => a.from === nodeId).map(a => a.to);
    // Sort children left to right by x position
    const childNodes = children
      .map(id => state.nodes.find(n => n.id === id))
      .filter(Boolean);
    childNodes.sort((a, b) => a.x - b.x);
    childNodes.forEach(cn => dfs(cn.id));
  }

  // Sort roots left to right
  roots.sort((a, b) => a.x - b.x);
  roots.forEach(r => dfs(r.id));

  // Add any unvisited nodes
  state.nodes.forEach(n => {
    if (!visited.has(n.id)) order.push(n.id);
  });

  return order;
}

function startPresentation() {
  if (state.nodes.length === 0) {
    statusText.textContent = '⚠️ 画布为空，无法演示';
    return;
  }

  presMode = true;
  presOrder = buildPresOrder();
  presIndex = -1;
  presSrtData = [];

  // Add overlay
  const overlay = document.createElement('div');
  overlay.id = 'pres-overlay';
  overlay.className = 'pres-overlay';
  document.body.appendChild(overlay);

  // Add subtitle bar
  const subtitle = document.createElement('div');
  subtitle.id = 'pres-subtitle';
  subtitle.className = 'pres-subtitle';
  subtitle.textContent = '';
  document.body.appendChild(subtitle);

  // Add slide counter
  const counter = document.createElement('div');
  counter.id = 'pres-counter';
  counter.className = 'pres-counter';
  counter.textContent = '0 / ' + presOrder.length;
  document.body.appendChild(counter);

  // Add controls
  const controls = document.createElement('div');
  controls.id = 'pres-controls';
  controls.className = 'pres-controls';
  controls.innerHTML =
    '<button id="pres-btn-prev" title="上一步 (←)">⬅ 上一步</button>' +
    '<button id="pres-btn-pause" title="暂停/继续">⏸ 暂停</button>' +
    '<button id="pres-btn-next" title="下一步 (→/空格)">下一步 ➡</button>' +
    '<button id="pres-btn-stop" title="退出 (Esc)">✕ 退出</button>' +
    '<button id="pres-btn-srt" title="导出字幕文件">📄 导出SRT</button>';
  document.body.appendChild(controls);

  // Wire control buttons
  document.getElementById('pres-btn-prev').addEventListener('click', function() { presStopAuto(); presGo(-1); });
  document.getElementById('pres-btn-next').addEventListener('click', function() { presStopAuto(); presGo(1); });
  document.getElementById('pres-btn-pause').addEventListener('click', function() { presToggleAuto(); });
  document.getElementById('pres-btn-stop').addEventListener('click', function() { stopPresentation(); });
  document.getElementById('pres-btn-srt').addEventListener('click', function() { exportSRT(); });

  // Add canvas transition class
  transformGroup.classList.add('pres-mode');

  // Hide toolbar and tabs
  document.getElementById('toolbar').style.display = 'none';
  document.getElementById('tabs-bar').style.display = 'none';
  document.getElementById('zoom-controls').style.display = 'none';
  document.getElementById('status-bar').style.display = 'none';

  // Hide editor if open
  editorPanel.classList.add('hidden');

  // Dim all nodes
  nodeLayer.querySelectorAll('.node').forEach(function(el) {
    el.classList.add('pres-dimmed');
  });

  // Start auto-play
  presAutoPlaying = true;
  presGo(1);
  presStartAuto();
}

function presStartAuto() {
  if (presAutoTimer) clearInterval(presAutoTimer);
  presAutoPlaying = true;
  var pauseBtn = document.getElementById('pres-btn-pause');
  if (pauseBtn) pauseBtn.textContent = '⏸ 暂停';
  presAutoTimer = setInterval(function() {
    if (presIndex >= presOrder.length - 1) {
      presStopAuto();
      return;
    }
    presGo(1);
  }, 4000);
}

function presStopAuto() {
  if (presAutoTimer) { clearInterval(presAutoTimer); presAutoTimer = null; }
  presAutoPlaying = false;
  var pauseBtn = document.getElementById('pres-btn-pause');
  if (pauseBtn) pauseBtn.textContent = '▶ 继续';
}

function presToggleAuto() {
  if (presAutoPlaying) { presStopAuto(); } else { presStartAuto(); }
}

function presGo(direction) {
  if (!presMode) return;

  var newIndex = presIndex + direction;
  if (newIndex < 0 || newIndex >= presOrder.length) return;

  // Un-highlight previous
  if (presIndex >= 0) {
    var prevId = presOrder[presIndex];
    var prevEl = nodeLayer.querySelector('[data-id="' + prevId + '"]');
    if (prevEl) prevEl.classList.remove('pres-highlight');
  }

  presIndex = newIndex;
  var nodeId = presOrder[presIndex];
  var node = state.nodes.find(function(n) { return n.id === nodeId; });
  if (!node) return;

  var el = nodeLayer.querySelector('[data-id="' + nodeId + '"]');
  if (!el) return;

  // Highlight current node
  el.classList.add('pres-highlight');
  el.classList.remove('pres-dimmed');

  // Also un-dim all previously visited nodes
  for (var i = 0; i <= presIndex; i++) {
    var visitedEl = nodeLayer.querySelector('[data-id="' + presOrder[i] + '"]');
    if (visitedEl) visitedEl.classList.remove('pres-dimmed');
  }

  // Re-dim nodes after current index when going backwards
  for (var j = presIndex + 1; j < presOrder.length; j++) {
    var futureEl = nodeLayer.querySelector('[data-id="' + presOrder[j] + '"]');
    if (futureEl) {
      futureEl.classList.add('pres-dimmed');
      futureEl.classList.remove('pres-highlight');
    }
  }

  // Zoom to this node — center it on screen
  var container = canvas; // canvas-container
  var cw = container.clientWidth;
  var ch = container.clientHeight;
  var nw = el.offsetWidth;
  var nh = el.offsetHeight;
  var targetZoom = 1.5;
  var targetPanX = cw / 2 - (node.x + nw / 2) * targetZoom;
  var targetPanY = ch / 2 - (node.y + nh / 2) * targetZoom;

  state.zoom = targetZoom;
  state.panX = targetPanX;
  state.panY = targetPanY;
  transformGroup.style.transform = 'translate(' + state.panX + 'px, ' + state.panY + 'px) scale(' + state.zoom + ')';

  // Update counter
  var counterEl = document.getElementById('pres-counter');
  if (counterEl) counterEl.textContent = (presIndex + 1) + ' / ' + presOrder.length;

  // Show subtitle
  var subtitleEl = document.getElementById('pres-subtitle');
  var title = node.label || '';
  var desc = node.desc || '';
  if (subtitleEl) {
    subtitleEl.innerHTML = '<strong>' + title + '</strong>' + (desc ? '<br>' + desc : '');
  }

  // Record SRT data
  var startTime = presIndex * 4; // 4 seconds per node
  var endTime = startTime + 4;
  presSrtData.push({
    index: presIndex + 1,
    start: formatSRTTime(startTime),
    end: formatSRTTime(endTime),
    text: title + (desc ? '\n' + desc : '')
  });
}

function stopPresentation() {
  presMode = false;

  // Stop auto-play timer
  if (presAutoTimer) { clearInterval(presAutoTimer); presAutoTimer = null; }

  // Remove overlay, subtitle, controls, counter
  var overlay = document.getElementById('pres-overlay');
  if (overlay) overlay.remove();
  var subtitle = document.getElementById('pres-subtitle');
  if (subtitle) subtitle.remove();
  var controls = document.getElementById('pres-controls');
  if (controls) controls.remove();
  var counter = document.getElementById('pres-counter');
  if (counter) counter.remove();

  // Remove canvas transition
  transformGroup.classList.remove('pres-mode');

  // Show toolbar, tabs, zoom controls, status bar
  document.getElementById('toolbar').style.display = '';
  document.getElementById('tabs-bar').style.display = '';
  document.getElementById('zoom-controls').style.display = '';
  document.getElementById('status-bar').style.display = '';

  // Un-dim and un-highlight all nodes
  nodeLayer.querySelectorAll('.node').forEach(function(el) {
    el.classList.remove('pres-dimmed');
    el.classList.remove('pres-highlight');
  });

  // Reset zoom
  state.zoom = 1;
  state.panX = 0;
  state.panY = 0;
  applyTransform();
  refreshArrows();

  statusText.textContent = '演示结束';
}

function formatSRTTime(seconds) {
  var h = Math.floor(seconds / 3600).toString().padStart(2, '0');
  var m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
  var s = Math.floor(seconds % 60).toString().padStart(2, '0');
  return h + ':' + m + ':' + s + ',000';
}

function exportSRT() {
  if (presSrtData.length === 0) {
    alert('请先播放演示再导出字幕');
    return;
  }
  var srt = '';
  presSrtData.forEach(function(item) {
    srt += item.index + '\n' + item.start + ' --> ' + item.end + '\n' + item.text + '\n\n';
  });
  var blob = new Blob([srt], { type: 'text/plain' });
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'mindmap-subtitles.srt';
  a.click();
}

// Keyboard shortcuts for presentation (capture phase to intercept before other handlers)
document.addEventListener('keydown', function(e) {
  if (!presMode) return;
  if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); e.stopImmediatePropagation(); presStopAuto(); presGo(1); }
  if (e.key === 'ArrowLeft') { e.preventDefault(); e.stopImmediatePropagation(); presStopAuto(); presGo(-1); }
  if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); stopPresentation(); }
}, true);
