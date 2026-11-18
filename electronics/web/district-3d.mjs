import * as THREE from './three/three.module.min.js';
import {studio,softBox,makeStudioActor} from './studio.mjs';
import {loadPolyAssets,placePoly} from './poly-assets.mjs';

export const districtBounds = new THREE.Box3(new THREE.Vector3(-.8,-.6,-.7),new THREE.Vector3(26.4,6.4,16.2));

const depotX=5.25;
const depotZ=3.22;
const freightLane=15.13;
const pickupDriveMs=1250;
const loadingMs=720;
const deliveryDriveMs=2480;

function lotCenter(lot){
  return {x:lot.x+.58,z:lot.y+.43};
}

// Fit the complete district in camera space, including its tower and outer lots.
// This keeps the same world visible when the browser or the map panel changes size.
export function fitDistrictCamera(camera,aspect){
  const center=districtBounds.getCenter(new THREE.Vector3());
  camera.position.copy(center).add(new THREE.Vector3(23,24,31));
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

export function deliveryPath(vendor,route=[],carrier){
  const lane=route.includes('Hub Selatan')?5.77:route.includes('Hub Utara')?3.70:4.7;
  const origin=lotCenter(vendor);
  const points=[[origin.x,origin.z],[origin.x,lane]];
  if(carrier){
    const terminal=lotCenter(carrier);
    const approach=terminal.x+2.15;
    points.push([approach,lane],[approach,freightLane],[terminal.x,freightLane],[depotX,freightLane]);
  }else{
    points.push([depotX,lane]);
  }
  points.push([depotX,depotZ]);
  return points.filter(([x,z],index)=>!index||x!==points[index-1][0]||z!==points[index-1][1])
    .map(([x,z])=>new THREE.Vector3(x,0,z));
}

function motionLeg(points){
  const lengths=points.slice(1).map((point,index)=>point.distanceTo(points[index]));
  return {points,lengths,distance:lengths.reduce((total,length)=>total+length,0)};
}

export function shipmentMotion(vendor,route=[],carrier){
  const direct=deliveryPath(vendor,route);
  if(!carrier)return {approach:null,delivery:motionLeg(direct)};
  const viaTerminal=deliveryPath(vendor,route,carrier);
  const terminal=lotCenter(carrier);
  const depotIndex=viaTerminal.findIndex(point=>point.x===terminal.x&&point.z===freightLane);
  const pickup=viaTerminal[0].clone();
  const curb=viaTerminal[1].z-pickup.z;
  pickup.z+=Math.sign(curb)*Math.min(.99,Math.abs(curb)*.7);
  viaTerminal[0]=pickup;
  direct[0]=pickup;
  const approach=viaTerminal.slice(0,depotIndex+1).reverse();
  const delivery=route.includes(carrier.name)?viaTerminal:direct;
  return {approach:motionLeg(approach),delivery:motionLeg(delivery)};
}

function legPose(leg,progress){
  if(progress>=1){
    const start=leg.points.at(-2),end=leg.points.at(-1);
    return {position:end.clone(),angle:Math.atan2(start.z-end.z,end.x-start.x)};
  }
  let remaining=leg.distance*Math.max(0,progress);
  let segment=0;
  while(segment<leg.lengths.length-1&&remaining>leg.lengths[segment]){
    remaining-=leg.lengths[segment++];
  }
  const start=leg.points[segment],end=leg.points[segment+1];
  return {
    position:start.clone().lerp(end,Math.min(1,remaining/leg.lengths[segment])),
    angle:Math.atan2(start.z-end.z,end.x-start.x),
  };
}

export function shipmentPose(motion,elapsedMs){
  let elapsed=elapsedMs;
  if(motion.approach){
    if(elapsed<pickupDriveMs){
      return {...legPose(motion.approach,elapsed/pickupDriveMs),phase:'approach',load:0};
    }
    elapsed-=pickupDriveMs;
    if(elapsed<loadingMs){
      return {...legPose(motion.approach,1),phase:'pickup',load:elapsed/loadingMs};
    }
    elapsed-=loadingMs;
  }
  const phase=elapsed<deliveryDriveMs?'delivery':'arrived';
  return {...legPose(motion.delivery,elapsed/deliveryDriveMs),phase,load:1};
}

export async function createDistrict(canvas,offices,vendors,markers,carriers={}){
  const assets=await loadPolyAssets(['office','truck']);
  const renderer=new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
  renderer.setSize(1400,700,false);
  renderer.domElement.className='district-webgl';
  renderer.domElement.setAttribute('aria-hidden','true');
  const scene=new THREE.Scene();
  scene.background=new THREE.Color('#d6e8ed');
  studio(renderer,scene);
  const sun=scene.children.find(light=>light.isDirectionalLight&&light.castShadow);
  sun.target.position.set(12.8,0,7.75);
  sun.position.set(1,17,12.75);
  Object.assign(sun.shadow.camera,{left:-19,right:19,top:19,bottom:-19,far:60});
  sun.shadow.camera.updateProjectionMatrix();
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
  const podium=box(12.8,-.27,7.75,27.2,.52,16.9,'#aac88e');
  podium.castShadow=false;
  const road=box(12.65,-.029,4.7,26.1,.07,1.15,'#70828e');
  road.castShadow=false;
  for(const z of [3.70,5.77])box(15.4,-.029,z,20.3,.07,.58,'#87959a').castShadow=false;
  for(const x of [7.1,12.0,17.0])box(x,-.028,4.7,.85,.075,9.5,'#70828e').castShadow=false;
  box(depotX,-.028,(depotZ+freightLane)/2,.95,.075,freightLane-depotZ+.6,'#70828e').castShadow=false;
  for(let x=.5;x<25.5;x+=.83)box(x,.015,4.7,.37,.014,.043,'#ffefc2').castShadow=false;
  for(const z of [4.05,5.35])box(12.65,.018,z,25.9,.052,.16,'#dddcc0').castShadow=false;
  box(15.9,-.035,13.58,20.7,.067,4.94,'#c9d8cc').castShadow=false;
  box(15.3,-.022,freightLane,20.8,.072,1.14,'#566574').castShadow=false;
  for(let x=5.7;x<25.3;x+=.86){
    box(x,.017,freightLane,.38,.018,.045,'#fff2c9').castShadow=false;
  }
  for(const carrier of Object.values(carriers)){
    const approach=lotCenter(carrier).x+2.15;
    box(approach,-.023,(3.70+freightLane)/2,.62,.07,freightLane-3.7,'#71828d').castShadow=false;
  }
  for(const [x,z,size] of [[1.1,1,.9],[2,7.7,1.05],[5.7,1.15,.8],[11.2,.15,.95],[19.1,2.4,.9],[8.2,8.95,.8],[18.9,8.6,.83],[.55,6.15,.85],[20.5,6.6,.9],[13.1,9.1,.8],[3,11.2,1.1],[1.7,14.1,.82],[25.3,9.6,.92],[25.5,13.1,.86]]){
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
    const {x,z}=lotCenter(o);
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
  const warehouses=new Map();
  for(const [name,carrier] of Object.entries(carriers)){
    const {x,z}=lotCenter(carrier);
    const kind=carrier.index%3;
    const wall=['#dbe9f3','#f4e5df','#f4ebd7'][kind];
    const roof=['#467ba6','#a85755','#9a733e'][kind];
    box(x,.075,z,4.5,.15,2.98,'#d8dbcd');
    box(x,1.05,z,3.72,1.88,1.95,wall);
    const fascia=box(x,1.92,z+.91,3.71,.48,.17,carrier.color);
    warehouses.set(name,fascia);
    box(x,2.1,z,3.86,.27,2.1,roof);
    if(kind===0){
      box(x-.43,2.32,z-.27,1.9,.24,.86,'#96b1c0');
      box(x-.43,2.48,z-.27,1.7,.12,.75,'#567a8d');
    }else if(kind===1){
      box(x-.83,2.35,z-.11,1.66,.31,1.41,'#c88982');
      box(x+.81,2.35,z-.11,1.66,.31,1.41,'#c88982');
    }else{
      box(x-1.34,2.44,z-.3,1.06,.56,1.12,'#c5975a');
      box(x-1.34,2.76,z-.3,1.19,.16,1.23,roof);
      box(x-1.34,2.51,z+.27,.58,.22,.04,'#85a7b0');
    }
    const dockSides=kind===1?[-1.13,0,1.13]:[-.73,.73];
    for(const dx of dockSides){
      box(x+dx,.74,z+1.01,.86,1.2,.09,'#405261');
      box(x+dx,.75,z+1.07,.66,.98,.07,'#a5b3bb');
      for(let y=.35;y<1.23;y+=.17){
        box(x+dx,y,z+1.111,.65,.022,.018,'#687c87').castShadow=false;
      }
      box(x+dx,.12,z+1.25,.91,.12,.38,'#e0ba64');
    }
    for(const dx of [-1.66,1.66]){
      box(x+dx,.35,z+1.38,.12,.62,.12,'#e9ad43');
      box(x+dx,.43,z+1.39,.125,.12,.126,'#475761');
    }
    const plaque=document.createElement('canvas');
    plaque.width=256;plaque.height=64;
    const pen=plaque.getContext('2d');
    pen.fillStyle='#fff';
    pen.font='700 35px system-ui';
    pen.textAlign='center';
    pen.textBaseline='middle';
    pen.fillText(['JNE','J&T CARGO','POS LOGISTIK'][kind],128,33);
    const print=new THREE.CanvasTexture(plaque);
    const sign=new THREE.Mesh(new THREE.PlaneGeometry(2.54,.37),
      new THREE.MeshBasicMaterial({map:print,transparent:true,depthWrite:false}));
    sign.position.set(x,1.92,z+1.01);
    scene.add(sign);
    anchors.set(name,[x,2.64,z+.26]);
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
  let frame=0,moveTime=-1,lastEvent,lastStamp,shippingMotions=[];

  function fleetEntry(shipment,carrier){
    const key=shipment.vendor;
    if(!fleet.has(key)){
      const vehicle=truck.clone(true);
      const stripe=box(-.13,.66,0,.46,.055,.34,'#e5b16c',vehicle);
      scene.add(vehicle);
      const parcel=new THREE.Group();
      box(0,.124,0,.28,.248,.25,'#efb758',parcel);
      box(0,.255,0,.064,.018,.246,'#fff2b6',parcel);
      scene.add(parcel);
      fleet.set(key,{vehicle,stripe,parcel});
    }
    const entry=fleet.get(key);
    entry.stripe.material.color.set(carrier?.color??'#e5b16c');
    return entry;
  }

  function prepareShipping(event){
    if(event?.shipment!=='shipping')return [];
    const shipments=event.shipments?.length?event.shipments:[{vendor:event.vendor}];
    return shipments.flatMap(shipment=>{
      const vendor=vendors[shipment.vendor];
      if(!vendor)return [];
      const route=shipment.route?.path??[];
      const carrierName=shipment.route?.carrier??route.find(stop=>Object.hasOwn(carriers,stop));
      const carrier=carriers[carrierName];
      return [{carrierName,motion:shipmentMotion(vendor,route,carrier),...fleetEntry(shipment,carrier)}];
    });
  }

  function animateShipping(time){
    for(const {vehicle,parcel} of fleet.values()){
      vehicle.visible=false;
      parcel.visible=false;
    }
    shippingMotions.forEach(({motion,vehicle,parcel},index)=>{
      const elapsed=reduce.matches?Infinity:time-moveTime-index*104;
      const {position,angle,phase,load}=shipmentPose(motion,elapsed);
      vehicle.position.copy(position);
      vehicle.rotation.y=angle;
      vehicle.visible=true;
      // The carton waits beside the bay, then rises into the cargo compartment.
      parcel.visible=!!motion.approach&&(phase==='approach'||phase==='pickup');
      if(parcel.visible){
        const pickup=motion.approach.points.at(-1);
        const loaded=phase==='pickup'?THREE.MathUtils.smoothstep(load,0,1):0;
        parcel.position.set(
          THREE.MathUtils.lerp(pickup.x+.54,pickup.x-.12*Math.cos(angle),loaded),
          .06+Math.sin(loaded*Math.PI)*.42+loaded*.30,
          THREE.MathUtils.lerp(pickup.z,pickup.z+.12*Math.sin(angle),loaded),
        );
      }
    });
  }

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
    const activeCarriers=new Set(shippingMotions.map(shipment=>shipment.carrierName));
    if(lastEvent?.carrier)activeCarriers.add(lastEvent.carrier);
    for(const [name,warehouse] of warehouses){
      warehouse.material.emissive.set(activeCarriers.has(name)?'#e8b360':'#000000');
      warehouse.material.emissiveIntensity=.32;
    }
    animateShipping(time);
    renderer.render(scene,camera);
    frame=requestAnimationFrame(draw);
  }
  let viewWidth=1400,viewHeight=700;
  function positionMarkers(){
    const occupied=[];
    const floorButtons=[...markers.children].filter(button=>offices[button.dataset.role]);
    const floorCount=floorButtons.length;
    const floorGap=Math.max(24,...floorButtons.map(button=>button.offsetHeight+5));
    const floorSpan=floorGap*(floorCount-1);
    const center=floorButtons.reduce((total,button)=>{
      const projected=point.set(...anchors.get(button.dataset.role)).project(camera);
      return total+(.5-.5*projected.y)*viewHeight;
    },0)/Math.max(1,floorCount);
    const floorTop=THREE.MathUtils.clamp(center-floorSpan/2,24,viewHeight-floorSpan-24);
    for(const button of markers.children){
      const anchor=anchors.get(button.dataset.role);
      if(!anchor)continue;
      point.set(...anchor).project(camera);
      const office=offices[button.dataset.role];
      const floor=!!office;
      const carrier=carriers[button.dataset.role];
      button.classList.toggle('floor-marker',floor);
      button.classList.toggle('carrier-marker',!!carrier);
      button.hidden=Math.abs(point.x)>1.09||Math.abs(point.y)>1.09;
      if(button.hidden)continue;
      const width=button.offsetWidth||36;
      const height=button.offsetHeight||24;
      const minLeft=floor?width+8:width/2+8;
      const maxLeft=viewWidth-(floor?8:width/2+8);
      const homeX=(.5+.5*point.x)*viewWidth;
      const homeY=floor?floorTop+(floorCount-1-office.level)*floorGap:(.5-.5*point.y)*viewHeight-16;
      const step=Math.max(22,height+4);
      const offsets=[[0,0],[0,-step],[0,step],[-width*.45,0],[width*.45,0],[0,-step*2],[0,step*2],
        [-width*.45,-step],[width*.45,step],[0,-step*3],[0,step*3]];
      function location(dx,dy){
        const left=THREE.MathUtils.clamp(homeX+dx,minLeft,maxLeft);
        const top=THREE.MathUtils.clamp(homeY+dy,height/2+6,viewHeight-height/2-6);
        const x=floor?left-width:left-width/2;
        return {left,top,x,y:top-height/2,width,height};
      }
      function isFree(rect){
        return occupied.every(other=>rect.x+rect.width+3<=other.x||other.x+other.width+3<=rect.x
          ||rect.y+rect.height+3<=other.y||other.y+other.height+3<=rect.y);
      }
      const placement=floor?location(0,0):offsets.map(([dx,dy])=>location(dx,dy)).find(isFree)??location(0,0);
      const {left,top}=placement;
      occupied.push(placement);
      button.style.left=100*left/viewWidth+'%';
      button.style.top=100*top/viewHeight+'%';
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
    const event=state?.history[0];
    const stamp=event&&[event.tick,event.title,event.shipment,event.vendor].join(':');
    if(stamp!==lastStamp){
      lastStamp=stamp;
      moveTime=performance.now();
      shippingMotions=prepareShipping(event);
    }
    lastEvent=event;
    if(!frame)frame=requestAnimationFrame(draw);
  },setZoom(value){
    camera.zoom=THREE.MathUtils.clamp(value,.8,1.8);
    camera.updateProjectionMatrix();positionMarkers();
    if(!frame)frame=requestAnimationFrame(draw);
    return camera.zoom;
  }};
}
