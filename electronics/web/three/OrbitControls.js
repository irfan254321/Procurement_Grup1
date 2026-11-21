import {MathUtils, Spherical, Vector3} from './three.module.min.js';

/** Damped orbit, pan and zoom controls for the local perspective-camera studio. */
export class OrbitControls {
  constructor(camera, surface) {
    this.camera = camera;
    this.surface = surface;
    this.target = new Vector3();
    this.destination = new Vector3();
    this.orbit = new Spherical();
    this.goal = new Spherical();
    this.offset = new Vector3();
    this.axis = new Vector3();
    this.touches = new Map();
    this.minDistance = 2.25;
    this.maxDistance = 8;
    this.enableDamping = true;
    const release = event => this.release(event);
    this.events = {
      pointerdown: event => this.press(event),
      pointermove: event => this.move(event),
      pointerup: release,
      pointercancel: release,
      lostpointercapture: release,
      contextmenu: event => event.preventDefault(),
      wheel: event => this.wheel(event),
      keydown: event => this.key(event),
    };
    for (const [name, listener] of Object.entries(this.events)) {
      surface.addEventListener(name, listener, name === 'wheel' ? {passive: false} : undefined);
    }
    this.saveState();
  }

  saveState() {
    this.initialTarget = this.target.clone();
    this.initialOrbit = new Spherical().setFromVector3(this.offset.copy(this.camera.position).sub(this.target));
    this.reset();
  }

  reset() {
    this.destination.copy(this.initialTarget);
    this.target.copy(this.initialTarget);
    this.goal.copy(this.initialOrbit);
    this.orbit.copy(this.initialOrbit);
    this.update();
  }

  press(event) {
    if (event.button !== 0 && event.button !== 1 && event.button !== 2) return;
    this.surface.setPointerCapture(event.pointerId);
    this.touches.set(event.pointerId, {x: event.clientX, y: event.clientY, button: event.button});
    this.surface.classList.add('is-grabbing');
  }

  release(event) {
    this.touches.delete(event.pointerId);
    this.surface.classList.toggle('is-grabbing', this.touches.size > 0);
  }

  move(event) {
    const point = this.touches.get(event.pointerId);
    if (!point) return;
    const dx = event.clientX - point.x;
    const dy = event.clientY - point.y;
    const peer = event.pointerType === 'touch' && [...this.touches.values()].find(other => other !== point);
    if (peer) {
      const before = Math.hypot(point.x - peer.x, point.y - peer.y);
      const after = Math.hypot(event.clientX - peer.x, event.clientY - peer.y);
      if (before > 1 && after > 1) this.zoom(before / after);
      this.pan(dx / 2, dy / 2);
    } else if (point.button !== 0 || event.shiftKey) {
      this.pan(dx, dy);
    } else {
      this.rotate(dx, dy);
    }
    point.x = event.clientX;
    point.y = event.clientY;
  }

  rotate(dx, dy) {
    const factor = Math.PI / Math.max(1, this.surface.clientHeight);
    this.goal.theta -= dx * factor;
    this.goal.phi = MathUtils.clamp(this.goal.phi - dy * factor, .18, Math.PI / 2 + .12);
  }

  pan(dx, dy) {
    const factor = (2 * this.orbit.radius * Math.tan(MathUtils.degToRad(this.camera.fov / 2))) /
      Math.max(1, this.surface.clientHeight);
    this.destination.addScaledVector(this.axis.setFromMatrixColumn(this.camera.matrixWorld, 0), -dx * factor);
    this.destination.addScaledVector(this.axis.setFromMatrixColumn(this.camera.matrixWorld, 1), dy * factor);
    this.offset.copy(this.destination).sub(this.initialTarget).clampLength(0, 2.5);
    this.destination.copy(this.initialTarget).add(this.offset);
  }

  zoom(factor) {
    this.goal.radius = MathUtils.clamp(this.goal.radius * factor, this.minDistance, this.maxDistance);
  }

  wheel(event) {
    event.preventDefault();
    const units = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? this.surface.clientHeight : 1;
    this.zoom(Math.exp(MathUtils.clamp(event.deltaY * units, -250, 250) * .00175));
  }

  key(event) {
    const dx = event.key === 'ArrowLeft' ? -35 : event.key === 'ArrowRight' ? 35 : 0;
    const dy = event.key === 'ArrowUp' ? -35 : event.key === 'ArrowDown' ? 35 : 0;
    if (dx || dy) {
      if (event.shiftKey) this.pan(dx, dy);
      else this.rotate(dx, dy);
    } else if (event.key === '+' || event.key === '=') this.zoom(.88);
    else if (event.key === '-') this.zoom(1.13);
    else if (event.key === 'Home') this.reset();
    else return;
    event.preventDefault();
  }

  update(delta = 1 / 60) {
    const blend = this.enableDamping ? 1 - Math.exp(-Math.min(.1, delta) * 11) : 1;
    this.orbit.theta = MathUtils.lerp(this.orbit.theta, this.goal.theta, blend);
    this.orbit.phi = MathUtils.lerp(this.orbit.phi, this.goal.phi, blend);
    this.orbit.radius = MathUtils.lerp(this.orbit.radius, this.goal.radius, blend);
    this.target.lerp(this.destination, blend);
    this.camera.position.copy(this.target).add(this.offset.setFromSpherical(this.orbit));
    this.camera.lookAt(this.target);
    this.camera.updateMatrixWorld();
  }

  dispose() {
    for (const [name, listener] of Object.entries(this.events)) this.surface.removeEventListener(name, listener);
    this.touches.clear();
  }
}
