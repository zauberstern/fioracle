(function () {
  var banner = document.getElementById("gate-banner");
  var status = document.getElementById("status");
  var body = document.getElementById("desk-body");
  var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var CASH = { US_CASH: 1, US_CASH_RETURN: 1, cash_allocation: 1 };
  var state = { bundle: null, day: null, asset: null, chart: null };

  function plainDate(iso) {
    var p = String(iso).slice(0, 10).split("-");
    return Number(p[2]) + " " + months[Number(p[1]) - 1] + " " + p[0];
  }

  function pct(n) {
    return (n * 100).toFixed(1) + "%";
  }

  function showEmpty(line) {
    body.hidden = true;
    status.textContent = line;
  }

  function slice() {
    var bundle = state.bundle;
    if (!bundle) return null;
    if (bundle.by_date && state.day && bundle.by_date[state.day]) return bundle.by_date[state.day];
    return { assets: bundle.assets || [], weights: bundle.weights || [] };
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
    var view = slice();
    var bundle = state.bundle;
    var assets = (view && view.assets) || [];
    var weights = (view && view.weights) || [];
    var cap = Number(bundle.max_weight);
    var tbody = document.querySelector("#probs tbody");
    tbody.textContent = "";
    assets.forEach(function (row) {
      var tr = document.createElement("tr");
      var cash = !!CASH[row.id];
      var cells = [
        row.label || row.id,
        cash || row.p_calm == null ? "No probability" : pct(row.p_calm),
        cash || row.p_inflationary == null ? "No probability" : pct(row.p_inflationary),
        cash || row.p_crisis == null ? "No probability" : pct(row.p_crisis)
      ];
      cells.forEach(function (text) {
        var td = document.createElement("td");
        td.textContent = text;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    var wbody = document.querySelector("#weights tbody");
    var sumLine = document.getElementById("weight-sum");
    var bars = document.getElementById("bars");
    wbody.textContent = "";
    bars.textContent = "";
    if (state.chart) {
      state.chart.destroy();
      state.chart = null;
    }
    if (!weightsOk(weights, cap)) {
      sumLine.textContent = "Weights withheld. The stored book is not a long-only fixed-income book.";
    } else {
      var sum = weights.reduce(function (a, w) { return a + w.weight; }, 0);
      sumLine.textContent = "Weight sum " + sum.toFixed(6) + ". Cash is outside the sleeve cap of " + cap + ".";
      weights.forEach(function (w) {
        var tr = document.createElement("tr");
        var name = document.createElement("td");
        var val = document.createElement("td");
        name.textContent = w.label || w.id;
        val.textContent = w.weight.toFixed(4);
        tr.appendChild(name);
        tr.appendChild(val);
        wbody.appendChild(tr);
      });
      var labels = weights.map(function (w) { return w.label || w.id; });
      var values = weights.map(function (w) { return w.weight; });
      state.chart = new uPlot({
        width: Math.min(840, bars.clientWidth || 840),
        height: 220,
        axes: [{}, { size: 40 }],
        scales: { x: { time: false } },
        series: [
          {},
          { paths: uPlot.paths.bars({ size: [0.6, 100] }), stroke: "#c4a574", fill: "#c4a574" }
        ]
      }, [labels.map(function (_, i) { return i; }), values], bars);
    }

    var select = document.getElementById("asset");
    var previous = state.asset;
    select.textContent = "";
    var trees = bundle.trees || [];
    assets.forEach(function (row) {
      if (CASH[row.id]) return;
      if (trees.indexOf(row.id) === -1) return;
      var opt = document.createElement("option");
      opt.value = row.id;
      opt.textContent = row.label || row.id;
      select.appendChild(opt);
    });
    if (previous && trees.indexOf(previous) !== -1) select.value = previous;
    state.asset = select.value || null;
    loadSchema(state.asset);
  }

  function loadSchema(assetId) {
    var list = document.getElementById("schema");
    var note = document.getElementById("path-note");
    var button = document.getElementById("open-path");
    var modelLink = document.getElementById("download-model");
    var schemaLink = document.getElementById("download-schema");
    var snippet = document.getElementById("snippet");
    list.textContent = "";
    if (!assetId) {
      note.textContent = "No stored path for this sleeve.";
      button.classList.add("is-off");
      button.removeAttribute("href");
      snippet.textContent = "";
      return;
    }
    modelLink.href = "data/trees/" + assetId + ".json";
    modelLink.setAttribute("download", assetId + ".json");
    schemaLink.href = "data/trees/" + assetId + ".schema.json";
    schemaLink.setAttribute("download", assetId + ".schema.json");
    button.classList.remove("is-off");
    button.href = "../world3d/#" + encodeURIComponent(assetId);
    note.textContent = "";
    snippet.textContent = [
      "import json",
      "import pandas as pd",
      "import xgboost as xgb",
      "",
      "booster = xgb.Booster()",
      "booster.load_model(\"" + assetId + ".json\")",
      "schema = json.load(open(\"" + assetId + ".schema.json\"))",
      "row = pd.DataFrame([values], columns=schema[\"feature_names\"])",
      "print(booster.predict(xgb.DMatrix(row)))"
    ].join("\n");
    fetch("data/trees/" + assetId + ".schema.json")
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (schema) {
        var names = (schema && schema.feature_names) || [];
        names.forEach(function (name) {
          var li = document.createElement("li");
          li.textContent = name;
          list.appendChild(li);
        });
      })
      .catch(function () {});
  }

  function bind() {
    var dates = document.getElementById("dates");
    dates.textContent = "";
    (state.bundle.dates || [state.bundle.as_of]).forEach(function (day) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = plainDate(day);
      button.setAttribute("aria-pressed", day === state.day ? "true" : "false");
      button.addEventListener("click", function () {
        state.day = day;
        bind();
        render();
      });
      dates.appendChild(button);
    });
    document.getElementById("asset").onchange = function (event) {
      state.asset = event.target.value;
      loadSchema(state.asset);
    };
  }

  fetch("../gate-status.json")
    .then(function (res) {
      if (!res.ok) throw new Error("missing");
      return res.json();
    })
    .then(function (gate) {
      if (!gate || gate.cleared !== false) {
        banner.textContent = "Gate status: " + (gate && gate.cleared);
        showEmpty("Dates, probabilities, and weights stay hidden.");
        return null;
      }
      banner.textContent = "Research software. Not investment advice. No live client capital. Gate status: cleared: false.";
      return fetch("data/baseline.json");
    })
    .then(function (res) {
      if (!res) return null;
      if (!res.ok) throw new Error("baseline");
      return res.json();
    })
    .then(function (bundle) {
      if (!bundle) return;
      if (!bundle.as_of) throw new Error("baseline");
      state.bundle = bundle;
      state.day = bundle.as_of;
      body.hidden = false;
      status.textContent = "Saved run dated " + plainDate(bundle.as_of) + ".";
      bind();
      render();
    })
    .catch(function (err) {
      if (String(err && err.message) === "missing") {
        banner.textContent = "The gate file could not be read.";
      }
      showEmpty("No saved forecast in this folder.");
    });
})();
