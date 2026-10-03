/**
 * Shader orb guide — idle / travel / think / celebrate.
 * Exposes window.MolOrb
 */
(function (global) {
  "use strict";

  function MolOrb(scene) {
    this.state = "idle";
    this._t0 = performance.now();
    var geo = new THREE.SphereGeometry(0.18, 32, 32);
    var mat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      uniforms: {
        uTime: { value: 0 },
        uPulse: { value: 1.0 },
        uColor: { value: new THREE.Color(0x2dd4bf) },
        uIntensity: { value: 1.0 },
      },
      vertexShader: [
        "varying vec3 vN; varying vec3 vP;",
        "void main(){",
        "  vN = normalize(normalMatrix * normal);",
        "  vP = position;",
        "  gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);",
        "}",
      ].join("\n"),
      fragmentShader: [
        "uniform float uTime; uniform float uPulse; uniform vec3 uColor; uniform float uIntensity;",
        "varying vec3 vN; varying vec3 vP;",
        "void main(){",
        "  float fres = pow(1.0 - max(dot(normalize(vN), vec3(0.0,0.0,1.0)), 0.0), 2.2);",
        "  float glow = 0.45 + 0.55 * fres;",
        "  float breathe = 0.85 + 0.15 * sin(uTime * uPulse);",
        "  vec3 col = uColor * glow * breathe * uIntensity;",
        "  float alpha = 0.55 + 0.35 * fres;",
        "  gl_FragColor = vec4(col, alpha);",
        "}",
      ].join("\n"),
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.mesh.position.set(0, 0.8, 2.2);
    scene.add(this.mesh);
    // soft point light parented conceptually
    this.light = new THREE.PointLight(0x2dd4bf, 1.2, 6);
    this.mesh.add(this.light);
  }

  MolOrb.prototype.setState = function (s) {
    this.state = s || "idle";
    var c = this.mesh.material.uniforms.uColor.value;
    var pulse = this.mesh.material.uniforms.uPulse;
    var inten = this.mesh.material.uniforms.uIntensity;
    if (s === "travel") {
      c.setHex(0x5eead4); pulse.value = 2.2; inten.value = 1.25;
    } else if (s === "think") {
      c.setHex(0xfbbf24); pulse.value = 3.4; inten.value = 1.4;
    } else if (s === "celebrate") {
      c.setHex(0xa78bfa); pulse.value = 4.5; inten.value = 1.7;
    } else {
      c.setHex(0x2dd4bf); pulse.value = 1.0; inten.value = 1.0;
    }
  };

  MolOrb.prototype.follow = function (x, y, z, ease) {
    var e = ease == null ? 0.08 : ease;
    this.mesh.position.x += (x - this.mesh.position.x) * e;
    this.mesh.position.y += (y - this.mesh.position.y) * e;
    this.mesh.position.z += (z - this.mesh.position.z) * e;
  };

  MolOrb.prototype.update = function (tMs) {
    this.mesh.material.uniforms.uTime.value = (tMs - this._t0) * 0.001;
    var squash = this.state === "celebrate" ? 1.0 + 0.08 * Math.sin(tMs * 0.02) : 1.0;
    this.mesh.scale.set(squash, 2.0 - squash, squash);
  };

  global.MolOrb = MolOrb;
})(window);
