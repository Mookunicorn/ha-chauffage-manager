/* Chauffage Manager - carte Lovelace (type: custom:chauffage-manager-card) */
const MODES = [
  ["off", "Off", "#9e9e9e"], ["frost_protection", "Hors-gel", "#42a5f5"], ["eco", "Éco", "#26a69a"],
  ["comfort_minus_2", "Confort -2", "#ffca28"], ["comfort_minus_1", "Confort -1", "#ffa726"], ["comfort", "Confort", "#ef5350"],
];
const MODE = Object.fromEntries(MODES.map((m) => [m[0], { label: m[1], color: m[2] }]));
const PILOT = { Off: "off", FrostProtection: "frost_protection", Eco: "eco", ComfortMinus2: "comfort_minus_2", ComfortMinus1: "comfort_minus_1", Comfort: "comfort" };
const DAYS = ["L", "M", "M", "J", "V", "S", "D"];
const TABS = { rooms: "Pièces", schedules: "Plannings", absence: "Absence", config: "Configuration" };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const toMin = (t) => { const [h, m] = t.split(":"); return +h * 60 + +m; };

function slotAt(slots, weekday, minute) {
  for (let back = 0; back < 8; back++) {
    const day = (((weekday - back) % 7) + 7) % 7;
    let best = null;
    for (const s of slots) {
      if (!s.days.includes(day)) continue;
      const st = toMin(s.time || "00:00");
      if (back === 0 && st > minute) continue;
      if (!best || st > toMin(best.time)) best = s;
    }
    if (best) return best;
  }
  return null;
}

function timeline(sched) {
  const slots = sched.slots.filter((s) => s.time);
  const rows = [0, 1, 2, 3, 4, 5, 6].map((d) => {
    const pts = [...new Set([0, ...slots.filter((s) => s.days.includes(d)).map((s) => toMin(s.time))])].sort((a, b) => a - b);
    const segs = pts.map((p, i) => {
      const end = i + 1 < pts.length ? pts[i + 1] : 1440;
      const s = slotAt(slots, d, p);
      const c = s ? MODE[s.mode].color : "transparent";
      return `<i style="width:${(end - p) / 14.4}%;background:${c}" title="${s ? MODE[s.mode].label : ""}"></i>`;
    }).join("");
    return `<div class="tr"><b>${DAYS[d]}</b><div class="bar">${segs}</div></div>`;
  }).join("");
  const legend = MODES.map((m) => `<span><i style="background:${m[2]}"></i>${m[1]}</span>`).join("");
  return `<div class="tl">${rows}<div class="legend">${legend}</div></div>`;
}

