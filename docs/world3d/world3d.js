(function () {
  var note = document.getElementById("note");
  var title = document.getElementById("title");
  var pathList = document.getElementById("path");
  var canvas = document.getElementById("scene");
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function walk(tree, names, row) {
    var nodes = [];
    var i = 0;
    var guard = 0;
    while (guard++ < 80) {
      if (tree.left_children[i] === -1) {
        nodes.push({ leaf: tree.base_weights[i] });
        return nodes;
      }
      var featureIndex = tree.split_indices[i];
      var threshold = tree.split_conditions[i];
      var value = row[featureIndex];
      var goLeft = value == null ? tree.default_left[i] === 1 : value < threshold;
      nodes.push({
        feature: names[featureIndex] || ("feature " + featureIndex),
        threshold: threshold,
        side: goLeft ? "left" : "right"
      });
      i = goLeft ? tree.left_children[i] : tree.right_children[i];
    }
    return nodes;
  }

  function listPath(nodes) {
    pathList.textContent = "";
    nodes.forEach(function (node) {
      var li = document.createElement("li");
      if (node.leaf != null) li.textContent = "Leaf vote " + Number(node.leaf).toFixed(4);
      else li.textContent = node.feature + " " + node.side + " of " + Number(node.threshold).toFixed(4);
      pathList.appendChild(li);
    });
  }

  function draw(probs, weights, nodes) {
    var renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
    } catch (err) {
      note.textContent = "The 3D view did not start.";
      listPath(nodes);
      return;
    }
    renderer.setSize(880, 480, false);
    renderer.setClearColor(0x07080c, 1);
    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(40, 880 / 480, 0.1, 100);
    camera.position.set(0, 1.2, 8);
    var light = new THREE.DirectionalLight(0xffffff, 1.1);
    light.position.set(2, 4, 3);
    scene.add(light);
    scene.add(new THREE.AmbientLight(0x334455, 0.8));
    var colors = [0x9aa3ad, 0xc4a574, 0xc4843a];
    probs.forEach(function (p, i) {
      var radius = 0.25 + Math.max(0, p) * 0.9;
      var mesh = new THREE.Mesh(
        new THREE.SphereGeometry(radius, 28, 18),
        new THREE.MeshStandardMaterial({ color: colors[i], roughness: 0.55, metalness: 0.15 })
      );
      mesh.position.set((i - 1) * 2.2, 1.1, 0);
      scene.add(mesh);
    });
    weights.forEach(function (w, i) {
      var h = Math.max(0.02, w.weight) * 2.2;
      var box = new THREE.Mesh(
        new THREE.BoxGeometry(0.18, h, 0.18),
        new THREE.MeshStandardMaterial({ color: 0xc4a574, roughness: 0.7 })
      );
      box.position.set(-3 + i * 0.45, -1.4 + h / 2, 0);
      scene.add(box);
    });
    var group = new THREE.Group();
    nodes.forEach(function (node, i) {
      if (node.leaf != null) return;
      var dot = new THREE.Mesh(
        new THREE.SphereGeometry(0.08, 12, 8),
        new THREE.MeshStandardMaterial({ color: 0xe8ecf4 })
      );
      dot.position.set(-2 + i * 0.7, -0.2, node.side === "left" ? 0.4 : -0.4);
      group.add(dot);
    });
    scene.add(group);
    var yaw = 0;
    var dragging = false;
    var lastX = 0;
    if (!reduced) {
      canvas.addEventListener("pointerdown", function (event) {
        dragging = true;
        lastX = event.clientX;
      });
      window.addEventListener("pointerup", function () { dragging = false; });
      canvas.addEventListener("pointermove", function (event) {
        if (!dragging) return;
        yaw += (event.clientX - lastX) * 0.01;
        lastX = event.clientX;
      });
    }
    function frame() {
      scene.rotation.y = yaw;
      renderer.render(scene, camera);
      if (!reduced) requestAnimationFrame(frame);
    }
    frame();
    if (reduced) listPath(nodes);
  }

  var wanted = decodeURIComponent((location.hash || "").replace(/^#/, ""));
  fetch("../sandbox/data/baseline.json")
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (bundle) {
      if (!bundle) {
        note.textContent = "This decision was not exported.";
        return;
      }
      var day = bundle.as_of;
      var view = (bundle.by_date && bundle.by_date[day]) || bundle;
      var assets = view.assets || [];
      var match = assets.filter(function (row) { return row.id === wanted; })[0];
      var asset = match || assets[0];
      if (!match) note.textContent = "This decision was not exported.";
      if (!asset) return;
      title.textContent = asset.label || asset.id;
      var probs = [
        Number(asset.p_calm) || 0,
        Number(asset.p_inflationary) || 0,
        Number(asset.p_crisis) || 0
      ];
      var weights = (view.weights || []).filter(function (w) { return !w.features_only; });
      if (!wanted || !(bundle.trees || []).includes(wanted) && !match) {
        draw(probs, weights, []);
        return;
      }
      var id = match ? match.id : wanted;
      return Promise.all([
        fetch("../sandbox/data/trees/" + id + ".json").then(function (r) { return r.ok ? r.json() : null; }),
        fetch("../sandbox/data/trees/" + id + ".schema.json").then(function (r) { return r.ok ? r.json() : null; })
      ]).then(function (pair) {
        var model = pair[0];
        var schema = pair[1];
        var row = schema && schema.feature_row;
        var names = (schema && schema.feature_names) || (model && model.learner && model.learner.feature_names) || [];
        var trees = model && model.learner && model.learner.gradient_booster && model.learner.gradient_booster.model && model.learner.gradient_booster.model.trees;
        var nodes = [];
        if (trees && trees[0] && row && row.length) nodes = walk(trees[0], names, row);
        else note.textContent = note.textContent || "No stored path for this sleeve.";
        listPath(nodes);
        draw(probs, weights, nodes);
      });
    })
    .catch(function () {
      note.textContent = "The 3D view did not start.";
    });
})();
