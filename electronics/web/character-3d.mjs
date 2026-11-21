import * as THREE from './three/three.module.min.js';
import {softBox} from './studio.mjs';

export const characterHeight = 2.35;

const uniforms = {
  buyer: ['#55456f', '#dec271'], seller: ['#28655d', '#f0bb71'], stock: ['#284e64', '#d89445'],
  finance: ['#41465a', '#b97b62'], procurement: ['#355775', '#de994e'], deal: ['#584872', '#b8829b'],
  vendor: ['#30655f', '#e0aa74'], carrier: ['#23566b', '#e5af48'],
};
const skins = ['#c68e61', '#9e6448', '#deaa81', '#7c4936', '#cd966f'];
const hairstyles = ['#37261f', '#2a2529', '#503828', '#241f24'];
const geometries = new Map();

function geometry(key, build) {
  if (!geometries.has(key)) geometries.set(key, build());
  return geometries.get(key);
}

function group(parent, name, x = 0, y = 0, z = 0) {
  const node = new THREE.Group();
  node.name = name;
  node.position.set(x, y, z);
  parent.add(node);
  return node;
}

function shade(color, amount) {
  return new THREE.Color(color).lerp(new THREE.Color(amount < 0 ? '#12121d' : '#fff4df'), Math.abs(amount));
}

function torsoShape() {
  const form = softBox(.66, .64, .392, .13);
  const position = form.attributes.position;
  for (let index = 0; index < position.count; index++) {
    const y = position.getY(index);
    position.setX(index, position.getX(index) * (.83 + .17 * (y / .64 + .5)));
  }
  form.computeVertexNormals();
  return form;
}

