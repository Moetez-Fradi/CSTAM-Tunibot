// Admin dashboard: live robot state, orders, system health.
'use strict';
(() => {
  const {
    $, el, api, stream, toast, initTheme, storage, label, robotSummary, stateBadge,
    orderStatus, orderStep, clock, clockSec, duration, itemsText, MapView, MOVING_STATES,
  } = CSTAM;

  // Task-manager battery policy (delivery_task_manager.py defaults).
  const THRESHOLDS = [
    { at: 80, text: 'Resumes deliveries', tone: 'ok' },
    { at: 35, text: 'No new deliveries', tone: 'warn' },
    { at: 20, text: 'Returns to dock', tone: 'err' },
  ];
  const WINDOW_SEC = 30 * 60;
  const FEEDS = [
    ['status', 'Delivery status', null], ['battery', 'Battery', 5], ['pose', 'Robot position', 2],
    ['plan', 'Planned route', null], ['people', 'People tracking', 3], ['safety', 'Safety metrics', 5],
  ];

  let config = null;
  let pin = storage.get('sessionStorage', 'cstam.pin') || '';
  let map = null;
  let latest = null;
  let historyKey = '';
  let chartKey = '';
  let live = null;

  initTheme($('#theme'));

  // ----- start & sign-in -------------------------------------------------------
  async function start() {
    try {
      config = await api('/api/config');
    } catch (error) { $('#summary').textContent = error.message; $('#dashboard').hidden = false; return; }
    if (config.admin_pin_required) {
      try { await api('/api/admin/state', { pin }); } catch (error) {
        if (error.status === 401) { showSignin(); return; }
      }
    }
    openDashboard();
  }

  function showSignin(message) {
    $('#signin').hidden = false;
    $('.tabs').hidden = true;
    $('#signin-error').textContent = message || '';
    $('#pin').focus();
  }

  $('#signin-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const tried = $('#pin').value.trim();
    try {
      await api('/api/admin/state', { pin: tried });
      pin = tried;
      storage.set('sessionStorage', 'cstam.pin', pin);
      $('#signin').hidden = true;
      openDashboard();
    } catch (error) {
      showSignin(error.status === 401 ? 'That PIN is not correct.' : error.message);
    }
  });

  function openDashboard() {
    $('#dashboard').hidden = false;
    $('.tabs').hidden = false;
    map = new MapView($('#map'), config, { padding: 20 });
    selectTab(location.hash.slice(1) || 'overview');
    live = stream(`/api/admin/events${pin ? `?pin=${encodeURIComponent(pin)}` : ''}`, render,
      (ok) => { $('#offline').hidden = ok; });
  }

  // ----- tabs ------------------------------------------------------------------
  const TABS = ['overview', 'orders', 'insights', 'maintenance', 'system'];
  function selectTab(name) {
    if (!TABS.includes(name)) name = 'overview';
    for (const tab of TABS) {
      $(`#tab-${tab}`).setAttribute('aria-selected', String(tab === name));
      $(`#${tab}`).hidden = tab !== name;
    }
    if (name === 'orders') loadHistory(true);
    if (name === 'insights') loadInsights();
    if (name === 'maintenance' && latest) renderMaintenance(latest);
    if (name === 'overview' && map) { map.resize(); chartKey = ''; if (latest) renderChart(latest); }
    if (name === 'system' && latest) renderSystem(latest);
    if (location.hash.slice(1) !== name) history.replaceState(null, '', `#${name}`);
  }
  for (const tab of TABS) $(`#tab-${tab}`).addEventListener('click', () => selectTab(tab));
  $('.tabs').addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    const current = TABS.findIndex((t) => $(`#tab-${t}`).getAttribute('aria-selected') === 'true');
    const next = TABS[(current + (event.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length];
    selectTab(next); $(`#tab-${next}`).focus();
  });

  // ----- commands ----------------------------------------------------------------
  $('#dock').addEventListener('click', async (event) => {
    event.currentTarget.disabled = true;
    try {
      const result = await api('/api/admin/return_to_dock', { method: 'POST', body: {}, pin });
      toast(result.message === 'already returning to dock' ? 'Already returning to the dock' : 'Returning to the dock');
    } catch (error) { toast(error.message, 'err'); }
    setTimeout(() => { $('#dock').disabled = false; }, 1500);
  });

  async function cancelOrder(order, button) {
    if (button.dataset.armed !== 'yes') {
      button.dataset.armed = 'yes';
      button.textContent = 'Confirm cancel';
      setTimeout(() => { button.dataset.armed = ''; button.textContent = 'Cancel'; }, 4000);
      return;
    }
    button.disabled = true;
    try {
      await api(`/api/admin/orders/${order.id}/cancel`, { method: 'POST', body: {}, pin });
      toast(`Order ${order.id} for ${label(order.location)} cancelled`);
    } catch (error) { toast(error.message, 'err'); button.disabled = false; }
  }

  // ----- render ------------------------------------------------------------------
  function render(state) {
    latest = state;
    const status = state.status || {};
    const robot = robotSummary(state.online ? status.state : null, status.current_location);

    const badge = $('#state-badge');
    badge.className = `badge tone-${robot.tone}${robot.live ? ' live' : ''}`;
    badge.lastElementChild.textContent = state.online ? (stateBadge[status.state] || status.state || 'Unknown') : 'Offline';
    $('#summary').textContent = state.online ? robot.text : 'The task manager is not running';
    $('#summary-detail').replaceChildren(state.online
      ? el('span', { class: 'mono' }, status.message || '')
      : 'Start the robot with: ros2 launch cstam_phase1 phase1.launch.py');
    $('#dock').disabled = !state.online || ['RETURNING_TO_DOCK', 'IDLE', 'CHARGING'].includes(status.state);

    const pose = state.pose;
    $('#pose').textContent = pose ? `x ${pose.x.toFixed(2)}  y ${pose.y.toFixed(2)}  ${Math.round(pose.yaw * 180 / Math.PI)}°` : 'No position yet';
    map.update({ pose, plan: state.plan, people: state.people, moving: MOVING_STATES.has(status.state) });

    renderActive(status);
    renderBattery(state.battery, status);
    renderQueue(status);
    renderChart(state);
    renderSystem(state);
    renderMaintenance(state);
    if (!$('#insights').hidden) renderCounters(status.counters);
    const key = (status.history || []).map((o) => o.id + o.status).join();
    if (key !== historyKey) { historyKey = key; loadHistory(false); if (!$('#insights').hidden) loadInsights(); }
  }

  const STEPS = ['Queued', 'Kitchen pickup', 'On the way', 'At the table', 'Delivered'];

  function renderActive(status) {
    const panel = $('#active');
    const order = status.active_order;
    const head = el('div', { class: 'panel-head' }, el('h2', {}, 'Active delivery'),
      order ? badgeFor(order.status) : null);
    if (!order) {
      panel.replaceChildren(head, el('div', { class: 'empty' },
        status.queue && status.queue.length ? 'The next order starts as soon as the robot is ready.' : 'No delivery in progress. New orders start automatically.'));
      return;
    }
    const step = orderStep(order);
    const times = [order.created_at, order.started_at, order.picked_up_at, order.arrived_at, order.finished_at];
    const steps = el('ol', { class: 'steps' }, STEPS.map((text, i) => {
      const s = i < step ? 'done' : i === step ? 'now' : '';
      return el('li', { class: `step ${s}` }, el('span', { class: 'step-mark', 'aria-hidden': 'true' }),
        el('span', { class: 'step-label' }, text), el('span', { class: 'step-time' }, s ? clockSec(times[i]) : ''));
    }));
    const progress = status.progress;
    const waitLeft = order.confirm_by ? order.confirm_by - latest.server_time : null;
    const cancel = el('button', { class: 'btn btn-sm btn-danger', type: 'button', onclick: (e) => cancelOrder(order, e.currentTarget) }, 'Cancel');
    panel.replaceChildren(head, el('div', { class: 'panel-body' },
      el('div', { class: 'order-head' }, el('strong', {}, label(order.location)), el('span', { class: 'mono muted', style: 'font-size:12px' }, order.id)),
      el('div', { class: 'order-items' }, itemsText(order.items) || 'No items listed', order.note ? ` — “${order.note}”` : ''),
      steps,
      progress || waitLeft !== null ? el('div', { class: 'eta-row' },
        progress ? el('div', {}, el('strong', {}, duration(progress.eta_sec)), el('span', {}, progress.stage === 'pickup' ? 'to the kitchen' : 'to the table')) : null,
        progress ? el('div', {}, el('strong', {}, `${progress.distance_remaining_m.toFixed(1)} m`), el('span', {}, 'remaining')) : null,
        waitLeft !== null ? el('div', {}, el('strong', {}, duration(waitLeft)), el('span', {}, 'until it leaves the table')) : null) : null),
    el('div', { class: 'panel-foot', style: 'display:flex;justify-content:space-between;align-items:center' },
      el('span', {}, `Placed ${clock(order.created_at)}${order.interruptions ? `, interrupted ${order.interruptions}×` : ''}`), cancel));
  }

  function badgeFor(status) {
    const s = orderStatus[status] || { text: status, tone: '' };
    return el('span', { class: `badge tone-${s.tone}` }, el('span', { class: 'dot' }), s.text);
  }

  function renderBattery(battery, status) {
    const panel = $('#battery');
    const pct = battery && battery.percentage;
    const state = !battery ? 'No battery data' : battery.full ? 'Full' : battery.charging ? 'Charging' : 'Discharging';
    const tone = !battery ? '' : pct <= 20 ? 'err' : pct < 35 ? 'warn' : battery.charging ? 'ok' : '';
    panel.replaceChildren(
      el('div', { class: 'panel-head' }, el('h2', {}, 'Battery'),
        el('span', { class: `badge tone-${tone}${battery && battery.charging ? ' live' : ''}` }, el('span', { class: 'dot' }), state)),
      el('div', { class: 'panel-body' },
        el('div', { class: 'big' }, pct === null || pct === undefined ? '—' : Math.round(pct), el('small', {}, ' %')),
        el('div', { class: 'meter', role: 'meter', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': pct ?? 0, 'aria-label': 'Battery level' },
          el('div', { class: 'meter-fill', style: `width:${pct ?? 0}%;background:${tone === 'err' ? 'var(--err)' : tone === 'warn' ? 'var(--warn-dot)' : 'var(--ink)'}` }),
          THRESHOLDS.map((t) => el('div', { class: 'meter-tick', style: `left:${t.at}%` }, el('span', {}, `${t.at}`)))),
        el('dl', { class: 'kv' },
          el('dt', {}, 'Voltage'), el('dd', {}, battery ? `${battery.voltage.toFixed(2)} V` : '—'),
          el('dt', {}, battery && battery.current > 0 ? 'Charging current' : 'Power draw'),
          el('dd', {}, battery ? `${Math.abs(battery.current).toFixed(2)} A` : '—'),
          el('dt', {}, 'Policy'), el('dd', {}, policyText(pct, status)))));
  }

  function policyText(pct, status) {
    if (pct === null || pct === undefined) return '—';
    if (status.state === 'CHARGING') return 'charging to 80%';
    if (pct <= 20) return 'return to dock';
    if (pct < 35) return 'no new deliveries';
    return 'normal';
  }

  function renderQueue(status) {
    const panel = $('#queue');
    const orders = status.orders || [];
    panel.replaceChildren(
      el('div', { class: 'panel-head' }, el('h2', {}, 'Queue'), el('span', { class: 'muted mono', style: 'font-size:12px' }, `${orders.length} waiting`)),
      orders.length
        ? el('ol', { class: 'list' }, orders.map((order, i) => el('li', {},
          el('span', { class: 'pos' }, i + 1),
          el('div', { style: 'min-width:0' },
            el('div', { class: 'title' }, label(order.location), order.interruptions ? el('span', { class: 'muted', style: 'font-weight:400' }, '  requeued') : null),
            el('div', { class: 'sub' }, `${clock(order.created_at)}  ${itemsText(order.items) || 'no items'}`)),
          el('button', { class: 'btn btn-sm btn-danger', type: 'button', onclick: (e) => cancelOrder(order, e.currentTarget) }, 'Cancel'))))
        : el('div', { class: 'empty' }, 'No orders waiting.'));
  }

  // ----- battery chart (single series, thresholds labelled directly) -----------------
  function renderChart(state) {
    const host = $('#battery-chart');
    const points = state.battery_history || [];
    const width = host.clientWidth;
    const key = `${points.length}:${points.length ? points[points.length - 1][0] : 0}:${width}:${document.documentElement.dataset.theme || ''}`;
    if (key === chartKey || !width) return;
    chartKey = key;
    const height = host.clientHeight;
    // Threshold labels live in a right margin, clear of the newest data.
    const m = { l: 36, r: width > 560 ? 150 : 8, t: 10, b: 24 };
    const now = state.server_time;
    const t0 = now - WINDOW_SEC;
    const x = (t) => m.l + ((t - t0) / WINDOW_SEC) * (width - m.l - m.r);
    const y = (p) => m.t + (1 - p / 100) * (height - m.t - m.b);
    const ns = 'http://www.w3.org/2000/svg';
    const svg = (tag, attrs = {}, text) => {
      const node = document.createElementNS(ns, tag);
      for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
      if (text !== undefined) node.textContent = text;
      return node;
    };
    const root = svg('svg', { viewBox: `0 0 ${width} ${height}`, 'aria-hidden': 'true' });
    const visible = points.filter((p) => p[0] >= t0 - 10);

    // charging periods as background bands
    let bandStart = null;
    visible.forEach((p, i) => {
      if (p[2] && bandStart === null) bandStart = p[0];
      const end = !p[2] || i === visible.length - 1;
      if (bandStart !== null && end) {
        const x1 = x(Math.max(bandStart, t0)); const x2 = x(p[0]);
        root.append(svg('rect', { x: x1, y: m.t, width: Math.max(1, x2 - x1), height: height - m.t - m.b, fill: 'var(--ok-soft)' }));
        if (x2 - x1 > 60) root.append(svg('text', { x: x1 + 6, y: m.t + 14, fill: 'var(--ok)', 'font-size': 11 }, 'Charging'));
        bandStart = null;
      }
    });

    for (const p of [0, 50, 100]) {
      root.append(svg('line', { x1: m.l, x2: width - m.r, y1: y(p), y2: y(p), stroke: 'var(--line)', 'stroke-width': 1 }));
      root.append(svg('text', { x: m.l - 8, y: y(p) + 4, 'text-anchor': 'end', fill: 'var(--faint)', 'font-size': 11, 'font-family': 'var(--mono)' }, `${p}%`));
    }
    for (const th of THRESHOLDS) {
      root.append(svg('line', { x1: m.l, x2: width - m.r, y1: y(th.at), y2: y(th.at), stroke: `var(--${th.tone === 'warn' ? 'warn-dot' : th.tone})`, 'stroke-width': 1, 'stroke-dasharray': '4 4' }));
      if (m.r > 8) root.append(svg('text', { x: width - m.r + 10, y: y(th.at) + 4, fill: 'var(--muted)', 'font-size': 11 }, `${th.at}%  ${th.text}`));
    }
    for (let k = 0; k <= 3; k += 1) {
      const t = t0 + (k * WINDOW_SEC) / 3;
      root.append(svg('text', { x: x(t), y: height - 6, 'text-anchor': k === 0 ? 'start' : k === 3 ? 'end' : 'middle', fill: 'var(--faint)', 'font-size': 11, 'font-family': 'var(--mono)' }, k === 3 ? 'now' : clock(t)));
    }

    if (visible.length > 1) {
      const line = visible.map((p, i) => `${i ? 'L' : 'M'}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join('');
      root.append(svg('path', { d: `${line}L${x(visible[visible.length - 1][0]).toFixed(1)},${y(0)}L${x(visible[0][0]).toFixed(1)},${y(0)}Z`, fill: 'var(--accent-soft)' }));
      root.append(svg('path', { d: line, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    }
    const last = visible[visible.length - 1];
    if (last) root.append(svg('circle', { cx: x(last[0]), cy: y(last[1]), r: 4, fill: 'var(--accent)', stroke: 'var(--bg)', 'stroke-width': 2 }));

    // hover: crosshair + tooltip on the nearest sample
    const cross = svg('line', { y1: m.t, y2: height - m.b, stroke: 'var(--line-strong)', 'stroke-width': 1, visibility: 'hidden' });
    const marker = svg('circle', { r: 4, fill: 'var(--accent)', stroke: 'var(--bg)', 'stroke-width': 2, visibility: 'hidden' });
    const hit = svg('rect', { x: m.l, y: 0, width: width - m.l - m.r, height, fill: 'transparent' });
    root.append(cross, marker, hit);
    const tip = el('div', { class: 'tip', hidden: true });
    hit.addEventListener('pointermove', (event) => {
      if (!visible.length) return;
      const box = host.getBoundingClientRect();
      const px = event.clientX - box.left;
      const nearest = visible.reduce((a, b) => (Math.abs(x(b[0]) - px) < Math.abs(x(a[0]) - px) ? b : a));
      const cx = x(nearest[0]); const cy = y(nearest[1]);
      cross.setAttribute('x1', cx); cross.setAttribute('x2', cx); cross.setAttribute('visibility', 'visible');
      marker.setAttribute('cx', cx); marker.setAttribute('cy', cy); marker.setAttribute('visibility', 'visible');
      tip.hidden = false;
      tip.style.left = `${Math.min(Math.max(cx, 70), width - 70)}px`; tip.style.top = `${cy - 10}px`;
      tip.replaceChildren(el('strong', {}, `${nearest[1].toFixed(1)}%`), `${clockSec(nearest[0])}, ${nearest[2] ? 'charging' : 'discharging'}`);
    });
    hit.addEventListener('pointerleave', () => { tip.hidden = true; cross.setAttribute('visibility', 'hidden'); marker.setAttribute('visibility', 'hidden'); });
    host.replaceChildren(root, tip);

    const first = visible[0]; const end = visible[visible.length - 1];
    $('#battery-note').textContent = first && end && end[0] - first[0] > 60
      ? `${(end[1] - first[1] >= 0 ? '+' : '')}${(end[1] - first[1]).toFixed(1)} points since ${clock(first[0])}` : 'Sampled every 5 seconds';
  }
  window.addEventListener('resize', () => { if (latest) renderChart(latest); });
  window.addEventListener('cstam-theme', () => { chartKey = ''; if (latest) renderChart(latest); });

  // ----- orders tab ------------------------------------------------------------------
  let historyLoading = false;
  async function loadHistory(force) {
    if ($('#orders').hidden && !force) return;
    if (historyLoading) return;
    historyLoading = true;
    try {
      const data = await api('/api/admin/history?limit=500', { pin });
      renderHistory(data.orders, data.total);
    } catch (error) {
      $('#history').replaceChildren(el('div', { class: 'empty' }, error.message));
    } finally { historyLoading = false; }
  }

  function renderHistory(orders, total) {
    const delivered = orders.filter((o) => o.status === 'delivered');
    const toTable = delivered.filter((o) => o.arrived_at).map((o) => o.arrived_at - o.created_at).sort((a, b) => a - b);
    const median = toTable.length ? toTable[Math.floor(toTable.length / 2)] : null;
    const confirmed = delivered.filter((o) => o.confirmed).length;
    const failed = orders.filter((o) => o.status === 'failed').length;
    const cancelled = orders.filter((o) => o.status === 'cancelled').length;
    const stat = (title, value, note) => el('div', { class: 'panel stat' },
      el('div', { class: 'label' }, title), el('div', { class: 'value' }, value), el('div', { class: 'note' }, note));
    $('#stats').replaceChildren(
      stat('Delivered', delivered.length, `of ${total} finished orders`),
      stat('Median time to table', median === null ? '—' : duration(median), 'from order to arrival'),
      stat('Confirmed by customer', delivered.length ? `${Math.round((100 * confirmed) / delivered.length)}%` : '—', 'the rest timed out at the table'),
      stat('Not delivered', failed + cancelled, `${failed} unreachable, ${cancelled} cancelled`));

    if (!orders.length) {
      $('#history').replaceChildren(el('div', { class: 'empty' }, 'No finished orders yet. They appear here as soon as the robot completes one.'));
      return;
    }
    $('#history').replaceChildren(el('table', {},
      el('thead', {}, el('tr', {}, ['Order', 'Table', 'Items', 'Status', 'Placed', 'Time to table', 'Total time'].map((h, i) =>
        el('th', { class: i >= 4 ? 'num' : '' }, h)))),
      el('tbody', {}, orders.map((o) => el('tr', {},
        el('td', { class: 'mono' }, o.id),
        el('td', {}, label(o.location)),
        el('td', { class: 'items' }, itemsText(o.items) || '—', o.note ? el('div', { class: 'faint' }, `“${o.note}”`) : null),
        el('td', {}, badgeFor(o.status), o.status === 'delivered' && !o.confirmed ? el('div', { class: 'faint', style: 'font-size:12px;margin-top:4px' }, 'not confirmed') : null,
          o.reason ? el('div', { class: 'faint', style: 'font-size:12px;margin-top:4px' }, o.reason) : null),
        el('td', { class: 'num' }, clock(o.created_at)),
        el('td', { class: 'num' }, o.arrived_at ? duration(o.arrived_at - o.created_at) : '—'),
        el('td', { class: 'num' }, o.finished_at ? duration(o.finished_at - o.created_at) : '—'))))));
  }

  // ----- system tab ----------------------------------------------------------------
  function renderSystem(state) {
    if ($('#system').hidden) return;
    const nodes = state.nodes || {};
    const names = Object.keys(nodes);
    const down = names.filter((n) => !nodes[n]);
    $('#nodes-note').textContent = names.length ? (down.length ? `${down.length} not running` : 'All running') : '';
    $('#nodes').replaceChildren(...names.map((name) => el('div', {},
      el('span', { class: 'name' }, name),
      el('span', { class: 'state' }, el('span', { class: `dot tone-${nodes[name] ? 'ok' : 'err'}` }), nodes[name] ? 'Running' : 'Not running'))));

    const ages = state.ages || {};
    $('#feeds').replaceChildren(...FEEDS.map(([key, title, staleAfter]) => {
      const age = ages[key];
      const stale = age === undefined || (staleAfter !== null && age > staleAfter);
      const text = age === undefined ? 'No data' : age < 1 ? 'Just now' : `${age < 60 ? age.toFixed(0) : Math.round(age / 60)} ${age < 60 ? 's' : 'min'} ago`;
      return el('div', {}, el('span', {}, title),
        el('span', { class: 'state' }, el('span', { class: `dot tone-${stale ? (age === undefined ? '' : 'warn') : 'ok'}` }), text));
    }));

    const safety = state.safety;
    $('#safety').replaceChildren(safety
      ? el('dl', { class: 'kv' },
        el('dt', {}, 'Closest pass'), el('dd', {}, safety.min_clearance_m === null ? '—' : `${safety.min_clearance_m.toFixed(2)} m`),
        el('dt', {}, 'Closest while moving'), el('dd', {}, safety.min_clearance_while_robot_moving_m === null ? '—' : `${safety.min_clearance_while_robot_moving_m.toFixed(2)} m`),
        el('dt', {}, 'Nearest person now'), el('dd', {}, safety.current_min_clearance_m === null ? '—' : `${safety.current_min_clearance_m.toFixed(2)} m`),
        el('dt', {}, 'Contacts'), el('dd', {}, `${safety.contacts} (${safety.robot_fault_contacts} robot’s fault)`),
        el('dt', {}, `Passes under ${safety.close_passes_under_m} m`), el('dd', {}, safety.close_passes),
        el('dt', {}, 'People tracked now'), el('dd', {}, (state.people || []).length))
      : el('p', { class: 'muted' }, 'No simulated people in this run. Launch with pedestrians:=true to measure clearances.'));

    const status = state.status || {};
    const rejection = status.last_rejection;
    $('#task').replaceChildren(el('dl', { class: 'kv' },
      el('dt', {}, 'State'), el('dd', {}, status.state || '—'),
      el('dt', {}, 'Stage'), el('dd', {}, status.current_stage || '—'),
      el('dt', {}, 'Wait at table'), el('dd', {}, status.confirmation_timeout_sec ? `${status.confirmation_timeout_sec} s` : 'off'),
      el('dt', {}, 'Unreachable orders'), el('dd', {}, (status.failed_orders || []).map(label).join(', ') || 'none'),
      el('dt', {}, 'Last rejected request'), el('dd', {}, rejection ? `${clock(rejection.at)} ${rejection.reason}` : 'none')));
    $('#task-message').textContent = status.message || '';
  }

  // ----- insights tab ------------------------------------------------------------------
  let range = 'today';
  let insights = null;
  for (const button of document.querySelectorAll('#range button')) {
    button.addEventListener('click', () => {
      range = button.dataset.range;
      for (const b of document.querySelectorAll('#range button')) b.setAttribute('aria-checked', String(b === button));
      loadInsights();
    });
  }

  async function loadInsights() {
    try {
      insights = await api(`/api/admin/analytics?range=${range}`, { pin });
      renderInsights(insights);
    } catch (error) {
      $('#insight-stats').replaceChildren(el('div', { class: 'empty' }, error.message));
    }
    if (latest) renderCounters((latest.status || {}).counters);
  }

  const money = (v, currency) => `${Number(v).toFixed(2)} ${currency}`;
  const pct = (v) => (v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`);

  function renderInsights(r) {
    const stat = (title, value, note) => el('div', { class: 'panel stat' },
      el('div', { class: 'label' }, title), el('div', { class: 'value' }, value), el('div', { class: 'note' }, note));
    const t = r.time_to_table;
    $('#insight-stats').replaceChildren(
      stat('Deliveries', r.delivered, r.success_rate === null ? 'no finished orders yet'
        : `${pct(r.success_rate)} delivered, ${r.failed} unreachable, ${r.cancelled} cancelled`),
      stat('Median time to table', t.median === null ? '—' : duration(t.median),
        t.p90 === null ? 'from order to arrival' : `90% within ${duration(t.p90)}`),
      stat('Revenue delivered', money(r.revenue, r.currency),
        r.average_ticket === null ? 'menu prices' : `${money(r.average_ticket, r.currency)} per order`),
      stat('Battery per delivery', r.battery_per_delivery === null ? '—' : `${r.battery_per_delivery}%`,
        r.deliveries_per_charge === null ? 'from start to finish of each order' : `about ${Math.floor(r.deliveries_per_charge)} deliveries per charge`));

    const hourly = r.range === 'today';
    $('#volume-title').textContent = hourly ? 'Deliveries per hour' : 'Deliveries per day';
    $('#volume-note').textContent = r.confirmed_rate === null ? '' : `${pct(r.confirmed_rate)} confirmed by the customer`;
    barChart($('#volume-chart'), r.volume, hourly);

    const list = (host, rows, nameOf, valueOf, empty) => {
      const top = Math.max(1, ...rows.map(valueOf));
      host.replaceChildren(...(rows.length ? rows.map((row) => el('div', { class: 'hbar' },
        el('span', { class: 'name', title: nameOf(row) }, nameOf(row)),
        el('span', { class: 'track' }, el('span', { class: 'fill', style: `display:block;width:${(100 * valueOf(row)) / top}%` })),
        el('span', { class: 'num' }, valueOf(row)))) : [el('p', { class: 'muted' }, empty)]));
    };
    list($('#top-items'), r.top_items, (i) => i.name, (i) => i.qty, 'Nothing delivered in this period.');
    list($('#top-tables'), r.tables, (i) => r.labels[i.location] || label(i.location), (i) => i.count, 'Nothing delivered in this period.');
  }

  function renderCounters(counters) {
    if (!counters) { $('#nav-counters').replaceChildren(el('p', { class: 'muted' }, 'No data from the task manager.')); return; }
    const failRate = counters.nav_goals ? counters.nav_failures / counters.nav_goals : null;
    $('#nav-counters').replaceChildren(el('dl', { class: 'kv' },
      el('dt', {}, 'Goals sent'), el('dd', {}, counters.nav_goals),
      el('dt', {}, 'Goals that failed'), el('dd', {}, `${counters.nav_failures}${failRate === null ? '' : ` (${pct(failRate)})`}`),
      el('dt', {}, 'Retries'), el('dd', {}, counters.nav_retries),
      el('dt', {}, 'Rerouted through the other terrace door'), el('dd', {}, counters.door_reroutes)));
  }

  // Single-series bar chart: thin bars, rounded tops, hover readout.
  function barChart(host, buckets, hourly) {
    const width = host.clientWidth; const height = host.clientHeight;
    if (!width) return;
    const m = { l: 28, r: 4, t: 8, b: 22 };
    const max = Math.max(1, ...buckets.map((b) => b.count));
    const top = max <= 4 ? max : Math.ceil(max / 2) * 2;
    const slot = (width - m.l - m.r) / buckets.length;
    const bar = Math.max(2, Math.min(28, slot - 2));
    const y = (v) => m.t + (1 - v / top) * (height - m.t - m.b);
    const ns = 'http://www.w3.org/2000/svg';
    const svg = (tag, attrs = {}, text) => {
      const node = document.createElementNS(ns, tag);
      for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
      if (text !== undefined) node.textContent = text;
      return node;
    };
    const root = svg('svg', { viewBox: `0 0 ${width} ${height}`, 'aria-hidden': 'true' });
    for (const v of [0, top / 2, top]) {
      if (v !== Math.round(v)) continue;
      root.append(svg('line', { x1: m.l, x2: width - m.r, y1: y(v), y2: y(v), stroke: 'var(--line)' }));
      root.append(svg('text', { x: m.l - 8, y: y(v) + 4, 'text-anchor': 'end', fill: 'var(--faint)', 'font-size': 11, 'font-family': 'var(--mono)' }, v));
    }
    const every = hourly ? 3 : Math.ceil(buckets.length / 10);
    const tip = el('div', { class: 'tip', hidden: true });
    buckets.forEach((b, i) => {
      const cx = m.l + slot * i + slot / 2;
      if (b.count) {
        const h = y(0) - y(b.count); const r = Math.min(4, bar / 2, h);
        const x = cx - bar / 2; const y0 = y(0);
        root.append(svg('path', { fill: 'var(--accent)', d: `M${x},${y0}V${y0 - h + r}Q${x},${y0 - h} ${x + r},${y0 - h}H${x + bar - r}Q${x + bar},${y0 - h} ${x + bar},${y0 - h + r}V${y0}Z` }));
      }
      if (i % every === 0) root.append(svg('text', { x: cx, y: height - 6, 'text-anchor': 'middle', fill: 'var(--faint)', 'font-size': 11, 'font-family': 'var(--mono)' }, hourly ? b.label.slice(0, 2) : b.label));
      const hit = svg('rect', { x: m.l + slot * i, y: 0, width: slot, height, fill: 'transparent' });
      hit.addEventListener('pointerenter', () => {
        tip.hidden = false;
        tip.style.left = `${Math.min(Math.max(cx, 70), width - 70)}px`; tip.style.top = `${y(b.count) - 8}px`;
        tip.replaceChildren(el('strong', {}, `${b.count} deliver${b.count === 1 ? 'y' : 'ies'}`), hourly ? `${b.label} to ${String(Number(b.label.slice(0, 2)) + 1).padStart(2, '0')}:00` : b.label);
      });
      hit.addEventListener('pointerleave', () => { tip.hidden = true; });
      root.append(hit);
    });
    host.setAttribute('aria-label', `${buckets.reduce((a, b) => a + b.count, 0)} deliveries, ${hourly ? 'by hour' : 'by day'}`);
    host.replaceChildren(root, tip);
  }
  window.addEventListener('resize', () => { if (insights && !$('#insights').hidden) barChart($('#volume-chart'), insights.volume, insights.range === 'today'); });

  // ----- maintenance tab ---------------------------------------------------------------
  const METRIC_FORMAT = {
    distance_m: (v) => (v < 1000 ? `${v.toFixed(0)} m` : `${(v / 1000).toFixed(v < 10000 ? 2 : 1)} km`),
    drive_s: (v) => (v < 3600 ? `${(v / 60).toFixed(0)} min` : `${(v / 3600).toFixed(1)} h`),
    operating_s: (v) => (v < 3600 ? `${(v / 60).toFixed(0)} min` : `${(v / 3600).toFixed(1)} h`),
    battery_cycles: (v) => `${v.toFixed(v < 10 ? 2 : 0)} cycles`,
  };
  const SERVICE_STATE = { ok: { text: 'OK', tone: 'ok' }, soon: { text: 'Due soon', tone: 'warn' }, overdue: { text: 'Overdue', tone: 'err' } };
  let maintenanceKey = '';

  function forecast(days) {
    if (days === null || days === undefined) return 'No recent use to forecast from';
    if (days < 1) return 'Due within a day at the current pace';
    if (days < 60) return `Due in about ${Math.round(days)} days`;
    if (days < 730) return `Due in about ${Math.round(days / 30)} months`;
    return `Due in about ${Math.round(days / 365)} years`;
  }

  function renderMaintenance(state) {
    if ($('#maintenance').hidden) return;
    const report = state.maintenance;
    if (!report) { $('#service-list').replaceChildren(el('li', { class: 'empty' }, 'Usage tracking is not running.')); return; }
    const key = JSON.stringify(report);
    if (key === maintenanceKey) return;   // keep buttons stable between identical updates
    maintenanceKey = key;
    const t = report.totals;
    const stat = (title, value, note) => el('div', { class: 'panel stat' },
      el('div', { class: 'label' }, title), el('div', { class: 'value' }, value), el('div', { class: 'note' }, note));
    $('#usage-stats').replaceChildren(
      stat('Distance driven', METRIC_FORMAT.distance_m(t.distance_m), 'wheel odometry'),
      stat('Driving time', METRIC_FORMAT.drive_s(t.drive_s), 'moving or turning'),
      stat('Operating time', METRIC_FORMAT.operating_s(t.operating_s), 'powered on'),
      stat('Battery cycles', t.battery_cycles.toFixed(2), 'full-charge equivalents'));
    $('#maintenance-since').textContent = `Lifetime usage since ${new Date(report.since * 1000).toLocaleDateString()}, measured from odometry and the battery.`;
    $('#service-list').replaceChildren(...report.items.map((item) => {
      const fmt = METRIC_FORMAT[item.metric];
      const s = SERVICE_STATE[item.state];
      const button = el('button', { class: 'btn btn-sm', type: 'button', onclick: (e) => markServiced(item, e.currentTarget) }, 'Mark serviced');
      return el('li', {},
        el('div', {}, el('div', { style: 'font-weight:500' }, item.name), el('div', { class: 'task' }, item.task)),
        el('div', { class: 'service-meter' },
          el('div', { class: 'line' }, el('span', {}, el('span', { class: 'mono' }, fmt(item.used)), ` of ${fmt(item.interval)}`), el('span', {}, `${Math.min(999, Math.round(item.fraction * 100))}%`)),
          el('div', { class: 'meter', role: 'meter', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': Math.min(100, item.fraction * 100), 'aria-label': `${item.name} usage` },
            el('div', { class: 'meter-fill', style: `width:${Math.min(100, Math.max(item.fraction * 100, item.used > 0 ? 1 : 0))}%;background:${item.state === 'overdue' ? 'var(--err)' : item.state === 'soon' ? 'var(--warn-dot)' : 'var(--ink)'}` })),
          el('div', { class: 'line' }, el('span', {}, forecast(item.due_in_days)),
            el('span', {}, item.last_service ? `serviced ${new Date(item.last_service * 1000).toLocaleDateString()}` : 'never serviced'))),
        el('div', { class: 'service-side' }, el('span', { class: `badge tone-${s.tone}` }, el('span', { class: 'dot' }), s.text), button));
    }));
  }

  async function markServiced(item, button) {
    if (button.dataset.armed !== 'yes') {
      button.dataset.armed = 'yes'; button.textContent = 'Confirm service';
      setTimeout(() => { button.dataset.armed = ''; button.textContent = 'Mark serviced'; }, 4000);
      return;
    }
    button.disabled = true;
    try {
      await api(`/api/admin/maintenance/${item.id}/service`, { method: 'POST', body: {}, pin });
      toast(`${item.name} marked as serviced`);
    } catch (error) { toast(error.message, 'err'); button.disabled = false; }
  }

  start();
})();
