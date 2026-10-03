/**
 * Mute-default ambient bed + event chimes (Howler).
 * Exposes window.MolAudio
 */
(function (global) {
  "use strict";

  function MolAudio() {
    this.enabled = false;
    this._hum = null;
    this._chime = null;
    this._ready = false;
  }

  MolAudio.prototype.init = function () {
    if (typeof Howl === "undefined") return;
    this._hum = new Howl({
      src: ["assets/ambient_hum.wav"],
      loop: true,
      volume: 0.18,
      html5: true,
    });
    this._chime = new Howl({
      src: ["assets/chime.wav"],
      volume: 0.35,
      html5: true,
    });
    this._ready = true;
  };

  MolAudio.prototype.setEnabled = function (on) {
    this.enabled = !!on;
    if (!this._ready) this.init();
    if (!this._hum) return;
    if (this.enabled) this._hum.play();
    else this._hum.stop();
  };

  MolAudio.prototype.chime = function () {
    if (!this.enabled || !this._chime) return;
    this._chime.play();
  };

  global.MolAudio = MolAudio;
})(window);
