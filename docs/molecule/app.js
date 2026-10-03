(function () {
  "use strict";

  var timeline = new MolTimeline();
  var audio = new MolAudio();
  var stage = null;
  var card = null;
  var tear = null;
  var simple = false;
  var lastChimeAction = null;

  function fmt(x, d) {
    if (x === null || x === undefined || Number.isNaN(Number(x))) return "—";
    return Number(x).toFixed(d === undefined ? 2 : d);
  }

  function prefersReduced() {
    try {
      return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch (e) {
      return false;
    }
  }

  function setFill(pct, invRl, invRi) {
    var bar = document.getElementById("fill-bar");
    var label = document.getElementById("fill-label");
    var rlLine = document.getElementById("inv-rl-line");
    var riLine = document.getElementById("inv-ri-line");
    if (!bar || !label) return;
    var p = Number(pct) || 0;
    if (p > 1.5) p = p / 100;
    p = Math.max(0, Math.min(1, p));
    var h = 140 * p;
    bar.setAttribute("y", String(160 - h));
    bar.setAttribute("height", String(h));
    label.textContent = "storage " + Math.round(p * 100) + "%";
    function yOf(v) {
      var f = Number(v);
      if (!Number.isFinite(f)) return 90;
      if (f > 1.5) f = f / 100;
      f = Math.max(0, Math.min(1, f));
      return 160 - 140 * f;
    }
    if (rlLine) {
      var y1 = yOf(invRl);
      rlLine.setAttribute("y1", String(y1));
      rlLine.setAttribute("y2", String(y1));
    }
    if (riLine) {
      var y2 = yOf(invRi);
      riLine.setAttribute("y1", String(y2));
      riLine.setAttribute("y2", String(y2));
    }
  }

  function drawEquity2d(days) {
    var canvas = document.getElementById("equity-canvas");
    if (!canvas || !days || !days.length) return;
    var ctx = canvas.getContext("2d");
    var w = canvas.width;
    var h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    function series(key) {
      return days.map(function (d) { return Number(d[key]); });
    }
    var rl = series("cum_pnl_rl");
    var ri = series("cum_pnl_ri");
    var vals = rl.concat(ri).filter(function (v) { return Number.isFinite(v); });
    if (vals.length < 2) return;
    var min = Math.min.apply(null, vals);
    var max = Math.max.apply(null, vals);
    var span = max - min || 1;
    function stroke(arr, color) {
      var started = false;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      arr.forEach(function (v, i) {
        if (!Number.isFinite(v)) return;
        var x = (i / (arr.length - 1)) * (w - 40) + 20;
        var y = h - 20 - ((v - min) / span) * (h - 40);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }
    stroke(ri, "rgba(233,196,106,0.9)");
    stroke(rl, "rgba(45,212,191,0.95)");
  }

  function renderWaterfall(cardData) {
    var el = document.getElementById("waterfall");
    if (!el) return;
    if (!cardData) {
      el.innerHTML = "<p>Decision card unavailable.</p>";
      return;
    }
    var legs = [];
    var wf = cardData.exposure_waterfall || cardData;
    if (wf.legs && Array.isArray(wf.legs)) legs = wf.legs;
    else if (typeof wf === "object") {
      Object.keys(wf).forEach(function (k) {
        if (k === "legs" || k === "as_of" || k === "exposure_id") return;
        var v = wf[k];
        if (v && typeof v === "object") legs.push(Object.assign({ name: k }, v));
      });
    }
    var rec = cardData.recommended || {};
    var html = "<table><thead><tr><th>Leg</th><th>Status</th><th>Note</th></tr></thead><tbody>";
    if (!legs.length) {
      html += "<tr><td colspan=3>Certificates remain <span class='unpriced'>unpriced</span> without GO marks.</td></tr>";
    } else {
      legs.forEach(function (leg) {
        var name = leg.name || leg.leg || leg.id || "leg";
        var status = leg.status || leg.mark_status || leg.pricing || "modeled";
        var note = leg.notes || leg.note || leg.source || "";
        var cls = String(status).toLowerCase().indexOf("unpriced") >= 0 ? "unpriced" : "";
        html += "<tr><td>" + name + "</td><td class='" + cls + "'>" + status + "</td><td>" + note + "</td></tr>";
      });
    }
    html += "</tbody></table>";
    html += "<p style='margin-top:10px'>Recommended: <strong>" + (rec.status || "—") + "</strong>";
    if (rec.x !== undefined) html += " · x=" + fmt(rec.x, 3);
    html += "</p>";
    var claims = cardData.non_claims || [];
    if (claims.length) {
      html += "<ul style='margin:8px 0 0 18px'>" + claims.map(function (c) { return "<li>" + c + "</li>"; }).join("") + "</ul>";
    }
    el.innerHTML = html;
  }

  function fillTearsheet(meta, tearData) {
    var champ = (tearData && tearData.champion) || (meta && meta.rl_tearsheet) || {};
    var ts = champ.tearsheet || champ || {};
    var gate = champ.gate || {};
    document.getElementById("ts-algo").textContent = (meta && meta.rl_algo) || champ.algo || "—";
    document.getElementById("ts-sharpe").textContent = fmt(ts.sharpe, 2);
    document.getElementById("ts-dd").textContent = fmt(ts.max_dd, 3);
    document.getElementById("ts-es").textContent = fmt(ts.es95, 4);
    document.getElementById("ts-ent").textContent = fmt(ts.action_entropy, 2);
    document.getElementById("ts-gate").textContent = (meta && meta.rl_status) || gate.status || "—";
  }

  function applyDay(d) {
    if (!d) return;
    document.getElementById("net-date").textContent = d.date || "—";
    document.getElementById("net-ttf").textContent = fmt(d.ttf_front);
    document.getElementById("net-stress").textContent = fmt(d.p_stress, 3);
    document.getElementById("net-action").textContent = d.rl_action || "—";
    document.getElementById("hub-de").textContent = fmt(d.storage_de, 2);
    document.getElementById("hub-nl").textContent = fmt(d.storage_nl, 2);
    document.getElementById("hub-fr").textContent = fmt(d.storage_fr, 2);
    document.getElementById("hub-lng").textContent = fmt(d.lng_sendout, 1);

    document.getElementById("cav-fill").textContent = fmt(
      (Number(d.storage_pct) > 1.5 ? Number(d.storage_pct) : Number(d.storage_pct) * 100),
      1
    ) + "%";
    document.getElementById("cavern-rl-action").textContent = d.rl_action || "—";
    document.getElementById("cavern-ri-action").textContent = d.heuristic_action || "—";
    document.getElementById("cavern-inv-rl").textContent = fmt(d.inventory_rl, 3);
    document.getElementById("cavern-inv-ri").textContent = fmt(d.inventory_ri, 3);
    setFill(d.storage_pct, d.inventory_rl, d.inventory_ri);

    document.getElementById("hud-date").textContent = d.date || "—";
    document.getElementById("hud-ttf").textContent = fmt(d.ttf_front);
    document.getElementById("hud-eua").textContent = fmt(d.eua_front);
    document.getElementById("hud-slope").textContent = fmt(d.ttf_slope, 4);
    document.getElementById("hud-hedge").textContent = fmt(d.hedge_ratio, 3);
    document.getElementById("hud-ols").textContent = fmt(d.ols_ratio, 3);
    document.getElementById("hud-stress").textContent = fmt(d.p_stress, 3);
    document.getElementById("hud-ig").textContent = d.ig_leader || "—";
    document.getElementById("hud-resid").textContent = fmt(d.residual_var, 6);
    document.getElementById("hud-cert").textContent = (timeline.meta && timeline.meta.certificates) || "unpriced";

    if (stage) stage.setDay(d);

    var cap = document.getElementById("orb-caption");
    if (cap && stage && stage.orb) cap.textContent = "Orb guide · " + (stage.orb.state || "idle");

    if (d.rl_action && d.rl_action !== lastChimeAction) {
      lastChimeAction = d.rl_action;
      audio.chime();
    }

    var slider = document.getElementById("date-slider");
    if (slider && Number(slider.value) !== timeline.idx) slider.value = String(timeline.idx);
  }

  function initScroll() {
    if (simple || prefersReduced() || typeof gsap === "undefined" || typeof ScrollTrigger === "undefined") {
      return;
    }
    gsap.registerPlugin(ScrollTrigger);

    var acts = [
      { id: "#act-network", name: "network" },
      { id: "#act-cavern", name: "cavern" },
      { id: "#act-cockpit", name: "cockpit" },
      { id: "#act-race", name: "race" },
    ];

    acts.forEach(function (a) {
      var el = document.querySelector(a.id);
      if (!el) return;
      ScrollTrigger.create({
        trigger: el,
        start: "top top",
        end: "bottom bottom",
        pin: el.querySelector(".act-pin"),
        scrub: 0.85,
        onUpdate: function (self) {
          if (stage) stage.setAct(a.name, self.progress);
          // map local act progress into global day index with slight offsets per act
          var base = { network: 0.05, cavern: 0.28, cockpit: 0.55, race: 0.78 };
          var span = 0.22;
          var p = (base[a.name] || 0) + self.progress * span;
          timeline.setProgress(Math.max(0, Math.min(1, p)));
        },
        onEnter: function () {
          if (stage) stage.setAct(a.name, 0);
          if (typeof anime !== "undefined") {
            anime({
              targets: a.id + " .mol-card",
              opacity: [0.55, 1],
              translateY: [8, 0],
              easing: "easeOutQuad",
              duration: 420,
              delay: anime.stagger(28),
            });
          }
        },
      });
    });
  }

  function setSimple(on) {
    simple = !!on;
    document.body.classList.toggle("simple-mode", simple);
    var btn = document.getElementById("simple-mode-btn");
    if (btn) btn.setAttribute("aria-pressed", on ? "true" : "false");
    var fallback = document.getElementById("stage-fallback");
    if (fallback) fallback.classList.toggle("hidden", !on);
    if (stage) stage.setSimple(on);
    if (on) {
      ScrollTrigger.getAll().forEach(function (t) { t.kill(); });
    } else {
      initScroll();
      if (stage) stage.start();
    }
  }

  function boot(data, cardData, tearData, topo) {
    timeline.load(data);
    card = cardData;
    tear = tearData || data.rl_tearsheet_full || null;

    var cleared = !!(timeline.meta && timeline.meta.cleared);
    var gate = document.getElementById("gate-cleared");
    var msg = document.getElementById("cleared-msg");
    var rlEl = document.getElementById("rl-status");
    if (gate) gate.textContent = "cleared: " + (cleared ? "true" : "false");
    if (rlEl) rlEl.textContent = (timeline.meta && timeline.meta.rl_status) || "not_trained";
    if (msg) {
      if (cleared) {
        msg.textContent = "Hedge WF gates cleared for research disclosure — synthetic book; still not investment advice.";
        msg.classList.add("ok");
      } else {
        msg.textContent = "Research prototype — gates not cleared.";
        msg.classList.remove("ok");
      }
    }

    fillTearsheet(timeline.meta, tear);
    renderWaterfall(card);
    drawEquity2d(timeline.days);

    var canvas = document.getElementById("stage-canvas");
    if (canvas && typeof THREE !== "undefined" && typeof MolStage !== "undefined") {
      stage = new MolStage(canvas);
      stage.loadTopology(topo || { nodes: [], edges: [] });
      var rl = timeline.days.map(function (d) { return Number(d.cum_pnl_rl); });
      var ri = timeline.days.map(function (d) { return Number(d.cum_pnl_ri); });
      stage.setEquityPaths(rl, ri);
      stage.setAct("network", 0);
      stage.start();
    }

    timeline.on(function (d) { applyDay(d); });
    applyDay(timeline.day());

    var slider = document.getElementById("date-slider");
    if (slider && timeline.days.length) {
      slider.max = String(timeline.days.length - 1);
      slider.value = "0";
      slider.addEventListener("input", function () {
        timeline.setIndex(Number(slider.value));
      });
    }

    audio.init();
    var soundBtn = document.getElementById("sound-btn");
    if (soundBtn) {
      soundBtn.addEventListener("click", function () {
        var on = soundBtn.getAttribute("aria-pressed") !== "true";
        soundBtn.setAttribute("aria-pressed", on ? "true" : "false");
        audio.setEnabled(on);
      });
    }

    var simpleBtn = document.getElementById("simple-mode-btn");
    if (simpleBtn) {
      simpleBtn.addEventListener("click", function () {
        setSimple(simpleBtn.getAttribute("aria-pressed") !== "true");
      });
    }

    if (prefersReduced()) setSimple(true);
    else initScroll();
  }

  Promise.all([
    fetch("../data/backtest_timeline.json").then(function (r) {
      if (!r.ok) throw new Error("timeline");
      return r.json();
    }),
    fetch("../data/decision_card.json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }),
    fetch("../data/rl_tearsheet.json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }),
    fetch("../data/network_topology.json").then(function (r) { return r.ok ? r.json() : { nodes: [], edges: [] }; }).catch(function () { return { nodes: [], edges: [] }; }),
  ])
    .then(function (arr) { boot(arr[0], arr[1], arr[2], arr[3]); })
    .catch(function () {
      boot({
        meta: { cleared: false, certificates: "unpriced", rl_status: "not_trained" },
        days: [],
      }, null, null, { nodes: [], edges: [] });
    });
})();
