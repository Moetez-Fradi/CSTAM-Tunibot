// CSTAM UI — shared helpers: API, live stream, map renderer, wording.
'use strict';

const CSTAM = (() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const el = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === undefined || value === null || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? '' : value);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  };

  const storage = {
    get(store, key) { try { return window[store].getItem(key); } catch { return null; } },
    set(store, key, value) {
      try { value === null ? window[store].removeItem(key) : window[store].setItem(key, value); } catch { /* private mode */ }
    },
  };

  // ----- API -------------------------------------------------------------
  class ApiError extends Error {
    constructor(status, message) { super(message); this.status = status; }
  }
  async function api(path, { method = 'GET', body, pin } = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (pin) headers['X-Admin-Pin'] = pin;
    let response;
    try {
      response = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch {
      throw new ApiError(0, 'No connection to the robot server. Check the Wi-Fi and try again.');
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new ApiError(response.status, data.error || `Request failed (${response.status})`);
    return data;
  }

  // EventSource reconnects on its own; we only report the connection state.
  function stream(url, onState, onConnection) {
    let source = null;
    let closed = false;
    const open = () => {
      source = new EventSource(url);
      source.addEventListener('state', (event) => { onConnection(true); onState(JSON.parse(event.data)); });
      source.onerror = () => {
        onConnection(false);
        if (source.readyState === EventSource.CLOSED && !closed) setTimeout(open, 3000);
      };
    };
    open();
    return { close() { closed = true; source && source.close(); } };
  }

  // ----- toasts ----------------------------------------------------------
  function toast(message, tone) {
    let host = $('.toast-host');
    if (!host) { host = el('div', { class: 'toast-host', role: 'status', 'aria-live': 'polite' }); document.body.append(host); }
    const node = el('div', { class: `toast${tone ? ` tone-${tone}` : ''}` }, message);
    host.append(node);
    setTimeout(() => node.remove(), 4000);
  }

  // ----- theme -----------------------------------------------------------
  function initTheme(button) {
    const saved = storage.get('localStorage', 'cstam.theme');
    if (saved) document.documentElement.dataset.theme = saved;
    if (!button) return;
    button.addEventListener('click', () => {
      const dark = getComputedStyle(document.documentElement).colorScheme === 'dark';
      const next = dark ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      storage.set('localStorage', 'cstam.theme', next);
      window.dispatchEvent(new Event('cstam-theme'));
    });
  }

  // ----- wording -----------------------------------------------------------
  const label = (name) => (name || '').split('_').map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(' ');

  function robotSummary(state, location) {
    const where = label(location);
    switch (state) {
      case 'IDLE': return { text: 'Ready at the dock', tone: 'ok' };
      case 'NAVIGATING_TO_PICKUP': return { text: `Collecting the order for ${where} from the kitchen`, tone: 'accent', live: true };
      case 'NAVIGATING_TO_CUSTOMER': return { text: `Delivering to ${where}`, tone: 'accent', live: true };
      case 'AWAITING_CONFIRMATION': return { text: `Waiting at ${where} for the customer`, tone: 'warn', live: true };
      case 'DELIVERY_COMPLETE': return { text: 'Delivery complete', tone: 'ok' };
      case 'RETURNING_TO_DOCK': return { text: 'Returning to the dock', tone: 'accent', live: true };
      case 'CHARGING': return { text: 'Charging at the dock', tone: 'ok', live: true };
      case 'BATTERY_DEPLETED': return { text: 'Battery empty, robot stopped', tone: 'err' };
      case 'ERROR': return { text: 'Needs attention', tone: 'err' };
      default: return { text: 'Connecting to the robot', tone: '' };
    }
  }

  const stateBadge = {
    IDLE: 'Ready', NAVIGATING_TO_PICKUP: 'To kitchen', NAVIGATING_TO_CUSTOMER: 'Delivering',
    AWAITING_CONFIRMATION: 'At table', DELIVERY_COMPLETE: 'Delivered', RETURNING_TO_DOCK: 'Returning',
    CHARGING: 'Charging', BATTERY_DEPLETED: 'Battery empty', ERROR: 'Error',
  };

  const orderStatus = {
    queued: { text: 'Queued', tone: '' },
    in_progress: { text: 'In progress', tone: 'accent' },
    awaiting_confirmation: { text: 'At table', tone: 'warn' },
    delivered: { text: 'Delivered', tone: 'ok' },
    cancelled: { text: 'Cancelled', tone: '' },
    failed: { text: 'Not delivered', tone: 'err' },
  };

  // Index into: queued, kitchen, on the way, at table, delivered.
  function orderStep(order) {
    if (!order) return -1;
    if (order.status === 'delivered') return 4;
    if (order.status === 'awaiting_confirmation') return 3;
    if (order.status === 'in_progress') return order.picked_up_at ? 2 : 1;
    return 0;
  }

  const clock = (t) => (t ? new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '');
  const clockSec = (t) => (t ? new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '');
  function duration(sec) {
    if (sec === null || sec === undefined || !isFinite(sec)) return '—';
    sec = Math.max(0, Math.round(sec));
    const m = Math.floor(sec / 60);
    return m ? `${m} min ${String(sec % 60).padStart(2, '0')} s` : `${sec} s`;
  }
  const money = (value, currency) => `${Number(value).toFixed(2)} ${currency}`;
  const itemsText = (items) => (items || []).map((i) => `${i.qty}× ${i.name}`).join(', ');

  // ----- map -------------------------------------------------------------
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const ROBOT_RADIUS = 0.27;   // m, the 0.54 m wide robot
  const PERSON_RADIUS = 0.25;  // m
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  class MapView {
    // floor: which floor's map to show; the robot, its route and the people
    // it tracks are drawn only while it is on that floor (update robotFloor).
    constructor(canvas, config, { focus = null, labels = true, padding = 16, floor = 1, floorName = null } = {}) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.config = config;
      this.focus = focus;
      this.labels = labels;
      this.padding = padding;
      this.floorName = floorName;
      this.data = { pose: null, plan: null, people: [], moving: false, robotFloor: 1 };
      this.shown = null;         // interpolated pose
      this.walls = null;
      this.ready = false;
      this.floor = null;
      if (!config.map) return;
      this.setFloor(floor);
      new ResizeObserver(() => this.resize()).observe(canvas);
      window.addEventListener('cstam-theme', () => { this._prepare(); this.draw(); });
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { this._prepare(); this.draw(); });
      this._tick = this._tick.bind(this);
      requestAnimationFrame(this._tick);
    }

    get floors() { return Object.keys(this.config.maps || { 1: this.config.map }).map(Number); }

    setFloor(floor) {
      if (floor === this.floor) return;
      this.floor = floor;
      this.meta = (this.config.maps || {})[floor] || this.config.map;
      const image = new Image();
      image.onload = () => {
        if (floor !== this.floor) return;   // switched again meanwhile
        this.image = image; this._prepare(); this.ready = true; this.resize();
      };
      image.src = `/api/map.png?floor=${floor}`;
    }

    // Recolour the occupancy image: walls in ink, known floor in the floor
    // colour, unknown cells transparent so the dot grid shows through.
    _prepare() {
      const { width, height } = this.image;
      const scratch = document.createElement('canvas');
      scratch.width = width; scratch.height = height;
      const sctx = scratch.getContext('2d');
      sctx.drawImage(this.image, 0, 0);
      const pixels = sctx.getImageData(0, 0, width, height);
      const wall = hexRgb(css('--wall'));
      const floor = hexRgb(css('--floor'));
      let x0 = width, y0 = height, x1 = 0, y1 = 0;
      for (let i = 0; i < width * height; i += 1) {
        const v = pixels.data[i * 4];
        const o = i * 4;
        let c = null;
        if (v < 100) c = wall; else if (v > 250) c = floor;
        if (c) {
          pixels.data[o] = c[0]; pixels.data[o + 1] = c[1]; pixels.data[o + 2] = c[2]; pixels.data[o + 3] = 255;
          const x = i % width; const y = (i / width) | 0;
          if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
        } else {
          pixels.data[o + 3] = 0;
        }
      }
      sctx.putImageData(pixels, 0, 0);
      this.walls = scratch;
      this.crop = { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
    }

    resize() {
      const rect = this.canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      this.canvas.width = Math.max(1, Math.round(rect.width * ratio));
      this.canvas.height = Math.max(1, Math.round(rect.height * ratio));
      this.ratio = ratio;
      this.draw();
    }

    update({ pose, plan, people, moving, robotFloor }) {
      if (robotFloor !== undefined && robotFloor !== null) this.data.robotFloor = robotFloor;
      if (pose !== undefined) this.data.pose = pose;
      if (plan !== undefined) this.data.plan = plan;
      if (people !== undefined) this.data.people = people || [];
      if (moving !== undefined) this.data.moving = moving;
      if (pose && !this.shown) this.shown = { ...pose };
      this.draw();
    }

    // world (map frame, m) -> canvas px. A tall map in a wide panel (or the
    // reverse) is turned 90° clockwise when that makes it markedly larger;
    // labels are drawn separately, so text stays upright.
    _transform() {
      const { width: cw, height: ch } = this.canvas;
      const pad = this.padding * this.ratio;
      const { w, h } = this.crop;
      const fit = (iw, ih) => Math.min((cw - 2 * pad) / iw, (ch - 2 * pad) / ih);
      const turned = fit(h, w) > 1.1 * fit(w, h);
      const scale = turned ? fit(h, w) : fit(w, h);
      const [vw, vh] = turned ? [h, w] : [w, h];
      const ox = (cw - vw * scale) / 2;
      const oy = (ch - vh * scale) / 2;
      const { resolution, origin, height } = this.meta;
      const pt = (x, y) => {
        const u = (x - origin[0]) / resolution - this.crop.x;
        const v = height - (y - origin[1]) / resolution - this.crop.y;
        return turned ? [ox + (h - v) * scale, oy + u * scale] : [ox + u * scale, oy + v * scale];
      };
      return {
        scale, ox, oy, pt, turned,
        m: (meters) => (meters / resolution) * scale,
        heading: (yaw) => -yaw + (turned ? Math.PI / 2 : 0),
        drawWalls: (ctx) => {
          ctx.save();
          if (turned) { ctx.translate(ox + h * scale, oy); ctx.rotate(Math.PI / 2); } else ctx.translate(ox, oy);
          ctx.drawImage(this.walls, this.crop.x, this.crop.y, w, h, 0, 0, w * scale, h * scale);
          ctx.restore();
        },
      };
    }

    _tick() {
      // Ease the drawn robot towards the latest pose (updates arrive ~4 Hz).
      const target = this.data.pose;
      if (target && this.shown) {
        const k = reducedMotion.matches ? 1 : 0.18;
        let dyaw = target.yaw - this.shown.yaw;
        dyaw = Math.atan2(Math.sin(dyaw), Math.cos(dyaw));
        const far = Math.hypot(target.x - this.shown.x, target.y - this.shown.y) > 0.002 || Math.abs(dyaw) > 0.002;
        if (far) {
          this.shown.x += (target.x - this.shown.x) * k;
          this.shown.y += (target.y - this.shown.y) * k;
          this.shown.yaw += dyaw * k;
        }
        if (far || (this.data.moving && !reducedMotion.matches)) this.draw();
      }
      requestAnimationFrame(this._tick);
    }

    draw() {
      if (!this.ready || !this.canvas.width) return;
      const { ctx } = this;
      const r = this.ratio;
      const t = this._transform();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

      // dot grid, one dot per metre
      ctx.fillStyle = css('--grid-dot');
      const step = Math.max(t.m(1), 10 * r);
      for (let x = t.ox % step; x < this.canvas.width; x += step) {
        for (let y = t.oy % step; y < this.canvas.height; y += step) ctx.fillRect(x, y, 1.5 * r, 1.5 * r);
      }

      ctx.imageSmoothingEnabled = t.scale < 2;
      t.drawWalls(ctx);

      const ink = css('--ink'); const muted = css('--muted'); const bg = css('--bg');
      const accent = css('--accent'); const line = css('--line-strong');
      ctx.font = `500 ${11 * r}px ${css('--mono') || 'monospace'}`;
      ctx.textBaseline = 'middle';

      const here = this.data.robotFloor === this.floor;
      const onThisFloor = (p) => (p.floor || 1) === this.floor;

      // floor name, when there is more than one
      if (this.floors.length > 1 && this.floorName) {
        ctx.font = `600 ${12 * r}px ${css('--sans') || 'sans-serif'}`;
        ctx.fillStyle = muted;
        ctx.fillText(this.floorName(this.floor), 10 * r, 14 * r);
        ctx.font = `500 ${11 * r}px ${css('--mono') || 'monospace'}`;
      }

      // terrace doors (floor 1)
      ctx.strokeStyle = muted; ctx.lineWidth = 2 * r; ctx.setLineDash([3 * r, 3 * r]);
      for (const door of this.floor === 1 ? this.config.doors || [] : []) {
        const mid = (door.inside_x + door.outside_x) / 2;
        ctx.beginPath(); ctx.moveTo(...t.pt(mid, door.y - 0.46)); ctx.lineTo(...t.pt(mid, door.y + 0.46)); ctx.stroke();
      }
      ctx.setLineDash([]);

      // delivery points
      // Label sides keep neighbours apart: tables stand in a column (a row
      // once the map is turned) with the terrace stops beside them, and the
      // kitchen sits just past the dock.
      const side = (p, name) => {
        const outer = p.zone === 'terrace' || name === 'Kitchen';
        if (t.turned) return outer ? 'above' : 'below';
        return p.zone === 'terrace' ? 'left' : 'right';
      };
      const pin = (p, name, highlight) => {
        const [x, y] = t.pt(p.x, p.y);
        const size = (highlight ? 9 : 6) * r;
        ctx.fillStyle = highlight ? accent : bg;
        ctx.strokeStyle = highlight ? accent : ink;
        ctx.lineWidth = 1.5 * r;
        roundRect(ctx, x - size / 2, y - size / 2, size, size, 2 * r);
        ctx.fill(); ctx.stroke();
        if (this.labels || highlight) {
          const text = name;
          const w = ctx.measureText(text).width + 8 * r;
          const gap = size / 2 + 4 * r;
          const where = side(p, name);
          const lx = where === 'left' ? x - gap - w : where === 'right' ? x + gap : x - w / 2;
          const ly = where === 'above' ? y - gap - 9 * r : where === 'below' ? y + gap + 9 * r : y;
          ctx.fillStyle = bg; ctx.strokeStyle = line; ctx.lineWidth = 1 * r;
          roundRect(ctx, lx, ly - 9 * r, w, 18 * r, 4 * r); ctx.fill(); ctx.stroke();
          ctx.fillStyle = highlight ? accent : ink;
          ctx.fillText(text, lx + 4 * r, ly + 0.5 * r);
        }
      };
      for (const p of this.config.locations || []) {
        if ((!this.labels && p.name !== this.focus) || !onThisFloor(p)) continue;
        pin(p, p.label, p.name === this.focus);
      }
      if (this.labels) {
        if (this.config.pickup && onThisFloor(this.config.pickup)) pin(this.config.pickup, 'Kitchen', false);
        if (this.config.dock && onThisFloor(this.config.dock)) pin(this.config.dock, 'Dock', false);
        const lift = this.config.elevator;
        if (lift) pin({ x: lift.x, y: lift.cabin_y, zone: 'room' }, 'Elevator', false);
      }

      // planned route
      const plan = this.data.plan;
      if (here && plan && plan.length > 1 && this.data.moving) {
        ctx.strokeStyle = accent; ctx.lineWidth = 2 * r; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
        ctx.beginPath();
        plan.forEach(([x, y], i) => (i ? ctx.lineTo(...t.pt(x, y)) : ctx.moveTo(...t.pt(x, y))));
        ctx.stroke();
        const [ex, ey] = plan[plan.length - 1];
        ctx.fillStyle = bg; ctx.beginPath(); ctx.arc(...t.pt(ex, ey), 4 * r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }

      // people (tracked by the robot's own sensors)
      for (const person of here ? this.data.people || [] : []) {
        const [x, y] = t.pt(person.x, person.y);
        if (person.moving) {
          ctx.strokeStyle = css('--person'); ctx.lineWidth = 1.5 * r;
          ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(...t.pt(person.x + person.vx, person.y + person.vy)); ctx.stroke();
        }
        ctx.fillStyle = css('--person'); ctx.strokeStyle = bg; ctx.lineWidth = 2 * r;
        ctx.beginPath(); ctx.arc(x, y, Math.max(t.m(PERSON_RADIUS), 4 * r), 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }

      // robot
      const pose = this.shown;
      if (pose && here) {
        const [x, y] = t.pt(pose.x, pose.y);
        const radius = Math.max(t.m(ROBOT_RADIUS), 7 * r);
        if (this.data.moving && !reducedMotion.matches) {
          const phase = (performance.now() % 1600) / 1600;
          ctx.strokeStyle = accent; ctx.globalAlpha = 0.5 * (1 - phase); ctx.lineWidth = 2 * r;
          ctx.beginPath(); ctx.arc(x, y, radius + phase * 14 * r, 0, Math.PI * 2); ctx.stroke();
          ctx.globalAlpha = 1;
        }
        ctx.fillStyle = accent; ctx.strokeStyle = bg; ctx.lineWidth = 2.5 * r;
        ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        // heading: canvas y grows downwards (and the view may be turned)
        const hx = Math.cos(t.heading(pose.yaw)); const hy = Math.sin(t.heading(pose.yaw));
        ctx.strokeStyle = bg; ctx.lineWidth = 2.5 * r; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + hx * radius * 0.75, y + hy * radius * 0.75); ctx.stroke();
      }
    }
  }

  function roundRect(ctx, x, y, w, h, radius) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.arcTo(x + w, y, x + w, y + h, radius);
    ctx.arcTo(x + w, y + h, x, y + h, radius);
    ctx.arcTo(x, y + h, x, y, radius);
    ctx.arcTo(x, y, x + w, y, radius);
    ctx.closePath();
  }

  function hexRgb(hex) {
    const h = hex.replace('#', '');
    const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
    return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16));
  }

  const MOVING_STATES = new Set(['NAVIGATING_TO_PICKUP', 'NAVIGATING_TO_CUSTOMER', 'RETURNING_TO_DOCK']);

  return {
    $, el, api, ApiError, stream, toast, initTheme, storage, label, robotSummary, stateBadge,
    orderStatus, orderStep, clock, clockSec, duration, money, itemsText, MapView, MOVING_STATES,
  };
})();