/** Original stylized character, local front +Z and feet at y=0. */
export function createCharacter(options = {}) {
  const variant = Math.abs(Math.trunc(options.variant ?? 0)) || 0;
  const gender = options.gender === 'female' ? 'female' : 'male';
  const hairStyle = options.hairStyle ?? (gender === 'female' ? ['bob','bun','ponytail'][variant % 3] : 'short');
  const full = options.detail !== 'compact';
  const [uniform, accent] = uniforms[options.role] ?? ['#2b4354', '#b55e4e'];
  const skin = options.skin ?? skins[variant % skins.length];
  const hair = options.hair ?? hairstyles[variant % hairstyles.length];
  const jacket = options.jacket ?? uniform;
  const shirt = options.shirt ?? '#fff3e2';
  const tie = options.tie ?? accent;
  const pants = options.pants ?? shade(jacket, -.32);
  const shoe = '#2c2529';
  const materials = new Map();
  const root = new THREE.Group();
  root.name = 'Character root';
  Object.assign(root.userData, {gender, hairStyle});
  const pelvis = group(root, 'Pelvis', 0, .875, 0);
  const torso = group(pelvis, 'Torso', 0, .106, 0);
  const neck = group(torso, 'Neck', 0, .615, 0);
  const head = group(neck, 'Head', 0, .35, .013);

  function part(parent, form, color, x, y, z, roughness = .63, metalness = 0, shadow = true) {
    const tint = new THREE.Color(color);
    const key = [tint.getHexString(), roughness, metalness].join('/');
    if (!materials.has(key)) materials.set(key, new THREE.MeshStandardMaterial({color: tint, roughness, metalness}));
    const mesh = new THREE.Mesh(form, materials.get(key));
    mesh.position.set(x, y, z);
    mesh.castShadow = shadow;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }

  function oval(parent, color, x, y, z, sx, sy, sz, roughness, shadow = true) {
    const mesh = part(parent, geometry(full ? 'oval' : 'oval-compact', () =>
      new THREE.SphereGeometry(1, full ? 24 : 12, full ? 16 : 10)), color, x, y, z, roughness, 0, shadow);
    mesh.scale.set(sx, sy, sz);
    return mesh;
  }

  function block(parent, color, x, y, z, w, h, d, radius = .04, roughness, metalness, shadow = true) {
    return part(parent, geometry([w, h, d, radius].join('/'), () => softBox(w, h, d, radius)),
      color, x, y, z, roughness, metalness, shadow);
  }

  function curved(parent, color, points, radius, segments = 12) {
    const form = geometry([points.join('/'), radius, segments].join(';'), () => {
      const curve = new THREE.CatmullRomCurve3(points.map(coords => new THREE.Vector3(...coords)));
      return new THREE.TubeGeometry(curve, segments, radius, 6, false);
    });
    return part(parent, form, color, 0, 0, 0, .72, 0, false);
  }

  function trim(parent, color, points, z) {
    const form = geometry(['trim', points.join(';')].join('/'), () => {
      const shape = new THREE.Shape(points.map(coords => new THREE.Vector2(...coords)));
      return new THREE.ExtrudeGeometry(shape, {depth: .008, bevelEnabled: true,
        bevelSegments: 2, bevelSize: .005, bevelThickness: .004, steps: 1});
    });
    return part(parent, form, color, 0, 0, z, .76, 0, false);
  }

  oval(pelvis, pants, 0, -.009, 0, .266, .17, .18);
  part(torso, geometry('tailored jacket', torsoShape), jacket, 0, .282, 0);
  oval(neck, skin, 0, .012, .009, .13, .14, .122);
  trim(torso, shirt, [[-.171, .577], [-.072, .388], [.066, .388], [.153, .578]], .183);
  trim(torso, tie, [[0, .544], [-.031, .497], [-.023, .335], [0, .302], [.025, .336], [.028, .495]], .199);
  trim(torso, shade(tie, .17), [[-.037, .524], [0, .548], [.036, .524], [.023, .494], [-.02, .494]], .217);
  for (const sign of [-1, 1]) {
    const mirrored = points => points.map(([x, y]) => [x * sign, y]);
    trim(torso, shade(shirt, .08), mirrored([[.012, .555], [.073, .594], [.126, .563], [.094, .497]]), .209);
    trim(torso, shade(jacket, .17), mirrored([[.11, .586], [.224, .522], [.169, .461], [.194, .431], [.049, .31]]), .194);
    if (full) block(torso, shade(jacket, -.1), sign * .188, .198, .193, .123, .02, .02, .007);
  }
  block(torso, '#dec797', 0, .397, .217, .085, .015, .015, .006, .29, .65);
  if (full) {
    for (const y of [.268, .183, .093]) oval(torso, shade(jacket, -.44), .023, y, .195, .018, .018, .012, .39, false);
    block(torso, shade(jacket, -.08), -.177, .408, .182, .114, .036, .018, .012);
    block(torso, shade(shirt, -.08), -.175, .43, .184, .069, .023, .012, .005).rotation.z = -.13;
  }

  const faceForm = geometry(full ? 'sculpted face' : 'sculpted face compact', () => {
    const mesh = new THREE.SphereGeometry(1, full ? 32 : 14, full ? 22 : 10);
    const pos = mesh.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const y = pos.getY(i);
      pos.setX(i, pos.getX(i) * (1 - Math.max(0, -y - .22) * .22));
    }
    mesh.computeVertexNormals();
    return mesh;
  });
  const face = part(head, faceForm, skin, 0, 0, 0, .52);
  face.scale.set(.332, .344, .29);
  oval(head, skin, 0, -.076, .282, .054, .051, .065, .56);
  const eyeGroups = [];
  for (const sign of [-1, 1]) {
    const ear = oval(head, skin, sign * .326, -.039, -.015, .067, .085, .046);
    ear.rotation.z = sign * -.2;
    if (full) oval(head, shade(skin, -.19), sign * .355, -.038, .014, .025, .043, .013);
    const x = sign * .127;
    const eye = group(head, sign < 0 ? 'Right eyelids' : 'Left eyelids', x, .024, .255);
    eye.rotation.y = sign * .14;
    eyeGroups.push(eye);
    oval(eye, shade(skin, -.26), 0, .003, -.008, .093, .085, .034, .63, false);
    oval(eye, '#fff6e8', 0, 0, 0, .084, .072, .035, .36, false);
    oval(eye, '#6d432e', -sign * .008, -.003, .031, .042, .052, .012, .3, false);
    if (full) oval(eye, '#9f6a43', -sign * .009, -.014, .041, .032, .038, .005, .37, false);
    oval(eye, '#241a21', -sign * .009, -.003, .045, .024, .033, .006, .25, false);
    oval(eye, '#ffffff', -.023, .023, .05, .015, .017, .004, .26, false);
    if (full) oval(eye, '#fce1bd', .015, -.027, .05, .007, .007, .003, .4, false);
    curved(eye, shade(skin, -.35), [[-.075, .024, .015], [-.037, .058, .028], [.019, .068, .028], [.071, .026, .018]], .008, 10);
    curved(head, shade(hair, .09), [[x - .068, .119, .249], [x - .031, .146, .264],
      [x + .021, .15, .266], [x + .065, .124, .247]], .016, 12);
    if (full) oval(head, shade(skin, -.14).lerp(new THREE.Color('#ee8d79'), .26), sign * .172, -.085, .235, .055, .034, .017, .72, false);
  }

  curved(head, '#833c37', [[-.091, -.126, .263], [-.047, -.154, .278], [0, -.165, .278],
    [.05, -.152, .27], [.09, -.12, .259]], .013);
  if (full) curved(head, '#f5d3ae', [[-.04, -.146, .28], [0, -.151, .282], [.036, -.145, .278]], .006, 8);
  oval(head, hair, 0, .135, -.102, .344, .234, .235, .36);
  oval(head, hair, 0, .207, -.034, .334, .164, .255, .37);
  const sweep = variant % 2 ? -1 : 1;
  oval(head, shade(hair, .06), sweep * .09, .228, .134, .254, .118, .155, .37).rotation.z = sweep * -.3;
  oval(head, hair, -sweep * .145, .208, .128, .171, .107, .151, .39).rotation.z = sweep * .43;
  oval(head, shade(hair, -.12), sweep * .284, .105, .051, .067, .128, .091, .38).rotation.z = sweep * .13;
  if (hairStyle === 'bob') {
    oval(head, hair, 0, -.018, -.175, .332, .319, .193, .38);
    for (const sign of [-1,1]) {
      oval(head, shade(hair, sign * .08), sign * .26, -.039, -.065, .09, .272, .144, .38).rotation.z = sign * .065;
    }
  } else if (hairStyle === 'bun') {
    oval(head, shade(hair, -.09), .008, .215, -.283, .162, .153, .152, .42);
    oval(head, shade(hair, .08), .055, .247, -.316, .111, .106, .122, .42);
  } else if (hairStyle === 'ponytail') {
    oval(head, tie, .015, .04, -.302, .081, .067, .057, .55);
    oval(head, hair, .060, -.124, -.332, .118, .228, .114, .42).rotation.z = .22;
    oval(head, shade(hair, .08), .133, -.263, -.323, .082, .116, .073, .42).rotation.z = .40;
  }
  if (gender === 'female') for (const sign of [-1,1]) {
    oval(head, '#d6ac66', sign * .301, -.113, .068, .021, .024, .018, .35);
  }
  if (full) {
    for (const offset of [0, .041, .078]) {
      curved(head, shade(hair, .14), [[-sweep * .2, .266 + offset * .3, .148 + offset],
        [-sweep * .079, .324 - offset * .18, .161 + offset],
        [sweep * .085, .319 - offset * .35, .159 + offset], [sweep * .241, .218, .132 + offset]], .009);
    }
  }

  function arm(sign) {
    const side = sign > 0 ? 'Left' : 'Right';
    const shoulder = group(torso, side + ' shoulder', sign * .303, .506, -.008);
    const elbow = group(shoulder, side + ' elbow', 0, -.286, 0);
    const wrist = group(elbow, side + ' wrist', 0, -.25, 0);
    oval(shoulder, jacket, sign * .006, -.098, 0, .097, .203, .109);
    oval(elbow, jacket, 0, -.102, 0, .078, .158, .087);
    block(wrist, shirt, 0, .021, .005, .143, .051, .134, .026);
    oval(wrist, skin, 0, -.074, .008, .063, .091, .049);
    oval(wrist, shade(skin, -.05), -sign * .047, -.042, .037, .031, .043, .027);
    if (sign > 0 && full) {
      block(wrist, '#342c32', 0, -.002, .003, .143, .036, .124, .018);
      block(wrist, '#d4bb8d', 0, -.002, .072, .061, .058, .019, .016, .24, .64);
      block(wrist, '#2c3e47', 0, -.002, .082, .044, .041, .013, .012, .16, .17);
    }
    return {shoulder, elbow, wrist};
  }

  function leg(sign) {
    const side = sign > 0 ? 'Left' : 'Right';
    const hip = group(pelvis, side + ' hip', sign * .133, -.021, 0);
    const knee = group(hip, side + ' knee', 0, -.382, 0);
    const ankle = group(knee, side + ' ankle', 0, -.35, 0);
    oval(hip, pants, 0, -.171, 0, .125, .255, .131);
    block(knee, pants, 0, -.155, .004, .199, .363, .209, .071);
    block(ankle, '#3b3033', 0, -.097, .068, .205, .041, .344, .018);
    block(ankle, shoe, 0, -.045, .072, .195, .11, .326, .048, .28);
    if (full) block(ankle, '#775e48', 0, .016, .104, .136, .019, .037, .009, .3);
    return {hip, knee, ankle};
  }

  const left = arm(1);
  const right = arm(-1);
  const leftLeg = leg(1);
  const rightLeg = leg(-1);
  const briefcase = group(right.wrist, 'Briefcase handle pivot', -.015, -.102, .018);
  briefcase.visible = options.briefcase !== false;
  curved(briefcase, '#483231', [[-.086, -.048, .003], [-.075, .022, .003], [.058, .022, .003], [.078, -.048, .003]], .022);
  block(briefcase, '#743e2d', 0, -.169, 0, .317, .258, .133, .037, .41);
  block(briefcase, '#985b3d', 0, -.1, .066, .294, .116, .022, .024, .45);
  if (full) for (const x of [-.093, .092]) block(briefcase, '#dfb36e', x, -.154, .076, .036, .037, .012, .006, .3, .45);

  const handProps = group(torso, 'Carried items', 0, .14, .493);
  const carton = group(handProps, 'Carton');
  block(carton, '#bc8351', 0, 0, 0, .37, .28, .28, .02, .82);
  block(carton, '#efd09c', 0, .139, 0, .068, .012, .28, .004);
  block(carton, '#efdbb4', -.073, .025, .14, .086, .055, .01, .005);
  const paper = group(handProps, 'File folder');
  block(paper, '#b89259', 0, -.018, 0, .39, .04, .275, .014);
  block(paper, '#fff3d9', 0, .011, .009, .33, .025, .24, .008);
  for (const z of [-.054, -.015, .03]) block(paper, '#bac9b4', -.025, .025, z, .188, .004, .008, .002);
  handProps.visible = false;
  carton.visible = false;
  paper.visible = false;

  let lastTime;
  function animate(mode = 'idle', seconds = 0, {reducedMotion = false, intensity = 1, prop, seated = mode === 'sit'} = {}) {
    const time = Number.isFinite(seconds) ? seconds : 0;
    const strength = THREE.MathUtils.clamp(intensity, 0, 1);
    const elapsed = lastTime === undefined ? 1 : time >= lastTime ? Math.min(.1, time - lastTime) : 1 / 60;
    lastTime = time;
    const ease = reducedMotion ? 1 : 1 - Math.exp(-elapsed * 15);
    const walk = mode === 'walk';
    const wave = mode === 'wave';
    const type = mode === 'type' || mode === 'typing';
    const reading = seated && mode === 'read';
    const present = ['present', 'presentation', 'talk', 'inspect', 'scan', 'stamp', 'mail'].includes(mode);
    const payload = prop ?? (mode === 'carry' ? 'box' : mode === 'mail' || mode === 'stamp' ? 'paper' : null);
    const carry = payload === 'box' || payload === 'paper';
    const beat = reducedMotion ? 0 : time * 10.7;
    const stride = reducedMotion ? 0 : Math.sin(beat) * strength;
    const gesture = reducedMotion ? 0 : Math.sin(time * 6.8) * strength;
    const breathing = reducedMotion ? 0 : Math.sin(time * 2.2 + variant * .7) * strength;
    const damp = (from, to) => THREE.MathUtils.lerp(from, to, ease);
    const bob = walk ? Math.abs(stride) * .045 : breathing * .018;
    pelvis.position.y = damp(pelvis.position.y, (seated ? .56 : .875) + (seated ? bob * .35 : bob));
    pelvis.rotation.y = damp(pelvis.rotation.y, walk ? .065 * stride : 0);
    torso.rotation.x = damp(torso.rotation.x, walk ? .055 : type || reading ? .09 : 0);
    torso.rotation.z = damp(torso.rotation.z, walk ? .042 * stride : breathing * .015);
    torso.scale.y = 1 + breathing * .018;
    head.rotation.x = damp(head.rotation.x, reading ? .23 + .035 * gesture : type ? .14 : present ? -.04 + .07 * gesture : breathing * .033);
    head.rotation.y = damp(head.rotation.y, carry ? .02 + breathing * .035 : wave ? .1 + .09 * gesture : .085 * breathing);
    head.rotation.z = damp(head.rotation.z, present || wave ? -.075 : 0);

    for (const [sign, limbs, lower] of [[1, left, leftLeg], [-1, right, rightLeg]]) {
      const isRight = sign < 0;
      const step = sign * stride;
      const shoulderPitch = carry ? -.52 : type || reading ? seated ? -.96 : -.78 : isRight && wave ? -1.46 : isRight && present ? -.53 - .17 * gesture : walk ? step * .48 : -.05;
      const shoulderRoll = carry ? -sign * .33 : type || reading ? -sign * .18 : isRight && wave ? -.82 : isRight && present ? -.29 : sign * .1;
      const elbowPitch = carry ? -1.06 : type ? -.67 + .13 * gesture * sign : reading ? -.60 : isRight && wave ? -1.26 : isRight && present ? -1.12 : -.12 - (walk ? Math.max(0, step) * .28 : 0);
      limbs.shoulder.rotation.x = damp(limbs.shoulder.rotation.x, shoulderPitch);
      limbs.shoulder.rotation.z = damp(limbs.shoulder.rotation.z, shoulderRoll);
      limbs.elbow.rotation.x = damp(limbs.elbow.rotation.x, elbowPitch);
      limbs.wrist.rotation.z = damp(limbs.wrist.rotation.z, isRight && wave && !carry ? gesture * .52 : 0);
      limbs.wrist.rotation.x = damp(limbs.wrist.rotation.x, type ? .12 + .19 * gesture * sign : 0);
      lower.hip.rotation.x = damp(lower.hip.rotation.x, seated ? -1.48 : walk ? -.51 * step : 0);
      lower.knee.rotation.x = damp(lower.knee.rotation.x, seated ? 1.48 : walk ? Math.max(0, -step) * .65 : 0);
      lower.ankle.rotation.x = damp(lower.ankle.rotation.x, walk ? Math.max(0, step) * .27 - Math.max(0, -step) * .23 : 0);
    }
    const blinkTime = ((time + variant * .73 + 3.6) % 4.9 + 4.9) % 4.9;
    const blink = reducedMotion ? 0 : Math.max(0, 1 - Math.abs(blinkTime - 4.64) / .105, 1 - Math.abs(blinkTime - 4.89) / .07);
    for (const eye of eyeGroups) eye.scale.y = 1 - .92 * blink;
    handProps.visible = carry;
    carton.visible = payload === 'box';
    paper.visible = payload === 'paper';
    briefcase.visible = options.briefcase !== false && !carry && !type && !wave && !present && !seated;
    briefcase.rotation.x = damp(briefcase.rotation.x, walk ? .37 * stride : .05 * breathing);
    briefcase.rotation.z = damp(briefcase.rotation.z, walk ? -.11 * stride : -.08);
  }

  animate();
  return {
    root, pelvis, torso, neck, head,
    hands: {left: left.wrist, right: right.wrist},
    rig: {leftArm: left, rightArm: right, leftLeg, rightLeg},
    briefcase,
    props: {box: carton, paper},
    animate,
    dispose() {
      root.removeFromParent();
      for (const material of materials.values()) material.dispose();
    },
  };
}
