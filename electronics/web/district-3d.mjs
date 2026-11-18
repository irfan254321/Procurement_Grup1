import * as THREE from './three/three.module.min.js';
import {studio,softBox,makeStudioActor} from './studio.mjs';
import {loadPolyAssets,placePoly} from './poly-assets.mjs';

export async function createDistrict(canvas,offices,vendors,markers){
  const assets=await loadPolyAssets(['office','truck']);
  const renderer=new THREE.WebGLRenderer({antialias:true});
  renderer.setSize(1100,660,false);
  renderer.domElement.className='district-webgl';
  renderer.domElement.setAttribute('aria-hidden','true');
  const scene=new THREE.Scene();
  scene.background=new THREE.Color('#d6e8ed');
  studio(renderer,scene);
  const camera=new THREE.OrthographicCamera(-10.65,10.65,6.39,-6.39,.2,75);
  camera.position.set(20,14,21);
  camera.lookAt(6.85,1.9,3.35);
  camera.updateMatrixWorld();
  const reduce=window.matchMedia('(prefers-reduced-motion: reduce)');
  function mesh(parent,geometry,color,x,y,z){
    const object=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,roughness:.74}));
    object.position.set(x,y,z);object.castShadow=true;object.receiveShadow=true;parent.add(object);
    return object;
  }
  const box=(x,y,z,w,h,d,color,parent=scene)=>mesh(parent,softBox(w,h,d,.14),color,x,y,z);
  const point=new THREE.Vector3(), anchors=new Map();
  const podium=box(6.8,-.27,3.55,14.5,.52,8.05,'#aac88e');
  podium.castShadow=false;
  const road=box(6.85,-.029,3.67,14,.07,.95,'#70828e');
  road.castShadow=false;
  box(6.35,-.028,3.7,1,.075,7.35,'#70828e').castShadow=false;
  for(let x=.5;x<14;x+=.83)box(x,.015,3.67,.37,.014,.043,'#ffefc2').castShadow=false;
  for(const z of [3.13,4.21])box(7,.018,z,13.9,.052,.16,'#dddcc0').castShadow=false;
  for(const [x,z,size] of [[1.1,2.4,.9],[2,5.9,1.05],[5.5,1.15,.8],[11.8,.74,.95],[13.4,2.55,.9],[8.1,6.65,.8],[12.8,6.65,.83],[.55,5.15,.85]]){
    mesh(scene,new THREE.CylinderGeometry(.085,.14,.78,10),'#987555',x,.4,z);
    for(const [dx,dy,dz,color] of [[0,.94,0,'#588e6d'],[-.25,1.12,.05,'#69a872'],[.15,1.36,-.08,'#8bb872']]){
      mesh(scene,new THREE.SphereGeometry(size*.34,19,13),color,x+dx,dy,z+dz);
    }
  }
  for(const x of [1,3,5.15,8.65,10.75,12.7]){
    mesh(scene,new THREE.CylinderGeometry(.026,.048,.56,8),'#5c7079',x,.28,3.14);
    mesh(scene,new THREE.SphereGeometry(.092,12,8),'#fff1ae',x,.59,3.14);
  }
  for(const [x,z] of [[1.65,5.1],[8.2,5.85],[10.8,.95]]){
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
    anchors.set(role,[2.18,y+.5,3.23]);
  }
  for(const [name,o] of Object.entries(vendors)){
    const x=o.x+.58,z=o.y+.43;
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
  let frame=0,world,moveTime=-1,lastEvent;
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
      figure.root.position.set(THREE.MathUtils.lerp(6.05,3.55,t)+index*.36,0,4.22+index*.12);
      figure.legs[0].rotation.x=stride*.45;
      figure.legs[1].rotation.x=-stride*.45;
      figure.body.position.y=Math.abs(stride)*.035;
    });
    const vendor=lastEvent?.shipment==='shipping'&&vendors[lastEvent.vendor];
    truck.visible=!!vendor;
    if(vendor){
      const t=reduce.matches?1:Math.max(0,Math.min((time-moveTime)/3300,1));
      const start=vendor.x+.45;
      truck.position.set(THREE.MathUtils.lerp(start,4.75,t),0,3.68);
      truck.rotation.y=Math.PI;
    }
    renderer.render(scene,camera);
    frame=requestAnimationFrame(draw);
  }
  const vendorOffsets=[[-3.7,-2.6],[3.8,-.9],[-4.6,-1.4],[-1.8,3.6],[4.2,1.7]];
  let vendorIndex=0;
  for(const button of markers.children){
    const anchor=anchors.get(button.dataset.role);
    if(!anchor)continue;
    point.set(...anchor).project(camera);
    const [dx,dy]=offices[button.dataset.role]?[0,0]:vendorOffsets[vendorIndex++]??[0,0];
    button.style.left=(50+50*point.x+dx)+'%';
    button.style.top=(50-50*point.y+dy)+'%';
  }
  canvas.hidden=true;
  canvas.after(renderer.domElement);
  return {update(state){
    world=state;
    const event=world?.history[0];
    if(event!==lastEvent){lastEvent=event;moveTime=performance.now()}
    if(!frame)frame=requestAnimationFrame(draw);
  }};
}
