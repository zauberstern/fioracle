(function () {
  var status = document.getElementById("status");
  var desk = document.getElementById("desk");
  var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var CASH = { US_CASH: 1, US_CASH_RETURN: 1, cash_allocation: 1 };
  var COLORS = { calm: "#7E9AA6", inflationary: "#C4A15A", crisis: "#C47A68" };
  var state = { bundle: null, day: null, asset: null, hold: null };

  function plainDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso).trim());
    if (!m) return String(iso);
    var month = months[Number(m[2]) - 1];
    var day = Number(m[3]);
    if (!month || !day) return String(iso);
    return day + " " + month + " " + m[1];
  }

  function slice(day) {
    var bundle = state.bundle;
    if (bundle.by_date && bundle.by_date[day]) return bundle.by_date[day];
    return { assets: bundle.assets || [], weights: bundle.weights || [] };
  }

  function mixedDays(bundle) {
    return (bundle.dates || []).filter(function (day) {
      return (slice(day).weights || []).some(function (w) {
        return !w.cash && Math.abs(w.weight) > 0.01;
      });
    });
  }

  function sameWeights(a, b) {
    if (!a || !b || a.length !== b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i].id !== b[i].id) return false;
      if (Math.abs(a[i].weight - b[i].weight) > 1e-6) return false;
    }
    return true;
  }

  function leading(asset) {
    if (!asset || CASH[asset.id]) return null;
    var rows = [
      ["calm", asset.p_calm],
      ["inflationary", asset.p_inflationary],
      ["crisis", asset.p_crisis]
    ];
    var best = rows[0];
    for (var i = 1; i < rows.length; i++) {
      if (rows[i][1] > best[1]) best = rows[i];
    }
    return best[0];
  }

  function weightsOk(weights, cap) {
    if (!weights || !weights.length) return false;
    var sum = 0;
    for (var i = 0; i < weights.length; i++) {
      var w = weights[i];
      if (!isFinite(w.weight) || w.weight < -1e-8) return false;
      if (w.features_only) return false;
      if (!w.cash && !CASH[w.id] && w.weight > cap + 1e-6) return false;
      sum += w.weight;
    }
    return Math.abs(sum - 1) < 5e-7;
  }

  function render() {
    var bundle = state.bundle;
    var open = slice(state.day);
    var assets = open.assets || [];
    var liveWeights = open.weights || [];
    var shown = state.hold ? state.hold.weights : liveWeights;
    var cap = Number(bundle.max_weight);
    var select = document.getElementById("asset");
    var previous = state.asset;
    select.textContent = "";
    assets.forEach(function (row) {
      if (CASH[row.id]) {
        if (row.id !== "US_CASH") return;
      } else if ((bundle.trees || []).indexOf(row.id) === -1) {
        return;
      }
      var opt = document.createElement("option");
      opt.value = row.id;
      opt.textContent = row.label || row.id;
      select.appendChild(opt);
    });
    if (previous) select.value = previous;
    if (!select.value || (select.value === "US_CASH" && !previous)) {
      select.value = "US_10Y_GOV_BOND";
    }
    state.asset = select.value || null;
    var asset = assets.filter(function (row) { return row.id === state.asset; })[0];
    var word = asset ? leading(asset) : null;
    var ring = document.getElementById("ring-stroke");
    var label = document.getElementById("ring-label");
    if (!asset || CASH[state.asset]) {
      ring.setAttribute("stroke", "#3E4642");
      label.textContent = "No probability.";
    } else {
      ring.setAttribute("stroke", COLORS[word] || "#3E4642");
      label.textContent = word ? word.charAt(0).toUpperCase() + word.slice(1) : "No probability.";
    }
    var probs = document.getElementById("probs");
    probs.textContent = "";
    if (!asset || CASH[asset.id]) {
      var empty = document.createElement("p");
      empty.className = "prob";
      empty.textContent = "No probability.";
      probs.appendChild(empty);
    } else {
      [["Calm", asset.p_calm, "calm"], ["Inflationary", asset.p_inflationary, "inflationary"], ["Crisis", asset.p_crisis, "crisis"]].forEach(function (row) {
        var line = document.createElement("p");
        line.className = "prob";
        var swatch = document.createElement("span");
        swatch.className = "swatch";
        swatch.style.background = COLORS[row[2]];
        var name = document.createElement("span");
        name.textContent = row[0];
        var num = document.createElement("span");
        num.textContent = (row[1] * 100).toFixed(1) + "%";
        line.appendChild(swatch);
        line.appendChild(name);
        line.appendChild(num);
        probs.appendChild(line);
      });
    }
    var download = document.getElementById("download");
    if (state.asset && (bundle.trees || []).indexOf(state.asset) !== -1) {
      download.hidden = false;
      download.href = "data/trees/" + state.asset + ".json";
      download.setAttribute("download", state.asset + ".json");
    } else {
      download.hidden = true;
    }
    var bars = document.getElementById("bars");
    var body = document.querySelector("#weights tbody");
    var sumLine = document.getElementById("weight-sum");
    bars.textContent = "";
    body.textContent = "";
    if (!weightsOk(liveWeights, cap)) {
      sumLine.textContent = "Weights withheld. The stored book is not a long-only fixed-income book.";
    } else {
      var sum = 0;
      shown.forEach(function (w) { sum += w.weight; });
      sumLine.textContent = "Weight sum " + sum.toFixed(6) + ". Cash is outside the sleeve cap of " + cap + ".";
      shown.forEach(function (w) {
        if (Math.abs(w.weight) < 0.005 && !w.cash) return;
        var live = liveWeights.filter(function (item) { return item.id === w.id; })[0];
        var moved = state.hold && live && Math.abs(live.weight - w.weight) > 0.01;
        var row = document.createElement("div");
        row.className = "bar-row" + (moved ? " tick" : "");
        var name = document.createElement("span");
        name.textContent = w.label || w.id;
        var track = document.createElement("div");
        track.className = "bar";
        var fill = document.createElement("span");
        fill.style.width = Math.min(100, Math.abs(w.weight) * 100) + "%";
        track.appendChild(fill);
        var num = document.createElement("span");
        num.textContent = w.weight.toFixed(2);
        row.appendChild(name);
        row.appendChild(track);
        row.appendChild(num);
        bars.appendChild(row);
        var tr = document.createElement("tr");
        var td1 = document.createElement("td");
        var td2 = document.createElement("td");
        td1.textContent = w.label || w.id;
        td2.textContent = w.weight.toFixed(4);
        tr.appendChild(td1);
        tr.appendChild(td2);
        body.appendChild(tr);
      });
    }
    var line = plainDate(state.day) + ".";
    if (state.day !== bundle.as_of) line += " The saved run ends " + plainDate(bundle.as_of) + ".";
    if (state.hold && sameWeights(state.hold.weights, liveWeights)) {
      var us10 = assets.filter(function (a) { return a.id === "US_10Y_GOV_BOND"; })[0];
      var ust = assets.filter(function (a) { return a.id === "BBG_US_TREASURY"; })[0];
      if (us10 && ust && leading(us10) === "calm" && leading(ust) === "crisis") {
        line = "Weights match " + plainDate(state.hold.day) + ", and on " + plainDate(state.day) + " US10Y is calm and UST is crisis.";
      } else {
        line = "Weights match " + plainDate(state.hold.day) + ".";
      }
    } else if (state.hold) {
      line = "Held book is " + plainDate(state.hold.day) + ". Open date is " + plainDate(state.day) + ".";
    }
    status.textContent = line;
    document.querySelectorAll("#dates button").forEach(function (button) {
      button.setAttribute("aria-pressed", button.dataset.day === state.day ? "true" : "false");
    });
  }

  function bindDates() {
    var box = document.getElementById("dates");
    box.textContent = "";
    (state.bundle.dates || []).forEach(function (day) {
      var button = document.createElement("button");
      button.type = "button";
      button.dataset.day = day;
      button.textContent = plainDate(day);
      button.addEventListener("click", function () {
        state.day = day;
        render();
      });
      box.appendChild(button);
    });
  }

  document.getElementById("asset").addEventListener("change", function (event) {
    state.asset = event.target.value;
    render();
  });
  document.getElementById("hold").addEventListener("click", function () {
    if (state.hold && state.hold.day === state.day) {
      state.hold = null;
      this.setAttribute("aria-pressed", "false");
    } else {
      state.hold = { day: state.day, weights: slice(state.day).weights };
      this.setAttribute("aria-pressed", "true");
    }
    render();
  });
  window.addEventListener("keydown", function (event) {
    var tag = event.target && event.target.tagName;
    if (tag === "SELECT" || tag === "INPUT" || tag === "TEXTAREA" || tag === "BUTTON") return;
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    var dates = state.bundle.dates || [];
    var i = dates.indexOf(state.day);
    if (i < 0) return;
    var next = event.key === "ArrowRight" ? Math.min(dates.length - 1, i + 1) : Math.max(0, i - 1);
    state.day = dates[next];
    render();
  });

  fetch("data/baseline.json")
    .then(function (res) {
      if (!res.ok) throw new Error("baseline");
      return res.json();
    })
    .then(function (bundle) {
      if (!bundle || !bundle.as_of) throw new Error("baseline");
      state.bundle = bundle;
      var mixed = mixedDays(bundle);
      state.day = mixed.length ? mixed[mixed.length - 1] : bundle.as_of;
      desk.hidden = false;
      bindDates();
      render();
    })
    .catch(function () {
      status.textContent = "No saved forecast in this folder.";
    });
})();
