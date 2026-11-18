import * as THREE from './three/three.module.min.js';
import {studio,softBox,makeStudioActor} from './studio.mjs';
import {loadPolyAssets,placePoly} from './poly-assets.mjs';

export const districtBounds = new THREE.Box3(new THREE.Vector3(-.8,-.6,-.7),new THREE.Vector3(21.7,6.4,10.2));

// Fit the complete district in camera space, including its tower and outer lots.
// This keeps the same world visible when the browser or the map panel changes size.
export function fitDistrictCamera(camera,aspect){
  const center=districtBounds.getCenter(new THREE.Vector3());
  camera.position.copy(center).add(new THREE.Vector3(25,19,30));
  camera.lookAt(center);
  camera.updateMatrixWorld();
  const corner=new THREE.Vector3();
  let halfWidth=0,halfHeight=0;
  for(const x of [districtBounds.min.x,districtBounds.max.x]){
    for(const y of [districtBounds.min.y,districtBounds.max.y]){
      for(const z of [districtBounds.min.z,districtBounds.max.z]){
        corner.set(x,y,z).applyMatrix4(camera.matrixWorldInverse);
        halfWidth=Math.max(halfWidth,Math.abs(corner.x));
        halfHeight=Math.max(halfHeight,Math.abs(corner.y));
      }
    }
  }
  const ratio=Math.max(.25,aspect||1);
  halfHeight=Math.max(halfHeight,halfWidth/ratio)*1.07;
  halfWidth=halfHeight*ratio;
  Object.assign(camera,{left:-halfWidth,right:halfWidth,top:halfHeight,bottom:-halfHeight});
  camera.updateProjectionMatrix();
  return camera;
}

export function deliveryPath(vendor,route=[]){
  const lane=route.includes('Hub Selatan')?5.77:route.includes('Hub Utara')?3.70:4.7;
  return [
    new THREE.Vector3(vendor.x+.58,0,vendor.y+.43),
    new THREE.Vector3(vendor.x+.58,0,lane),
    new THREE.Vector3(5.25,0,lane),
    new THREE.Vector3(5.25,0,3.22),
  ];
}

