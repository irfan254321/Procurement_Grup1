import * as THREE from './three/three.module.min.js';

export function softBox(w,h,d,radius=.1){
  const r=Math.min(radius,w/2,h/2,d/2);
  const shape=new THREE.BoxGeometry(w,h,d,6,6,6);
  const pos=shape.attributes.position;
  const center=new THREE.Vector3(), corner=new THREE.Vector3();
  const x=w/2-r,y=h/2-r,z=d/2-r;
  for(let i=0;i<pos.count;i++){
    corner.fromBufferAttribute(pos,i);
    center.set(THREE.MathUtils.clamp(corner.x,-x,x),THREE.MathUtils.clamp(corner.y,-y,y),THREE.MathUtils.clamp(corner.z,-z,z));
    corner.sub(center).normalize();
    pos.setXYZ(i,center.x+corner.x*r,center.y+corner.y*r,center.z+corner.z*r);
    shape.attributes.normal.setXYZ(i,corner.x,corner.y,corner.z);
  }
  return shape;
}

export function studio(renderer,scene){
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=1.24;
  renderer.shadowMap.enabled=true;
  renderer.shadowMap.type=THREE.PCFShadowMap;
  scene.add(new THREE.HemisphereLight('#fff3dc','#819dc2',2.1));
  const key=new THREE.DirectionalLight('#ffe1bb',3.3);
  key.position.set(-6,17,9);
  key.castShadow=true;
  key.target.position.set(6,0,4);
  Object.assign(key.shadow.camera,{left:-12,right:12,top:12,bottom:-12,near:.5,far:40});
  key.shadow.mapSize.set(1024,1024);
  key.shadow.normalBias=.035;
  scene.add(key,key.target);
  const fill=new THREE.DirectionalLight('#b7dcff',1.45);
  fill.position.set(10,5,-8);
  scene.add(fill);
}
