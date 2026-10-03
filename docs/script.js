/* FIOracle hybrid site -- driven by site-config.js + gate-status.json */

(function () {
  if (!window.FIORACLE_SITE) {
    console.error("site-config.js missing");
    return;
  }
  const CFG = window.FIORACLE_SITE;
  const cheapMotion = shouldUseCheapMotion();

  document.addEventListener("DOMContentLoaded", () => {
    applyConfig();
    wireNav();
    wireBriefingForm();
    if (!cheapMotion) {
      initBackgroundField();
      runHeroTimeline();
      animateHeroOrbs();
    } else {
      showStaticHero();
    }
    wireRegimeStage();
    drawShieldChart();
    wireHarvestGate();
    buildTrialsTimeline();
    buildGateCriteria();
    loadGateStatus();
    wireScrollReveal();
    typewriterScreenplay();
    maybeInsertAnalytics();
  });

  function shouldUseCheapMotion() {
    try {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return true;
      if (window.matchMedia("(prefers-reduced-data: reduce)").matches) return true;
      if (window.matchMedia("(max-width: 768px)").matches) return true;
      const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      if (conn && (conn.saveData || /2g/.test(String(conn.effectiveType || "")))) return true;
    } catch (_) {
      /* ignore */
    }
    return false;
  }

  function applyConfig() {
    document.querySelectorAll("[data-trust]").forEach((el) => {
      const key = el.getAttribute("data-trust");
      const val = CFG.trust && CFG.trust[key];
      if (val !== undefined && val !== null) el.textContent = String(val);
    });
    document.querySelectorAll("[data-site-version]").forEach((el) => {
      el.textContent = CFG.version || "0.2.0";
    });
    document.querySelectorAll("[data-published-date]").forEach((el) => {
      el.textContent = CFG.publishedDate || "";
    });
    const gh = document.getElementById("github-link");
    if (gh && CFG.githubUrl) gh.href = CFG.githubUrl;

    const mailto = document.getElementById("mailto-fallback");
    const emailNote = document.getElementById("email-placeholder-note");
    if (mailto && CFG.contactEmail) {
      const subject = encodeURIComponent("FIOracle briefing request");
      mailto.href = `mailto:${CFG.contactEmail}?subject=${subject}`;
      mailto.textContent = `Email ${CFG.contactEmail}`;
    }
    if (emailNote) {
      emailNote.hidden = !CFG.contactIsPlaceholder;
    }

    const params = new URLSearchParams(window.location.search);
    const utmSource = document.getElementById("utm_source");
    const utmMedium = document.getElementById("utm_medium");
    const utmRef = document.getElementById("utm_ref");
    if (utmSource) utmSource.value = params.get("utm_source") || "";
    if (utmMedium) utmMedium.value = params.get("utm_medium") || "";
    if (utmRef) utmRef.value = params.get("ref") || "";
  }

  function wireNav() {
    const toggle = document.getElementById("nav-toggle");
    const links = document.getElementById("nav-links");
    if (!toggle || !links) return;
    toggle.addEventListener("click", () => {
      const open = links.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    });
    links.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => {
        links.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  function wireBriefingForm() {
    const form = document.getElementById("briefing-form");
    const submit = document.getElementById("briefing-submit");
    const note = document.getElementById("form-placeholder-note");
    if (!form || !submit) return;
    const id = CFG.formspreeId;
    const ready = id && id !== "PLACEHOLDER";
    if (ready) {
      form.action = `https://formspree.io/f/${id}`;
      submit.disabled = false;
      if (note) note.hidden = true;
    } else {
      form.action = "#";
      submit.disabled = true;
      if (note) note.hidden = false;
      form.addEventListener("submit", (e) => {
        e.preventDefault();
      });
    }
  }

  function maybeInsertAnalytics() {
    const a = CFG.analytics || {};
    if (!a.enabled || !a.plausibleDomain) return;
    const s = document.createElement("script");
    s.defer = true;
    s.setAttribute("data-domain", a.plausibleDomain);
    s.src = "https://plausible.io/js/script.js";
    document.head.appendChild(s);
  }

  function showStaticHero() {
    document.querySelectorAll(".eyebrow, #hero-title .line, #hero-subtitle, .hero-cta").forEach((el) => {
      el.style.opacity = "1";
      el.style.transform = "none";
    });
  }

  function initBackgroundField() {
    const canvas = document.getElementById("bg-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let w, h, rafId = null, running = true;
    function resize() {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    const colors = ["#2dd4bf", "#f5a623", "#ef4444"];
    const particles = Array.from({ length: 55 }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.6 + 0.4,
      c: colors[Math.floor(Math.random() * colors.length)],
      vx: (Math.random() - 0.5) * 0.15,
      vy: (Math.random() - 0.5) * 0.15,
      a: Math.random() * 0.45 + 0.12,
    }));

    function tick() {
      if (!running) return;
      ctx.clearRect(0, 0, w, h);
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = w;
        if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h;
        if (p.y > h) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = p.c;
        ctx.globalAlpha = p.a;
        ctx.fill();
      });
      ctx.globalAlpha = 1;
      rafId = requestAnimationFrame(tick);
    }

    function setRunning(on) {
      running = on;
      if (on && rafId == null) {
        rafId = requestAnimationFrame(tick);
      } else if (!on && rafId != null) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
    }

    document.addEventListener("visibilitychange", () => {
      setRunning(!document.hidden);
    });

    const hero = document.querySelector(".hero");
    if (hero && "IntersectionObserver" in window) {
      const io = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => setRunning(entry.isIntersecting && !document.hidden));
        },
        { threshold: 0.05 }
      );
      io.observe(hero);
    }

    setRunning(true);
  }

  function runHeroTimeline() {
    if (typeof anime === "undefined") return;
    const tl = anime.timeline({ easing: "easeOutExpo" });
    tl.add({ targets: ".eyebrow", opacity: [0, 1], translateY: [10, 0], duration: 500 })
      .add({
        targets: "#hero-title .line",
        opacity: [0, 1],
        translateY: [30, 0],
        duration: 800,
        delay: anime.stagger(120),
      })
      .add({ targets: "#hero-subtitle", opacity: [0, 1], translateY: [16, 0], duration: 650 })
      .add({ targets: ".hero-cta", opacity: [0, 1], translateY: [12, 0], duration: 600 });
  }

  let heroOrbAnims = [];

  function animateHeroOrbs() {
    if (typeof anime === "undefined") return;
    heroOrbAnims = [
      anime({
        targets: ".orb-calm",
        translateX: [0, 30, -10, 0],
        translateY: [0, -20, 10, 0],
        scale: [1, 1.08, 0.96, 1],
        duration: 14000,
        easing: "easeInOutSine",
        loop: true,
      }),
      anime({
        targets: ".orb-inflation",
        translateX: [0, -25, 15, 0],
        translateY: [0, 20, -12, 0],
        scale: [1, 0.95, 1.1, 1],
        duration: 11000,
        easing: "easeInOutSine",
        loop: true,
      }),
      anime({
        targets: ".orb-crisis",
        translateX: [0, 18, -22, 0],
        translateY: [0, -14, 18, 0],
        scale: [1, 1.15, 0.9, 1],
        duration: 7000,
        easing: "easeInOutQuad",
        loop: true,
      }),
    ];

    const hero = document.querySelector(".hero");
    if (!hero || !("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !document.hidden) {
            heroOrbAnims.forEach((a) => a && a.play && a.play());
          } else if (typeof anime !== "undefined") {
            anime.remove(".orb-calm, .orb-inflation, .orb-crisis");
          }
        });
      },
      { threshold: 0.1 }
    );
    io.observe(hero);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && typeof anime !== "undefined") {
        anime.remove(".orb-calm, .orb-inflation, .orb-crisis");
      }
    });
  }

  const REGIME_COPY = {
    calm: "Cash floors relax, the volatility-harvest sleeve (if enabled) is allowed to run, and allocation leans into carry. This is also the regime everyone assumes is permanent, which is exactly why it is tracked as a probability, not a certainty.",
    inflation:
      "The transitional state. Cash floors tighten modestly, forecasting confidence typically drops, and the system blends allocations across possible outcomes rather than committing to one.",
    crisis:
      "Cash floors rise directly with crisis probability, the volatility-harvest sleeve shuts off, and this is the one regime the entire crisis-convexity thesis is built to answer for. If the portfolio does not behave differently here, nothing else in this system matters.",
  };

  function wireRegimeStage() {
    const detail = document.getElementById("regime-detail");
    document.querySelectorAll(".regime-orb").forEach((orb) => {
      const activate = () => {
        const key = orb.dataset.target;
        detail.innerHTML = `<p>${REGIME_COPY[key]}</p>`;
        document.querySelectorAll(".regime-orb").forEach((o) => o.setAttribute("aria-pressed", "false"));
        orb.setAttribute("aria-pressed", "true");
        if (!cheapMotion && typeof anime !== "undefined") {
          anime({ targets: orb, scale: [1, 1.25, 1], duration: 600, easing: "easeOutElastic(1, .6)" });
          anime({ targets: detail, opacity: [0.2, 1], translateY: [10, 0], duration: 500, easing: "easeOutQuad" });
        }
      };
      orb.addEventListener("click", activate);
      orb.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activate();
        }
      });
    });

    if (!cheapMotion && typeof anime !== "undefined") {
      anime({ targets: ".regime-calm", scale: [1, 1.05, 1], duration: 4000, easing: "easeInOutSine", loop: true });
      anime({ targets: ".regime-inflation", scale: [1, 1.08, 1], duration: 3000, easing: "easeInOutSine", loop: true });
      anime({ targets: ".regime-crisis", scale: [1, 1.15, 0.95, 1], duration: 1600, easing: "easeInOutQuad", loop: true });
    }
  }

  function drawShieldChart() {
    const benchPath = document.getElementById("benchmark-path");
    const stratPath = document.getElementById("strategy-path");
    if (!benchPath || !stratPath) return;

    const n = 60;
    const benchY = [];
    const stratY = [];
    for (let i = 0; i < n; i++) {
      const t = i / (n - 1);
      const crash = t > 0.35 && t < 0.7 ? Math.sin(((t - 0.35) / 0.35) * Math.PI) : 0;
      benchY.push(60 + crash * 130);
      const partialCrash = t > 0.35 && t < 0.7 ? Math.sin(((t - 0.35) / 0.35) * Math.PI) * 0.3 : 0;
      stratY.push(40 + partialCrash * 130 - t * 8);
    }

    function toPath(ys) {
      return ys
        .map((y, i) => {
          const x = (i / (ys.length - 1)) * 800;
          return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
        })
        .join(" ");
    }

    benchPath.setAttribute("d", toPath(benchY));
    stratPath.setAttribute("d", toPath(stratY));

    if (!cheapMotion && typeof anime !== "undefined") {
      [benchPath, stratPath].forEach((p) => {
        const len = p.getTotalLength();
        p.style.strokeDasharray = len;
        p.style.strokeDashoffset = len;
      });
      anime({
        targets: "#benchmark-path, #strategy-path",
        strokeDashoffset: [anime.setDashoffset, 0],
        easing: "easeInOutSine",
        duration: 2200,
        delay: anime.stagger(300),
      });
    }
  }

  function wireHarvestGate() {
    const lampContango = document.getElementById("lamp-contango");
    const lampCrisis = document.getElementById("lamp-crisis");
    const gateStatus = document.getElementById("gate-status");
    const footnote = document.getElementById("harvest-footnote");
    const btn = document.getElementById("volmageddon-btn");
    if (!btn) return;

    function setState(contangoOn, crisisLow) {
      lampContango.classList.toggle("on", contangoOn);
      lampContango.classList.toggle("off", !contangoOn);
      lampCrisis.classList.toggle("on", crisisLow);
      lampCrisis.classList.toggle("off", !crisisLow);
      const harvestOn = contangoOn && crisisLow;
      gateStatus.textContent = harvestOn ? "ON" : "OFF";
      gateStatus.classList.toggle("off", !harvestOn);
    }

    setState(true, true);

    btn.addEventListener("click", () => {
      setState(true, true);
      if (!cheapMotion && typeof anime !== "undefined") {
        anime({
          targets: "#gate-toggle",
          translateX: [0, -6, 6, -4, 4, 0],
          duration: 500,
          easing: "easeInOutSine",
        });
      }
      setTimeout(() => {
        setState(false, false);
        footnote.textContent =
          "February 5, 2018: term structure inverted, crisis probability spiked. The lagged signal (available_date, not event_date) still closed the gate before the worst of it -- this is the exact scenario the regression fixture replays before this sleeve is ever allowed to run live.";
      }, 650);
    });
  }

  function buildTrialsTimeline() {
    const container = document.getElementById("timeline");
    if (!container) return;
    const trials = CFG.trials || [];
    trials.forEach((t, i) => {
      const el = document.createElement("div");
      el.className = `t-item ${t.status || "pending"}`;
      el.innerHTML = `
      <span class="t-track">${t.track} &middot; Step ${String(i + 1).padStart(2, "0")}</span>
      <div class="t-title">${t.title}</div>
      <div class="t-desc">${t.desc}</div>
    `;
      container.appendChild(el);
    });
  }

  function buildGateCriteria() {
    const ul = document.getElementById("gate-conditions");
    if (!ul) return;
    const criteria = (CFG.gate && CFG.gate.criteria) || [];
    ul.innerHTML = "";
    criteria.forEach((c) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="cond-check" aria-hidden="true">&#9675;</span>${c}`;
      ul.appendChild(li);
    });
  }

  function setGateFinal(cleared) {
    const el = document.getElementById("gate-final-text");
    if (!el) return;
    el.textContent = `cleared: ${cleared ? "true" : "false"}`;
  }

  function loadGateStatus() {
    setGateFinal(false);
    fetch("gate-status.json", { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error("gate status missing");
        return r.json();
      })
      .then((data) => {
        setGateFinal(Boolean(data && data.cleared === true));
      })
      .catch(() => {
        setGateFinal(false);
      });
  }

  function wireScrollReveal() {
    const sections = document.querySelectorAll(".reveal");
    if (cheapMotion) {
      sections.forEach((s) => s.classList.add("is-visible"));
      return;
    }
    const timelineItems = document.querySelectorAll(".t-item");
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            if (typeof anime !== "undefined") {
              anime({
                targets: entry.target,
                opacity: [0, 1],
                translateY: [30, 0],
                duration: 800,
                easing: "easeOutCubic",
              });
            }
            if (entry.target.id === "transparency" && typeof anime !== "undefined") {
              anime({
                targets: timelineItems,
                opacity: [0, 1],
                translateX: [-14, 0],
                delay: anime.stagger(80),
                duration: 500,
                easing: "easeOutQuad",
              });
            }
            if (entry.target.id === "gate") {
              revealGateConditions();
            }
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2 }
    );
    sections.forEach((s) => observer.observe(s));
  }

  function revealGateConditions() {
    if (cheapMotion || typeof anime === "undefined") return;
    anime({
      targets: ".gate-conditions li",
      opacity: [0, 1],
      translateX: [-10, 0],
      delay: anime.stagger(150),
      duration: 500,
      easing: "easeOutQuad",
    });
  }

  function typewriterScreenplay() {
    const el = document.getElementById("typewriter-quote");
    if (!el) return;
    const line =
      "\u201CI built a career\u2019s worth of instruments. Regime detectors, forecasters, identity locks, conformal shields, a harvest with a leash. And still, I do not walk through this gate until it opens on its own.\u201D";
    if (cheapMotion) {
      el.textContent = line;
      return;
    }
    let i = 0;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && el.dataset.typed !== "true") {
            el.dataset.typed = "true";
            const interval = setInterval(() => {
              el.textContent = line.slice(0, i);
              i++;
              if (i > line.length) clearInterval(interval);
            }, 18);
            observer.disconnect();
          }
        });
      },
      { threshold: 0.4 }
    );
    observer.observe(el);
  }
})();
