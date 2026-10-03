/**
 * Shared day-index timeline for molecule scrollytelling.
 * Exposes window.MolTimeline
 */
(function (global) {
  "use strict";

  function clamp(v, a, b) {
    return Math.max(a, Math.min(b, v));
  }

  function MolTimeline() {
    this.days = [];
    this.meta = {};
    this.idx = 0;
    this.listeners = [];
  }

  MolTimeline.prototype.load = function (data) {
    this.meta = (data && data.meta) || {};
    this.days = (data && data.days) || [];
    this.idx = 0;
    this.emit();
  };

  MolTimeline.prototype.on = function (fn) {
    this.listeners.push(fn);
  };

  MolTimeline.prototype.emit = function () {
    var d = this.days[this.idx] || null;
    for (var i = 0; i < this.listeners.length; i++) this.listeners[i](d, this.idx, this);
  };

  MolTimeline.prototype.setIndex = function (i) {
    if (!this.days.length) return;
    var next = clamp(Math.floor(i), 0, this.days.length - 1);
    if (next === this.idx) return;
    this.idx = next;
    this.emit();
  };

  MolTimeline.prototype.setProgress = function (p) {
    if (!this.days.length) return;
    this.setIndex(p * (this.days.length - 1));
  };

  MolTimeline.prototype.day = function () {
    return this.days[this.idx] || null;
  };

  global.MolTimeline = MolTimeline;
})(window);