export async function createDistrict(canvas,offices,vendors,markers){
  const assets=await loadPolyAssets(['office','truck']);
  const renderer=new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
  renderer.setSize(1400,700,false);
  renderer.domElement.className='district-webgl';
  renderer.domElement.setAttribute('aria-hidden','true');
  const scene=new THREE.Scene();
  scene.background=new THREE.Color('#d6e8ed');
  studio(renderer,scene);
  const camera=new THREE.OrthographicCamera(-15,15,8,-8,.2,100);
  fitDistrictCamera(camera,2);
  const reduce=window.matchMedia('(prefers-reduced-motion: reduce)');
  function mesh(parent,geometry,color,x,y,z){
    const object=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,roughness:.74}));
    object.position.set(x,y,z);object.castShadow=true;object.receiveShadow=true;parent.add(object);
    return object;
  }
  const box=(x,y,z,w,h,d,color,parent=scene)=>mesh(parent,softBox(w,h,d,.14),color,x,y,z);
  const point=new THREE.Vector3(), anchors=new Map();
  const podium=box(10.45,-.27,4.7,22,.52,10.6,'#aac88e');
  podium.castShadow=false;
  const road=box(10.45,-.029,4.7,21.7,.07,1.15,'#70828e');
  road.castShadow=false;
  for(const z of [3.70,5.77])box(12.7,-.029,z,15.55,.07,.58,'#87959a').castShadow=false;
  for(const x of [7.1,12.0,17.0])box(x,-.028,4.7,.85,.075,9.5,'#70828e').castShadow=false;
  box(5.25,-.028,4.52,.85,.075,3.1,'#70828e').castShadow=false;
  for(let x=.5;x<21;x+=.83)box(x,.015,4.7,.37,.014,.043,'#ffefc2').castShadow=false;
  for(const z of [4.05,5.35])box(10.45,.018,z,21.5,.052,.16,'#dddcc0').castShadow=false;
  for(const [x,z,size] of [[1.1,1,.9],[2,7.7,1.05],[5.7,1.15,.8],[11.2,.15,.95],[19.1,2.4,.9],[8.2,8.95,.8],[18.9,8.6,.83],[.55,6.15,.85],[20.5,6.6,.9],[13.1,9.1,.8]]){
    mesh(scene,new THREE.CylinderGeometry(.085,.14,.78,10),'#987555',x,.4,z);
    for(const [dx,dy,dz,color] of [[0,.94,0,'#588e6d'],[-.25,1.12,.05,'#69a872'],[.15,1.36,-.08,'#8bb872']]){
      mesh(scene,new THREE.SphereGeometry(size*.34,19,13),color,x+dx,dy,z+dz);
    }
  }
  for(const x of [1,3,5.15,8.65,10.75,13,15.3,18,20.7]){
    mesh(scene,new THREE.CylinderGeometry(.026,.048,.56,8),'#5c7079',x,.28,4.05);
    mesh(scene,new THREE.SphereGeometry(.092,12,8),'#fff1ae',x,.59,4.05);
  }
  for(const [x,z] of [[1.65,7.1],[7.9,8.6],[14.6,.45]]){
    box(x,.13,z,.72,.22,.34,'#9b7659');
    box(x,.24,z-.13,.72,.11,.08,'#ab8965');
  }
  box(3.15,.18,2.2,3.5,.38,2.7,'#dad8ba');
  box(3.15,2.75,1.83,3.2,5.25,1.44,'#397b83');
  box(3.15,5.48,2.16,3.48,.33,2.15,'#edbb73');
  box(3.15,5.69,2.16,2.62,.13,1.56,'#71b2ac');
  const towerSign=document.createElement('canvas');
  towerSign.width=256;towerSign.height=96;
  const sign=towerSign.getContext('2d');
  sign.fillStyle='#e3f5e7';sign.font='bold 70px system-ui';sign.textAlign='center';sign.textBaseline='middle';sign.fillText('BIZ',128,48);
  const texture=new THREE.CanvasTexture(towerSign),material=new THREE.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false});
  const logo=new THREE.Mesh(new THREE.PlaneGeometry(1.01,.4),material);
  logo.position.set(3.15,5.48,3.246);scene.add(logo);
  const floors=new Map();
  const cast=[];
  for(const [role,o] of Object.entries(offices)){
    const y=.43+o.level*.79;
    const deck=box(3.16,y,2.53,3.3,.12,1.32,'#e7d9bb');
    box(1.76,y+.34,2.53,.13,.58,1.2,o.color);
    box(4.56,y+.34,2.53,.13,.58,1.2,o.color);
    box(3.73,y+.18,2.49,.56,.25,.37,'#be8d5a');
    box(3.79,y+.34,2.5,.23,.21,.07,'#78bdcf');
    const figure=makeStudioActor(o.level,false,role);
    figure.root.scale.setScalar(.47);scene.add(figure.root);
    figure.root.position.set(3.20,y+.066,2.67);
    figure.root.rotation.y=.58;
    figure.prop.visible=false;
    cast.push({role,figure});
    floors.set(role,deck);
    anchors.set(role,[1.87,y+.5,3.3]);
  }
  for(const [name,o] of Object.entries(vendors)){
    const x=o.x+.58,z=o.y+.43;
    box(x,-.025,(z+4.7)/2,.46,.06,Math.abs(z-4.7)+1.1,'#87959a').castShadow=false;
    box(x,.09,z,1.94,.18,1.72,'#e3d6b9');
    const office=assets.office&&placePoly(scene,assets.office,{
      x,y:.16,z,width:1.76,height:o.floors*.74+.22,depth:1.57,
    });
    if(office){
      box(x,.115,z,1.72,.1,1.57,o.color);
    }else{
      box(x,.37*o.floors+.11,z,1.62,.74*o.floors,1.45,'#f5dfbb');
      for(let floor=0;floor<o.floors;floor++){
        const y=.52+floor*.74;
        box(x,y-.34,z,1.71,.11,1.55,o.color);
        for(const dx of [-.48,0,.48])box(x+dx,y,z+.727,.30,.29,.052,'#78b9d0');
        for(const dz of [-.39,.19])box(x+.813,y,z+dz,.053,.29,.31,'#74acc0');
      }
      box(x,o.floors*.74+.22,z,1.79,.24,1.65,o.color);
      box(x+.26,o.floors*.74+.41,z-.2,.41,.18,.39,'#749092');
    }
    anchors.set(name,[x,o.floors*.74+.54,z]);
  }
  const visitors=Array.from({length:4},(_,index)=>{
    const figure=makeStudioActor(index+2,true);
    scene.add(figure.root);
    figure.root.scale.setScalar(.53);
    figure.root.rotation.y=-Math.PI/2;
    figure.prop.visible=false;
    return figure;
  });
  const truck=new THREE.Group();scene.add(truck);
  if(assets.truck){
    placePoly(truck,assets.truck,{width:1.12,height:.73,depth:.50,angle:Math.PI/2});
  }else{
    box(-.18,.35,0,.65,.43,.37,'#e8a95f',truck);
    box(.24,.29,0,.27,.33,.37,'#548eb9',truck);
    box(.299,.369,.01,.18,.13,.39,'#9bdee5',truck);
    for(const x of [-.33,.25])for(const z of [-.201,.201]){
      const wheel=mesh(truck,new THREE.CylinderGeometry(.104,.104,.073,14),'#324354',x,.12,z);
      wheel.rotation.x=Math.PI/2;
    }
  }
  truck.visible=false;
  const fleet=new Map();
  let frame=0,world,moveTime=-1,lastEvent,lastStamp;
  function draw(time){
    frame=0;
    if(!canvas.parentElement?.getClientRects().length)return;
    for(const {role,figure} of cast){
      const active=role===lastEvent?.role;
      const swing=reduce.matches?0:Math.sin(time/190);
      figure.head.rotation.y=swing*.12;
      figure.arms[1].rotation.x=active?-.75+swing*.54:-.08;
      figure.body.position.y=active?Math.abs(swing)*.032:0;
      floors.get(role).material.emissive.set(active?'#e1bf5e':'#000000');
      floors.get(role).material.emissiveIntensity=.37;
    }
    const arrivals=lastEvent?.role==='buyer'?(lastEvent.customers??[]):[];
    visitors.forEach((figure,index)=>{
      figure.root.visible=index<arrivals.length;
      if(!figure.root.visible)return;
      const t=reduce.matches?1:THREE.MathUtils.clamp((time-moveTime-index*180)/1750,0,1);
      const stride=t<1?Math.sin(time/78):0;
      figure.root.position.set(THREE.MathUtils.lerp(6.05,3.55,t)+index*.36,0,5.35+index*.12);
      figure.legs[0].rotation.x=stride*.45;
      figure.legs[1].rotation.x=-stride*.45;
      figure.body.position.y=Math.abs(stride)*.035;
    });
    for(const vehicle of fleet.values())vehicle.visible=false;
    const shipments=lastEvent?.shipment==='shipping'
      ?(lastEvent.shipments?.length?lastEvent.shipments:[{vendor:lastEvent.vendor}]):[];
    shipments.forEach((shipment,index)=>{
      const vendor=vendors[shipment.vendor];
      if(!vendor)return;
      const key=shipment.vendor;
      let vehicle=fleet.get(key);
      if(!vehicle){vehicle=truck.clone(true);scene.add(vehicle);fleet.set(key,vehicle)}
      vehicle.visible=true;
      const t=reduce.matches?1:Math.max(0,Math.min((time-moveTime-index*180)/3300,1));
      const points=deliveryPath(vendor,shipment.route?.path),segments=points.slice(1).map((point,i)=>point.distanceTo(points[i]));
      let remaining=t*segments.reduce((a,b)=>a+b,0),segment=0;
      while(segment<segments.length-1&&remaining>segments[segment])remaining-=segments[segment++];
      vehicle.position.lerpVectors(points[segment],points[segment+1],Math.min(1,remaining/segments[segment]));
      const direction=points[segment+1].clone().sub(points[segment]);
      vehicle.rotation.y=Math.atan2(-direction.z,direction.x);
    });
    renderer.render(scene,camera);
    frame=requestAnimationFrame(draw);
  }
  let viewWidth=1400,viewHeight=700;
  function positionMarkers(){
    for(const button of markers.children){
      const anchor=anchors.get(button.dataset.role);
      if(!anchor)continue;
      point.set(...anchor).project(camera);
      const office=offices[button.dataset.role];
      const floor=!!office;
      button.classList.toggle('floor-marker',floor);
      const width=button.offsetWidth||170;
      const minLeft=floor?width+8:width/2+8;
      const maxLeft=viewWidth-(floor?8:width/2+8);
      const left=THREE.MathUtils.clamp((.5+.5*point.x)*viewWidth,minLeft,maxLeft);
      const compactOffset=floor&&viewWidth<600?(office.level-2.5)*16:0;
      const top=THREE.MathUtils.clamp((.5-.5*point.y)*viewHeight-(!floor?16:0)-compactOffset,20,viewHeight-20);
      button.style.left=100*left/viewWidth+'%';
      button.style.top=100*top/viewHeight+'%';
      button.hidden=Math.abs(point.x)>1.12||Math.abs(point.y)>1.12;
    }
  }
  function resize(){
    const rect=canvas.parentElement.getBoundingClientRect();
    if(!rect.width||!rect.height)return;
    viewWidth=rect.width;viewHeight=rect.height;
    renderer.setSize(viewWidth,viewHeight,false);
    fitDistrictCamera(camera,viewWidth/viewHeight);
    positionMarkers();
    if(!frame)frame=requestAnimationFrame(draw);
  }
  canvas.hidden=true;
  canvas.after(renderer.domElement);
  const observer=typeof ResizeObserver==='function'?new ResizeObserver(resize):null;
  observer?.observe(canvas.parentElement);
  window.addEventListener('resize',resize);
  resize();
  return {update(state){
    world=state;
    const event=world?.history[0];
    const stamp=event&&[event.tick,event.title,event.shipment,event.vendor].join(':');
    if(stamp!==lastStamp){lastStamp=stamp;moveTime=performance.now()}
    lastEvent=event;
    if(!frame)frame=requestAnimationFrame(draw);
  },setZoom(value){
    camera.zoom=THREE.MathUtils.clamp(value,.8,1.8);
    camera.updateProjectionMatrix();positionMarkers();
    if(!frame)frame=requestAnimationFrame(draw);
    return camera.zoom;
  }};
}
