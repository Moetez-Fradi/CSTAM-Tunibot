// Customer page: /table/<location> — menu, order, live tracking.
'use strict';
(() => {
  const { $, el, api, stream, toast, initTheme, storage, label, orderStep, clock, duration, money } = CSTAM;
  const app = $('#app');
  const table = decodeURIComponent(location.pathname.split('/')[2] || '').toLowerCase();
  const orderKey = `cstam.order.${table}`;
  const RECENT_SEC = 15 * 60;   // keep showing a finished order this long

  let config = null;
  let cart = {};
  let note = '';
  let live = null;
  let track = null;            // DOM slots of the tracking view
  let latest = null;
  let clockOffset = 0;         // server_time - local time
  let cancelArmed = false;

  initTheme($('#theme'));

  async function start() {
    try {
      config = await api('/api/config');
    } catch (error) {
      app.replaceChildren(el('p', {}, error.message));
      return;
    }
    const spot = config.locations.find((l) => l.name === table);
    if (!spot) { chooseTable(table); return; }
    document.title = `Order to ${spot.label}`;
    const saved = storage.get('localStorage', orderKey);
    if (saved) {
      try {
        const { order } = await api(`/api/orders/${saved}`);
        const age = Date.now() / 1000 - (order.finished_at || Date.now() / 1000);
        if (!order.finished_at || age < RECENT_SEC) { showTracking(saved); return; }
      } catch { /* unknown now: start over */ }
      storage.set('localStorage', orderKey, null);
    }
    showMenu(spot);
  }

  // ----- choose a table ----------------------------------------------------
  function chooseTable(unknown) {
    app.replaceChildren(
      el('div', { class: 'hello' },
        el('h1', {}, unknown ? 'We can’t find that table' : 'Where are you sitting?'),
        el('p', { class: 'muted' }, unknown
          ? `There is no table called “${unknown}”. Pick yours below, or scan the code on your table again.`
          : 'Pick your table and the robot will bring your order there.')),
      el('nav', { class: 'tables', 'aria-label': 'Tables' },
        config.locations.map((l) => el('a', { href: `/table/${l.name}` }, l.label,
          el('span', { class: 'muted', style: 'font-weight:400' }, l.zone)))));
  }

  // ----- menu ----------------------------------------------------------------
  function showMenu(spot) {
    live && live.close(); live = null; track = null;
    const categories = [...new Set(config.menu.map((m) => m.category))];
    const bar = el('div', { class: 'bar' });
    const noteField = el('textarea', {
      class: 'input', id: 'note', rows: 2, maxlength: 200, placeholder: 'Allergies, no sugar, extra napkins…',
      oninput: (e) => { note = e.target.value; },
    });
    noteField.value = note;

    const rows = new Map();
    const renderRow = (item) => {
      const qty = cart[item.id] || 0;
      const control = qty
        ? el('div', { class: 'stepper', role: 'group', 'aria-label': `${item.name} quantity` },
          el('button', { type: 'button', 'aria-label': `Remove one ${item.name}`, onclick: () => change(item, -1) }, '−'),
          el('output', { 'aria-live': 'polite' }, qty),
          el('button', { type: 'button', 'aria-label': `Add one ${item.name}`, disabled: qty >= 20, onclick: () => change(item, 1) }, '+'))
        : el('button', { type: 'button', class: 'btn add', onclick: () => change(item, 1) }, 'Add');
      rows.get(item.id).replaceChildren(
        el('div', {}, el('div', { class: 'item-name' }, item.name),
          el('div', { class: 'item-price' }, money(item.price, config.currency))),
        control);
    };
    const renderBar = () => {
      const count = Object.values(cart).reduce((a, b) => a + b, 0);
      const total = config.menu.reduce((sum, m) => sum + (cart[m.id] || 0) * m.price, 0);
      bar.replaceChildren(el('div', { class: 'bar-inner' },
        el('button', { class: 'btn btn-primary btn-lg', type: 'button', disabled: !count, onclick: submit },
          el('span', {}, count ? `Send ${count} item${count > 1 ? 's' : ''} to ${spot.label}` : 'Add something to order'),
          count ? el('span', { class: 'mono' }, money(total, config.currency)) : null)));
    };
    const change = (item, delta) => {
      cart[item.id] = Math.max(0, Math.min(20, (cart[item.id] || 0) + delta));
      if (!cart[item.id]) delete cart[item.id];
      renderRow(item); renderBar();
    };

    const submit = async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const result = await api('/api/orders', { method: 'POST', body: {
          location: spot.name, note,
          items: Object.entries(cart).map(([id, qty]) => ({ id, qty })),
        } });
        storage.set('localStorage', orderKey, result.order.id);
        cart = {}; note = '';
        showTracking(result.order.id);
      } catch (error) {
        toast(error.message, 'err');
        button.disabled = false;
      }
    };

    const addHeard = (items) => {
      for (const { id, qty } of items) {
        cart[id] = Math.min(20, (cart[id] || 0) + qty);
        renderRow(config.menu.find((m) => m.id === id));
      }
      renderBar();
    };

    app.replaceChildren(...[
      el('section', { class: 'hello' },
        el('h1', {}, spot.label),
        el('p', { class: 'muted' }, `Choose what you’d like and the robot brings it to your table on the ${spot.zone === 'terrace' ? 'terrace' : 'dining room floor'}.`)),
      voiceBox(spot, addHeard),
      categories.map((category) => el('section', { class: 'category', 'aria-label': category },
        el('h2', {}, category),
        config.menu.filter((m) => m.category === category).map((item) => {
          const row = el('div', { class: 'item' });
          rows.set(item.id, row);
          return row;
        }))),
      el('div', { class: 'field note' }, el('label', { for: 'note' }, 'Note for the kitchen'), noteField),
      bar].flat());
    config.menu.forEach(renderRow);
    renderBar();
  }

  // ----- voice / typed order -----------------------------------------------------
  // Speech recognition only runs in a secure context (HTTPS or localhost);
  // elsewhere the same box takes a typed sentence.
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const canListen = Boolean(Recognition) && window.isSecureContext;

  function voiceBox(spot, addHeard) {
    let lang = storage.get('localStorage', 'cstam.voice.lang') || (navigator.language || 'en').slice(0, 2);
    if (!['en', 'fr'].includes(lang)) lang = 'en';
    const input = el('input', { class: 'input', id: 'voice-text', autocomplete: 'off', maxlength: 300,
      placeholder: lang === 'fr' ? 'deux cafés, une citronnade' : 'two cappuccinos, a brik' });
    const result = el('p', { class: 'voice-result', 'aria-live': 'polite' });
    let listening = null;

    const understand = async (text) => {
      if (!text.trim()) return;
      result.className = 'voice-result muted';
      result.textContent = 'Reading your order…';
      try {
        const heard = await api('/api/voice', { method: 'POST', body: { text } });
        if (!heard.items.length) {
          result.className = 'voice-result';
          result.textContent = `No menu item recognised in “${heard.transcript}”. Try “two espressos and a brik”.`;
          return;
        }
        addHeard(heard.items);
        input.value = '';
        const added = heard.items.map((i) => `${i.qty}× ${i.name}`).join(', ');
        const other = heard.location && heard.location !== spot.name
          ? config.locations.find((l) => l.name === heard.location) : null;
        result.className = 'voice-result';
        result.replaceChildren(...[`Added ${added}. Check the order below, then send it.`,
          other && el('span', {}, ' You mentioned ', el('a', { href: `/table/${other.name}` }, other.label),
            `; this page orders to ${spot.label}.`)].filter(Boolean));
      } catch (error) {
        result.className = 'voice-result';
        result.textContent = error.message;
      }
    };

    const mic = canListen ? el('button', {
      class: 'btn mic', type: 'button', 'aria-pressed': 'false', 'aria-label': 'Speak your order',
      onclick: () => (listening ? listening.stop() : listen()),
    }, micIcon()) : null;

    function listen() {
      const recognition = new Recognition();
      recognition.lang = lang === 'fr' ? 'fr-FR' : 'en-US';
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      let finalText = '';
      recognition.onresult = (event) => {
        const text = [...event.results].map((r) => r[0].transcript).join(' ');
        input.value = text;
        if (event.results[event.results.length - 1].isFinal) finalText = text;
      };
      recognition.onerror = (event) => {
        result.className = 'voice-result';
        result.textContent = {
          'not-allowed': 'Microphone access is blocked. Type your order instead.',
          'service-not-allowed': 'Microphone access is blocked. Type your order instead.',
          network: 'Voice needs an internet connection. Type your order instead.',
          'no-speech': 'I didn’t hear anything. Tap the microphone and speak.',
        }[event.error] || 'Voice input stopped. Type your order instead.';
      };
      recognition.onend = () => {
        listening = null;
        mic.setAttribute('aria-pressed', 'false');
        mic.classList.remove('listening');
        if (finalText) understand(finalText);
      };
      listening = recognition;
      mic.setAttribute('aria-pressed', 'true');
      mic.classList.add('listening');
      result.className = 'voice-result muted';
      result.textContent = lang === 'fr' ? 'J’écoute…' : 'Listening…';
      recognition.start();
    }

    const langButton = el('button', { class: 'btn btn-ghost lang', type: 'button',
      'aria-label': 'Voice language', title: 'Voice language' }, lang.toUpperCase());
    langButton.addEventListener('click', () => {
      lang = lang === 'en' ? 'fr' : 'en';
      storage.set('localStorage', 'cstam.voice.lang', lang);
      langButton.textContent = lang.toUpperCase();
      input.placeholder = lang === 'fr' ? 'deux cafés, une citronnade' : 'two cappuccinos, a brik';
    });

    return el('section', { class: 'voice', 'aria-label': 'Order in your own words' },
      el('label', { for: 'voice-text' }, canListen ? 'Say or type your order' : 'Type your order in your own words'),
      el('form', { class: 'voice-row', onsubmit: (e) => { e.preventDefault(); understand(input.value); } },
        mic, input, canListen ? langButton : null, el('button', { class: 'btn', type: 'submit' }, 'Add')),
      result);
  }

  function micIcon() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', '16'); svg.setAttribute('height', '16'); svg.setAttribute('viewBox', '0 0 16 16');
    svg.setAttribute('aria-hidden', 'true');
    svg.innerHTML = '<rect x="5.5" y="1.5" width="5" height="8" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.5"/>'
      + '<path d="M3 7.5a5 5 0 0 0 10 0M8 12.5v2" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>';
    return svg;
  }

  // ----- tracking --------------------------------------------------------------
  function showTracking(orderId) {
    const canvas = el('canvas', { 'aria-label': 'Map of the restaurant with the robot and your table' });
    track = {
      id: orderId,
      head: el('div', { class: 'track-head' }),
      eta: el('div', { class: 'eta' }),
      map: el('div', { class: 'mini-map map-wrap' }, canvas),
      steps: el('ol', { class: 'steps', 'aria-label': 'Order progress' }),
      receipt: el('div', { class: 'receipt' }),
      actions: el('div', { class: 'actions' }),
    };
    app.replaceChildren(track.head, track.eta, track.map,
      el('div', { class: 'panel', style: 'margin-bottom:20px' }, el('div', { class: 'panel-body' }, track.steps)),
      track.receipt, track.actions);
    track.view = new CSTAM.MapView(canvas, config, { focus: table, labels: false, padding: 12 });
    live && live.close();
    live = stream(`/api/events?order=${encodeURIComponent(orderId)}`, (state) => {
      latest = state;
      clockOffset = state.server_time - Date.now() / 1000;
      renderTracking();
    }, (ok) => { $('#offline').hidden = ok; });
  }

  const STEPS = ['Order received', 'Collecting from the kitchen', 'On the way to you', 'At your table', 'Delivered'];

  function renderTracking() {
    if (!track || !latest) return;
    const { order, queue_position: position, robot } = latest;
    const moving = CSTAM.MOVING_STATES.has(robot.state);
    track.view.update({ pose: robot.pose, plan: order && order.status === 'in_progress' ? latest.plan : null, moving });

    if (!order) {
      track.title = null;
      track.head.replaceChildren(el('h1', {}, 'We can’t find this order'),
        el('p', { class: 'muted' }, 'The robot was restarted and no longer knows it. Please order again or ask a member of staff.'));
      track.eta.replaceChildren(); track.steps.replaceChildren(); track.receipt.replaceChildren();
      track.actions.replaceChildren(newOrderButton());
      return;
    }

    const [title, detail] = headline(order, position, robot);
    // Rebuild only on change: the countdown re-renders every second and
    // must not restart the arrival animation.
    if (track.title !== title + detail) {
      track.title = title + detail;
      track.head.className = `track-head${order.status === 'awaiting_confirmation' ? ' arrived' : ''}`;
      track.head.replaceChildren(...[el('h1', {}, title), detail && el('p', { class: 'muted' }, detail)].filter(Boolean));
    }

    const progress = robot.progress;
    if (order.status === 'in_progress' && progress) {
      const toKitchen = progress.stage === 'pickup';
      track.eta.replaceChildren(
        el('div', {}, el('strong', {}, duration(progress.eta_sec)), el('span', {}, toKitchen ? 'until it reaches the kitchen' : 'until it reaches you')),
        el('div', {}, el('strong', {}, `${progress.distance_remaining_m.toFixed(1)} m`), el('span', {}, 'still to drive')));
    } else if (order.status === 'awaiting_confirmation' && order.confirm_by) {
      const left = order.confirm_by - (Date.now() / 1000 + clockOffset);
      track.eta.replaceChildren(el('div', {},
        el('strong', { class: 'countdown' }, duration(left)), el('span', {}, 'before the robot moves on')));
    } else {
      track.eta.replaceChildren();
    }

    const step = orderStep(order);
    const times = [order.created_at, order.started_at, order.picked_up_at, order.arrived_at, order.finished_at];
    const finishedBadly = order.status === 'failed' || order.status === 'cancelled';
    track.steps.replaceChildren(...STEPS.map((text, i) => {
      const state = finishedBadly ? (i === 0 ? 'done' : '') : i < step || step === 4 ? 'done' : i === step ? 'now' : '';
      return el('li', { class: `step ${state}`, 'aria-current': state === 'now' ? 'step' : null },
        el('span', { class: 'step-mark', 'aria-hidden': 'true' }),
        el('span', { class: 'step-label' }, text),
        el('span', { class: 'step-time' }, state === 'done' || state === 'now' ? clock(times[i]) : ''));
    }));

    const price = (name) => (config.menu.find((m) => m.name === name) || { price: 0 }).price;
    const total = order.items.reduce((sum, i) => sum + i.qty * price(i.name), 0);
    track.receipt.replaceChildren(...[
      ...order.items.map((i) => el('div', { class: 'receipt-row' },
        el('span', {}, `${i.qty}× ${i.name}`), el('span', {}, money(i.qty * price(i.name), config.currency)))),
      order.note ? el('div', { class: 'receipt-row muted' }, el('span', {}, `Note: ${order.note}`)) : null,
      el('div', { class: 'receipt-row', style: 'border-top:1px solid var(--line);padding-top:8px;font-weight:500' },
        el('span', {}, 'Total'), el('span', {}, money(total, config.currency))),
      el('div', { class: 'receipt-row faint', style: 'font-size:12px' }, el('span', {}, `Order ${order.id}`))].filter(Boolean));

    track.actions.replaceChildren(...actionsFor(order));
  }

  function headline(order, position, robot) {
    switch (order.status) {
      case 'queued': {
        const ahead = position - 1;
        const charging = robot.state === 'CHARGING' || robot.state === 'BATTERY_DEPLETED';
        const title = ahead > 0 ? `${ahead} order${ahead > 1 ? 's' : ''} ahead of yours` : 'Your order is next';
        if (charging) return [title, 'The robot is charging and sets off again at 80% battery.'];
        if (order.interruptions) return [title, 'The robot had to return to its dock and will bring your order first.'];
        return [title, 'The kitchen is preparing it. You can still cancel.'];
      }
      case 'in_progress':
        return order.picked_up_at
          ? ['Your order is on its way', 'Please keep the path to your table clear.']
          : ['The robot is collecting your order', 'It picks it up at the kitchen hatch.'];
      case 'awaiting_confirmation':
        return ['Your order has arrived', 'Take your items from the robot, then tap the button so it can go.'];
      case 'delivered':
        return ['Enjoy your meal', order.confirmed ? null : 'The robot has gone back to its dock.'];
      case 'cancelled':
        return ['Order cancelled', 'Nothing will be brought to your table.'];
      case 'failed':
        return ['The robot couldn’t reach your table', 'A member of staff will bring your order instead.'];
      default:
        return ['Order received', null];
    }
  }

  function actionsFor(order) {
    if (order.status === 'awaiting_confirmation') {
      return [el('button', { class: 'btn btn-primary btn-lg', type: 'button', onclick: confirm }, 'I’ve got my order')];
    }
    if (order.status === 'queued') {
      return [el('button', { class: 'btn btn-lg btn-danger', type: 'button', onclick: cancel },
        cancelArmed ? 'Tap again to cancel the order' : 'Cancel order')];
    }
    if (order.finished_at) return [newOrderButton()];
    return [];
  }

  function newOrderButton() {
    return el('button', { class: 'btn btn-lg', type: 'button', onclick: () => {
      storage.set('localStorage', orderKey, null);
      showMenu(config.locations.find((l) => l.name === table));
    } }, 'Order something else');
  }

  async function confirm(event) {
    event.currentTarget.disabled = true;
    try {
      await api(`/api/orders/${track.id}/confirm`, { method: 'POST', body: {} });
    } catch (error) { toast(error.message, 'err'); event.target.disabled = false; }
  }

  async function cancel() {
    if (!cancelArmed) {
      cancelArmed = true; renderTracking();
      setTimeout(() => { cancelArmed = false; renderTracking(); }, 4000);
      return;
    }
    cancelArmed = false;
    try {
      await api(`/api/orders/${track.id}/cancel`, { method: 'POST', body: {} });
      toast('Order cancelled');
    } catch (error) { toast(error.message, 'err'); }
  }

  // Countdown at the table ticks between server updates.
  setInterval(() => { if (latest && latest.order && latest.order.status === 'awaiting_confirmation') renderTracking(); }, 1000);

  if (!table) {
    api('/api/config').then((c) => { config = c; chooseTable(null); })
      .catch((error) => app.replaceChildren(el('p', {}, error.message)));
  } else {
    start();
  }
})();
