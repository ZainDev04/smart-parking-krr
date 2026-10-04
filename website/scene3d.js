/* The 3D journey: a night car park with the morning rush, a knowledge core for
   forward chaining, a proof tower for backward chaining, a walkable semantic
   network and twelve test beacons. The camera flies between them as the page
   scrolls. All content comes from data.js (exported from the engine).
   If anything here fails, the page falls back to the 2D version. */
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const D = window.KRR;
const UI = window.KRRUI;
const root = document.documentElement;

// CC0 car models from Kenney's Car Kit (website/models). Without them the scene
// still works with the simple built-in cars.
const MODEL_FILES = ["sedan", "sedan-sports", "suv", "suv-luxury", "hatchback-sports", "van", "cone"];
async function loadModels() {
  const loader = new GLTFLoader().setPath("models/");
  const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error("timed out")), 15000));
  try {
    const list = await Promise.race([Promise.all(MODEL_FILES.map((f) => loader.loadAsync(`${f}.glb`))), timeout]);
    return Object.fromEntries(MODEL_FILES.map((f, i) => [f, list[i].scene]));
  } catch (err) {
    console.warn("car models did not load, using simple cars", err);
    return null;
  }
}

async function boot() {
  if (!root.classList.contains("is-3d") || !D || !UI) return;
  const models = await loadModels();
  try { build(models); } catch (err) {
    console.error("3D scene failed, using the 2D page", err);
    document.getElementById("scene3d")?.remove();
    document.querySelector(".labels3d")?.remove();
    UI && UI.fallback2D();
  }
}

