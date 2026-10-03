/**
 * Premium procedural Three.js stage: network tubes, cavern liquid, equity ribbons.
 * Driven by timeline day + scroll act progress. Exposes window.MolStage
 */
(function (global) {
  "use strict";

  function nodeMap(topo) {
    var m = {};
    (topo.nodes || []).forEach(function (n) { m[n.id] = n; });
    return m;
  }

  function MolStage(canvas) {
    this.canvas = canvas;
    this.act = "network"; // network | cavern | cockpit | race
    this.actProgress = 0;
    this.day = null;
    this.topo = null;
    this._running = false;
    this._simple = false;

    this.renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setClearColor(0x05080f, 0);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace || THREE.sRGBEncoding;

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2(0x071018, 0.045);

    this.camera = new THREE.PerspectiveCamera(42, 1, 0.1, 80);
    this.camera.position.set(0, 2.4, 7.2);

    this.scene.add(new THREE.AmbientLight(0x94a3b8, 0.45));
    var key = new THREE.DirectionalLight(0xe2e8f0, 1.15);
    key.position.set(3, 6, 4);
    this.scene.add(key);
    var rim = new THREE.DirectionalLight(0x2dd4bf, 0.55);
    rim.position.set(-4, 2, -2);
    this.scene.add(rim);

    this.root = new THREE.Group();
    this.scene.add(this.root);

    this.networkGroup = new THREE.Group();
    this.cavernGroup = new THREE.Group();
    this.raceGroup = new THREE.Group();
    this.root.add(this.networkGroup);
    this.root.add(this.cavernGroup);
    this.root.add(this.raceGroup);
    this.cavernGroup.visible = false;
    this.raceGroup.visible = false;

    this.particles = null;
    this.particlePhases = null;
    this.curves = [];
    this.hubMeshes = {};
    this.fill = { de: 0.5, nl: 0.5, fr: 0.5, lng: 0.4 };
    this.liquid = null;
    this.liquidMat = null;
    this.ribbonRl = null;
    this.ribbonRi = null;
    this.orb = null;

    this._camFrom = new THREE.Vector3();
    this._camTo = new THREE.Vector3();
    this._look = new THREE.Vector3(0, 0, 0);

    this._onResize = this.resize.bind(this);
    window.addEventListener("resize", this._onResize);
    this.resize();
  }

  MolStage.prototype.setSimple = function (on) {
    this._simple = !!on;
    this.canvas.style.visibility = on ? "hidden" : "visible";
    if (on) this._running = false;
    else if (!this._running) this.start();
  };

  MolStage.prototype.resize = function () {
    var w = this.canvas.clientWidth || window.innerWidth;
    var h = this.canvas.clientHeight || Math.max(420, window.innerHeight * 0.72);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / Math.max(h, 1);
    this.camera.updateProjectionMatrix();
  };

  MolStage.prototype.loadTopology = function (topo) {
    this.topo = topo;
    // clear network
    while (this.networkGroup.children.length) {
      var c = this.networkGroup.children[0];
      this.networkGroup.remove(c);
    }
    this.curves = [];
    this.hubMeshes = {};

    var nodes = nodeMap(topo);
    var tubeMat = new THREE.MeshStandardMaterial({
      color: 0x64748b,
      metalness: 0.72,
      roughness: 0.28,
    });

    (topo.edges || []).forEach(function (e) {
      var a = nodes[e[0]];
      var b = nodes[e[1]];
      if (!a || !b) return;
      var p0 = new THREE.Vector3(a.x, a.y, a.z);
      var p1 = new THREE.Vector3(b.x, b.y, b.z);
      var mid = p0.clone().lerp(p1, 0.5);
      mid.y += 0.35 + Math.random() * 0.25;
      var curve = new THREE.CatmullRomCurve3([p0, mid, p1]);
      this.curves.push(curve);
      var geo = new THREE.TubeGeometry(curve, 48, 0.035, 8, false);
      this.networkGroup.add(new THREE.Mesh(geo, tubeMat));
    }.bind(this));

    (topo.nodes || []).forEach(function (n) {
      var r = n.kind === "lng" ? 0.16 : 0.12;
      var color = n.kind === "storage" ? 0x2dd4bf : n.kind === "lng" ? 0x60a5fa : 0xe2e8f0;
      var mesh = new THREE.Mesh(
        new THREE.SphereGeometry(r, 20, 20),
        new THREE.MeshStandardMaterial({ color: color, emissive: color, emissiveIntensity: 0.35, metalness: 0.2, roughness: 0.4 })
      );
      mesh.position.set(n.x, n.y, n.z);
      this.networkGroup.add(mesh);
      this.hubMeshes[n.id] = mesh;
      // label sprite-ish: small ring
      var ring = new THREE.Mesh(
        new THREE.TorusGeometry(r * 1.45, 0.012, 8, 32),
        new THREE.MeshBasicMaterial({ color: 0x94a3b8, transparent: true, opacity: 0.5 })
      );
      ring.rotation.x = Math.PI / 2;
      mesh.add(ring);
    }.bind(this));

    // particle flow along first curves
    var pCount = 900;
    var positions = new Float32Array(pCount * 3);
    var phases = new Float32Array(pCount);
    for (var i = 0; i < pCount; i++) {
      phases[i] = Math.random();
      positions[i * 3] = 0;
      positions[i * 3 + 1] = 0;
      positions[i * 3 + 2] = 0;
    }
    var pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    var pMat = new THREE.PointsMaterial({
      color: 0x5eead4,
      size: 0.045,
      transparent: true,
      opacity: 0.9,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.particles = new THREE.Points(pGeo, pMat);
    this.particlePhases = phases;
    this.particleSpeed = 0.12;
    this.networkGroup.add(this.particles);

    this._buildCavern();
    this._buildRacePlaceholder();

    if (typeof MolOrb !== "undefined") {
      this.orb = new MolOrb(this.scene);
      this.orb.setState("idle");
    }
  };

  MolStage.prototype._buildCavern = function () {
    while (this.cavernGroup.children.length) this.cavernGroup.remove(this.cavernGroup.children[0]);
    var shell = new THREE.Mesh(
      new THREE.SphereGeometry(1.6, 48, 32, 0, Math.PI * 2, 0, Math.PI * 0.55),
      new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        metalness: 0.1,
        roughness: 0.85,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.85,
      })
    );
    shell.rotation.x = Math.PI;
    shell.position.y = 0.2;
    this.cavernGroup.add(shell);

    this.liquidMat = new THREE.ShaderMaterial({
      transparent: true,
      uniforms: {
        uFill: { value: 0.55 },
        uTime: { value: 0 },
        uColor: { value: new THREE.Color(0x14b8a6) },
      },
      vertexShader: [
        "varying vec2 vUv; varying vec3 vP;",
        "void main(){ vUv=uv; vP=position; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }",
      ].join("\n"),
      fragmentShader: [
        "uniform float uFill; uniform float uTime; uniform vec3 uColor;",
        "varying vec2 vUv; varying vec3 vP;",
        "void main(){",
        "  float wave = 0.02 * sin(vP.x * 8.0 + uTime * 2.0) * cos(vP.z * 6.0 + uTime);",
        "  float h = (vP.y + 1.2) / 2.2;",
        "  float edge = smoothstep(uFill + wave - 0.02, uFill + wave + 0.02, h);",
        "  float alpha = (1.0 - edge) * 0.72;",
        "  vec3 col = mix(uColor * 0.55, uColor * 1.15, h);",
        "  gl_FragColor = vec4(col, alpha);",
        "}",
      ].join("\n"),
    });
    this.liquid = new THREE.Mesh(new THREE.CylinderGeometry(1.25, 1.35, 2.2, 48), this.liquidMat);
    this.liquid.position.y = 0.1;
    this.cavernGroup.add(this.liquid);

    // ghost inventory markers
    this.invRl = new THREE.Mesh(
      new THREE.TorusGeometry(1.28, 0.02, 8, 48),
      new THREE.MeshBasicMaterial({ color: 0x2dd4bf })
    );
    this.invRi = new THREE.Mesh(
      new THREE.TorusGeometry(1.32, 0.015, 8, 48),
      new THREE.MeshBasicMaterial({ color: 0xe9c46a, transparent: true, opacity: 0.85 })
    );
    this.invRl.rotation.x = this.invRi.rotation.x = Math.PI / 2;
    this.cavernGroup.add(this.invRl);
    this.cavernGroup.add(this.invRi);
  };

  MolStage.prototype._buildRacePlaceholder = function () {
    while (this.raceGroup.children.length) this.raceGroup.remove(this.raceGroup.children[0]);
    var floor = new THREE.Mesh(
      new THREE.CircleGeometry(3.2, 48),
      new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.3, roughness: 0.8 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.6;
    this.raceGroup.add(floor);
  };

  MolStage.prototype.setEquityPaths = function (rlVals, riVals) {
    // rebuild ribbons from cumulative series
    function toCurve(vals, yOff, xScale) {
      var pts = [];
      var n = vals.length;
      if (n < 2) return null;
      var finite = vals.filter(function (v) { return Number.isFinite(v); });
      if (finite.length < 2) return null;
      var min = Math.min.apply(null, finite);
      var max = Math.max.apply(null, finite);
      var span = max - min || 1;
      var step = Math.max(1, Math.floor(n / 120));
      for (var i = 0; i < n; i += step) {
        var v = vals[i];
        if (!Number.isFinite(v)) continue;
        var x = (i / (n - 1)) * xScale - xScale * 0.5;
        var y = ((v - min) / span) * 1.6 - 0.2 + yOff;
        pts.push(new THREE.Vector3(x, y, Math.sin(i * 0.02) * 0.15));
      }
      if (pts.length < 2) return null;
      return new THREE.CatmullRomCurve3(pts);
    }
    if (this.ribbonRl) this.raceGroup.remove(this.ribbonRl);
    if (this.ribbonRi) this.raceGroup.remove(this.ribbonRi);
    var cRl = toCurve(rlVals, 0.15, 5.5);
    var cRi = toCurve(riVals, 0.0, 5.5);
    if (cRl) {
      this.ribbonRl = new THREE.Mesh(
        new THREE.TubeGeometry(cRl, 160, 0.04, 8, false),
        new THREE.MeshStandardMaterial({ color: 0x2dd4bf, emissive: 0x115e59, emissiveIntensity: 0.6, metalness: 0.4, roughness: 0.35 })
      );
      this.raceGroup.add(this.ribbonRl);
    }
    if (cRi) {
      this.ribbonRi = new THREE.Mesh(
        new THREE.TubeGeometry(cRi, 160, 0.035, 8, false),
        new THREE.MeshStandardMaterial({ color: 0xe9c46a, emissive: 0x78350f, emissiveIntensity: 0.35, metalness: 0.3, roughness: 0.45 })
      );
      this.raceGroup.add(this.ribbonRi);
    }
  };

  MolStage.prototype.setAct = function (act, progress) {
    this.act = act || "network";
    this.actProgress = progress || 0;
    this.networkGroup.visible = act === "network" || act === "cockpit";
    this.cavernGroup.visible = act === "cavern";
    this.raceGroup.visible = act === "race";
    if (this.orb) {
      if (act === "network") this.orb.setState("travel");
      else if (act === "cavern") this.orb.setState("think");
      else if (act === "race") this.orb.setState("celebrate");
      else this.orb.setState("idle");
    }
  };

  MolStage.prototype.setDay = function (d) {
    this.day = d;
    if (!d) return;
    function frac(v) {
      var x = Number(v);
      if (!Number.isFinite(x)) return 0.5;
      return x > 1.5 ? x / 100 : Math.max(0, Math.min(1, x));
    }
    this.fills.de = frac(d.storage_de);
    this.fills.nl = frac(d.storage_nl);
    this.fills.fr = frac(d.storage_fr);
    this.fills.lng = Math.min(1, (Number(d.lng_sendout) || 800) / 3500);

    ["de", "nl", "fr"].forEach(function (id) {
      var m = this.hubMeshes[id];
      if (!m) return;
      var f = this.fills[id];
      m.scale.setScalar(0.85 + 0.6 * f);
      m.material.emissiveIntensity = 0.2 + 0.7 * f;
    }.bind(this));
    if (this.hubMeshes.zeebrugge) {
      this.hubMeshes.zeebrugge.scale.setScalar(0.9 + 0.7 * this.fills.lng);
    }

    var act = (d.rl_action || "hold");
    this.particleSpeed = act === "withdraw" ? 0.28 : act === "inject" ? 0.2 : 0.1;
    if (Number(d.p_stress) > 0.55 && this.particles) {
      this.particles.material.color.setHex(0xfbbf24);
    } else if (this.particles) {
      this.particles.material.color.setHex(0x5eead4);
    }

    if (this.liquidMat) {
      this.liquidMat.uniforms.uFill.value = frac(d.storage_pct);
    }
    function yInv(v) {
      return -0.9 + frac(v) * 1.8;
    }
    if (this.invRl) this.invRl.position.y = yInv(d.inventory_rl != null ? d.inventory_rl : d.storage_pct);
    if (this.invRi) this.invRi.position.y = yInv(d.inventory_ri != null ? d.inventory_ri : d.storage_pct);
  };

  MolStage.prototype._updateCamera = function () {
    var p = this.actProgress;
    var target = new THREE.Vector3();
    var look = new THREE.Vector3(0, 0.2, 0);
    if (this.act === "network") {
      target.set(Math.sin(p * Math.PI) * 1.2, 2.1 - p * 0.4, 6.8 - p * 1.5);
      look.set(0, 0.1, 0);
    } else if (this.act === "cavern") {
      target.set(0.2, 0.6 + p * 0.4, 4.2 - p * 0.8);
      look.set(0, 0.2, 0);
    } else if (this.act === "cockpit") {
      target.set(0, 1.6, 5.5);
      look.set(0, 0.4, 0);
    } else {
      target.set(-0.4 + p * 0.6, 1.4, 5.8 - p * 1.2);
      look.set(0, 0.3, 0);
    }
    this.camera.position.lerp(target, 0.08);
    this._look.lerp(look, 0.08);
    this.camera.lookAt(this._look);
  };

  MolStage.prototype._updateParticles = function (dt) {
    if (!this.particles || !this.curves.length) return;
    var pos = this.particles.geometry.attributes.position.array;
    var n = this.particlePhases.length;
    for (var i = 0; i < n; i++) {
      this.particlePhases[i] = (this.particlePhases[i] + dt * this.particleSpeed * (0.6 + (i % 5) * 0.08)) % 1;
      var curve = this.curves[i % this.curves.length];
      var pt = curve.getPointAt(this.particlePhases[i]);
      pos[i * 3] = pt.x;
      pos[i * 3 + 1] = pt.y;
      pos[i * 3 + 2] = pt.z;
    }
    this.particles.geometry.attributes.position.needsUpdate = true;
  };

  MolStage.prototype.start = function () {
    if (this._running || this._simple) return;
    this._running = true;
    var last = performance.now();
    var self = this;
    function tick(now) {
      if (!self._running) return;
      var dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      self._updateCamera();
      self._updateParticles(dt);
      if (self.liquidMat) self.liquidMat.uniforms.uTime.value = now * 0.001;
      if (self.orb) {
        if (self.act === "network") self.orb.follow(Math.sin(now * 0.0004) * 1.5, 0.9, 1.8, 0.06);
        else if (self.act === "cavern") self.orb.follow(1.1, 0.7, 1.4, 0.06);
        else if (self.act === "race") self.orb.follow(0.2, 1.4, 2.0, 0.05);
        else self.orb.follow(0, 1.1, 2.4, 0.05);
        self.orb.update(now);
      }
      self.renderer.render(self.scene, self.camera);
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  };

  MolStage.prototype.destroy = function () {
    this._running = false;
    window.removeEventListener("resize", this._onResize);
    this.renderer.dispose();
  };

  global.MolStage = MolStage;
})(window);