const CSS = `
:host{display:block}
ha-card{padding:12px}
.tabs{display:flex;gap:4px;margin-bottom:12px;border-bottom:1px solid var(--divider-color)}
.tabs button{background:none;border:none;padding:8px 12px;cursor:pointer;color:var(--secondary-text-color);font:inherit;border-bottom:2px solid transparent}
.tabs button.on{color:var(--primary-color);border-bottom-color:var(--primary-color)}
.title{font-size:1.2em;font-weight:500;margin-bottom:8px}
.row{padding:10px 0;border-bottom:1px solid var(--divider-color)}
.row:last-child{border-bottom:none}
.head{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.name{font-weight:500;flex:1;min-width:100px}
.name small{display:block;font-weight:400;color:var(--secondary-text-color)}
.temp{color:var(--secondary-text-color)}
.badge{padding:2px 8px;border-radius:10px;color:#fff;font-size:.8em}
.seg{display:flex;border:1px solid var(--divider-color);border-radius:8px;overflow:hidden}
.seg button{border:none;background:none;padding:4px 10px;cursor:pointer;color:var(--primary-text-color);font:inherit}
.seg button.on{background:var(--primary-color);color:var(--text-primary-color,#fff)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;align-items:center}
.chip{border:1px solid var(--c);background:none;color:var(--primary-text-color);border-radius:14px;padding:4px 10px;cursor:pointer;font:inherit}
.chip.on{background:var(--c);color:#fff}
.step{display:flex;align-items:center;gap:6px;margin-left:8px}
.step button,.btn{border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);border-radius:8px;padding:4px 10px;cursor:pointer;font:inherit}
.btn.primary{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:var(--primary-color)}
.btn.danger{color:var(--error-color)}
.bar{display:flex;height:10px;flex:1;border-radius:3px;overflow:hidden;background:var(--divider-color)}
.bar i{display:block;height:100%}
.tl .tr{display:flex;align-items:center;gap:6px;margin:2px 0}
.tl b{width:12px;font-size:.75em;color:var(--secondary-text-color)}
.legend{display:flex;flex-wrap:wrap;gap:8px;font-size:.75em;color:var(--secondary-text-color);margin-top:6px}
.legend i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:3px}
.f{display:flex;flex-direction:column;gap:3px;margin:8px 0;font-size:.9em;color:var(--secondary-text-color)}
input,select{font:inherit;padding:6px;border-radius:6px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color)}
.slot{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 0;border-bottom:1px dashed var(--divider-color)}
.days{display:flex;gap:2px}
.days button{width:26px;height:26px;border-radius:50%;border:1px solid var(--divider-color);background:none;cursor:pointer;color:var(--primary-text-color);font:inherit;font-size:.8em;padding:0}
.days button.on{background:var(--primary-color);color:#fff;border-color:var(--primary-color)}
.actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.check{display:flex;align-items:center;gap:8px;margin:4px 0;color:var(--primary-text-color)}
.err{background:var(--error-color);color:#fff;padding:6px 10px;border-radius:6px;margin-bottom:8px}
.info{background:var(--primary-color);color:#fff;padding:6px 10px;border-radius:6px;margin-bottom:8px}
.muted{color:var(--secondary-text-color)}
.li{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--divider-color)}
.li .name{flex:1}
`;

class ChauffageManagerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null; this._edit = null; this._abs = null; this._absDirty = false;
    this._temps = {}; this._error = ""; this._sig = ""; this._tab = null;
    const r = this.shadowRoot;
    r.addEventListener("click", (e) => this._click(e));
    r.addEventListener("change", (e) => this._change(e));
    r.addEventListener("input", (e) => this._change(e));
  }
  setConfig(config) {
    this._config = { tabs: ["rooms", "schedules", "absence", "config"], ...config };
    if (!this._tab || !this._config.tabs.includes(this._tab)) this._tab = this._config.tabs[0];
    this._render();
  }
  getCardSize() { return 6; }
  getGridOptions() { return { columns: 12, min_columns: 6 }; }
  static getStubConfig() { return {}; }
  connectedCallback() { if (this._hass) { this._subscribe(); this._load(); } }
  disconnectedCallback() { if (this._unsub) { this._unsub(); this._unsub = null; } }
  set hass(hass) {
    this._hass = hass;
    if (!this._loaded) { this._loaded = true; this._load(); }
    this._subscribe();
    const sig = this._liveSig();
    if (sig !== this._sig) { this._sig = sig; if (this._tab === "rooms" && !this._edit) this._render(); }
  }
  _subscribe() {
    if (this._unsub || this._subbing || !this._hass) return;
    this._subbing = true;
    this._hass.connection.subscribeEvents(() => this._load(), "chauffage_manager_updated")
      .then((u) => { this._subbing = false; if (this.isConnected) this._unsub = u; else u(); })
      .catch(() => { this._subbing = false; });
  }
  async _load() {
    try {
      this._data = await this._hass.callWS({ type: "chauffage_manager/get" });
      if (!this._absDirty) this._abs = JSON.parse(JSON.stringify(this._data.absence));
      this._error = "";
    } catch (e) { this._error = e.message || "Intégration non disponible"; }
    this._render();
  }
  _liveSig() {
    if (!this._data) return "";
    return this._data.heaters.map((h) => [h.entity, h.climate].map((id) => {
      const s = id && this._hass.states[id];
      return s ? `${s.state}|${s.attributes.temperature}|${s.attributes.current_temperature}` : "";
    }).join(",")).join(";");
  }
  _admin() { return !!this._hass?.user?.is_admin; }
  _toast(msg) {
    this._error = String(msg?.message || msg);
    this._render();
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { this._error = ""; this._render(); }, 5000);
  }

  /* ---------- état des chauffages ---------- */
  _hstate(h) {
    const s = this._hass.states[h.entity];
    if (!s) return {};
    if (h.type === "pilot_wire") {
      const c = h.climate && this._hass.states[h.climate];
      return { mode: PILOT[s.state], cur: c?.attributes.current_temperature };
    }
    return { mode: s.state === "off" ? "off" : "comfort", temp: s.attributes.temperature, cur: s.attributes.current_temperature };
  }
  _info(t) {
    const hs = t.members.map((id) => this._data.heaters.find((h) => h.id === id)).filter(Boolean);
    const sts = hs.map((h) => ({ h, ...this._hstate(h) }));
    const modes = sts.map((s) => s.mode).filter(Boolean);
    const curs = sts.map((s) => Number(s.cur)).filter((v) => !isNaN(v) && v !== 0);
    return {
      hs, mode: modes[0], mixed: new Set(modes).size > 1,
      cur: curs.length ? curs.reduce((a, b) => a + b) / curs.length : null,
      thermo: sts.find((s) => s.h.type === "thermostat"),
    };
  }
  _tempOf(t) {
    const th = this._info(t).thermo;
    return this._temps[t.id] ?? (th && Number(th.temp) > 0 ? Number(th.temp) : 19);
  }

  /* ---------- rendu ---------- */
  _render() {
    if (!this._config) return;
    const admin = this._admin();
    let tabs = this._config.tabs.filter((t) => admin || t !== "config");
    if (!tabs.includes(this._tab)) this._tab = tabs[0];
    const bar = tabs.length > 1 ? `<div class="tabs">${tabs.map((t) => `<button data-a="tab" data-v="${t}" class="${t === this._tab ? "on" : ""}">${TABS[t]}</button>`).join("")}</div>` : "";
    const body = !this._data ? `<div class="muted">${this._error ? "" : "Chargement…"}</div>` : this[`_v_${this._tab}`]();
    this.shadowRoot.innerHTML = `<style>${CSS}</style><ha-card>${this._config.title ? `<div class="title">${esc(this._config.title)}</div>` : ""}${bar}${this._error ? `<div class="err">${esc(this._error)}</div>` : ""}${body}</ha-card>`;
  }

  _v_rooms() {
    const d = this._data;
    if (!d.targets.length) return `<div class="muted">Aucun chauffage configuré. Ajoutez-en dans l'onglet Configuration.</div>`;
    const admin = this._admin();
    const rows = d.targets.map((t) => {
      const i = this._info(t);
      const m = i.mode && MODE[i.mode];
      const sub = t.kind === "group" ? `<small>${i.hs.map((h) => esc(h.name)).join(" + ")}</small>` : "";
      let ctl;
      if (t.control === "manual") {
        const chips = MODES.map((x) => `<button class="chip ${i.mode === x[0] ? "on" : ""}" style="--c:${x[2]}" data-a="mode" data-t="${t.id}" data-v="${x[0]}">${x[1]}</button>`).join("");
        const step = i.thermo ? `<span class="step"><button data-a="temp" data-t="${t.id}" data-d="-0.5">−</button><b>${this._tempOf(t).toFixed(1)}°C</b><button data-a="temp" data-t="${t.id}" data-d="0.5">+</button></span>` : "";
        ctl = `<div class="chips">${chips}${step}</div>`;
      } else {
        const opts = `<option value="">— Aucun planning —</option>` + d.schedules.map((s) => `<option value="${s.id}" ${s.id === t.schedule_id ? "selected" : ""}>${esc(s.name)}</option>`).join("");
        ctl = `<div class="chips"><span class="muted">Planning :</span><select data-a="sched" data-t="${t.id}" data-k="${t.kind}" ${admin ? "" : "disabled"}>${opts}</select></div>`;
      }
      return `<div class="row"><div class="head"><div class="name">${esc(t.name)}${sub}</div>
        ${i.cur != null ? `<span class="temp">${i.cur.toFixed(1)}°C</span>` : ""}
        ${m ? `<span class="badge" style="background:${m.color}">${m.label}${i.mixed ? "…" : ""}</span>` : ""}
        <div class="seg"><button data-a="control" data-t="${t.id}" data-v="auto" class="${t.control === "auto" ? "on" : ""}">Auto</button><button data-a="control" data-t="${t.id}" data-v="manual" class="${t.control === "manual" ? "on" : ""}">Manuel</button></div></div>${ctl}</div>`;
    }).join("");
    const banner = d.absence.active ? `<div class="info">Mode absence actif</div>` : "";
    return `${banner}${rows}<div class="actions"><button class="btn" data-a="alloff">Tout éteindre</button></div>`;
  }

  _v_schedules() {
    const admin = this._admin();
    const e = this._edit;
    if (e && e.kind === "schedule") {
      const slots = e.slots.map((s, i) => `<div class="slot"><div class="days">${DAYS.map((l, d) => `<button data-a="day" data-i="${i}" data-d="${d}" class="${s.days.includes(d) ? "on" : ""}">${l}</button>`).join("")}</div>
        <input type="time" data-f="time" data-i="${i}" value="${esc(s.time)}">
        <select data-f="mode" data-i="${i}">${MODES.map((m) => `<option value="${m[0]}" ${s.mode === m[0] ? "selected" : ""}>${m[1]}</option>`).join("")}</select>
        <input type="number" step="0.5" min="5" max="30" style="width:70px" placeholder="°C" title="Température (thermostat)" data-f="temperature" data-i="${i}" value="${s.temperature ?? ""}">
        <button class="btn danger" data-a="delslot" data-i="${i}">✕</button></div>`).join("");
      return `<label class="f"><span>Nom du planning</span><input data-f="name" value="${esc(e.name)}"></label>
        <div class="muted" style="font-size:.85em">Chaque créneau s'applique à partir de son heure jusqu'au suivant. La température ne concerne que les thermostats.</div>${slots}
        <div class="actions"><button class="btn" data-a="addslot">+ Créneau</button></div>
        <div id="pv" style="margin-top:12px">${timeline(e)}</div>
        <div class="actions"><button class="btn primary" data-a="save">Enregistrer</button><button class="btn" data-a="cancel">Annuler</button></div>`;
    }
    const list = this._data.schedules.map((s) => {
      const users = this._data.targets.filter((t) => t.schedule_id === s.id).map((t) => esc(t.name)).join(", ");
      return `<div class="row"><div class="head"><div class="name">${esc(s.name)}<small>${users ? "Utilisé par : " + users : "Non assigné"}</small></div>
        ${admin ? `<button class="btn" data-a="edit" data-k="schedule" data-id="${s.id}">Modifier</button><button class="btn danger" data-a="del" data-k="schedule" data-id="${s.id}">Supprimer</button>` : ""}</div>${timeline(s)}</div>`;
    }).join("") || `<div class="muted">Aucun planning.</div>`;
    return `${list}${admin ? `<div class="actions"><button class="btn primary" data-a="new" data-v="schedule">+ Nouveau planning</button></div>` : ""}
      <div class="muted" style="margin-top:8px;font-size:.85em">L'assignation d'un planning se fait dans l'onglet Pièces (mode Auto).</div>`;
  }

  _v_absence() {
    const a = this._abs, admin = this._admin(), dis = admin ? "" : "disabled";
    const persons = Object.keys(this._hass.states).filter((id) => id.startsWith("person.") || a.persons.includes(id)).sort();
    const checks = persons.map((id) => `<label class="check"><input type="checkbox" ${dis} data-scope="abs" data-f="person" data-v="${id}" ${a.persons.includes(id) ? "checked" : ""}>${esc(this._hass.states[id]?.attributes.friendly_name || id)}</label>`).join("");
    const modeOpts = MODES.map((m) => `<option value="${m[0]}" ${a.mode === m[0] ? "selected" : ""}>${m[1]}</option>`).join("");
    const status = this._data.absence.active ? `<div class="info">Absence en cours</div>` : `<div class="muted">Présence détectée (absence = plus aucune des personnes cochées à la maison).</div>`;
    return `${status}<div class="f"><span>Personnes</span>${checks}</div>
      <label class="f"><span>Mode du chauffage en absence</span><select ${dis} data-scope="abs" data-f="mode">${modeOpts}</select></label>
      <label class="f"><span>Programmation en absence</span><select ${dis} data-scope="abs" data-f="control"><option value="manual" ${a.control === "manual" ? "selected" : ""}>Manuel (applique le mode ci-dessus)</option><option value="auto" ${a.control === "auto" ? "selected" : ""}>Automatique (suit le planning)</option></select></label>
      <label class="check"><input type="checkbox" ${dis} data-scope="abs" data-f="restore" ${a.restore ? "checked" : ""}>Restaurer l'état au retour</label>
      ${admin ? `<div class="actions"><button class="btn primary" data-a="abs-save">Enregistrer</button></div>` : ""}`;
  }

  _opts(domain, value, filter) {
    let ids = Object.keys(this._hass.states).filter((id) => id.startsWith(domain + "."));
    if (filter) { const f = ids.filter((id) => filter(this._hass.states[id])); if (f.length) ids = f; }
    if (value && !ids.includes(value)) ids.push(value);
    ids.sort();
    return ids.map((id) => `<option value="${id}" ${id === value ? "selected" : ""}>${esc(this._hass.states[id]?.attributes.friendly_name || id)} — ${id}</option>`).join("");
  }

  _v_config() {
    const e = this._edit;
    if (e && e.kind === "heater") {
      const pilot = e.type === "pilot_wire";
      const opts = (o) => `<option value="">—</option>${o}`;
      return `<div class="title">${e.id ? "Modifier" : "Nouveau"} chauffage</div>
        <label class="f"><span>Nom</span><input data-f="name" value="${esc(e.name)}"></label>
        <label class="f"><span>Type</span><select data-f="type"><option value="pilot_wire" ${pilot ? "selected" : ""}>Fil pilote (select)</option><option value="thermostat" ${pilot ? "" : "selected"}>Thermostat (climate)</option></select></label>
        <label class="f"><span>${pilot ? "Entité select du fil pilote" : "Entité climate"}</span><select data-f="entity">${opts(pilot ? this._opts("select", e.entity, (s) => (s.attributes.options || []).some((o) => o in PILOT)) : this._opts("climate", e.entity))}</select></label>
        ${pilot ? `<label class="f"><span>Entité climate (température mesurée, optionnel)</span><select data-f="climate">${opts(this._opts("climate", e.climate))}</select></label>`
          : `<label class="f"><span>Température en absence (°C)</span><input type="number" step="0.5" data-f="absence_temperature" value="${e.absence_temperature}"></label>`}
        <div class="actions"><button class="btn primary" data-a="save">Enregistrer</button><button class="btn" data-a="cancel">Annuler</button></div>`;
    }
    if (e && e.kind === "group") {
      const checks = this._data.heaters.map((h) => `<label class="check"><input type="checkbox" data-f="member" data-v="${h.id}" ${e.members.includes(h.id) ? "checked" : ""}>${esc(h.name)}</label>`).join("") || `<span class="muted">Créez d'abord des chauffages.</span>`;
      return `<div class="title">${e.id ? "Modifier" : "Nouveau"} groupe</div>
        <label class="f"><span>Nom</span><input data-f="name" value="${esc(e.name)}"></label>
        <div class="f"><span>Chauffages synchronisés (un chauffage appartient à un seul groupe)</span>${checks}</div>
        <div class="actions"><button class="btn primary" data-a="save">Enregistrer</button><button class="btn" data-a="cancel">Annuler</button></div>`;
    }
    const row = (k, x, sub) => `<div class="li"><div class="name">${esc(x.name)}<small>${sub}</small></div><button class="btn" data-a="edit" data-k="${k}" data-id="${x.id}">Modifier</button><button class="btn danger" data-a="del" data-k="${k}" data-id="${x.id}">Supprimer</button></div>`;
    const hs = this._data.heaters.map((h) => row("heater", h, `${h.type === "pilot_wire" ? "Fil pilote" : "Thermostat"} · ${esc(h.entity)}`)).join("") || `<div class="muted">Aucun chauffage.</div>`;
    const gs = this._data.groups.map((g) => row("group", g, g.members.map((m) => esc(this._data.heaters.find((h) => h.id === m)?.name || m)).join(" + "))).join("") || `<div class="muted">Aucun groupe.</div>`;
    return `<div class="title">Chauffages</div>${hs}<div class="actions"><button class="btn primary" data-a="new" data-v="heater">+ Chauffage</button></div>
      <div class="title" style="margin-top:16px">Groupes</div>${gs}<div class="actions"><button class="btn primary" data-a="new" data-v="group">+ Groupe</button></div>`;
  }

  /* ---------- interactions ---------- */
  _blank(kind) {
    return {
      schedule: { kind, id: null, name: "", slots: [{ days: [0, 1, 2, 3, 4], time: "06:30", mode: "comfort", temperature: 19 }, { days: [0, 1, 2, 3, 4], time: "22:00", mode: "eco", temperature: 17 }] },
      heater: { kind, id: null, name: "", type: "pilot_wire", entity: "", climate: "", absence_temperature: 12, schedule_id: null },
      group: { kind, id: null, name: "", members: [], schedule_id: null },
    }[kind];
  }
  async _click(e) {
    const el = e.target.closest("[data-a]");
    if (!el) return;
    const d = el.dataset, h = this._hass;
    const call = (s, data) => h.callService("chauffage_manager", s, data).catch((err) => this._toast(err));
    switch (d.a) {
      case "tab": this._tab = d.v; this._edit = null; this._render(); break;
      case "control": call("set_control", { target: d.t, control: d.v }); break;
      case "mode": {
        const t = this._data.targets.find((x) => x.id === d.t);
        const data = { target: d.t, mode: d.v };
        if (this._info(t).thermo) data.temperature = this._tempOf(t);
        call("set_manual", data); break;
      }
      case "temp": {
        const t = this._data.targets.find((x) => x.id === d.t);
        const v = Math.min(30, Math.max(5, this._tempOf(t) + Number(d.d)));
        this._temps[d.t] = v;
        call("set_manual", { target: d.t, mode: "comfort", temperature: v }); break;
      }
      case "alloff": this._data.targets.forEach((t) => call("set_manual", { target: t.id, mode: "off" })); break;
      case "new": this._edit = this._blank(d.v); this._render(); break;
      case "edit": {
        const coll = { schedule: "schedules", heater: "heaters", group: "groups" }[d.k];
        this._edit = { kind: d.k, ...JSON.parse(JSON.stringify(this._data[coll].find((x) => x.id === d.id))) };
        if (d.k === "heater") { this._edit.climate = this._edit.climate || ""; this._edit.absence_temperature = this._edit.absence_temperature ?? 12; }
        this._render(); break;
      }
      case "del":
        if (confirm("Supprimer ?")) h.callWS({ type: "chauffage_manager/delete", kind: d.k, id: d.id }).catch((err) => this._toast(err));
        break;
      case "cancel": this._edit = null; this._render(); break;
      case "save": this._save(); break;
      case "abs-save":
        try { await h.callWS({ type: "chauffage_manager/save", kind: "absence", value: { persons: this._abs.persons, mode: this._abs.mode, control: this._abs.control, restore: !!this._abs.restore } }); this._absDirty = false; await this._load(); }
        catch (err) { this._toast(err); }
        break;
      case "day": {
        const s = this._edit.slots[+d.i], n = +d.d;
        s.days = s.days.includes(n) ? s.days.filter((x) => x !== n) : [...s.days, n].sort();
        el.classList.toggle("on");
        this.shadowRoot.getElementById("pv").innerHTML = timeline(this._edit);
        break;
      }
      case "addslot": this._edit.slots.push({ days: [0, 1, 2, 3, 4, 5, 6], time: "12:00", mode: "comfort", temperature: 19 }); this._render(); break;
      case "delslot": this._edit.slots.splice(+d.i, 1); this._render(); break;
    }
  }
  _change(e) {
    const el = e.target, d = el.dataset;
    if (d.a === "sched") {
      if (e.type !== "change") return;
      const coll = d.k === "group" ? "groups" : "heaters";
      const item = { ...this._data[coll].find((x) => x.id === d.t) };
      delete item.id;
      item.schedule_id = el.value || null;
      this._hass.callWS({ type: "chauffage_manager/save", kind: d.k, id: d.t, value: item }).catch((err) => this._toast(err));
      return;
    }
    if (!d.f) return;
    const val = el.type === "checkbox" ? el.checked : el.value;
    if (d.scope === "abs") {
      this._absDirty = true;
      if (d.f === "person") this._abs.persons = val ? [...new Set([...this._abs.persons, d.v])] : this._abs.persons.filter((p) => p !== d.v);
      else this._abs[d.f] = val;
      return;
    }
    const ed = this._edit;
    if (!ed) return;
    if (d.i !== undefined) { ed.slots[+d.i][d.f] = val; if (e.type === "change") this.shadowRoot.getElementById("pv").innerHTML = timeline(ed); return; }
    if (d.f === "member") { ed.members = val ? [...new Set([...ed.members, d.v])] : ed.members.filter((m) => m !== d.v); return; }
    ed[d.f] = val;
    if (d.f === "type" && e.type === "change") { ed.entity = ""; ed.climate = ""; this._render(); }
  }
  async _save() {
    const e = this._edit;
    let value;
    if (!e.name.trim()) return this._toast("Nom requis");
    if (e.kind === "schedule") {
      if (e.slots.some((s) => !s.days.length || !s.time)) return this._toast("Chaque créneau nécessite des jours et une heure");
      value = { name: e.name.trim(), slots: e.slots.map((s) => ({ days: s.days, time: s.time, mode: s.mode, temperature: s.temperature === "" || s.temperature == null ? null : Number(s.temperature) })) };
    } else if (e.kind === "heater") {
      if (!e.entity) return this._toast("Entité requise");
      value = { name: e.name.trim(), type: e.type, entity: e.entity, climate: e.type === "pilot_wire" ? e.climate || null : null, schedule_id: e.schedule_id || null, absence_temperature: Number(e.absence_temperature) || 12 };
    } else {
      value = { name: e.name.trim(), members: e.members, schedule_id: e.schedule_id || null };
    }
    try {
      await this._hass.callWS({ type: "chauffage_manager/save", kind: e.kind, id: e.id || undefined, value });
      this._edit = null; await this._load();
    } catch (err) { this._toast(err); }
  }
}
customElements.define("chauffage-manager-card", ChauffageManagerCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "chauffage-manager-card", name: "Chauffage Manager", description: "Pièces, plannings, groupes et absence des chauffages" });
