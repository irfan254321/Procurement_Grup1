import * as THREE from './three/three.module.min.js';
import {OrbitControls} from './three/OrbitControls.js';
import {createCharacter} from './character-3d.mjs';

const mount = document.getElementById('character-canvas');
const feedback = document.getElementById('studio-feedback');
const captions = {idle: 'Idle', walk: 'Walk', wave: 'Wave', type: 'Mengetik', carry: 'Bawa kardus', present: 'Presentasi'};
const buttons = [...document.querySelectorAll('[data-mode]')];
const resetCamera = document.getElementById('reset-camera');
const lowMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

function light(scene, color, intensity, position, shadow = false) {
  const lamp = new THREE.DirectionalLight(color, intensity);
  lamp.position.set(...position);
  if (shadow) {
    lamp.castShadow = true;
    Object.assign(lamp.shadow.camera, {left: -3, right: 3, bottom: -3, top: 3, near: .1, far: 18});
    lamp.shadow.mapSize.set(1024, 1024);
    lamp.shadow.normalBias = .014;
    lamp.shadow.bias = -.00024;
    lamp.shadow.radius = 3;
  }
  scene.add(lamp);
}

function buildScene() {
  const renderer = new THREE.WebGLRenderer({antialias: true, alpha: false});
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.75));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.13;
  renderer.domElement.tabIndex = 0;
  renderer.domElement.setAttribute('aria-label', 'Kamera 3D. Gunakan tombol panah dan plus atau minus.');
  mount.append(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#d7e7d2');
  scene.fog = new THREE.Fog('#d7e7d2', 7, 18);

  const ground = new THREE.Mesh(new THREE.PlaneGeometry(45, 45), new THREE.MeshStandardMaterial({color: '#dce8d2', roughness: .97}));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -.158;
  ground.receiveShadow = true;
  scene.add(ground);
  const plinth = new THREE.Mesh(new THREE.CylinderGeometry(1.13, 1.18, .15, 96),
    new THREE.MeshStandardMaterial({color: '#719479', roughness: .76}));
  plinth.position.y = -.077;
  plinth.castShadow = plinth.receiveShadow = true;
  scene.add(plinth);
  const track = new THREE.Mesh(new THREE.RingGeometry(.915, .926, 96),
    new THREE.MeshStandardMaterial({color: '#c6debc', roughness: .91, side: THREE.DoubleSide}));
  track.rotation.x = -Math.PI / 2;
  track.position.y = -.001;
  scene.add(track);

  scene.add(new THREE.HemisphereLight('#f9fff3', '#6c8c84', 1.8));
  light(scene, '#fff0d5', 3.2, [-3, 6, 5], true);
  light(scene, '#c8e7f2', 1.85, [5, 2.5, 4]);
  light(scene, '#f9ecbb', 2.55, [1.4, 4, -4]);

  const camera = new THREE.PerspectiveCamera(33, 1, .05, 34);
  camera.position.set(3.4, 2.46, 4.38);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 1.12, 0);
  controls.saveState();
  const actor = createCharacter({role: 'procurement', variant: 0});
  actor.root.rotation.y = .23;
  scene.add(actor.root);
  let mode = 'idle';
  let previous = performance.now();
  function render(time) {
    const duration = Math.max(0, (time - previous) / 1000);
    previous = time;
    controls.enableDamping = !lowMotion.matches;
    controls.update(duration);
    actor.animate(mode, time / 1000, {reducedMotion: lowMotion.matches});
    renderer.render(scene, camera);
  }
  const size = new ResizeObserver(() => {
    const bounds = mount.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    renderer.setSize(bounds.width, bounds.height, false);
    camera.aspect = bounds.width / bounds.height;
    camera.updateProjectionMatrix();
  });
  size.observe(mount);
  for (const button of buttons) button.onclick = () => {
    mode = button.dataset.mode;
    document.getElementById('mode-caption').textContent = captions[mode];
    for (const option of buttons) option.setAttribute('aria-pressed', String(button === option));
  };
  resetCamera.onclick = () => controls.reset();
  renderer.setAnimationLoop(render);
}

try {
  buildScene();
} catch (error) {
  console.warn('Studio karakter tidak dapat membuka WebGL.', error);
  feedback.textContent = 'Pratinjau 3D membutuhkan browser dengan dukungan WebGL.';
  feedback.hidden = false;
  for (const button of [...buttons, resetCamera]) button.disabled = true;
}
