(function () {
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var TREES = {
    BBG_US_CORPORATE: 1, BBG_US_HIGH_YIELD: 1, BBG_US_TREASURY: 1,
    GOLD: 1, US_10Y_GOV_BOND: 1, US_BOND_AGG: 1
  };
  var LINES = [
    {key: "yours", label: "Yours", color: "#1C1B19", on: true, own: true, width: 2},
    {key: "book", label: "FIOracle", color: "#3D6B8C", on: true, width: 1},
    {key: "equal_weight", label: "Equal weight", color: "#8A8478", on: true, width: 1},
    {key: "sixty_forty", label: "60/40", color: "#9A7430", on: true, width: 1},
    {key: "mv", label: "Mean-variance", color: "#5C7C8A", on: false, width: 1},
    {key: "agg_buy_hold", label: "Aggregate", color: "#8C6E2E", on: false, width: 1},
    {key: "true_ew_buy_hold", label: "Buy and hold", color: "#7A756C", on: false, width: 1},
    {key: "barbell", label: "Barbell", color: "#6E8B74", on: false, width: 1},
    {key: "diversified_core", label: "Diversified core", color: "#8A6A62", on: false, width: 1},
    {key: "inv_vol", label: "Inverse vol", color: "#5E6E78", on: false, width: 1},
    {key: "unconditional_minvar", label: "Unconditional min-variance", color: "#4E6A78", on: false, width: 1},
    {key: "unconditional_mvo", label: "Unconditional mean-variance", color: "#6A5870", on: false, width: 1},
    {key: "cash", label: "Cash", color: "#9A948A", on: false, width: 1},
    {key: "ghost", label: "Matched answers", color: "#A85C4C", on: false, own: true, width: 1}
  ];
  var FACE = {
    US_CASH: {mark: "🇺🇸", plain: "US T-bills", hint: "US Treasury bills. Short US government paper that pays a cash-like yield."},
    US_10Y_GOV_BOND: {mark: "🇺🇸", plain: "US 10-year", hint: "US 10-year Treasury. A single US government note around ten years."},
    ISHARES_20Y_TREASURY: {mark: "🇺🇸", plain: "Long US Treasuries", hint: "iShares 20+ Year Treasury (TLT). US government bonds with 20 years or more left."},
    ISHARES_7_10Y_TREASURY: {mark: "🇺🇸", plain: "Medium US Treasuries", hint: "iShares 7-10 Year Treasury (IEF). US government notes around 7 to 10 years."},
    ISHARES_1_3Y_TREASURY: {mark: "🇺🇸", plain: "Short US Treasuries", hint: "iShares 1-3 Year Treasury (SHY). US government notes around 1 to 3 years."},
    BBG_US_TREASURY: {mark: "🇺🇸", plain: "US Treasury index", hint: "Bloomberg US Treasury total return. US government notes and bonds across maturities."},
    US_BOND_AGG: {mark: "🇺🇸", plain: "US bond market", hint: "US Aggregate Bond. Treasuries, mortgages, and company bonds in one US taxable market book."},
    VANGUARD_TOTAL_BOND: {mark: "🇺🇸", plain: "US total bond", hint: "Vanguard Total Bond (BND). A fund of the broad US taxable bond market."},
    BBG_US_CORPORATE: {mark: "🇺🇸", plain: "US company bonds", hint: "Bloomberg US Corporate. Dollar bonds of US companies rated investment grade."},
    BBG_GLOBAL_AGG: {mark: "🌍", plain: "World bonds", hint: "Bloomberg Global Aggregate. Government and company bonds from many countries."},
    BBG_US_HIGH_YIELD: {mark: "🇺🇸", plain: "US junk bonds", hint: "Bloomberg US High Yield. Dollar bonds of US companies rated below investment grade."},
    BBG_EM_USD_AGG: {mark: "🌍", plain: "EM dollar bonds", hint: "Bloomberg EM USD Aggregate. Dollar bonds issued by emerging-market borrowers."},
    US_TIPS_0_5: {mark: "🇺🇸", plain: "US TIPS", hint: "US TIPS, 0 to 5 years. Short US government bonds whose principal tracks US consumer prices."},
    GLOBAL_ILB_0_5: {mark: "🌍", plain: "World inflation bonds", hint: "Global inflation-linked bonds, 0 to 5 years. Short government linkers from several countries."},
    ISHARES_SWISS_GOV_7_15: {mark: "🇨🇭", plain: "Swiss government", hint: "iShares Swiss government bonds, 7 to 15 years. Confederation notes in francs."},
    GOLD: {mark: "🥇", plain: "Gold", hint: "Gold. The metal, not a mining stock."},
    cash_allocation: {mark: "💵", plain: "Idle cash", hint: "Uninvested cash. Money not placed in any of the books."}
  };
  var root = document.body;
  var replayUrl = root.getAttribute("data-replay") || "sandbox/data/replay.json";
  var treeUrl = root.getAttribute("data-trees") || "sandbox/data/trees/";
  var status = document.getElementById("status");
  var bundle = null;
  var state = {focus: 0, answers: {}, edits: [], reveal: false};
  var cursor = 0;
  var weights = [];
  var yours = [];
  var plot = null;
  var silent = false;
  var draft = false;
  var note = "";
  var ids = [];

  function plainDate(iso) {
    var match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso).trim());
    if (!match) return String(iso);
    var month = MONTHS[Number(match[2]) - 1];
    var day = Number(match[3]);
    if (!month || !day) return String(iso);
    return day + " " + month + " " + match[1];
  }

  function cashRow() {
    var row = ids.map(function () { return 0; });
    row[row.length - 1] = 10000;
    return row;
  }

  function questionDay(index) {
    return bundle.dates.indexOf(bundle.questions[index].date);
  }

  function answeredDays() {
    return Object.keys(state.answers).map(function (key) { return questionDay(Number(key)); }).filter(function (day) { return day >= 0; }).sort(function (a, b) { return a - b; });
  }

  function bookEnd() {
    var days = answeredDays();
    return days.length ? days[days.length - 1] : null;
  }

  function same(a, b) {
    if (!a || !b || a.length !== b.length) return false;
    for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
    return true;
  }

  function rebuild() {
    var answers = {};
    Object.keys(state.answers).forEach(function (key) {
      var day = questionDay(Number(key));
      if (day >= 0) answers[day] = state.answers[key];
    });
    var questions = bundle.questions.map(function (_item, index) { return questionDay(index); });
    var edits = state.edits.map(function (edit) {
      return {day: bundle.dates.indexOf(edit.date), bps: edit.bps};
    }).filter(function (edit) { return edit.day >= 0; });
    weights = FIStyle.assemblePath(ids, bundle.book_bps, bundle.mv_bps, bundle.ew_bps, bundle.live, questions, answers, edits);
    yours = compound(weights);
  }

  function compound(rows) {
    var out = rows.map(function () { return null; });
    var start = -1;
    var end = -1;
    rows.forEach(function (row, day) {
      if (!row) return;
      if (start < 0) start = day;
      end = day;
    });
    if (start < 0) return out;
    var count = ids.length - 1;
    var prev = [];
    for (var i = 0; i < count; i++) prev.push(0);
    var value = 1;
    for (var day = start; day <= end; day++) {
      var bps = rows[day];
      if (!bps) continue;
      var gross = 0;
      var cost = 0;
      for (i = 0; i < count; i++) {
        var weight = bps[i] / 10000;
        var ret = bundle.returns[day][i];
        gross += weight * (ret == null ? 0 : ret);
        var delta = Math.abs(weight - prev[i]);
        if (delta > 1e-12) cost += delta * bundle.sleeves[i].cost;
        prev[i] = weight;
      }
      var rate = bundle.rf[day] == null ? 0 : bundle.rf[day];
      gross += (bps[count] / 10000) * rate;
      value *= 1 + gross - cost;
      out[day] = value;
    }
    return out;
  }

  function store() {
    localStorage.setItem("fioracle-sandbox-book-v3:" + bundle.sha256, JSON.stringify(state));
  }

  function loadState() {
    var raw = null;
    try { raw = JSON.parse(localStorage.getItem("fioracle-sandbox-book-v3:" + bundle.sha256) || "null"); }
    catch (err) { raw = null; }
    if (!raw || !raw.answers) return "";
    var ok = true;
    Object.keys(raw.answers).forEach(function (key) {
      var row = raw.answers[key];
      if (!row || !row.bps || row.bps.length !== ids.length) ok = false;
      else if (row.bps.reduce(function (sum, value) { return sum + value; }, 0) !== 10000) ok = false;
    });
    if (!ok) return "Saved answers from another FIOracle run were left unused.";
    state = raw;
    state.edits = state.edits || [];
    state.reveal = !!state.reveal;
    return "";
  }

  function pathAt(series, day) {
    if (!series || day == null || day < 0) return null;
    var value = series[day];
    return value == null || !isFinite(Number(value)) ? null : Number(value);
  }

  function paintFigure() {
    var end = bookEnd();
    var fig = document.getElementById("wealth-fig");
    var on = document.getElementById("wealth-on");
    var stats = document.getElementById("wealth-stats");
    var count = Object.keys(state.answers).length;
    var day = end;
    if (count === 0) {
      day = -1;
      for (var i = 0; i < yours.length; i++) if (yours[i] != null) day = i;
    }
    if (stats) stats.textContent = "";
    var yoursNow = pathAt(yours, day);
    fig.textContent = (yoursNow == null ? 0 : yoursNow).toFixed(1);
    if (day == null || day < 0 || yoursNow == null) {
      on.textContent = "Yours has no line yet.";
    } else if (count === 0) {
      on.textContent = "Wealth so far, through " + plainDate(bundle.dates[day]) + ". All questions are off.";
    } else if (count >= bundle.questions.length) {
      on.textContent = "All 20 dates answered, through " + plainDate(bundle.dates[day]) + ".";
    } else {
      on.textContent = "Wealth so far, through " + plainDate(bundle.dates[day]) + ". " + count + " of 20 dates answered.";
    }
    if (!stats) return;
    LINES.forEach(function (line) {
      if (!line.on && line.key !== "yours" && line.key !== "book" && line.key !== "equal_weight" && line.key !== "sixty_forty") return;
      if (line.key === "ghost") return;
      var series = line.key === "yours" ? yours : bundle.lines[line.key];
      var value = pathAt(series, day);
      var dt = document.createElement("dt");
      dt.textContent = line.label;
      var dd = document.createElement("dd");
      dd.textContent = (value == null ? 0 : value).toFixed(1);
      stats.appendChild(dt);
      stats.appendChild(dd);
    });
  }

  function paintStatus() {
    var date = bundle.dates[cursor];
    var line = plainDate(date) + ".";
    if (!Object.keys(state.answers).length) line += " All questions are off, so this path is the weights you apply.";
    if (draft) line += " Weights on this date stay unsaved until you press Apply.";
    else if (note) line += " " + note;
    var read = readRows();
    if (read && (read.bad || read.sum !== 10000)) line += " Weights must sum to 10000.";
    status.textContent = line;
    var when = document.getElementById("when");
    when.value = String(cursor);
    when.setAttribute("aria-valuetext", plainDate(date));
  }

  function readRows() {
    var inputs = document.querySelectorAll("#rows input");
    if (!inputs.length) return null;
    var bps = [];
    var sum = 0;
    var bad = false;
    inputs.forEach(function (input) {
      var value = input.disabled ? 0 : Number(input.value);
      if (!isFinite(value) || value < 0 || Math.round(value) !== value) bad = true;
      bps.push(bad ? 0 : value);
      sum += bad ? 0 : value;
    });
    return {bps: bps, sum: sum, bad: bad};
  }

  function heldRow() {
    if (weights[cursor]) return weights[cursor].slice();
    return cashRow();
  }

  function seenBefore(pos) {
    for (var day = 0; day < cursor; day++) {
      if (bundle.live[day][pos]) return true;
    }
    return false;
  }

  function sleeveFace(sleeve) {
    var face = FACE[sleeve.id];
    if (!face) return {mark: "", plain: sleeve.label, hint: sleeve.label};
    return face;
  }

  function paintRows() {
    var box = document.getElementById("rows");
    box.textContent = "";
    var bps = heldRow();
    bundle.sleeves.forEach(function (sleeve, pos) {
      var face = sleeveFace(sleeve);
      var row = document.createElement("label");
      row.className = "wrow";
      var name = document.createElement("span");
      name.textContent = (face.mark ? face.mark + " " : "") + face.plain;
      name.title = face.hint;
      var input = document.createElement("input");
      input.type = "number";
      input.min = "0";
      input.step = "1";
      input.value = String(bps[pos] || 0);
      var locked = pos < bundle.live[cursor].length && !bundle.live[cursor][pos];
      if (locked) {
        input.disabled = true;
        input.value = "0";
        row.className += " off";
        name.title = seenBefore(pos)
          ? "No price for " + face.plain + " on this date. " + face.hint
          : face.plain + " is not in FIOracle yet. " + face.hint;
      }
      input.addEventListener("input", function () {
        draft = true;
        note = "";
        paintBars();
        paintStatus();
      });
      row.appendChild(name);
      row.appendChild(input);
      box.appendChild(row);
    });
    paintBars();
  }

  function deadClear(bps) {
    for (var pos = 0; pos < bundle.live[cursor].length; pos++) {
      if (!bundle.live[cursor][pos] && bps[pos]) return false;
    }
    return true;
  }

  function paintBars() {
    var read = readRows();
    document.getElementById("sum").textContent = "Sum " + (read ? read.sum : 0);
    var end = bookEnd();
    var manual = end === null;
    var ready = read && !read.bad && read.sum === 10000 && deadClear(read.bps) && (manual || cursor <= end);
    document.getElementById("apply").disabled = !ready;
  }

  function formatFeature(row) {
    var value = Number(row.value);
    if (!isFinite(value)) return "";
    if (/_level$/.test(row.id) && value > 0 && value < 1) {
      return (value * 100).toFixed(2) + "%";
    }
    if (Math.abs(value) >= 100) return value.toFixed(1);
    if (Math.abs(value) >= 1) return value.toFixed(3);
    if (Math.abs(value) >= 0.01) return value.toFixed(4);
    return value.toExponential(2);
  }

  function shortFeature(row) {
    var label = String(row.label || row.id || "");
    return label
      .replace("average return", "Average return")
      .replace("drawdown", "Drawdown")
      .replace("Sortino", "Sortino")
      .replace(" change, ", " change - ")
      .replace(" change", " change")
      .replace(" level", " level")
      .replace(", 63-day", " - 63-day")
      .replace(", 21-day", " - 21-day");
      .replace(", 10-day", " 10d")
      .replace(", 252-day", " 1y")
      .replace("Geopolitical risk", "GPR")
      .replace("High-yield spread", "HY OAS")
      .replace("Unemployment", "U-rate")
      .replace("Inflation", "CPI")
      .replace("2-year yield", "2y")
      .replace("Yield curve slope", "slope")
      .replace("Stock-bond correlation", "S/B corr")
      .replace("VIX", "VIX");
  }

  function paintQuestion() {
    var item = bundle.questions[state.focus];
    document.getElementById("qcount").textContent = (state.focus + 1) + " of 20";
    document.getElementById("clear").disabled = !state.answers[state.focus];
    var box = document.getElementById("reading");
    box.textContent = "";
    var body = document.createElement("div");
    body.className = "qbody";
    var prose = document.createElement("div");
    prose.className = "qprose";
    var ask = null;
    var regime = null;
    item.prompt.split(/\n\n+/).forEach(function (para) {
      var line = document.createElement("p");
      line.textContent = para;
      if (para.indexOf("On ") === 0) {
        line.className = "lead";
        prose.appendChild(line);
      } else if (para.indexOf("The regime label") === 0) {
        line.className = "regime";
        regime = line;
      } else if (para.indexOf("Which weights") === 0) {
        line.className = "ask";
        ask = line;
      }
    });
    if (regime) prose.appendChild(regime);
    if (ask) prose.appendChild(ask);
    var picked = state.answers[state.focus];
    var missed = picked && !same(picked.bps, item.book_bps);
    var matchedPick = picked && same(picked.bps, item.book_bps);
    var grid = document.createElement("div");
    grid.className = "choices";
    item.choices.forEach(function (choice) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "choice";
      var isBook = same(choice.bps, item.book_bps);
      var isPicked = picked && picked.policy === choice.policy && same(picked.bps, choice.bps);
      if (matchedPick && isPicked) button.className += " match";
      else if (missed && isPicked) button.className += " miss";
      else if ((state.reveal || missed) && isBook) button.className += " match";
      var title = document.createElement("strong");
      title.textContent = choice.headline;
      button.appendChild(title);
      if (choice.sleeves) {
        var sub = document.createElement("span");
        sub.textContent = choice.sleeves;
        button.appendChild(sub);
      }
      button.addEventListener("click", function () { answer(choice); });
      grid.appendChild(button);
    });
    prose.appendChild(grid);
    if (missed) {
      var matched = item.choices.filter(function (choice) { return same(choice.bps, picked.bps); })[0];
      if (matched && matched.miss) {
        matched.miss.split(/\n\n+/).forEach(function (para) {
          var noteLine = document.createElement("p");
          noteLine.className = "miss";
          noteLine.textContent = para;
          prose.appendChild(noteLine);
        });
      }
    }
    var hud = document.createElement("aside");
    hud.className = "hud";
    hud.setAttribute("aria-label", "Inputs");
    var hudTitle = document.createElement("p");
    hudTitle.className = "hud-title";
    hudTitle.textContent = "Inputs used for this question";
    hud.appendChild(hudTitle);
    var list = document.createElement("dl");
    list.className = "hud-grid";
    (item.features || []).forEach(function (row) {
      var dt = document.createElement("dt");
      dt.textContent = shortFeature(row);
      dt.title = row.label || "";
      var dd = document.createElement("dd");
      dd.textContent = formatFeature(row);
      dd.title = row.label || "";
      list.appendChild(dt);
      list.appendChild(dd);
    });
    hud.appendChild(list);
    body.appendChild(prose);
    body.appendChild(hud);
    box.appendChild(body);
    var download = document.getElementById("download");
    var sleeve = TREES[item.sleeve] ? item.sleeve : "";
    download.hidden = !sleeve;
    if (sleeve) download.href = treeUrl + sleeve + ".json";
  }

  function paintDates() {
    var box = document.getElementById("dates");
    box.textContent = "";
    bundle.questions.forEach(function (item, index) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "qchip"
        + (index === state.focus ? " open" : "")
        + (state.answers[index] ? " done" : "");
      button.textContent = String(index + 1).padStart(2, "0");
      button.title = plainDate(item.date);
      button.setAttribute("data-date", plainDate(item.date));
      button.setAttribute("aria-label", "Question " + (index + 1) + ", " + plainDate(item.date));
      button.addEventListener("click", function () { jump(index); });
      button.addEventListener("mouseenter", function () {
        var tip = document.getElementById("qtip");
        var box = button.getBoundingClientRect();
        tip.textContent = plainDate(item.date);
        tip.hidden = false;
        tip.style.left = (box.left + box.width / 2) + "px";
        tip.style.top = box.top + "px";
      });
      button.addEventListener("mouseleave", function () {
        document.getElementById("qtip").hidden = true;
      });
      box.appendChild(button);
    });
  }

  function draw() {
    var host = document.getElementById("chart");
    var data = [bundle.dates.map(function (iso) { return Date.parse(iso + "T00:00:00Z") / 1000; })];
    LINES.forEach(function (line) {
      if (line.key === "yours") data.push(yours);
      else if (!line.on) data.push(yours.map(function () { return null; }));
      else if (line.key === "ghost") data.push(bundle.lines.book);
      else data.push(bundle.lines[line.key]);
    });
    var width = host.clientWidth || 700;
    var height = Math.max(120, (host.clientHeight || 280) - 16);
    if (!plot) {
      plot = new uPlot({
        width: width,
        height: height,
        legend: {show: false},
        series: [{}].concat(LINES.map(function (line) {
          return {label: line.label, stroke: line.color, width: line.width, value: function (u, v) { return v == null ? "" : Number(v).toFixed(1); }};
        })),
        axes: [
          {
            stroke: "#6E685F",
            grid: {show: false},
            values: function (u, vals) {
              return vals.map(function (raw) { return new Date(raw * 1000).getUTCFullYear(); });
            }
          },
          {
            label: "Wealth",
            size: 40,
            labelSize: 16,
            stroke: "#6E685F",
            grid: {stroke: "#E7E1D6"},
            values: function (u, vals) { return vals.map(function (v) { return Number(v).toFixed(1); }); }
          }
        ],
        scales: {x: {time: true}, y: {range: function () { return [0.8, 3.4]; }}},
        cursor: {drag: {x: false, y: false, setScale: false}},
        hooks: {setCursor: [function (u) {
          if (silent) return;
          if (u.cursor.idx == null) return;
          cursor = u.cursor.idx;
          if (u.cursor.event) {
            paintHover(cursor, u.cursor.left, u.cursor.top);
            draft = false;
            note = "This date shows the weights already held for it.";
            paintRows();
            paintStatus();
            paintFigure();
          }
        }]}
      }, data, host);
      var over = host.querySelector(".u-over") || host;
      over.addEventListener("mousemove", function () {
        if (!plot || plot.cursor.idx == null) return;
        paintHover(plot.cursor.idx, plot.cursor.left, plot.cursor.top);
      });
      over.addEventListener("mouseleave", hideHover);
    } else {
      plot.setSize({width: width, height: height});
      plot.setData(data);
    }
  }

  function hideHover() {
    var node = document.getElementById("hover");
    if (node) {
      node.hidden = true;
      node.textContent = "";
    }
  }

  function paintHover(index, left, top) {
    var node = document.getElementById("hover");
    var wrap = document.getElementById("chart-wrap");
    if (!node || !wrap || index == null || index < 0 || !bundle) return;
    var parts = [plainDate(bundle.dates[index])];
    LINES.forEach(function (line) {
      if (!line.on) return;
      var series = line.key === "yours" ? yours : (line.key === "ghost" ? bundle.lines.book : bundle.lines[line.key]);
      var value = series ? series[index] : null;
      if (value == null) parts.push(line.label + (line.key === "yours" ? " no line yet" : ""));
      else parts.push(line.label + " " + Number(value).toFixed(1));
    });
    node.hidden = false;
    node.textContent = parts.join("\n");
    var tipW = Math.max(node.offsetWidth, 120);
    var tipH = Math.max(node.offsetHeight, 36);
    var x = Number(left);
    var y = Number(top);
    if (!isFinite(x)) x = 48;
    if (!isFinite(y)) y = 24;
    var maxLeft = Math.max(8, wrap.clientWidth - tipW - 8);
    var maxTop = Math.max(4, wrap.clientHeight - tipH - 24);
    var nextLeft = Math.min(maxLeft, Math.max(8, x + 14));
    var nextTop = y - tipH - 10;
    if (nextTop < 4) nextTop = Math.min(maxTop, y + 14);
    node.style.left = nextLeft + "px";
    node.style.top = Math.min(maxTop, Math.max(4, nextTop)) + "px";
  }

  function pinCursor() {
    if (!plot) return;
    silent = true;
    plot.setCursor({left: plot.valToPos(plot.data[0][cursor], "x"), top: 20});
    silent = false;
  }

  function paint() {
    rebuild();
    paintDates();
    paintQuestion();
    paintRows();
    paintFigure();
    paintStatus();
    draw();
    pinCursor();
    hideHover();
  }

  function answer(choice) {
    state.answers[state.focus] = {policy: choice.policy, bps: choice.bps.slice()};
    var date = bundle.questions[state.focus].date;
    state.edits = state.edits.filter(function (edit) { return edit.date !== date; });
    cursor = questionDay(state.focus);
    draft = false;
    note = "This choice is saved and this question is answered.";
    store();
    paint();
  }

  function jump(index) {
    state.focus = index;
    cursor = questionDay(index);
    draft = false;
    note = "This date shows the weights already held for it.";
    store();
    paint();
  }

  function bootToggles() {
    var box = document.getElementById("toggles");
    LINES.forEach(function (line) {
      if (line.own || line.key === "book" || line.key === "equal_weight" || line.key === "sixty_forty") return;
      var label = document.createElement("label");
      var input = document.createElement("input");
      input.type = "checkbox";
      input.checked = line.on;
      input.addEventListener("change", function () {
        line.on = input.checked;
        draw();
        hideHover();
      });
      var mark = document.createElement("i");
      mark.style.background = line.color;
      label.appendChild(input);
      label.appendChild(mark);
      label.appendChild(document.createTextNode(line.label));
      box.appendChild(label);
    });
  }

  document.getElementById("nav-toggle").addEventListener("click", function () {
    var nav = document.getElementById("nav-links");
    var open = nav.classList.toggle("is-open");
    this.setAttribute("aria-expanded", open ? "true" : "false");
  });
  function setPathsOpen(open) {
    var panel = document.getElementById("other");
    panel.hidden = !open;
    document.getElementById("other-toggle").setAttribute("aria-expanded", open ? "true" : "false");
  }
  document.getElementById("other-toggle").addEventListener("click", function (event) {
    event.stopPropagation();
    setPathsOpen(document.getElementById("other").hidden);
  });
  document.addEventListener("click", function (event) {
    var menu = document.querySelector(".path-menu");
    if (!menu || document.getElementById("other").hidden) return;
    if (!menu.contains(event.target)) setPathsOpen(false);
  });
  document.getElementById("reveal-btn").addEventListener("click", function () {
    state.reveal = !state.reveal;
    store();
    paintQuestion();
  });
  document.getElementById("clear").addEventListener("click", function () {
    if (!state.answers[state.focus]) return;
    delete state.answers[state.focus];
    draft = false;
    note = "This question is unanswered, so the style no longer uses it.";
    store();
    paint();
  });
  document.getElementById("prev-q").addEventListener("click", function () { jump(Math.max(0, state.focus - 1)); });
  document.getElementById("next-q").addEventListener("click", function () { jump(Math.min(bundle.questions.length - 1, state.focus + 1)); });
  document.getElementById("when").addEventListener("input", function (event) {
    cursor = Number(event.target.value);
    draft = false;
    note = "This date shows the weights already held for it.";
    paintRows();
    paintStatus();
    hideHover();
    pinCursor();
  });
  document.getElementById("apply").addEventListener("click", function () {
    var read = readRows();
    var end = bookEnd();
    if (!read || read.bad || read.sum !== 10000 || !deadClear(read.bps) || (end !== null && cursor > end)) {
      paintStatus();
      return;
    }
    var date = bundle.dates[cursor];
    state.edits = state.edits.filter(function (edit) { return edit.date !== date; });
    state.edits.push({date: date, bps: read.bps});
    draft = false;
    note = "Saved the weights for this date.";
    store();
    paint();
  });
  window.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      setPathsOpen(false);
      return;
    }
    var tag = event.target && event.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (event.key >= "1" && event.key <= "8") return;
    if (event.key === "ArrowRight") cursor = Math.min(bundle.dates.length - 1, cursor + 1);
    else if (event.key === "ArrowLeft") cursor = Math.max(0, cursor - 1);
    else if (event.key === "]") { jump(Math.min(bundle.questions.length - 1, state.focus + 1)); return; }
    else if (event.key === "[") { jump(Math.max(0, state.focus - 1)); return; }
    else return;
    event.preventDefault();
    draft = false;
    note = "This date shows the weights already held for it.";
    paintRows();
    paintStatus();
    hideHover();
    pinCursor();
  });
  window.addEventListener("resize", function () {
    if (!plot) return;
    var node = document.getElementById("chart");
    plot.setSize({width: node.clientWidth, height: node.clientHeight});
  });

  fetch(replayUrl)
    .then(function (res) { if (!res.ok) throw new Error("replay"); return res.json(); })
    .then(function (payload) {
      bundle = payload;
      ids = payload.sleeves.map(function (sleeve) { return sleeve.id; });
      document.getElementById("note").textContent = payload.note;
      document.getElementById("when").max = String(payload.dates.length - 1);
      var warning = loadState();
      bootToggles();
      cursor = questionDay(state.focus || 0);
      note = warning;
      paint();
    })
    .catch(function (err) {
      status.textContent = err && err.message ? err.message : "No saved replay in this folder.";
    });
})();