function build(models) {
  const small = matchMedia("(max-width: 760px), (pointer: coarse)").matches;
  // quality: "auto" starts high on desktops and drops to low if the frame rate is poor
  const QKEY = "krr-quality";
  let qPref = (() => { try { return localStorage.getItem(QKEY) || "auto"; } catch (e) { return "auto"; } })();
  if (!["auto", "high", "low"].includes(qPref)) qPref = "auto";
  let quality = qPref === "auto" ? (small ? "low" : "high") : qPref;
  const loaderFill = document.getElementById("loader-fill");
  const setLoad = (p) => { if (loaderFill) loaderFill.style.width = `${Math.round(p * 100)}%`; };
  setLoad(0.2);

  /* ---------------------------------------------------------------- */
  /* renderer, camera, post-processing                                 */
  /* ---------------------------------------------------------------- */
  const canvas = document.createElement("canvas");
  canvas.id = "scene3d";
  canvas.setAttribute("aria-hidden", "true");
  document.body.prepend(canvas);
  // logarithmic depth keeps the stacked ground layers (grass, car park, road, paint)
  // from flickering through each other at any camera distance
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: !small, powerPreference: "high-performance", logarithmicDepthBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, quality === "high" ? 1.5 : 1));
  renderer.setSize(innerWidth, innerHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = quality === "high";
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 0.5, 1500);
  camera.position.set(-140, 90, 160);

  const labels = new CSS2DRenderer();
  labels.setSize(innerWidth, innerHeight);
  labels.domElement.className = "labels3d";
  labels.domElement.setAttribute("aria-hidden", "true");
  document.body.prepend(labels.domElement);

  let composer = null, bloomPass = null;
  if (!small) {
    composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 }));
    composer.setSize(innerWidth, innerHeight);
    composer.addPass(new RenderPass(scene, camera));
    bloomPass = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.6, 0.45, 0.85);
    composer.addPass(bloomPass);
    composer.addPass(new OutputPass());
  }

  /* ---------------------------------------------------------------- */
  /* helpers                                                           */
  /* ---------------------------------------------------------------- */
  const tweens = new Set();
  const ease = {
    inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    out: (t) => 1 - Math.pow(1 - t, 3),
    back: (t) => 1 + 2.2 * Math.pow(t - 1, 3) + 1.2 * Math.pow(t - 1, 2),
    lin: (t) => t,
  };
  const tween = (dur, update, e = ease.inOut, delay = 0) => new Promise((resolve) => {
    tweens.add({ start: performance.now() + delay, dur, update, e, resolve });
  });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const label = (text, cls, parent, pos) => {
    const div = document.createElement("div");
    div.className = `label3d ${cls || ""}`;
    div.innerHTML = text;
    const o = new CSS2DObject(div);
    if (pos) o.position.copy(pos);
    parent.add(o);
    return o;
  };
  const glowTex = (() => {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const g = c.getContext("2d");
    const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    grd.addColorStop(0, "rgba(255,255,255,1)");
    grd.addColorStop(0.35, "rgba(255,255,255,0.45)");
    grd.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = grd;
    g.fillRect(0, 0, 128, 128);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  })();
  const glowPlane = (w, h, color, opacity) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h),
      new THREE.MeshBasicMaterial({ map: glowTex, color, transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false, polygonOffset: true, polygonOffsetFactor: 0, polygonOffsetUnits: -2 }));
    m.rotation.x = -Math.PI / 2;
    return m;
  };
  const hdr = (hex, k) => new THREE.Color(hex).multiplyScalar(k);

  /* ---------------------------------------------------------------- */
  /* sky, stars, ground, city                                          */
  /* ---------------------------------------------------------------- */
  const skyMat = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false,
    uniforms: { top: { value: new THREE.Color() }, mid: { value: new THREE.Color() }, bottom: { value: new THREE.Color() } },
    vertexShader: "varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }",
    fragmentShader: "uniform vec3 top; uniform vec3 mid; uniform vec3 bottom; varying vec3 vP;" +
      "void main(){ float h = vP.y; vec3 c = h > 0.08 ? mix(mid, top, smoothstep(0.08, 0.6, h)) : mix(bottom, mid, smoothstep(-0.2, 0.08, h)); gl_FragColor = vec4(c, 1.0); }",
  });
  scene.add(new THREE.Mesh(new THREE.SphereGeometry(1000, 32, 16), skyMat));

  const starGeo = new THREE.BufferGeometry();
  const starPos = [];
  for (let i = 0; i < 1600; i++) {
    const th = Math.random() * Math.PI * 2, ph = Math.acos(Math.random() * 0.9);
    starPos.push(900 * Math.sin(ph) * Math.cos(th), 900 * Math.cos(ph), 900 * Math.sin(ph) * Math.sin(th));
  }
  starGeo.setAttribute("position", new THREE.Float32BufferAttribute(starPos, 3));
  const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 1.6, sizeAttenuation: false, transparent: true, opacity: 0.85 });
  scene.add(new THREE.Points(starGeo, starMat));

  const ground = new THREE.Mesh(new THREE.PlaneGeometry(2400, 2400), new THREE.MeshStandardMaterial({ color: 0x0b0b0e, roughness: 0.96 }));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  // distant city with lit windows
  const winTex = (() => {
    const c = document.createElement("canvas");
    c.width = 64; c.height = 128;
    const g = c.getContext("2d");
    g.fillStyle = "#000"; g.fillRect(0, 0, 64, 128);
    for (let y = 4; y < 128; y += 8) for (let x = 4; x < 64; x += 8) {
      if (Math.random() < 0.38) { g.fillStyle = Math.random() < 0.8 ? "#ffd59a" : "#9fd3ff"; g.fillRect(x, y, 4, 4); }
    }
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  })();
  const nBuild = small ? 70 : 150;
  const city = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1),
    new THREE.MeshStandardMaterial({ color: 0x07080d, roughness: 0.8, emissive: 0xffffff, emissiveMap: winTex, emissiveIntensity: 0.9 }), nBuild);
  const m4 = new THREE.Matrix4();
  for (let i = 0; i < nBuild; i++) {
    const a = Math.random() * Math.PI * 2, r = 330 + Math.random() * 260;
    const h = 14 + Math.pow(Math.random(), 1.8) * 85, w = 12 + Math.random() * 22;
    m4.compose(new THREE.Vector3(Math.cos(a) * r - 20, h / 2, Math.sin(a) * r),
      new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.random() * Math.PI),
      new THREE.Vector3(w, h, w * (0.6 + Math.random() * 0.8)));
    city.setMatrixAt(i, m4);
  }
  scene.add(city);

  /* lights */
  const hemi = new THREE.HemisphereLight(0x5a6aa0, 0x07070a, 0.6);
  scene.add(hemi);
  const moon = new THREE.DirectionalLight(0xa9b8ff, 0.7);
  moon.position.set(-60, 90, 50);
  moon.castShadow = true;
  moon.shadow.mapSize.set(2048, 2048);
  moon.shadow.bias = -0.0006;
  moon.shadow.normalBias = 0.05;
  Object.assign(moon.shadow.camera, { left: -80, right: 60, top: 40, bottom: -40, near: 10, far: 260 });
  scene.add(moon);
  // soft reflections on paint and glass
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.22;
  setLoad(0.4);

  /* ---------------------------------------------------------------- */
  /* the car park                                                      */
  /* ---------------------------------------------------------------- */
  // speckled asphalt, tiled; its colour comes from the time of day
  const asphaltTex = (rx, ry) => {
    const c = document.createElement("canvas");
    c.width = c.height = 256;
    const g = c.getContext("2d");
    g.fillStyle = "#8f8f8f";
    g.fillRect(0, 0, 256, 256);
    for (let i = 0; i < 5200; i++) {
      const v = 80 + Math.floor(Math.random() * 110);
      g.fillStyle = `rgb(${v},${v},${v})`;
      g.fillRect(Math.random() * 256, Math.random() * 256, 1 + Math.random() * 1.6, 1 + Math.random() * 1.6);
    }
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(rx, ry);
    t.anisotropy = 4;
    return t;
  };
  const lot = new THREE.Group();
  scene.add(lot);
  const lotLabels = [];
  const GATE_X = -26, BAY_W = 4.4, BAY_D = 7.2, ROAD_HALF = 4.2;
  const asphalt = new THREE.Mesh(new THREE.PlaneGeometry(64, 34), new THREE.MeshStandardMaterial({ map: asphaltTex(14, 8), roughness: 0.62, metalness: 0.08 }));
  asphalt.rotation.x = -Math.PI / 2;
  asphalt.position.set(-4, 0.02, 0);
  asphalt.receiveShadow = true;
  lot.add(asphalt);
  const road = new THREE.Mesh(new THREE.PlaneGeometry(240, ROAD_HALF * 2), new THREE.MeshStandardMaterial({ map: asphaltTex(56, 2), roughness: 0.8 }));
  road.rotation.x = -Math.PI / 2;
  road.position.set(-60, 0.035, 0);
  road.receiveShadow = true;
  lot.add(road);
  // moving centre dashes
  const dashMat = new THREE.MeshStandardMaterial({ color: 0x4a4b52, emissive: 0x2a2b30 });
  const dashes = new THREE.Group();
  for (let x = -170; x < 60; x += 6) {
    const d = new THREE.Mesh(new THREE.BoxGeometry(3, 0.03, 0.22), dashMat);
    d.position.set(x, 0.05, 0);
    dashes.add(d);
  }
  lot.add(dashes);

  const paintMat = new THREE.MeshStandardMaterial({ color: 0xf2c230, emissive: 0xf2c230, emissiveIntensity: 1.25, roughness: 0.5 });
  const paintLines = [];
  const bays = {};
  const zoneName = { student_zone: "Student zone", employee_zone: "Employee zone", visitor_zone: "Visitor zone" };
  const typeText = { standard: "standard", accessible: "accessible", ev_charging: "EV charging", motorbike: "motorbike" };
  const hhmm = (t) => String(Math.floor(t / 100)).padStart(2, "0") + ":" + String(t % 100).padStart(2, "0");
  const zoneLabels = [];
  // the scenario clock can move the decision outside a zone's hours
  const markZones = () => zoneLabels.forEach(([z, zl]) => {
    const shut = D.run.hour < z.opens || D.run.hour >= z.closes;
    zl.element.innerHTML = `${zoneName[z.type] || z.id}<br><span>${hhmm(z.opens * 100)} to ${hhmm(z.closes * 100)}${shut ? ", closed" : ""}</span>`;
    zl.element.classList.toggle("is-closed", shut);
  });
  const layout = { zone_a: { x: -18, side: -1 }, zone_e: { x: -18, side: 1 }, zone_v: { x: 6, side: 1 } };
  D.lot.zones.forEach((z) => {
    const L = layout[z.id] || { x: -18, side: -1 };
    const zl = label(`${zoneName[z.type] || z.id}<br><span>${hhmm(z.opens * 100)} to ${hhmm(z.closes * 100)}</span>`, "zone", lot,
      new THREE.Vector3(L.x + 0.3, 0.2, L.side * (ROAD_HALF + BAY_D + 2.4)));
    lotLabels.push(zl);
    zoneLabels.push([z, zl]);
    z.bays.forEach((b, i) => {
      const x0 = L.x + i * BAY_W, x1 = x0 + BAY_W, zOpen = L.side * ROAD_HALF, zEnd = L.side * (ROAD_HALF + BAY_D);
      const mk = (w, d, x, zz) => {
        const m = new THREE.Mesh(new THREE.BoxGeometry(w, 0.05, d), paintMat);
        m.position.set(x, 0.05, zz);
        lot.add(m);
        paintLines.push(m);
      };
      mk(0.16, BAY_D, x0, (zOpen + zEnd) / 2);
      mk(0.16, BAY_D, x1, (zOpen + zEnd) / 2);
      mk(BAY_W, 0.16, (x0 + x1) / 2, zEnd);
      const fill = new THREE.Mesh(new THREE.PlaneGeometry(BAY_W - 0.3, BAY_D - 0.3),
        new THREE.MeshBasicMaterial({ color: 0x4ade80, transparent: true, opacity: 0, depthWrite: false, toneMapped: false, polygonOffset: true, polygonOffsetFactor: 0, polygonOffsetUnits: -2 }));
      fill.rotation.x = -Math.PI / 2;
      fill.position.set((x0 + x1) / 2, 0.03, (zOpen + zEnd) / 2);
      lot.add(fill);
      const res = b.reservedFor ? `<span>reserved for ${b.reservedFor}</span>` : "";
      const bl = label(`<b>${b.id}</b><span>${typeText[b.type] || b.type}</span>${res}`, "bay", lot,
        new THREE.Vector3((x0 + x1) / 2, 0.2, zEnd - L.side * 1.6));
      lotLabels.push(bl);
      bays[b.id] = { cx: (x0 + x1) / 2, cz: zEnd - L.side * 3.3, side: L.side, fill, occupied: b.status === "occupied" };
    });
  });

  // gate: post, striped arm, scanner beam
  const stripeTex = (() => {
    const c = document.createElement("canvas");
    c.width = 256; c.height = 16;
    const g = c.getContext("2d");
    for (let i = 0; i < 16; i++) { g.fillStyle = i % 2 ? "#111" : "#f2c230"; g.fillRect(i * 16, 0, 16, 16); }
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  })();
  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.28, 1.6, 12), new THREE.MeshStandardMaterial({ color: 0x2b2c33, metalness: 0.6, roughness: 0.4 }));
  post.position.set(GATE_X, 0.8, -ROAD_HALF - 0.6);
  post.castShadow = true;
  lot.add(post);
  const armPivot = new THREE.Group();
  armPivot.position.set(GATE_X, 1.45, -ROAD_HALF - 0.6);
  lot.add(armPivot);
  const arm = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.22, 9),
    new THREE.MeshStandardMaterial({ map: stripeTex, emissive: 0xffffff, emissiveMap: stripeTex, emissiveIntensity: 0.8 }));
  arm.position.z = 4.5;
  arm.castShadow = true;
  armPivot.add(arm);
  const counter = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.46, 0.9), new THREE.MeshStandardMaterial({ color: 0x2b2c33, metalness: 0.5, roughness: 0.5 }));
  counter.position.z = -0.55;
  counter.castShadow = true;
  armPivot.add(counter);
  const housing = new THREE.Mesh(new THREE.BoxGeometry(0.62, 1.1, 0.62), new THREE.MeshStandardMaterial({ color: 0xf2c230, roughness: 0.5 }));
  housing.position.set(GATE_X, 0.55, -ROAD_HALF - 0.6);
  housing.castShadow = true;
  lot.add(housing);
  const armTip = new THREE.Mesh(new THREE.SphereGeometry(0.16, 12, 8), new THREE.MeshBasicMaterial({ color: hdr(0xff4040, 3), toneMapped: false }));
  armTip.position.z = 9;
  armPivot.add(armTip);
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(3.6, 3.6, 10, 32, 1, true),
    new THREE.MeshBasicMaterial({ color: 0xf2c230, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending }));
  beam.position.set(GATE_X - 3.2, 5, 0);
  lot.add(beam);
  const beamRing = glowPlane(9, 9, 0xf2c230, 0);
  beamRing.position.set(GATE_X - 3.2, 0.06, 0);
  lot.add(beamRing);
  lotLabels.push(label("Gate", "zone small", lot, new THREE.Vector3(GATE_X, 0.2, ROAD_HALF + 1.6)));
  lotLabels.push(label("Turned away", "zone small", lot, new THREE.Vector3(GATE_X - 36, 0.2, -ROAD_HALF - 3.4)));
  lotLabels.push(label("Queue", "zone small", lot, new THREE.Vector3(GATE_X - 22, 0.2, ROAD_HALF + 1.6)));

  // street lamps with light pools
  const lampMat = new THREE.MeshStandardMaterial({ color: 0x23242a, metalness: 0.7, roughness: 0.4 });
  const lamps = [];
  [[-30, -6.2], [-8, -13.8], [12, -13.8], [-8, 13.8], [12, 13.8], [-48, 6.2]].forEach(([x, z], i) => {
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.16, 7, 8), lampMat);
    pole.position.set(x, 3.5, z);
    pole.castShadow = true;
    lot.add(pole);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.42, 16, 10), new THREE.MeshBasicMaterial({ color: hdr(0xffd58a, 0.05), toneMapped: false }));
    head.position.set(x, 7.1, z);
    lot.add(head);
    const pool = glowPlane(12, 12, 0xffc56b, 0);
    pool.position.set(x, 0.05, z);
    lot.add(pool);
    let light = null;
    if (i < (small ? 2 : 4)) {
      light = new THREE.PointLight(0xffc77a, 0, 26, 1.6);
      light.position.set(x, 6.6, z);
      lot.add(light);
    }
    lamps.push({ head, pool, light, on: 0 });
  });

  // kerbs around the car park and along the approach road
  const kerbMat = new THREE.MeshStandardMaterial({ color: 0xb9bbc0, roughness: 0.9 });
  [[64, 0.4, -4, 17], [64, 0.4, -4, -17], [144, 0.4, -108, ROAD_HALF + 0.4], [90, 0.4, -135, -ROAD_HALF - 0.4]].forEach(([w, d, x, z]) => {
    const k = new THREE.Mesh(new THREE.BoxGeometry(w, 0.2, d), kerbMat);
    k.position.set(x, 0.1, z);
    k.receiveShadow = true;
    lot.add(k);
  });
  [-36, 28].forEach((x) => [10.8, -10.8].forEach((z) => {
    const k = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.2, 12.4), kerbMat);
    k.position.set(x, 0.1, z);
    lot.add(k);
  }));

  // bay numbers painted at the mouth of each bay
  Object.entries(bays).forEach(([id, b]) => {
    const c = document.createElement("canvas");
    c.width = 256; c.height = 128;
    const g = c.getContext("2d");
    g.fillStyle = "rgba(255,255,255,0.88)";
    g.font = "bold 92px Poppins, Arial, sans-serif";
    g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText(id.replace("s_", "").toUpperCase(), 128, 68);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    const m = new THREE.Mesh(new THREE.PlaneGeometry(2.1, 1.05), new THREE.MeshStandardMaterial({ map: t, transparent: true, depthWrite: false, roughness: 0.8, polygonOffset: true, polygonOffsetFactor: 0, polygonOffsetUnits: -2 }));
    m.rotation.x = -Math.PI / 2;
    // upright for the main camera, which always looks from the +z side
    m.position.set(b.cx, 0.045, b.side * (ROAD_HALF + 1.15));
    lot.add(m);
  });

  // gate booth with a lit window
  const booth = new THREE.Group();
  booth.position.set(GATE_X + 3.6, 0, -ROAD_HALF - 2.5);
  const boothWall = new THREE.Mesh(new THREE.BoxGeometry(3, 2.4, 2.4), new THREE.MeshStandardMaterial({ color: 0xd9dbe0, roughness: 0.8 }));
  boothWall.position.y = 1.2;
  const boothGlass = new THREE.Mesh(new THREE.BoxGeometry(3.04, 0.8, 2.44), new THREE.MeshStandardMaterial({ color: 0x1d2a3a, roughness: 0.08, metalness: 0.3, emissive: 0xffd9a0, emissiveIntensity: 0 }));
  boothGlass.position.y = 1.55;
  const boothRoof = new THREE.Mesh(new THREE.BoxGeometry(3.7, 0.18, 3.1), new THREE.MeshStandardMaterial({ color: 0x2b2c31, roughness: 0.6 }));
  boothRoof.position.y = 2.5;
  [boothWall, boothGlass, boothRoof].forEach((m) => { m.castShadow = true; m.receiveShadow = true; booth.add(m); });
  lot.add(booth);

  // trees round the edge
  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x5a4433, roughness: 0.9 });
  const leafMats = [0x3d6e35, 0x4a7d3a, 0x355f2f].map((c) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.85, flatShading: true }));
  const leafGeo = new THREE.IcosahedronGeometry(1, 1), trunkGeo = new THREE.CylinderGeometry(0.16, 0.24, 2.4, 7);
  let treeSeed = 7;
  const treeRnd = () => { treeSeed = (treeSeed * 16807) % 2147483647; return treeSeed / 2147483647; };
  const tree = (x, z) => {
    const g = new THREE.Group();
    const trunk = new THREE.Mesh(trunkGeo, trunkMat);
    trunk.position.y = 1.2;
    trunk.castShadow = true;
    g.add(trunk);
    [[0, 2.9, 0, 1.7], [0.6, 3.6, 0.3, 1.3], [-0.5, 3.5, -0.4, 1.2]].forEach(([lx, ly, lz, sc]) => {
      const leaf = new THREE.Mesh(leafGeo, leafMats[Math.floor(treeRnd() * leafMats.length)]);
      leaf.position.set(lx, ly, lz);
      leaf.scale.setScalar(sc * (0.85 + treeRnd() * 0.3));
      leaf.castShadow = true;
      g.add(leaf);
    });
    g.scale.setScalar(0.9 + treeRnd() * 0.5);
    g.rotation.y = treeRnd() * Math.PI * 2;
    g.position.set(x, 0, z);
    lot.add(g);
  };
  for (let x = -32; x <= 24; x += 7) tree(x, 20.5);
  for (let x = -34; x <= -12; x += 7) tree(x, -20.5);
  [-44, -56, -68, -80, -92, -104].forEach((x) => tree(x, 8.8));
  [-96, -108, -120, -132].forEach((x) => tree(x, -9.6));

  // traffic cones and tape across a zone while it is closed
  const tapeTex = (() => {
    const c = document.createElement("canvas");
    c.width = 64; c.height = 8;
    const g = c.getContext("2d");
    for (let i = 0; i < 4; i++) { g.fillStyle = i % 2 ? "#ffffff" : "#e3342f"; g.fillRect(i * 16, 0, 16, 8); }
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    t.wrapS = THREE.RepeatWrapping;
    return t;
  })();
  const zoneBarriers = {};
  D.lot.zones.forEach((z) => {
    const L = layout[z.id] || { x: -18, side: -1 };
    const grp = new THREE.Group();
    grp.visible = false;
    const n = z.bays.length, zEdge = L.side * (ROAD_HALF + 0.45);
    for (let i = 0; i <= n; i++) {
      const c = models && models.cone ? models.cone.clone(true)
        : new THREE.Mesh(new THREE.ConeGeometry(0.3, 0.9, 16), new THREE.MeshStandardMaterial({ color: 0xff6a1a }));
      if (models && models.cone) c.scale.setScalar(1.8); else c.position.y = 0.45;
      c.position.x = L.x + i * BAY_W;
      c.position.z = zEdge;
      c.traverse((o) => { if (o.isMesh) o.castShadow = true; });
      grp.add(c);
    }
    const tex = tapeTex.clone();
    tex.repeat.set(n * 4, 1);
    tex.needsUpdate = true;
    const tape = new THREE.Mesh(new THREE.BoxGeometry(n * BAY_W, 0.12, 0.03), new THREE.MeshStandardMaterial({ map: tex, emissive: 0xffffff, emissiveMap: tex, emissiveIntensity: 0.25 }));
    tape.position.set(L.x + (n * BAY_W) / 2, 0.78, zEdge);
    grp.add(tape);
    lot.add(grp);
    zoneBarriers[z.id] = grp;
  });
  function markBarriers() {
    D.lot.zones.forEach((z) => {
      const g = zoneBarriers[z.id];
      if (!g) return;
      const shut = D.run.hour < z.opens || D.run.hour >= z.closes;
      if (shut && !g.visible) { g.visible = true; g.scale.y = 0.01; tween(650, (t) => { g.scale.y = Math.max(0.01, t); }, ease.back); }
      else if (!shut) g.visible = false;
    });
  }

  // test beacons behind the student zone
  const beacons = [];
  const RING = new THREE.Vector3(6, 0, -32);
  const ringPad = glowPlane(30, 30, 0x4ade80, 0.08);
  ringPad.position.copy(RING).add(new THREE.Vector3(0, 0.05, 0));
  lot.add(ringPad);
  D.testCases.forEach((t, i) => {
    const a = (i / D.testCases.length) * Math.PI * 2;
    const x = RING.x + Math.cos(a) * 9, z = RING.z + Math.sin(a) * 9;
    const h = 2.2 + (i % 2) * 0.8;
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.12, h, 8), lampMat);
    pole.position.set(x, h / 2, z);
    lot.add(pole);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.5, 18, 12), new THREE.MeshBasicMaterial({ color: new THREE.Color(0x3a3b44), toneMapped: false }));
    head.position.set(x, h + 0.3, z);
    lot.add(head);
    const l = label(t.id, "beacon", lot, new THREE.Vector3(x, h + 1.4, z));
    l.visible = false;
    beacons.push({ head, label: l, pass: t.pass });
  });
  setLoad(0.6);

  /* ---------------------------------------------------------------- */
  /* cars                                                              */
  /* ---------------------------------------------------------------- */
  const carGeo = {
    body: new RoundedBoxGeometry(3.8, 0.9, 1.8, 3, 0.3),
    cabin: new RoundedBoxGeometry(2.0, 0.66, 1.58, 2, 0.24),
    wheel: new THREE.CylinderGeometry(0.42, 0.42, 0.32, 18).rotateX(Math.PI / 2),
    lamp: new THREE.BoxGeometry(0.08, 0.18, 0.42),
    rim: new THREE.CylinderGeometry(0.24, 0.24, 0.34, 14).rotateX(Math.PI / 2),
    bumper: new RoundedBoxGeometry(0.22, 0.34, 1.86, 2, 0.08),
    mirror: new THREE.BoxGeometry(0.22, 0.16, 0.18),
    cone: new THREE.ConeGeometry(1.7, 7.5, 20, 1, true).rotateZ(Math.PI / 2),
  };
  const wheelMat = new THREE.MeshStandardMaterial({ color: 0x111114, roughness: 0.8 });
  const rimMat = new THREE.MeshStandardMaterial({ color: 0xc9ccd6, metalness: 0.9, roughness: 0.25 });
  const trimMat = new THREE.MeshStandardMaterial({ color: 0x1a1b20, roughness: 0.5, metalness: 0.4 });
  const cabinMat = new THREE.MeshStandardMaterial({ color: 0x0d1018, metalness: 0.3, roughness: 0.08 });
  const headMat = new THREE.MeshBasicMaterial({ color: hdr(0xfff3d0, 4), toneMapped: false });
  const tailMat = new THREE.MeshBasicMaterial({ color: hdr(0xff2a2a, 2.5), toneMapped: false });
  const vehicleOf = (d) => (D.drivers[d] || {}).vehicle || "car";
  const nightHeadMat = new THREE.MeshBasicMaterial({ color: hdr(0xfff3d0, 2), toneMapped: false });
  const REAR = { off: new THREE.Color(0x4a0c0c), brake: hdr(0xff2020, 3), reverse: hdr(0xffffff, 2.2) };
  const IND_OFF = new THREE.Color(0x4a3008), IND_ON = hdr(0xffa020, 3.2);
  const lampGeo = { rear: new THREE.BoxGeometry(0.06, 0.16, 0.34), head: new THREE.BoxGeometry(0.06, 0.14, 0.36), ind: new THREE.BoxGeometry(0.1, 0.1, 0.1) };
  // one model per built-in driver, so the same person always has the same car
  const CAR_MODEL = { ahmed: "suv-luxury", zara: "hatchback-sports", usman: "sedan", ali: "sedan-sports", sara: "suv", hina: "van", bilal: "sedan", parked: "van" };
  const POOL = ["sedan-sports", "suv", "hatchback-sports", "van", "suv-luxury", "sedan"];
  const modelFor = (name) => CAR_MODEL[name] || POOL[[...name].reduce((h, ch) => h + ch.charCodeAt(0), 0) % POOL.length];
  function makeModelCar(name, kind) {
    const g = new THREE.Group();
    const m = models[modelFor(name)].clone(true);
    m.rotation.y = Math.PI / 2;          // the models face +z; the scene drives along +x
    m.scale.setScalar(1.5);
    const spins = [], steers = [];
    [...m.children].forEach((w) => {
      if (!/^wheel-(front|back)-(left|right)$/.test(w.name)) return;
      // pivot (steering) > spin (rolling) > wheel, so both turn about the right axes
      const pivot = new THREE.Group(), spin = new THREE.Group();
      pivot.position.copy(w.position);
      m.add(pivot);
      pivot.add(spin);
      spin.add(w);
      w.position.set(0, 0, 0);
      spins.push(spin);
      if (w.name.includes("front")) steers.push(pivot);
    });
    m.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    g.add(m);
    const box = new THREE.Box3().setFromObject(g);
    const front = box.max.x, back = box.min.x, half = box.max.z, lampY = box.min.y + (box.max.y - box.min.y) * 0.42;
    const rearMat = new THREE.MeshBasicMaterial({ color: REAR.off.clone(), toneMapped: false });
    const ind = { 1: new THREE.MeshBasicMaterial({ color: IND_OFF.clone(), toneMapped: false }), "-1": new THREE.MeshBasicMaterial({ color: IND_OFF.clone(), toneMapped: false }) };
    [half * 0.62, -half * 0.62].forEach((z) => {
      const r = new THREE.Mesh(lampGeo.rear, rearMat); r.position.set(back - 0.02, lampY, z); g.add(r);
      const h = new THREE.Mesh(lampGeo.head, nightHeadMat); h.position.set(front + 0.02, lampY - 0.05, z); g.add(h);
    });
    [front - 0.05, back + 0.05].forEach((x) => [1, -1].forEach((side) => {
      const i = new THREE.Mesh(lampGeo.ind, ind[side]); i.position.set(x, lampY + 0.12, side * (half - 0.05)); g.add(i);
    }));
    const cone = new THREE.Mesh(carGeo.cone, new THREE.MeshBasicMaterial({ color: 0xfff1c9, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }));
    cone.position.set(front + 3.7, 0.7, 0);
    g.add(cone);
    const glow = glowPlane(6.5, 4, 0xffffff, 0);
    glow.position.y = 0.04;
    g.add(glow);
    const tag = label(name, `car ${kind}`, g, new THREE.Vector3(0, box.max.y + 0.7, 0));
    lotLabels.push(tag);
    lot.add(g);
    return {
      g, wheels: [], cone, glow, tag, kind, model: true, steer: 0, indicate: 0, ind,
      roll: (d) => spins.forEach((sp) => { sp.rotation.x += d / 0.45; }),
      setSteer: (a) => steers.forEach((pv) => { pv.rotation.y = a; }),
      rear: (mode) => rearMat.color.copy(REAR[mode]),
    };
  }
  const COLORS = { wait: 0xd9dbe2, ok: 0x3fcf78, no: 0xe25a5a, static: 0x4b4d56 };
  const cars = [];

  const bikeGeo = {
    wheel: new THREE.TorusGeometry(0.36, 0.11, 10, 24),
    hub: new THREE.CylinderGeometry(0.1, 0.1, 0.14, 10).rotateX(Math.PI / 2),
    tank: new RoundedBoxGeometry(1.25, 0.42, 0.42, 2, 0.16),
    seat: new RoundedBoxGeometry(0.8, 0.14, 0.36, 2, 0.06),
    fork: new THREE.CylinderGeometry(0.05, 0.05, 0.95, 8),
    bar: new THREE.CylinderGeometry(0.04, 0.04, 0.8, 8).rotateX(Math.PI / 2),
    torso: new THREE.CapsuleGeometry(0.24, 0.5, 4, 10),
    helmet: new THREE.SphereGeometry(0.24, 16, 12),
    lamp: new THREE.SphereGeometry(0.1, 10, 8),
  };
  // Fatima rides a motorbike: drawing her as a car made her refusal look wrong.
  function makeBike(g, bodyMat) {
    const wheels = [];
    [0.82, -0.82].forEach((x) => {
      const w = new THREE.Mesh(bikeGeo.wheel, wheelMat);
      w.position.set(x, 0.42, 0);
      w.add(new THREE.Mesh(bikeGeo.hub, rimMat));
      g.add(w);
      wheels.push(w);
    });
    const tank = new THREE.Mesh(bikeGeo.tank, bodyMat);
    tank.position.set(0.1, 0.86, 0);
    tank.castShadow = true;
    const seat = new THREE.Mesh(bikeGeo.seat, trimMat);
    seat.position.set(-0.4, 1.12, 0);
    const fork = new THREE.Mesh(bikeGeo.fork, rimMat);
    fork.position.set(0.72, 0.9, 0);
    fork.rotation.z = 0.35;
    const bar = new THREE.Mesh(bikeGeo.bar, trimMat);
    bar.position.set(0.58, 1.36, 0);
    const torso = new THREE.Mesh(bikeGeo.torso, trimMat);
    torso.position.set(-0.25, 1.62, 0);
    torso.rotation.z = -0.35;
    const helmet = new THREE.Mesh(bikeGeo.helmet, bodyMat);
    helmet.position.set(-0.05, 2.18, 0);
    const head = new THREE.Mesh(bikeGeo.lamp, headMat);
    head.position.set(0.86, 1.1, 0);
    const tail = new THREE.Mesh(bikeGeo.lamp, tailMat);
    tail.position.set(-0.86, 0.95, 0);
    g.add(tank, seat, fork, bar, torso, helmet, head, tail);
    return { body: tank, wheels };
  }

  function makeCar(name, kind = "wait", vehicle = "car") {
    const g = new THREE.Group();
    const bodyMat = new THREE.MeshPhysicalMaterial({ color: COLORS[kind], metalness: 0.5, roughness: 0.3, clearcoat: 1, clearcoatRoughness: 0.12 });
    if (vehicle === "motorbike") {
      const { body, wheels } = makeBike(g, bodyMat);
      const cone = new THREE.Mesh(carGeo.cone, new THREE.MeshBasicMaterial({ color: 0xfff1c9, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }));
      cone.position.set(4.6, 0.9, 0);
      cone.scale.set(1, 0.6, 0.6);
      g.add(cone);
      const glow = glowPlane(3.6, 2.4, 0xffffff, 0);
      glow.position.y = 0.04;
      g.add(glow);
      const tag = label(name, `car ${kind}`, g, new THREE.Vector3(0, 2.9, 0));
      lotLabels.push(tag);
      lot.add(g);
      return { g, body, bodyMat, wheels, cone, glow, tag, kind, bike: true, roll: (d) => wheels.forEach((w) => { w.rotation.z -= d / 0.47; }) };
    }
    if (models) return makeModelCar(name, kind);
    const body = new THREE.Mesh(carGeo.body, bodyMat);
    body.position.y = 0.78;
    body.castShadow = true;
    const cabin = new THREE.Mesh(carGeo.cabin, cabinMat);
    cabin.position.set(-0.25, 1.48, 0);
    cabin.castShadow = true;
    g.add(body, cabin);
    const wheels = [];
    [[1.2, 0.92], [1.2, -0.92], [-1.2, 0.92], [-1.2, -0.92]].forEach(([x, z]) => {
      const w = new THREE.Mesh(carGeo.wheel, wheelMat);
      w.position.set(x, 0.42, z);
      g.add(w);
      w.add(new THREE.Mesh(carGeo.rim, rimMat));
      wheels.push(w);
    });
    [1.92, -1.92].forEach((x) => { const bm = new THREE.Mesh(carGeo.bumper, trimMat); bm.position.set(x, 0.5, 0); g.add(bm); });
    [0.86, -0.86].forEach((z) => { const mr = new THREE.Mesh(carGeo.mirror, trimMat); mr.position.set(0.55, 1.22, z * 1.06); g.add(mr); });
    [0.55, -0.55].forEach((z) => {
      const h = new THREE.Mesh(carGeo.lamp, headMat); h.position.set(1.92, 0.85, z); g.add(h);
      const t = new THREE.Mesh(carGeo.lamp, tailMat); t.position.set(-1.92, 0.85, z); g.add(t);
    });
    const cone = new THREE.Mesh(carGeo.cone, new THREE.MeshBasicMaterial({ color: 0xfff1c9, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }));
    cone.position.set(5.6, 0.7, 0);
    g.add(cone);
    const glow = glowPlane(6.5, 4, 0xffffff, 0);
    glow.position.y = 0.04;
    g.add(glow);
    const tag = label(name, `car ${kind}`, g, new THREE.Vector3(0, 2.5, 0));
    lotLabels.push(tag);
    lot.add(g);
    const car = { g, body, bodyMat, wheels, cone, glow, tag, kind, roll: (d) => wheels.forEach((w) => { w.rotation.z -= d / 0.42; }) };
    return car;
  }
  function setCarKind(car, kind) {
    car.kind = kind;
    if (car.bodyMat) car.bodyMat.color.setHex(COLORS[kind]);
    car.tag.element.className = `label3d car ${kind}`;
    if (kind === "ok") { car.glow.material.color.setHex(0x4ade80); car.glow.material.opacity = 0.9; }
    if (kind === "no") { car.glow.material.color.setHex(0xff5252); car.glow.material.opacity = 0.9; }
  }
  const removeCar = (car) => { lot.remove(car.g); car.tag.element.remove(); const k = lotLabels.indexOf(car.tag); if (k >= 0) lotLabels.splice(k, 1); };

  let driving = 0;
  const wrapA = (x) => Math.atan2(Math.sin(x), Math.cos(x));
  // Follows a smooth path. Front wheels steer from the path's curvature, the
  // brake lights come on as the car slows, and reverse turns on white lamps.
  async function drive(car, pts, speed = 11, opt = {}) {
    const rev = Boolean(opt.reverse);
    const curve = new THREE.CatmullRomCurve3([car.g.position.clone(), ...pts.map((p) => new THREE.Vector3(p[0], 0, p[1]))], false, "centripetal", 0.4);
    const len = curve.getLength();
    driving++;
    car.moving = !rev;
    if (car.rear) car.rear(rev ? "reverse" : "off");
    const tan = new THREE.Vector3();
    let last = 0, steer = car.steer || 0;
    await tween(Math.max(700, (len / speed) * 1000), (t) => {
      const u = Math.min(1, Math.max(0, t));
      car.g.position.copy(curve.getPointAt(u));
      curve.getTangentAt(Math.min(0.999, Math.max(0.001, u)), tan);
      const ds = (u - last) * len;
      if (tan.lengthSq() > 1e-6) {
        const dYaw = wrapA(Math.atan2(-tan.z, tan.x) + (rev ? Math.PI : 0) - car.g.rotation.y);
        car.g.rotation.y += dYaw;
        if (ds > 1e-4 && car.setSteer) {
          const want = Math.max(-0.6, Math.min(0.6, Math.atan((2.1 * dYaw) / ds) * (rev ? -1 : 1)));
          steer += (want - steer) * 0.3;
          car.setSteer(steer);
        }
      }
      if (car.roll) car.roll(rev ? -ds : ds);
      if (car.rear && !rev) car.rear(t > 0.7 ? "brake" : "off");
      last = u;
    }, ease.inOut);
    car.steer = steer;
    car.moving = false;
    if (car.rear) car.rear(rev ? "off" : "brake");
    driving--;
  }
  function placeCar(car, x, z, yaw) { car.g.position.set(x, 0, z); car.g.rotation.y = yaw; }

  // a car already parked in the occupied bay
  Object.entries(bays).forEach(([id, b]) => {
    if (!b.occupied) return;
    const c = makeCar("parked", "static");
    placeCar(c, b.cx, b.cz, b.side < 0 ? Math.PI / 2 : -Math.PI / 2);
  });

  // reasoning ring that fills over the ten cycles
  const ringGroup = new THREE.Group();
  ringGroup.position.set(-8, 10, 0);
  ringGroup.visible = false;
  lot.add(ringGroup);
  const ringBg = new THREE.Mesh(new THREE.TorusGeometry(3.2, 0.12, 12, 96), new THREE.MeshBasicMaterial({ color: 0x2a2a33 }));
  ringGroup.add(ringBg);
  let ringFill = null;
  const ringLabel = label("", "ring", ringGroup, new THREE.Vector3(0, -4.6, 0));
  const setRing = (p) => {
    if (ringFill) { ringGroup.remove(ringFill); ringFill.geometry.dispose(); }
    ringFill = new THREE.Mesh(new THREE.TorusGeometry(3.2, 0.2, 12, 96, Math.max(0.001, p * Math.PI * 2)),
      new THREE.MeshBasicMaterial({ color: hdr(0xf2c230, 3), toneMapped: false }));
    ringFill.rotation.z = Math.PI / 2;
    ringGroup.add(ringFill);
  };

  /* ---------------------------------------------------------------- */
  /* the morning rush                                                  */
  /* ---------------------------------------------------------------- */
  const QUEUE = (i) => [GATE_X - 5.5 - i * 4.6, 0];
  const STOP = [GATE_X - 3.2, 0];
  const AWAY = (k) => [GATE_X - 6 - k * 4.6, -ROAD_HALF - 3.4];
  // refused cars fill the row from the far end, so each one drives past empty spaces only
  // (counted on each call: the scenario clock on the page can swap the decisions)
  const AWAY_SLOT = (k) => AWAY(D.requests.filter((q) => !q.allocated).length - 1 - k);
  let runId = 0, rushCars = [];
  const resetRush = () => {
    rushCars.forEach(removeCar);
    rushCars = [];
    Object.values(bays).forEach((b) => { b.fill.material.opacity = 0; });
    armPivot.rotation.x = 0;
    ringGroup.visible = false;
    markZones();
    markBarriers();
    setTimeOfDay(D.run.hour);
  };
  // reverse parking: drive past the bay, swing out, then back in
  const parkLegs = (b) => {
    const s = b.side;
    return {
      fwd: [[GATE_X + 3, 0], [b.cx + 2, -s * 0.5], [b.cx + 5.2, -s * 1.7]],
      back: [[b.cx + 3.4, -s * 0.7], [b.cx + 1.0, s * (ROAD_HALF - 0.9)], [b.cx, b.cz]],
    };
  };
  // a refused car backs off the barrier and makes a three-point turn
  async function turnAway(car, slot) {
    const S = STOP[0];
    await drive(car, [[S - 2.4, 0]], 4, { reverse: true });
    await drive(car, [[S - 1.5, -0.5], [S - 0.9, -1.7], [S - 0.8, -2.9]], 5);
    await drive(car, [[S - 0.9, -1.5], [S - 0.3, -0.2]], 4, { reverse: true });
    await drive(car, [[S - 1.6, -2.6], [S - 4, -4.0], [slot[0] + 3.2, slot[1] + 0.5], slot], 9);
    if (car.rear) car.rear("off");
  }
  async function openArm(open) {
    const from = armPivot.rotation.x, to = open ? -1.38 : 0;
    await tween(open ? 650 : 800, (t) => { armPivot.rotation.x = from + (to - from) * t; }, open ? ease.out : ease.back);
  }
  async function scan(color) {
    beam.material.color.setHex(color);
    beamRing.material.color.setHex(color);
    await tween(650, (t) => {
      const k = Math.sin(t * Math.PI);
      beam.material.opacity = 0.16 * k;
      beamRing.material.opacity = 0.9 * k;
      beam.scale.set(1 - 0.25 * t, 1, 1 - 0.25 * t);
    }, ease.lin);
  }
  async function shake(car) {
    const z0 = car.g.position.z;
    await tween(450, (t) => { car.g.position.z = z0 + Math.sin(t * Math.PI * 6) * 0.25 * (1 - t); }, ease.lin);
    car.g.position.z = z0;
  }
  function bubble(car, html, cls, ms = 2600) {
    const b = label(`<div class="bubble ${cls}">${html}</div>`, "verdict", car.g, new THREE.Vector3(0, 4.2, 0));
    lotLabels.push(b);
    setTimeout(() => {
      b.element.classList.add("is-leaving");
      setTimeout(() => { car.g.remove(b); b.element.remove(); const k = lotLabels.indexOf(b); if (k >= 0) lotLabels.splice(k, 1); }, 500);
    }, ms);
  }
  function sparks(x, z, color) {
    const n = 70, pos = new Float32Array(n * 3), vel = [];
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2, r = Math.random() * 1.6;
      pos.set([x + Math.cos(a) * r, 0.3, z + Math.sin(a) * r], i * 3);
      vel.push([Math.cos(a) * (0.5 + Math.random()), 3 + Math.random() * 4, Math.sin(a) * (0.5 + Math.random())]);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const pts = new THREE.Points(geo, new THREE.PointsMaterial({ color: hdr(color, 3), size: 0.34, map: glowTex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
    lot.add(pts);
    const base = pos.slice();
    tween(1400, (t) => {
      for (let i = 0; i < n; i++) {
        pos[i * 3] = base[i * 3] + vel[i][0] * t * 1.4;
        pos[i * 3 + 1] = base[i * 3 + 1] + vel[i][1] * t - 4.5 * t * t;
        pos[i * 3 + 2] = base[i * 3 + 2] + vel[i][2] * t * 1.4;
      }
      geo.attributes.position.needsUpdate = true;
      pts.material.opacity = 1 - t;
    }, ease.lin).then(() => { lot.remove(pts); geo.dispose(); });
  }
  function shockRing(x, z, color) {
    const ring = new THREE.Mesh(new THREE.RingGeometry(0.8, 1.05, 48), new THREE.MeshBasicMaterial({ color: hdr(color, 2.5), transparent: true, side: THREE.DoubleSide, depthWrite: false, toneMapped: false }));
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(x, 0.1, z);
    lot.add(ring);
    tween(900, (t) => { ring.scale.setScalar(1 + t * 4); ring.material.opacity = 1 - t; }, ease.out).then(() => { lot.remove(ring); ring.geometry.dispose(); });
  }
  const ymd = (n) => { const t = String(n); const m = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]; return `${Number(t.slice(6))} ${m[Number(t.slice(4, 6)) - 1]}`; };
  function shortReason(q) {
    const r = q.reasons[0] || ""; let m;
    if ((m = r.match(/fits\((\w+), (\w+)\)/))) return `a ${m[1].replace("_", " ")} does not fit a ${m[2]} bay`;
    if ((m = r.match(/by R26; competing request: requests\((\w+)/))) return `${m[1]} asked earlier`;
    if ((m = r.match(/competing request: requests\((\w+)/))) return `${m[1]} has priority for ${q.space}`;
    if ((m = r.match(/fails at (\d{8}) >= /))) return `permit expired ${ymd(m[1])}`;
    if ((m = r.match(/fails at (\d{8}) =< /))) return `permit starts ${ymd(m[1])}`;
    if ((m = r.match(/zone_open\((\w+)\)/))) return "zone is closed now";
    if (/holds_reservation/.test(q.reasons[1] || "")) return "reservation was for another day";
    if (/has_permit/.test(r)) return "no permit or visitor pass";
    return "rule R28 fails";
  }
  // director: during a replay the camera follows the story instead of the scroll
  let director = null;
  const cinema = (on) => root.classList.toggle("is-cinema", on);
  addEventListener("scroll", () => { if (root.classList.contains("is-cinema") && scrollY > innerHeight * 0.25) cinema(false); }, { passive: true });

  async function glowBay(b) {
    await tween(1300, (t) => { b.fill.material.opacity = 0.18 + 0.5 * Math.pow(1 - t, 2); }, ease.lin);
  }

  async function play() {
    const id = ++runId;
    const alive = () => id === runId;
    resetRush();
    UI.resetLog();
    UI.playing();
    if (scrollY > 40) scrollTo({ top: 0, behavior: "smooth" });
    cinema(true);
    director = { pos: V(-82, 11, 22), at: V(-42, 0, -2) };
    UI.setNote(`${hhmm(D.requests[0].time)}. ${D.requests.length} drivers head for the campus gate.`);
    const arrivals = D.requests.map(async (q, i) => {
      await sleep(i * 560);
      if (!alive()) return;
      UI.setClock(hhmm(q.time));
      UI.showLog(i);
      UI.setNote(`${q.driver} arrives and asks for ${q.space}`);
      const car = makeCar(q.driver, "wait", vehicleOf(q.driver));
      placeCar(car, -150 - i * 3, 0, 0);
      rushCars[i] = car;
      await drive(car, [QUEUE(i)], 26);
    });
    await Promise.all(arrivals);
    if (!alive()) return;
    await sleep(300);

    // reason once over all requests
    UI.setClock(UI.decisionTime());
    director = { pos: V(-34, 14, 30), at: V(-12, 8, 0) };
    ringGroup.visible = true;
    let known = D.run.facts;
    const n = D.run.fired.length;
    for (const [k, fired] of D.run.fired.entries()) {
      if (!alive()) return;
      known += fired;
      setRing((k + 1) / n);
      ringLabel.element.textContent = `Reasoning: cycle ${k + 1} of ${n}, ${known} facts`;
      UI.setNote(`Forward chaining, cycle ${k + 1} of ${n}: ${known} facts known`);
      await sleep(240);
    }
    await sleep(500);
    ringGroup.visible = false;

    let away = 0;
    const gateShot = { pos: V(GATE_X - 9, 6.5, 15), at: V(GATE_X - 2, 1.2, 0) };
    for (const [i, q] of D.requests.entries()) {
      if (!alive()) return;
      const car = rushCars[i];
      director = gateShot;
      UI.setNote(`The gate checks ${q.driver}, who asks for ${q.space}`);
      await drive(car, [STOP], 12);
      if (!alive()) return;
      await scan(q.allocated ? 0x4ade80 : 0xff4a4a);
      if (q.allocated) {
        setCarKind(car, "ok");
        bubble(car, `Allocated <b>${q.space}</b>`, "ok");
        UI.setNote(`${q.driver} is allocated ${q.space}: rule R28 holds`);
        await openArm(true);
        const bay = bays[q.space];
        director = { follow: car, off: V(-6, 8, -bay.side * 10) };
        const legs = parkLegs(bay);
        car.indicate = bay.side;
        await drive(car, legs.fwd, 11);
        openArm(false);
        // watch the reverse from across the road, looking into the bay
        director = { follow: car, off: V(7, 9, -bay.side * 11) };
        await sleep(250);
        await drive(car, legs.back, 5, { reverse: true });
        car.indicate = 0;
        glowBay(bay);
        sparks(bay.cx, bay.cz, 0x4ade80);
        await sleep(500);
      } else {
        setCarKind(car, "no");
        shockRing(car.g.position.x, car.g.position.z, 0xff4a4a);
        bubble(car, `Refused<span>${shortReason(q)}</span>`, "no", 3000);
        UI.setNote(`${q.driver} is refused. ${UI.plainReason(i)}`);
        await shake(car);
        await sleep(800);
        await turnAway(car, AWAY_SLOT(away++));
      }
      if (!alive()) return;
      UI.setVerdict(i);
      await sleep(150);
    }
    if (!alive()) return;
    director = { pos: V(-20, 40, 46), at: V(-20, 0, -2) };
    UI.finished();
    await sleep(2600);
    if (alive()) { cinema(false); director = null; }
  }

  function finalRush() {
    runId++;
    cinema(false);
    director = null;
    resetRush();
    UI.resetLog();
    let away = 0;
    D.requests.forEach((q, i) => {
      const car = makeCar(q.driver, q.allocated ? "ok" : "no", vehicleOf(q.driver));
      setCarKind(car, q.allocated ? "ok" : "no");
      if (q.allocated) {
        const b = bays[q.space];
        placeCar(car, b.cx, b.cz, (b.side * Math.PI) / 2);   // reversed in, facing the road
        b.fill.material.opacity = 0.18;
      } else {
        const s = AWAY_SLOT(away++);
        placeCar(car, s[0], s[1], Math.PI);
      }
      rushCars[i] = car;
      UI.setVerdict(i);
    });
    UI.finished();
  }
  setLoad(0.7);

  /* ---------------------------------------------------------------- */
  /* knowledge core (forward chaining)                                 */
  /* ---------------------------------------------------------------- */
  const CORE = new THREE.Vector3(-8, 46, -40);
  const core = new THREE.Group();
  core.position.copy(CORE);
  scene.add(core);
  const coreLabels = [];
  const shell = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(4, 1)),
    new THREE.LineBasicMaterial({ color: hdr(0xf2c230, 2.2), toneMapped: false, transparent: true, opacity: 0.9 }));
  core.add(shell);
  const heart = new THREE.Mesh(new THREE.IcosahedronGeometry(2.2, 2), new THREE.MeshBasicMaterial({ color: hdr(0xffb020, 1.6), toneMapped: false }));
  core.add(heart);
  const coreGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0xffb84a, transparent: true, opacity: 0.55, depthWrite: false, blending: THREE.AdditiveBlending }));
  coreGlow.scale.set(22, 22, 1);
  core.add(coreGlow);

  const ruleRing = new THREE.Group();
  core.add(ruleRing);
  const ruleNodes = D.rules.map((r, i) => {
    const a = (i / D.rules.length) * Math.PI * 2;
    const m = new THREE.Mesh(new THREE.OctahedronGeometry(0.62), new THREE.MeshBasicMaterial({ color: hdr(0xf2c230, 1.2), toneMapped: false }));
    m.position.set(Math.cos(a) * 20, Math.sin(a * 3) * 1.5, Math.sin(a) * 20);
    ruleRing.add(m);
    m.userData.label = label(r.id, "rule", m, new THREE.Vector3(0, 1.3, 0));
    m.userData.label.visible = false;
    return m;
  });
  const ruleIndex = Object.fromEntries(D.rules.map((r, i) => [r.id, i]));

  const total = D.stats.facts + D.stats.derived;
  const slots = [];
  for (let i = 0; i < total; i++) {
    const y = 1 - (i / (total - 1)) * 2, r = Math.sqrt(1 - y * y), th = i * Math.PI * (3 - Math.sqrt(5));
    slots.push(new THREE.Vector3(Math.cos(th) * r * 13, y * 13, Math.sin(th) * r * 13));
  }
  const facts = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(0.3, 0), new THREE.MeshBasicMaterial({ toneMapped: false }), total);
  facts.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  core.add(facts);
  const baseCol = new THREE.Color(0.55, 0.62, 1.1), newCol = new THREE.Color(2.6, 1.9, 0.4), doneCol = new THREE.Color(1.5, 1.15, 0.35);
  const derivedOrder = [];
  D.cycles.forEach((c, ci) => c.derived.forEach((f) => derivedOrder.push({ cycle: ci, rule: f.rule })));
  const factScale = new Float32Array(total);
  const factPos = slots.map((v) => v.clone());
  const setFact = (i, pos, s, col) => {
    m4.compose(pos, new THREE.Quaternion(), new THREE.Vector3(s, s, s));
    facts.setMatrixAt(i, m4);
    if (col) facts.setColorAt(i, col);
  };
  for (let i = 0; i < total; i++) {
    const derived = i >= D.stats.facts;
    factScale[i] = derived ? 0 : 1;
    setFact(i, slots[i], factScale[i], derived ? doneCol : baseCol);
  }
  facts.instanceMatrix.needsUpdate = true;
  facts.instanceColor.needsUpdate = true;
  const coreCount = label("", "core", core, new THREE.Vector3(0, -17, 0));
  coreLabels.push(coreCount);
  let shownCycle = -1;
  let firedNow = new Set();
  const knownAt = (ci) => D.stats.facts + D.cycles.slice(0, ci + 1).reduce((s, c) => s + c.fired, 0);
  function setCycleInstant(ci) {
    derivedOrder.forEach((d, k) => {
      const i = D.stats.facts + k;
      factScale[i] = d.cycle <= ci ? 1 : 0;
      factPos[i].copy(slots[i]);
      setFact(i, slots[i], factScale[i], doneCol);
    });
    facts.instanceMatrix.needsUpdate = true;
    facts.instanceColor.needsUpdate = true;
    shownCycle = ci;
    firedNow = new Set(ci >= 0 ? D.cycles[ci].rules : []);
    coreCount.element.innerHTML = `<b>${knownAt(ci)}</b> facts known after cycle ${ci + 1}`;
  }
  function playCycle(ci) {
    if (ci !== shownCycle + 1) { setCycleInstant(ci); return; }
    shownCycle = ci;
    coreCount.element.innerHTML = `<b>${knownAt(ci)}</b> facts known after cycle ${ci + 1}`;
    const fired = new Set(D.cycles[ci].rules);
    firedNow = fired;
    fired.forEach((rid) => {
      const node = ruleNodes[ruleIndex[rid]];
      if (node) tween(900, (t) => { node.scale.setScalar(1 + 1.6 * Math.sin(t * Math.PI)); }, ease.lin);
    });
    let k = 0;
    derivedOrder.forEach((d, idx) => {
      if (d.cycle !== ci) return;
      const i = D.stats.facts + idx;
      const node = ruleNodes[ruleIndex[d.rule]] || heart;
      const from = new THREE.Vector3();
      node.getWorldPosition(from);
      core.worldToLocal(from);
      const to = slots[i], mid = from.clone().add(to).multiplyScalar(0.5).multiplyScalar(1.4);
      tween(1100, (t) => {
        const a = (1 - t) * (1 - t), b2 = 2 * (1 - t) * t, c = t * t;
        factPos[i].set(from.x * a + mid.x * b2 + to.x * c, from.y * a + mid.y * b2 + to.y * c, from.z * a + mid.z * b2 + to.z * c);
        factScale[i] = 0.4 + 1.2 * Math.sin(t * Math.PI) + t * 0.6;
        setFact(i, factPos[i], Math.min(1.6, factScale[i]), t < 0.98 ? newCol : doneCol);
        facts.instanceMatrix.needsUpdate = true;
        facts.instanceColor.needsUpdate = true;
      }, ease.inOut, Math.min(k++ * 28, 900)).then(() => { factScale[i] = 1; setFact(i, slots[i], 1, doneCol); facts.instanceMatrix.needsUpdate = true; facts.instanceColor.needsUpdate = true; });
    });
  }
  setCycleInstant(-1);
  coreCount.element.innerHTML = `<b>${D.stats.facts}</b> facts at the start`;
  setLoad(0.8);

  /* ---------------------------------------------------------------- */
  /* proof tower (backward chaining)                                   */
  /* ---------------------------------------------------------------- */
  const TOWER = new THREE.Vector3(72, 0, -30);
  const tower = new THREE.Group();
  tower.position.copy(TOWER);
  scene.add(tower);
  const towerPad = glowPlane(46, 46, 0xf2c230, 0.18);
  towerPad.position.copy(TOWER).add(new THREE.Vector3(0, 0.05, 0));
  scene.add(towerPad);
  let towerNodes = [], towerLabels = [];
  const hoverLabel = label("", "hover", scene);
  hoverLabel.visible = false;
  const nodeGeo = { rule: new RoundedBoxGeometry(1.3, 1.3, 1.3, 2, 0.2), fact: new THREE.SphereGeometry(0.5, 18, 12), naf: new THREE.OctahedronGeometry(0.75), bi: new THREE.TorusGeometry(0.45, 0.16, 10, 24) };
  const nodeMat = {
    rule: new THREE.MeshStandardMaterial({ color: 0xf2c230, emissive: 0xf2c230, emissiveIntensity: 0.9, roughness: 0.4 }),
    fact: new THREE.MeshBasicMaterial({ color: hdr(0x4ade80, 1.8), toneMapped: false }),
    naf: new THREE.MeshBasicMaterial({ color: hdr(0xb07cff, 1.8), toneMapped: false }),
    bi: new THREE.MeshBasicMaterial({ color: hdr(0x5cd0ff, 1.8), toneMapped: false }),
    fail: new THREE.MeshBasicMaterial({ color: hdr(0xff4a4a, 2.4), toneMapped: false }),
    block: new THREE.MeshStandardMaterial({ color: 0xff8a3d, emissive: 0xff7a2d, emissiveIntensity: 0.8, roughness: 0.4 }),
  };
  let towerRun = 0;
  function buildTower(i) {
    const run = ++towerRun;
    towerNodes.forEach((n) => tower.remove(n.mesh));
    towerLabels.forEach((l) => { tower.remove(l); l.element.remove(); });
    tower.children.filter((c) => c.isLineSegments).forEach((c) => { tower.remove(c); c.geometry.dispose(); });
    towerNodes = []; towerLabels = [];
    const q = D.requests[i];
    // normalise both tree kinds to {text, kind, children}
    const norm = q.allocated
      ? (n) => ({ text: `${n.t}   [${n.how}]`, kind: /^R\d+/.test(n.how) ? "rule" : n.how === "fact" ? "fact" : n.how.startsWith("negation") ? "naf" : "bi", c: n.c.map(norm) })
      : (r) => ({ text: (r.rule ? `${r.rule} blocked at ${r.goal}` : r.goal) + (r.detail ? `  (${r.detail})` : ""), kind: r.c.length ? (r.rule ? "block" : "fail") : "fail", c: r.c.map(norm) });
    const tree = norm(q.allocated ? q.proof : q.whyNot);
    if (!q.allocated) tree.kind = "fail";
    let leaf = 0, maxDepth = 0;
    const place = (n, depth) => {
      maxDepth = Math.max(maxDepth, depth);
      if (!n.c.length) { n.x = leaf++ * 2.6; } else { n.c.forEach((c) => place(c, depth + 1)); n.x = n.c.reduce((s, c) => s + c.x, 0) / n.c.length; }
      n.y = depth * 3.1 + 1.2;
      n.depth = depth;
    };
    place(tree, 0);
    const width = Math.max(1, (leaf - 1) * 2.6), height = maxDepth * 3.1 + 2;
    const s = Math.min(1.6, 30 / Math.max(width, 1), 24 / height);
    // centre the tower on the camera target (y = 12)
    tower.position.y = 12 - ((1.2 + maxDepth * 3.1 + 1.2) / 2) * s;
    const all = [];
    const walk = (n, parent) => { all.push({ n, parent }); n.c.forEach((c) => walk(c, n)); };
    walk(tree, null);
    const pos = (n) => new THREE.Vector3((n.x - width / 2) * s, n.y * s, Math.sin(n.x * 0.7) * 1.2 * s);
    const lineVerts = [];
    all.forEach(({ n, parent }) => {
      const mesh = new THREE.Mesh(nodeGeo[n.kind === "block" ? "rule" : n.kind === "fail" ? "fact" : n.kind], nodeMat[n.kind]);
      mesh.position.copy(pos(n));
      mesh.scale.setScalar(0.001);
      mesh.userData.text = n.text;
      mesh.castShadow = true;
      tower.add(mesh);
      towerNodes.push({ mesh, n });
      if (parent) { const a = pos(parent), b = pos(n); lineVerts.push(a.x, a.y, a.z, b.x, b.y, b.z); }
      tween(700, (t) => { if (run === towerRun) mesh.scale.setScalar(Math.max(0.001, t) * s * (n.kind === "fail" ? 1.4 : 1)); }, ease.back, n.depth * 160 + Math.random() * 120);
    });
    const lg = new THREE.BufferGeometry();
    lg.setAttribute("position", new THREE.Float32BufferAttribute(lineVerts, 3));
    const lines = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: q.allocated ? 0x8a8fa8 : 0xff8a6a, transparent: true, opacity: 0 }));
    tower.add(lines);
    tween(900, (t) => { lines.material.opacity = 0.75 * t; }, ease.out, 200);
    const rootLabel = label(`${q.goal}<span>${q.allocated ? "proved" : "cannot be proved"}</span>`, `towerroot ${q.allocated ? "ok" : "no"}`, tower, pos(tree).add(new THREE.Vector3(0, -2.2 * s - 0.6, 0)));
    towerLabels.push(rootLabel);
  }
  buildTower(UI.currentAnswer());
  setLoad(0.88);

  /* ---------------------------------------------------------------- */
  /* semantic network                                                  */
  /* ---------------------------------------------------------------- */
  const NET = new THREE.Vector3(-96, 20, -34);
  const net = new THREE.Group();
  net.position.copy(NET);
  scene.add(net);
  const netLabels = [];
  const NN = D.network.nodes, NE = D.network.edges;
  const idx = Object.fromEntries(NN.map((n, i) => [n.id, i]));
  // deterministic 3D force layout
  let seed = 7;
  const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647 - 0.5; };
  const P = NN.map(() => new THREE.Vector3(rnd() * 20, rnd() * 20, rnd() * 20));
  for (let it = 0; it < 420; it++) {
    const F = P.map(() => new THREE.Vector3());
    for (let a = 0; a < P.length; a++) for (let b = a + 1; b < P.length; b++) {
      const d = P[a].clone().sub(P[b]); const l = Math.max(0.5, d.length());
      const f = d.multiplyScalar(60 / (l * l * l));
      F[a].add(f); F[b].sub(f);
    }
    NE.forEach((e) => {
      const a = idx[e.s], b = idx[e.t]; const d = P[b].clone().sub(P[a]); const l = d.length();
      const f = d.multiplyScalar((l - 6.5) * 0.06 / Math.max(l, 0.01));
      F[a].add(f); F[b].sub(f);
    });
    P.forEach((p, i) => { F[i].add(p.clone().multiplyScalar(-0.012)); p.add(F[i].clampLength(0, 1.5)); });
  }
  const center = P.reduce((s, p) => s.add(p), new THREE.Vector3()).multiplyScalar(1 / P.length);
  P.forEach((p) => p.sub(center));
  const maxR = Math.max(...P.map((p) => p.length()));
  P.forEach((p) => p.multiplyScalar(14 / maxR));
  const kindStyle = {
    class: { geo: new THREE.IcosahedronGeometry(1.05, 1), col: hdr(0x6aa6ff, 1.6) },
    value: { geo: new THREE.SphereGeometry(0.85, 20, 14), col: hdr(0xffc04a, 1.7) },
    instance: { geo: new THREE.SphereGeometry(0.72, 20, 14), col: hdr(0x4ade80, 1.6) },
  };
  const netNodes = NN.map((n, i) => {
    const st = kindStyle[n.kind] || kindStyle.class;
    const m = new THREE.Mesh(st.geo, new THREE.MeshBasicMaterial({ color: st.col.clone(), toneMapped: false }));
    m.position.copy(P[i]);
    m.userData.text = n.id;
    net.add(m);
    const l = label(n.id, `net ${n.kind}`, m, new THREE.Vector3(0, 1.6, 0));
    netLabels.push(l);
    return { m, l, base: st.col.clone() };
  });
  const edgeLines = NE.map((e) => {
    const g = new THREE.BufferGeometry().setFromPoints([P[idx[e.s]], P[idx[e.t]]]);
    const mat = e.label === "instance-of"
      ? new THREE.LineDashedMaterial({ color: 0x3fae6a, dashSize: 0.6, gapSize: 0.4, transparent: true, opacity: 0.7 })
      : new THREE.LineBasicMaterial({ color: e.label === "is-a" ? 0x6aa6ff : 0x8a8fa8, transparent: true, opacity: 0.75 });
    const line = new THREE.Line(g, mat);
    if (e.label === "instance-of") line.computeLineDistances();
    net.add(line);
    return line;
  });
  const pulse = new THREE.Mesh(new THREE.SphereGeometry(0.55, 16, 12), new THREE.MeshBasicMaterial({ color: hdr(0xffe08a, 4), toneMapped: false }));
  pulse.visible = false;
  net.add(pulse);
  const highlights = [];
  const TRACES = {
    r13: { edges: [["p_ali", "has-class", "student_permit"], ["student_permit", "grants", "student_zone"], ["zone_a", "has-type", "student_zone"]],
      text: "p_ali has-class student_permit, which grants student_zone, which is the has-type of zone_a. This chain is rule R13: Ali may enter zone_a." },
    r14: { edges: [["car_ali", "has-type", "car"], ["car", "fits", "standard"], ["s_a5", "has-type", "standard"]],
      text: "car_ali has-type car, car fits standard, and standard is the has-type of s_a5. This chain is the vehicle-fit test in rule R14." },
  };
  let traceRun = 0;
  async function trace(key) {
    const run = ++traceRun;
    highlights.forEach((h) => net.remove(h));
    highlights.length = 0;
    netNodes.forEach((n) => { n.m.material.color.copy(n.base); n.m.scale.setScalar(1); n.l.element.classList.remove("lit"); });
    const T = TRACES[key];
    const cap = document.getElementById("trace-caption");
    if (cap) cap.textContent = T.text;
    autoSpin = false;
    for (const [s, , t] of T.edges) {
      if (run !== traceRun) return;
      const a = P[idx[s]], b = P[idx[t]];
      if (!a || !b) continue;
      [s, t].forEach((id) => { const n = netNodes[idx[id]]; n.m.material.color.set(hdr(0xffe08a, 2.6)); n.l.element.classList.add("lit"); tween(500, (k) => n.m.scale.setScalar(1 + 0.6 * Math.sin(k * Math.PI)), ease.lin); });
      const hl = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.13, 1, 8), new THREE.MeshBasicMaterial({ color: hdr(0xffd04a, 3), toneMapped: false }));
      net.add(hl);
      highlights.push(hl);
      pulse.visible = true;
      const dir = b.clone().sub(a), len = dir.length();
      hl.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
      await tween(900, (k) => {
        pulse.position.copy(a.clone().lerp(b, k));
        hl.scale.set(1, Math.max(0.001, len * k), 1);
        hl.position.copy(a.clone().lerp(b, k / 2));
      }, ease.inOut);
    }
    pulse.visible = false;
  }
  document.querySelectorAll("[data-trace]").forEach((b) => b.addEventListener("click", () => trace(b.dataset.trace)));
  setLoad(0.95);

  /* ---------------------------------------------------------------- */
  /* time of day: the scene follows the scenario clock                 */
  /* ---------------------------------------------------------------- */
  const PAL = {
    night: { top: 0x02030a, mid: 0x0b1030, bot: 0x1d1230, fog: 0x0a0b16, hemiSky: 0x5a6aa0, hemiGround: 0x07070a, hemi: 0.6, sunCol: 0xa9b8ff, sun: 0.7, exp: 1.05, stars: 0.85, lamps: 1, cityE: 0.9, cityCol: 0x07080d, ground: 0x0b0b0e, asphalt: 0x2a2c33, road: 0x121215, paint: 1.25, bloom: 0.6, env: 0.22 },
    dawn: { top: 0x2a3d6e, mid: 0xc47a6a, bot: 0xf3b27a, fog: 0x9a8088, hemiSky: 0xa8b4d8, hemiGround: 0x3a3024, hemi: 0.85, sunCol: 0xffb27a, sun: 1.7, exp: 1.0, stars: 0.1, lamps: 0.55, cityE: 0.35, cityCol: 0x3a3d47, ground: 0x2c3326, asphalt: 0x6a6c72, road: 0x45464b, paint: 0.45, bloom: 0.4, env: 0.45 },
    day: { top: 0x3f7bc8, mid: 0x93c0e8, bot: 0xdde9f2, fog: 0xbcd2e3, hemiSky: 0xd6e8ff, hemiGround: 0x4f5a3c, hemi: 1.15, sunCol: 0xfff3df, sun: 2.7, exp: 0.92, stars: 0, lamps: 0, cityE: 0.04, cityCol: 0xa4adbb, ground: 0x5b6e48, asphalt: 0x8a8d94, road: 0x5d5f66, paint: 0.12, bloom: 0.16, env: 0.85 },
    dusk: { top: 0x2a3a72, mid: 0xc7688a, bot: 0xffa866, fog: 0xa07a80, hemiSky: 0xc0a0c8, hemiGround: 0x3a2c20, hemi: 1.0, sunCol: 0xff9a5c, sun: 2.0, exp: 1.02, stars: 0.12, lamps: 0.7, cityE: 0.5, cityCol: 0x4a4650, ground: 0x48503a, asphalt: 0x74747a, road: 0x4c4c52, paint: 0.5, bloom: 0.4, env: 0.55 },
  };
  const KEYS = [[0, "night"], [4.5, "night"], [6, "dawn"], [8.5, "day"], [15.5, "day"], [18, "dusk"], [20, "night"], [24, "night"]];
  const COLOR_KEYS = new Set(["top", "mid", "bot", "fog", "hemiSky", "hemiGround", "sunCol", "cityCol", "ground", "asphalt", "road"]);
  const mixPal = (a, b, t) => {
    const o = {};
    for (const k in a) o[k] = COLOR_KEYS.has(k) ? new THREE.Color(a[k]).lerp(new THREE.Color(b[k]), t) : a[k] + (b[k] - a[k]) * t;
    return o;
  };
  const paletteAt = (h) => {
    for (let i = 0; i < KEYS.length - 1; i++) {
      const [h0, a] = KEYS[i], [h1, b] = KEYS[i + 1];
      if (h >= h0 && h <= h1) return mixPal(PAL[a], PAL[b], (h - h0) / Math.max(1e-6, h1 - h0));
    }
    return mixPal(PAL.night, PAL.night, 0);
  };
  // the sun crosses the sky from 06:00 to 18:00; at night the moon light stays put
  const sunPos = (h) => {
    if (h <= 5.5 || h >= 18.5) return V(-60, 90, 50);
    const a = Math.max(0.12, Math.min(Math.PI - 0.12, ((h - 6) / 12) * Math.PI));
    return V(-Math.cos(a) * 140, Math.max(14, Math.sin(a) * 130), 60);
  };
  scene.fog = new THREE.Fog(0x0a0b16, 150, 720);
  // Dark theme: the neon night at every hour. Light theme: real daylight, dusk
  // and night following the scenario clock. Closed zones get cones either way.
  const followsClock = () => root.getAttribute("data-theme") === "light";
  const skyHourFor = (h) => (followsClock() ? h : 0);
  let sky = paletteAt(skyHourFor(D.run.hour)), skyHour = -1;
  const sunTarget = new THREE.Vector3();
  function applySky(p) {
    skyMat.uniforms.top.value.copy(p.top); skyMat.uniforms.mid.value.copy(p.mid); skyMat.uniforms.bottom.value.copy(p.bot);
    scene.fog.color.copy(p.fog);
    hemi.color.copy(p.hemiSky); hemi.groundColor.copy(p.hemiGround); hemi.intensity = p.hemi;
    moon.color.copy(p.sunCol); moon.intensity = p.sun;
    renderer.toneMappingExposure = p.exp;
    starMat.opacity = p.stars;
    city.material.emissiveIntensity = p.cityE; city.material.color.copy(p.cityCol);
    ground.material.color.copy(p.ground); asphalt.material.color.copy(p.asphalt); road.material.color.copy(p.road);
    paintMat.emissiveIntensity = p.paint;
    if (bloomPass) bloomPass.strength = p.bloom;
    scene.environmentIntensity = p.env;
    boothGlass.material.emissiveIntensity = p.lamps * 1.4;
    nightHeadMat.color.copy(hdr(0xfff3d0, 0.5 + 3.5 * p.lamps));
  }
  function setTimeOfDay(hour, instant) {
    const h = skyHourFor(hour);
    sunTarget.copy(sunPos(h));
    if (h === skyHour) return;
    skyHour = h;
    const from = sky, to = paletteAt(h);
    if (instant) { sky = to; applySky(sky); moon.position.copy(sunTarget); return; }
    tween(1600, (t) => { sky = mixPal(from, to, t); applySky(sky); }, ease.inOut);
  }
  setTimeOfDay(D.run.hour, true);
  new MutationObserver(() => setTimeOfDay(D.run.hour)).observe(root, { attributes: true, attributeFilter: ["data-theme"] });

  /* quality: high = shadows, bloom, sharper pixels; low = none of those */
  const qBtn = document.getElementById("quality-toggle");
  const qLabel = () => { if (qBtn) qBtn.textContent = qPref === "auto" ? `Auto (${quality})` : quality === "high" ? "High" : "Low"; };
  function setQuality(q) {
    quality = q;
    renderer.setPixelRatio(Math.min(devicePixelRatio, q === "high" ? 1.5 : 1));
    renderer.setSize(innerWidth, innerHeight);
    if (composer) { composer.setPixelRatio(renderer.getPixelRatio()); composer.setSize(innerWidth, innerHeight); }
    const shadows = q === "high";
    if (renderer.shadowMap.enabled !== shadows) {
      renderer.shadowMap.enabled = shadows;
      scene.traverse((o) => { if (o.material) [].concat(o.material).forEach((m) => { m.needsUpdate = true; }); });
    }
    qLabel();
  }
  if (qBtn) {
    qBtn.hidden = false;
    qBtn.addEventListener("click", () => {
      qPref = { auto: "high", high: "low", low: "auto" }[qPref];
      try { localStorage.setItem(QKEY, qPref); } catch (e) { /* private mode */ }
      setQuality(qPref === "auto" ? (small ? "low" : "high") : qPref);
      fpsDone = qPref !== "auto";
    });
  }
  let fpsDone = qPref !== "auto" || quality === "low", fpsStart = 0, fpsFrames = 0;
  qLabel();

  /* ---------------------------------------------------------------- */
  /* scroll-driven camera                                              */
  /* ---------------------------------------------------------------- */
  const shots = [
    { el: "#top", zone: "lot", pos: V(-23, 54, 56), at: V(-23, 0, 0), fx: 0.55, fy: 0.64, nfy: 0.72 },
    { el: "#numbers-sec", zone: "lot", pos: V(18, 30, 52), at: V(-10, 2, -4), fx: 0.5, fy: 0.62 },
    { el: "#decide", zone: "core", pos: V(CORE.x + 6, CORE.y + 10, CORE.z + 62), at: CORE.clone(), fx: 0.72, fy: 0.5 },
    { el: "#why", zone: "tower", pos: V(TOWER.x - 4, 20, TOWER.z + 50), at: V(TOWER.x, 12, TOWER.z), fx: 0.27, fy: 0.5 },
    { el: "#network3d", zone: "net", pos: V(NET.x + 4, NET.y + 8, NET.z + 46), at: NET.clone(), fx: 0.73, fy: 0.52 },
    { el: "#models", zone: "orbit", pos: V(50, 46, 70), at: V(-10, 0, 0), fx: 0.5, fy: 0.5 },
    { el: "#tests", zone: "tests", pos: V(6, 17, -4), at: V(6, 1.5, -32), fx: 0.27, fy: 0.5 },
    { el: "#team", zone: "lot", pos: V(-70, 60, 130), at: V(-10, 14, 0), fx: 0.65, fy: 0.5 },
].map((s) => ({ nfy: 0.3, ...s, node: document.querySelector(s.el) })).filter((s) => s.node);
  const anchors = () => shots.map((s) => {
    const r = s.node.getBoundingClientRect();
    // wide: the section centred; narrow: the section top, where the scene shows above the panel
    return Math.max(0, innerWidth < 980 ? r.top + scrollY : r.top + scrollY + r.height / 2 - innerHeight / 2);
  });
  let A = anchors();
  addEventListener("resize", () => {
    A = anchors();
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
    labels.setSize(innerWidth, innerHeight);
    composer && composer.setSize(innerWidth, innerHeight);
  });
  new ResizeObserver(() => { A = anchors(); }).observe(document.body);
  let activeZone = "lot";
  // The camera holds still while a section is being read and glides once to
  // the next shot when the reader moves on. (It used to follow every scroll
  // step, so the whole scene kept shifting under the text.)
  const shotPose = (sh) => ({ pos: sh.pos.clone(), at: sh.at.clone(), zone: sh.zone, fx: sh.fx, fy: sh.fy, nfy: sh.nfy });
  const nearestIdx = (y) => A.reduce((best, a, i) => (Math.abs(a - y) < Math.abs(A[best] - y) ? i : best), 0);
  const nextShot = (y, cur) => {
    const best = nearestIdx(y);
    // leave the current shot only once the reader is clearly nearer another one
    return best !== cur && Math.abs(A[cur] - y) - Math.abs(A[best] - y) > innerHeight * 0.12 ? best : cur;
  };
  let shotIdx = nearestIdx(scrollY), glide = null;
  let pose = shotPose(shots[shotIdx]);
  function shotNow(now) {
    const want = nextShot(scrollY, shotIdx);
    if (want !== shotIdx) {
      glide = { from: { ...pose, pos: pose.pos.clone(), at: pose.at.clone() }, t0: now };
      shotIdx = want;
    }
    const to = shots[shotIdx];
    if (!glide) { pose = shotPose(to); return pose; }
    const f = glide.from, dist = f.pos.distanceTo(to.pos);
    const p = Math.min(1, (now - glide.t0) / Math.min(2200, 1100 + dist * 6)), e = ease.inOut(p);
    pose = {
      pos: f.pos.clone().lerp(to.pos, e).add(V(0, Math.sin(p * Math.PI) * Math.min(22, dist * 0.12), 0)),
      at: f.at.clone().lerp(to.at, e), zone: p < 0.5 ? f.zone : to.zone,
      fx: f.fx + (to.fx - f.fx) * e, fy: f.fy + (to.fy - f.fy) * e, nfy: f.nfy + (to.nfy - f.nfy) * e,
    };
    if (p >= 1) glide = null;
    return pose;
  }

  /* pointer: parallax, drag to look around, drag to turn the network, hover labels */
  let mx = 0, my = 0, yaw = 0, pitch = 0, dragging = false, dragKind = null, lastX = 0, lastY = 0, autoSpin = true;
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  canvas.addEventListener("pointerdown", (e) => {
    dragging = true; lastX = e.clientX; lastY = e.clientY;
    dragKind = activeZone === "net" ? "net" : "look";
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointerup", () => { dragging = false; });
  canvas.addEventListener("pointercancel", () => { dragging = false; });
  addEventListener("pointermove", (e) => {
    mx = e.clientX / innerWidth - 0.5; my = e.clientY / innerHeight - 0.5;
    ndc.set(mx * 2, -my * 2);
    if (!dragging) return;
    const dx = e.clientX - lastX, dy = e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;
    if (dragKind === "net") { net.rotation.y += dx * 0.008; net.rotation.x = Math.max(-0.8, Math.min(0.8, net.rotation.x + dy * 0.006)); autoSpin = false; }
    else { yaw = Math.max(-0.9, Math.min(0.9, yaw - dx * 0.005)); pitch = Math.max(-0.3, Math.min(0.35, pitch + dy * 0.003)); }
  });

  /* events from the page */
  addEventListener("krr:cycle", (e) => playCycle(e.detail.i));
  addEventListener("krr:answer", (e) => buildTower(e.detail.i));
  let testsLit = false;
  addEventListener("krr:tests", () => {
    if (testsLit) return;
    testsLit = true;
    beacons.forEach((b, i) => tween(600, (t) => {
      b.head.material.color.copy(new THREE.Color(0x3a3b44).lerp(b.pass ? new THREE.Color(0.35, 2.6, 0.9) : new THREE.Color(2.6, 0.4, 0.4), t));
      b.head.scale.setScalar(1 + Math.sin(t * Math.PI) * 0.8);
    }, ease.out, 300 + i * 140));
  });

  /* ---------------------------------------------------------------- */
  /* intro and frame loop                                              */
  /* ---------------------------------------------------------------- */
  paintLines.forEach((m) => m.scale.set(0.001, 1, 0.001));
  const t0 = performance.now();
  let introDone = false;
  const intro = { k: 1 };
  tween(3400, (t) => { intro.k = 1 - t; }, ease.inOut, 300).then(() => { introDone = true; });
  paintLines.forEach((m, i) => tween(700, (t) => { m.scale.set(Math.max(0.001, t), 1, Math.max(0.001, t)); }, ease.out, 900 + i * 45));
  lamps.forEach((l, i) => {
    tween(900, (t) => {
      const flick = t < 0.6 ? (Math.random() < 0.5 ? 0.15 : 1) * t : 1;
      l.on = flick;
    }, ease.lin, 1500 + i * 260);
  });
  const introFrom = { pos: V(-150, 95, 170), at: V(-10, 0, 0) };

  const camPos = camera.position.clone(), camAt = new THREE.Vector3(-10, 0, 0);
  let frameX = 0.5, frameY = 0.5;
  let lastT = performance.now();
  let hovered = null, labelsFar = false;
  function frame(now) {
    const dt = Math.min(0.05, (now - lastT) / 1000);
    lastT = now;
    for (const tw of [...tweens]) {
      if (now < tw.start) continue;
      const p = Math.min(1, (now - tw.start) / tw.dur);
      tw.update(tw.e(p));
      if (p >= 1) { tweens.delete(tw); tw.resolve(); }
    }
    const time = (now - t0) / 1000;

    // camera
    const s = { ...shotNow(now) };
    activeZone = s.zone;
    let pos = s.pos, at = s.at;
    const directing = director && root.classList.contains("is-cinema");
    if (directing) {
      activeZone = "lot";
      if (director.follow) {
        at = director.follow.g.position.clone().add(V(0, 1, 0));
        pos = at.clone().add(director.off);
      } else { pos = director.pos; at = director.at; }
      s.fx = 0.5; s.fy = 0.44; s.nfy = 0.4;
    }
    if (activeZone === "orbit") {
      const off = pos.clone().sub(at);
      off.applyAxisAngle(V(0, 1, 0), Math.sin(time * 0.07) * 0.12);
      pos = at.clone().add(off);
    }
    if (!directing && innerWidth < 980 && activeZone !== "lot") {
      // narrow screens see less sideways: pull back so each scene still fits
      pos = at.clone().add(pos.clone().sub(at).multiplyScalar(innerWidth < 600 ? 1.9 : 1.4));
    }
    if (!dragging) { yaw *= Math.pow(0.35, dt); pitch *= Math.pow(0.35, dt); }
    const off = pos.clone().sub(at).applyAxisAngle(V(0, 1, 0), yaw);
    off.y += pitch * off.length();
    pos = at.clone().add(off).add(V(mx * 1.2, -my * 0.8, 0));
    if (!introDone || intro.k > 0) {
      pos = pos.clone().lerp(introFrom.pos, intro.k);
      at = at.clone().lerp(introFrom.at, intro.k);
    }
    const k = 1 - Math.exp(-dt * 3.2);
    camPos.lerp(pos, k);
    camAt.lerp(at, k);
    camera.position.copy(camPos);
    camera.lookAt(camAt);
    // two thresholds, so the label size does not flick back and forth near one value
    const camDist = camPos.distanceTo(camAt);
    if (camDist > 46) labelsFar = true; else if (camDist < 38) labelsFar = false;
    labels.domElement.classList.toggle("far", labelsFar);
    // put the target where the page leaves room for it (narrow screens: centre)
    const wide = innerWidth > 980;
    frameX += ((wide ? s.fx : 0.5) - frameX) * k;
    frameY += ((wide ? s.fy : s.nfy) - frameY) * k;
    camera.setViewOffset(innerWidth, innerHeight, (0.5 - frameX) * innerWidth, (0.5 - frameY) * innerHeight, innerWidth, innerHeight);

    // ambient motion
    shell.rotation.y += dt * 0.25; shell.rotation.x += dt * 0.1;
    heart.scale.setScalar(1 + Math.sin(time * 2.2) * 0.06);
    ruleRing.rotation.y += dt * 0.08;
    if (autoSpin && !(dragging && dragKind === "net")) net.rotation.y += dt * 0.12;
    if (driving > 0) dashes.position.x = (dashes.position.x + dt * 6) % 6;
    lamps.forEach((l) => {
      const v = l.on * sky.lamps;
      l.head.material.color.set(hdr(0xffd58a, 0.05 + 2 * v));
      l.pool.material.opacity = 0.3 * v;
      if (l.light) l.light.intensity = 40 * v;
    });
    armTip.material.color.set(hdr(0xff4040, 1.6 + Math.sin(time * 2.2) * 0.6));
    moon.position.lerp(sunTarget, k * 0.6);
    const blink = (time * 2.4) % 1 < 0.5;
    rushCars.forEach((c) => {
      if (!c) return;
      c.cone.material.opacity = c.moving ? 0.12 * sky.lamps : 0;
      if (c.ind) [1, -1].forEach((side) => c.ind[side].color.copy(c.indicate === side && blink ? IND_ON : IND_OFF));
    });

    // first visit to the core: play the cycle the stepper is showing
    if (activeZone === "core" && shownCycle === -1) playCycle(UI.currentCycle());

    // labels for the zone in view only
    const show = (arr, on) => arr.forEach((l) => { l.visible = on; });
    show(lotLabels, activeZone === "lot" || activeZone === "tests" || activeZone === "orbit");
    show(coreLabels, activeZone === "core");
    D.rules.forEach((r, i) => { ruleNodes[i].userData.label.visible = activeZone === "core" && firedNow.has(r.id); });
    show(towerLabels, activeZone === "tower");
    show(netLabels, activeZone === "net");
    beacons.forEach((b) => { b.label.visible = activeZone === "tests"; });

    // hover labels for proof nodes
    if (activeZone === "tower" && !dragging) {
      ray.setFromCamera(ndc, camera);
      const hit = ray.intersectObjects(towerNodes.map((n) => n.mesh), false)[0];
      if (hit !== hovered) {
        hovered = hit ? hit.object : null;
        hoverLabel.visible = !!hovered;
        if (hovered) { hoverLabel.element.textContent = hovered.userData.text; hovered.getWorldPosition(hoverLabel.position); hoverLabel.position.y += 1.6; }
      }
    } else if (hoverLabel.visible) hoverLabel.visible = false;

    if (composer && quality === "high") composer.render(); else renderer.render(scene, camera);
    // auto quality: measure three seconds after the intro and drop to low below 30 fps
    if (!fpsDone && introDone) {
      if (!fpsStart) fpsStart = now;
      fpsFrames++;
      if (now - fpsStart > 3000) {
        fpsDone = true;
        if ((fpsFrames * 1000) / (now - fpsStart) < 30) setQuality("low");
      }
    }
    labels.render(scene, camera);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  setLoad(1);
  const loader = document.getElementById("loader");
  if (loader) { loader.classList.add("is-done"); setTimeout(() => loader.remove(), 900); }

  /* public controls used by app.js, then start the rush once it is on screen */
  window.KRR3D = { play, final: finalRush };
  setCycleInstant(-1);
  coreCount.element.innerHTML = `<b>${D.stats.facts}</b> facts at the start`;
  setTimeout(() => {
    if (UI.userActed()) return;
    if (scrollY < innerHeight * 0.6) play(); else finalRush();
  }, 3600);
}

boot();
