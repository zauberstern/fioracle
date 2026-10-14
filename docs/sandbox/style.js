(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.FIStyle = api;
})(typeof self !== "undefined" ? self : this, function () {
  function toBps(weights) {
    var raw = weights.map(function (value) {
      return isFinite(value) ? value * 10000 : 0;
    });
    var floors = raw.map(function (value) { return Math.floor(value + 1e-9); });
    var leftover = 10000 - floors.reduce(function (sum, value) { return sum + value; }, 0);
    var order = raw.map(function (value, index) { return index; });
    order.sort(function (a, b) { return (raw[b] - floors[b]) - (raw[a] - floors[a]); });
    var step;
    if (leftover > 0) {
      for (step = 0; step < leftover; step++) floors[order[step % floors.length]] += 1;
    } else {
      for (step = 0; step < -leftover; step++) {
        var take = order[order.length - 1 - (step % order.length)];
        if (floors[take] > 0) floors[take] -= 1;
      }
    }
    return floors.map(function (value) { return value | 0; });
  }

  function mask(ids, kind) {
    return ids.map(function (name) {
      if (name === "cash_allocation") return false;
      if (kind === "treasury") {
        return name === "US_10Y_GOV_BOND" || name === "BBG_US_TREASURY" || (name.indexOf("ISHARES_") === 0 && name.indexOf("TREASURY") >= 0);
      }
      return name === "BBG_US_CORPORATE" || name === "BBG_US_HIGH_YIELD";
    });
  }

  function dead(row, live) {
    if (!live) return false;
    for (var i = 0; i < live.length; i++) {
      if (row[i] > 0 && !live[i]) return true;
    }
    return false;
  }

  function policyRow(policy, ids, book, prev, mv, ew, live) {
    var width = ids.length;
    var row;
    if (policy === "book") return dead(book, live) ? null : book.slice();
    if (policy === "mv") return !mv || dead(mv, live) ? null : mv.slice();
    if (policy === "ew") return !ew || dead(ew, live) ? null : ew.slice();
    if (policy === "previous") return prev ? prev.slice() : null;
    if (policy === "cash") {
      row = book.map(function () { return 0; });
      row[width - 1] = 10000;
      return row;
    }
    if (policy === "flip") {
      var delta = book.map(function (value, index) { return value - prev[index]; });
      var pos = 0;
      var neg = 0;
      delta.forEach(function (value, index) {
        if (value > delta[pos]) pos = index;
        if (value < delta[neg]) neg = index;
      });
      if (pos === neg || delta[pos] <= 0 || delta[neg] >= 0) return null;
      row = book.slice();
      var swap = row[pos];
      row[pos] = row[neg];
      row[neg] = swap;
      return toBps(row.map(function (value) { return value / 10000; }));
    }
    if (policy === "treasury" || policy === "credit") {
      var flags = mask(ids, policy);
      var held = 0;
      flags.forEach(function (flag, index) { if (flag) held += book[index]; });
      if (held < 1) return null;
      var base = [];
      var baseSum = 0;
      flags.forEach(function (flag, index) {
        var value = flag ? Math.max(0, book[index]) : 0;
        base.push(value);
        baseSum += value;
      });
      var risky = 0;
      book.forEach(function (value, index) { if (index < width - 1) risky += Math.max(0, value); });
      if (baseSum <= 0) return null;
      var out = book.map(function () { return 0; });
      flags.forEach(function (flag, index) {
        if (flag) out[index] = base[index] / baseSum * risky;
      });
      out[width - 1] = Math.max(0, 10000 - out.slice(0, -1).reduce(function (sum, value) { return sum + value; }, 0));
      return toBps(out.map(function (value) { return value / 10000; }));
    }
    if (policy.indexOf("shift") === 0) {
      var move = parseInt(policy.replace("shift", ""), 10) || 0;
      var top = 0;
      for (var i = 1; i < width - 1; i++) if (book[i] > book[top]) top = i;
      row = book.slice();
      var taken = Math.min(move, row[top]);
      row[top] -= taken;
      row[width - 1] += taken;
      return toBps(row.map(function (value) { return value / 10000; }));
    }
    if (policy.indexOf("sleeve:") === 0) {
      var name = policy.split(":")[1];
      var at = ids.indexOf(name);
      if (at < 0) return null;
      if (live && at < live.length && !live[at]) return null;
      row = book.map(function () { return 0; });
      row[at] = 2500;
      row[width - 1] = 7500;
      return row;
    }
    return null;
  }

  function mixBps(style, built) {
    var keys = Object.keys(style).filter(function (key) { return style[key] > 0 && built[key]; });
    if (!keys.length) return null;
    var total = keys.reduce(function (sum, key) { return sum + style[key]; }, 0);
    var width = built[keys[0]].length;
    var acc = [];
    for (var i = 0; i < width; i++) acc.push(0);
    keys.forEach(function (key) {
      built[key].forEach(function (value, index) {
        acc[index] += (style[key] / total) * value;
      });
    });
    return toBps(acc.map(function (value) { return value / 10000; }));
  }

  function zeroDead(row, live) {
    if (!row || !live) return row;
    var cleaned = row.slice();
    var changed = false;
    for (var i = 0; i < live.length; i++) {
      if (!live[i] && cleaned[i]) {
        cleaned[i] = 0;
        changed = true;
      }
    }
    if (!changed) return cleaned;
    var total = cleaned.reduce(function (sum, value) { return sum + value; }, 0);
    if (total <= 0) {
      var cash = cleaned.map(function () { return 0; });
      cash[cash.length - 1] = 10000;
      return cash;
    }
    return toBps(cleaned.map(function (value) { return value / total; }));
  }

  function styleFill(ids, bookRows, mvRows, ewRows, liveRows, questionIndexes, answers) {
    var count = bookRows.length;
    var width = ids.length;
    var cash = [];
    for (var i = 0; i < width - 1; i++) cash.push(0);
    cash.push(10000);
    var answered = questionIndexes.filter(function (day) { return answers[day]; }).sort(function (a, b) { return a - b; });
    var out = [];
    for (var day = 0; day < count; day++) out.push(null);
    if (!answered.length) return out;
    var first = answered[0];
    var bookEnd = answered[answered.length - 1];
    for (day = 0; day < first; day++) out[day] = cash.slice();
    for (day = first; day <= bookEnd; day++) {
      if (answers[day]) {
        out[day] = answers[day].bps.slice();
        continue;
      }
      var prior = answered.filter(function (q) { return q < day; });
      if (!prior.length) {
        out[day] = cash.slice();
        continue;
      }
      var used = answered.filter(function (q) { return q <= prior[prior.length - 1]; });
      var counts = {};
      used.forEach(function (qday) {
        var policy = answers[qday].policy;
        counts[policy] = (counts[policy] || 0) + 1;
      });
      var style = {book: ((counts.book || 0) + 1) / (used.length + 1)};
      Object.keys(counts).forEach(function (policy) {
        if (policy !== "book") style[policy] = counts[policy] / (used.length + 1);
      });
      var prev = day ? bookRows[day - 1] : cash;
      var built = {};
      Object.keys(style).forEach(function (policy) {
        built[policy] = policyRow(policy, ids, bookRows[day], prev, mvRows[day], ewRows[day], liveRows[day]);
      });
      var mixed = mixBps(style, built);
      out[day] = zeroDead(mixed || bookRows[day].slice(), liveRows[day]);
    }
    return out;
  }

  function manualFill(count, edits) {
    var out = [];
    var day;
    for (day = 0; day < count; day++) out.push(null);
    var marks = (edits || []).filter(function (edit) {
      return edit && edit.day >= 0 && edit.day < count && edit.bps;
    }).slice().sort(function (a, b) { return a.day - b.day; });
    marks.forEach(function (edit, index) {
      var stop = index + 1 < marks.length ? marks[index + 1].day : count;
      for (day = edit.day; day < stop; day++) out[day] = edit.bps.slice();
    });
    return out;
  }

  function assemblePath(ids, bookRows, mvRows, ewRows, liveRows, questionIndexes, answers, edits) {
    var styleRows = styleFill(ids, bookRows, mvRows, ewRows, liveRows, questionIndexes, answers || {});
    var answered = (questionIndexes || []).filter(function (day) { return answers && answers[day]; }).sort(function (a, b) { return a - b; });
    if (!answered.length) return manualFill(styleRows.length, edits);
    var first = answered[0];
    var last = answered[answered.length - 1];
    var out = styleRows.map(function (row) { return row ? row.slice() : null; });
    (edits || []).forEach(function (edit) {
      if (!edit || edit.day < first || edit.day > last || !out[edit.day]) return;
      out[edit.day] = edit.bps.slice();
    });
    return out;
  }

  return {styleFill: styleFill, toBps: toBps, assemblePath: assemblePath};
});
