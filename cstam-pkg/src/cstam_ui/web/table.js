// Customer page: /table/<location> — menu, order, live tracking.
// Wording comes from i18n.js (English, French, Arabic); the page re-renders
// in place when the guest switches language.
'use strict';
(() => {
  const { $, el, api, stream, toast, initTheme, storage, orderStep } = CSTAM;
  const { t, place, itemName } = I18N;
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
  let view = null;             // re-renders the current screen (language switch)

  initTheme($('#theme'));
  languagePicker($('#lang'));

  // ----- wording helpers ----------------------------------------------------------
  const money = (value) => t('currency', { amount: Number(value).toFixed(2) });
  const clock = (time) => (time ? new Date(time * 1000).toLocaleTimeString(`${I18N.lang()}-TN`,
    { hour: '2-digit', minute: '2-digit', numberingSystem: 'latn' }) : '');
  function duration(sec) {
    if (sec === null || sec === undefined || !isFinite(sec)) return '—';
    sec = Math.max(0, Math.round(sec));
    const m = Math.floor(sec / 60);
    return m ? `${m} ${t('min')} ${String(sec % 60).padStart(2, '0')} ${t('sec')}` : `${sec} ${t('sec')}`;
  }
  const menuItem = (name) => config.menu.find((m) => m.name === name);
  const category = (name) => ((config.categories || {})[name] || {})[I18N.lang()] || name;
  const failed = (error) => toast(I18N.server(error.message), 'err');

  function languagePicker(host) {
    const buttons = Object.entries(I18N.LANGS).map(([code, info]) => el('button', {
      type: 'button', class: 'btn btn-ghost', lang: code, title: info.name, 'aria-label': info.name,
      'aria-pressed': String(code === I18N.lang()), onclick: () => I18N.set(code),
    }, info.short));
    host.replaceChildren(...buttons);
    const sync = () => {
      host.setAttribute('aria-label', t('language'));
      buttons.forEach((b) => b.setAttribute('aria-pressed', String(b.lang === I18N.lang())));
      $('#theme').setAttribute('aria-label', t('theme'));
      $('#offline').textContent = t('offline');
    };
    sync();
    window.addEventListener('cstam-lang', () => { sync(); view && view(); });
  }

  async function start() {
    try {
      config = await api('/api/config');
    } catch (error) {
      app.replaceChildren(el('p', {}, I18N.server(error.message)));
      return;
    }
    const spot = config.locations.find((l) => l.name === table);
    if (!spot) { chooseTable(table); return; }
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

  function setTitle() {
    document.title = table && config.locations.some((l) => l.name === table)
      ? t('page_title', { place: place(table) }) : 'Tunibot';
  }

  // ----- choose a table ----------------------------------------------------
  function chooseTable(unknown) {
    view = () => chooseTable(unknown);
    setTitle();
    app.replaceChildren(
      el('div', { class: 'hello' },
        el('h1', {}, unknown ? t('unknown_table_title') : t('choose_title')),
        el('p', { class: 'muted' }, unknown ? t('unknown_table_text', { name: unknown }) : t('choose_text'))),
      el('nav', { class: 'tables', 'aria-label': t('tables') },
        config.locations.map((l) => el('a', { href: `/table/${l.name}` }, place(l.name),
          el('span', { class: 'muted', style: 'font-weight:400' },
            t(l.zone === 'terrace' ? 'zone_terrace' : 'zone_room'))))));
  }

  // ----- menu ----------------------------------------------------------------
  function showMenu(spot) {
    view = () => showMenu(spot);
    setTitle();
    live && live.close(); live = null; track = null;
    const categories = [...new Set(config.menu.map((m) => m.category))];
    const bar = el('div', { class: 'bar' });
    const noteField = el('textarea', {
      class: 'input', id: 'note', rows: 2, maxlength: 200, placeholder: t('note_placeholder'),
      oninput: (e) => { note = e.target.value; },
    });
    noteField.value = note;

    const rows = new Map();
    const renderRow = (item) => {
      const qty = cart[item.id] || 0;
      const name = itemName(item);
      const control = qty
        ? el('div', { class: 'stepper', role: 'group', 'aria-label': t('quantity', { item: name }) },
          el('button', { type: 'button', 'aria-label': t('remove_one', { item: name }), onclick: () => change(item, -1) }, '−'),
          el('output', { 'aria-live': 'polite' }, qty),
          el('button', { type: 'button', 'aria-label': t('add_one', { item: name }), disabled: qty >= 20, onclick: () => change(item, 1) }, '+'))
        : el('button', { type: 'button', class: 'btn add', onclick: () => change(item, 1) }, t('add'));
      rows.get(item.id).replaceChildren(
        el('div', {}, el('div', { class: 'item-name' }, name),
          el('div', { class: 'item-price' }, money(item.price))),
        control);
    };
    const renderBar = () => {
      const count = Object.values(cart).reduce((a, b) => a + b, 0);
      const total = config.menu.reduce((sum, m) => sum + (cart[m.id] || 0) * m.price, 0);
      bar.replaceChildren(el('div', { class: 'bar-inner' },
        el('button', { class: 'btn btn-primary btn-lg', type: 'button', disabled: !count, onclick: submit },
          el('span', {}, count ? t('send', { n: count, place: place(spot.name) }) : t('empty_cart')),
          count ? el('span', { class: 'mono' }, money(total)) : null)));
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
        failed(error);
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
        el('h1', {}, place(spot.name)),
        el('p', { class: 'muted' }, t(spot.zone === 'terrace' ? 'intro_terrace' : 'intro_room'))),
      voiceBox(spot, addHeard),
      categories.map((name) => el('section', { class: 'category', 'aria-label': category(name) },
        el('h2', {}, category(name)),
        config.menu.filter((m) => m.category === name).map((item) => {
          const row = el('div', { class: 'item' });
          rows.set(item.id, row);
          return row;
        }))),
      el('div', { class: 'field note' }, el('label', { for: 'note' }, t('note_label')), noteField),
      bar].flat());
    config.menu.forEach(renderRow);
    renderBar();
  }

  // ----- voice / typed order -----------------------------------------------------
  // Speech recognition only runs in a secure context (HTTPS or localhost);
  // elsewhere the same box takes a typed sentence. The parser understands
  // English and French, so Arabic pages dictate in French by default.
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const canListen = Boolean(Recognition) && window.isSecureContext;

  function voiceBox(spot, addHeard) {
    let lang = storage.get('localStorage', 'cstam.voice.lang') || (I18N.lang() === 'en' ? 'en' : 'fr');
    if (!['en', 'fr'].includes(lang)) lang = 'en';
    const example = () => (lang === 'fr' ? 'deux cafés, une citronnade' : 'two cappuccinos, a brik');
    const input = el('input', { class: 'input', id: 'voice-text', autocomplete: 'off', maxlength: 300,
      dir: 'auto', placeholder: example() });
    const result = el('p', { class: 'voice-result', 'aria-live': 'polite' });
    let listening = null;

    const understand = async (text) => {
      if (!text.trim()) return;
      result.className = 'voice-result muted';
      result.textContent = t('voice_reading');
      try {
        const heard = await api('/api/voice', { method: 'POST', body: { text } });
        if (!heard.items.length) {
          result.className = 'voice-result';
          result.textContent = t('voice_none', { text: heard.transcript });
          return;
        }
        addHeard(heard.items);
        input.value = '';
        const added = heard.items.map((i) => `${i.qty}× ${itemName(config.menu.find((m) => m.id === i.id))}`).join(', ');
        const other = heard.location && heard.location !== spot.name
          ? config.locations.find((l) => l.name === heard.location) : null;
        result.className = 'voice-result';
        result.replaceChildren(...[t('voice_added', { items: added }),
          other && el('span', {}, t('voice_other_before'),
            el('a', { href: `/table/${other.name}` }, place(other.name)),
            t('voice_other_after', { place: place(spot.name) }))].filter(Boolean));
      } catch (error) {
        result.className = 'voice-result';
        result.textContent = I18N.server(error.message);
      }
    };

    const mic = canListen ? el('button', {
      class: 'btn mic', type: 'button', 'aria-pressed': 'false', 'aria-label': t('voice_speak'),
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
        result.textContent = t({
          'not-allowed': 'mic_blocked', 'service-not-allowed': 'mic_blocked',
          network: 'mic_network', 'no-speech': 'mic_silence',
        }[event.error] || 'mic_stopped');
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
      result.textContent = t('voice_listening');
      recognition.start();
    }

    const langButton = el('button', { class: 'btn btn-ghost lang', type: 'button',
      'aria-label': t('voice_language'), title: t('voice_language') }, lang.toUpperCase());
    langButton.addEventListener('click', () => {
      lang = lang === 'en' ? 'fr' : 'en';
      storage.set('localStorage', 'cstam.voice.lang', lang);
      langButton.textContent = lang.toUpperCase();
      input.placeholder = example();
    });

    return el('section', { class: 'voice', 'aria-label': t('voice_section') },
      el('label', { for: 'voice-text' }, canListen ? t('voice_label_speak') : t('voice_label_type')),
      el('form', { class: 'voice-row', onsubmit: (e) => { e.preventDefault(); understand(input.value); } },
        mic, input, canListen ? langButton : null, el('button', { class: 'btn', type: 'submit' }, t('add'))),
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
    view = () => {
      if (!track) return;
      track.title = null;
      track.map.firstChild.setAttribute('aria-label', t('map'));
      track.steps.setAttribute('aria-label', t('progress'));
      setTitle();
      renderTracking();
    };
    setTitle();
    const canvas = el('canvas', { 'aria-label': t('map') });
    track = {
      id: orderId,
      head: el('div', { class: 'track-head' }),
      eta: el('div', { class: 'eta' }),
      map: el('div', { class: 'mini-map map-wrap' }, canvas),
      steps: el('ol', { class: 'steps', 'aria-label': t('progress') }),
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

  function renderTracking() {
    if (!track || !latest) return;
    const { order, queue_position: position, robot } = latest;
    const moving = CSTAM.MOVING_STATES.has(robot.state);
    track.view.update({ pose: robot.pose, plan: order && order.status === 'in_progress' ? latest.plan : null, moving });

    if (!order) {
      track.title = null;
      track.head.replaceChildren(el('h1', {}, t('lost_title')), el('p', { class: 'muted' }, t('lost_text')));
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
        el('div', {}, el('strong', { dir: 'ltr' }, duration(progress.eta_sec)), el('span', {}, t(toKitchen ? 'eta_kitchen' : 'eta_you'))),
        el('div', {}, el('strong', { dir: 'ltr' }, `${progress.distance_remaining_m.toFixed(1)} m`), el('span', {}, t('to_drive'))));
    } else if (order.status === 'awaiting_confirmation' && order.confirm_by) {
      const left = order.confirm_by - (Date.now() / 1000 + clockOffset);
      track.eta.replaceChildren(el('div', {},
        el('strong', { class: 'countdown' }, duration(left)), el('span', {}, t('before_leaving'))));
    } else {
      track.eta.replaceChildren();
    }

    const step = orderStep(order);
    const times = [order.created_at, order.started_at, order.picked_up_at, order.arrived_at, order.finished_at];
    const finishedBadly = order.status === 'failed' || order.status === 'cancelled';
    track.steps.replaceChildren(...t('steps').map((text, i) => {
      const state = finishedBadly ? (i === 0 ? 'done' : '') : i < step || step === 4 ? 'done' : i === step ? 'now' : '';
      return el('li', { class: `step ${state}`, 'aria-current': state === 'now' ? 'step' : null },
        el('span', { class: 'step-mark', 'aria-hidden': 'true' }),
        el('span', { class: 'step-label' }, text),
        el('span', { class: 'step-time' }, state === 'done' || state === 'now' ? clock(times[i]) : ''));
    }));

    const price = (name) => (menuItem(name) || { price: 0 }).price;
    const total = order.items.reduce((sum, i) => sum + i.qty * price(i.name), 0);
    track.receipt.replaceChildren(...[
      ...order.items.map((i) => el('div', { class: 'receipt-row' },
        el('span', {}, `${i.qty}× ${itemName(menuItem(i.name)) || i.name}`), el('span', {}, money(i.qty * price(i.name))))),
      order.note ? el('div', { class: 'receipt-row muted' }, el('span', { dir: 'auto' }, t('note', { note: order.note }))) : null,
      el('div', { class: 'receipt-row', style: 'border-top:1px solid var(--line);padding-top:8px;font-weight:500' },
        el('span', {}, t('total')), el('span', {}, money(total))),
      el('div', { class: 'receipt-row faint', style: 'font-size:12px' }, el('span', {}, t('order_id', { id: order.id })))].filter(Boolean));

    track.actions.replaceChildren(...actionsFor(order));
  }

  function headline(order, position, robot) {
    switch (order.status) {
      case 'queued': {
        const ahead = position - 1;
        const charging = robot.state === 'CHARGING' || robot.state === 'BATTERY_DEPLETED';
        const title = ahead > 0 ? t('ahead', { n: ahead }) : t('next');
        if (charging) return [title, t('charging')];
        if (order.interruptions) return [title, t('interrupted')];
        return [title, t('preparing')];
      }
      case 'in_progress':
        return order.picked_up_at ? [t('on_way'), t('keep_clear')] : [t('collecting'), t('at_hatch')];
      case 'awaiting_confirmation':
        return [t('arrived'), t('take_items')];
      case 'delivered':
        return [t('enjoy'), order.confirmed ? null : t('gone_back')];
      case 'cancelled':
        return [t('cancelled'), t('nothing_brought')];
      case 'failed':
        return [t('failed'), t('staff_brings')];
      default:
        return [t('received'), null];
    }
  }

  function actionsFor(order) {
    if (order.status === 'awaiting_confirmation') {
      return [el('button', { class: 'btn btn-primary btn-lg', type: 'button', onclick: confirm }, t('got_it'))];
    }
    if (order.status === 'queued') {
      return [el('button', { class: 'btn btn-lg btn-danger', type: 'button', onclick: cancel },
        cancelArmed ? t('cancel_again') : t('cancel'))];
    }
    if (order.finished_at) return [newOrderButton()];
    return [];
  }

  function newOrderButton() {
    return el('button', { class: 'btn btn-lg', type: 'button', onclick: () => {
      storage.set('localStorage', orderKey, null);
      showMenu(config.locations.find((l) => l.name === table));
    } }, t('order_more'));
  }

  async function confirm(event) {
    event.currentTarget.disabled = true;
    try {
      await api(`/api/orders/${track.id}/confirm`, { method: 'POST', body: {} });
    } catch (error) { failed(error); event.target.disabled = false; }
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
      toast(t('cancelled_toast'));
    } catch (error) { failed(error); }
  }

  // Countdown at the table ticks between server updates.
  setInterval(() => { if (latest && latest.order && latest.order.status === 'awaiting_confirmation') renderTracking(); }, 1000);

  if (!table) {
    api('/api/config').then((c) => { config = c; chooseTable(null); })
      .catch((error) => app.replaceChildren(el('p', {}, I18N.server(error.message))));
  } else {
    start();
  }
})();
