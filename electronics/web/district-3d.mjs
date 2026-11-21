import * as THREE from './three/three.module.min.js';
import {studio} from './studio.mjs';
import {MEADOW_SIZE,buildDistrictScenery,districtTransport,makeDistrictVehicle} from './district-scenery.mjs';

export const districtBounds = new THREE.Box3(
  new THREE.Vector3(-MEADOW_SIZE.width/2,-1.2,-MEADOW_SIZE.depth/2),
  new THREE.Vector3(MEADOW_SIZE.width/2,10.3,MEADOW_SIZE.depth/2),
);
const districtCenter=districtBounds.getCenter(new THREE.Vector3());
const defaultOrbit=new THREE.Spherical().setFromVector3(new THREE.Vector3(49,63,67));
const boundsRadius=districtBounds.getSize(new THREE.Vector3()).length()/2;

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
export function fitDistrictCamera(camera,aspect,orbit=defaultOrbit){
  camera.position.setFromSpherical(orbit).add(districtCenter);
  camera.lookAt(districtCenter);
  camera.updateMatrixWorld();
  camera.far=Math.max(camera.far,orbit.radius+boundsRadius+1);
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
  if(vendor.dockOffset!=null)return districtTransport(vendor,route,carrier).delivery;
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

function easeCorners(points,radius=.58){
  const eased=[points[0]];
  for(let index=1;index<points.length-1;index++){
    const prev=points[index-1],corner=points[index],next=points[index+1];
    const incoming=prev.clone().sub(corner),outgoing=next.clone().sub(corner);
    const inset=Math.min(radius,incoming.length()*.32,outgoing.length()*.32);
    incoming.normalize();outgoing.normalize();
    if(Math.abs(incoming.dot(outgoing))>.985){
      eased.push(corner);
      continue;
    }
    const start=corner.clone().addScaledVector(incoming,inset);
    const end=corner.clone().addScaledVector(outgoing,inset);
    eased.push(...new THREE.QuadraticBezierCurve3(start,corner,end).getPoints(5));
  }
  eased.push(points.at(-1));
  return eased;
}

export function shipmentMotion(vendor,route=[],carrier){
  if(vendor.dockOffset!=null){
    const {approach,delivery}=districtTransport(vendor,route,carrier);
    return {approach:approach&&motionLeg(easeCorners(approach)),delivery:motionLeg(easeCorners(delivery))};
  }
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


function routeRibbon(points,width){
  const positions=[];
  for(let i=1;i<points.length;i++){
    const a=points[i-1],b=points[i],dx=b.x-a.x,dz=b.z-a.z;
    const scale=width/Math.hypot(dx,dz)/2;
    const x=dz*scale,z=-dx*scale;
    positions.push(
      a.x+x,.141,a.z+z,a.x-x,.141,a.z-z,b.x+x,.141,b.z+z,
      a.x-x,.141,a.z-z,b.x-x,.141,b.z-z,b.x+x,.141,b.z+z,
    );
  }
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  return geometry;
}

export async function createDistrict(
  canvas,offices,vendors,markers,carriers={},onZoom=()=>{},
  {onSelect=()=>{},bizMarker=null,onAutoRotate=()=>{},onFollowTruck=()=>{}}={},
){
  const renderer=new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
  renderer.setSize(1400,700,false);
  const surface=renderer.domElement;
  surface.className='district-webgl';
  surface.tabIndex=0;
  surface.setAttribute('aria-label','Kamera distrik 3D. Panah untuk memutar, Shift dan panah untuk menggeser, plus dan minus untuk zoom, Home untuk atur ulang.');
  const scene=new THREE.Scene();
  scene.background=new THREE.Color('#d5e6ec');
  studio(renderer,scene);
  renderer.toneMappingExposure=1.16;
  const sun=scene.children.find(light=>light.isDirectionalLight&&light.castShadow);
  sun.target.position.set(0,0,0);
  sun.position.set(-29,43,31);
  Object.assign(sun.shadow.camera,{left:-47,right:47,top:43,bottom:-43,far:145});
  const shadowSize=window.innerWidth>=850?2048:1024;
  sun.shadow.mapSize.set(shadowSize,shadowSize);
  sun.shadow.camera.updateProjectionMatrix();

  const {createCharacter}=await import('./character-3d.mjs');
  const {
    anchors,pickables,actors,floorLights,carrierLights,trees,
    vendorLots,carrierLots,quarantine,quarantineCrate,
  }=buildDistrictScenery(scene,offices,vendors,carriers,createCharacter);
  const visitors=Array.from({length:4},(_,index)=>{
    const visitor=createCharacter({role:'buyer',variant:index,briefcase:false,detail:'compact'});
    visitor.root.scale.setScalar(.52);
    visitor.root.rotation.y=-Math.PI/2;
    visitor.root.visible=false;
    scene.add(visitor.root);
    return visitor;
  });
  const ambientLoops=[
    [[-25.56,-17.51],[25.51,-17.51],[25.51,17.52],[-25.56,17.52],[-25.56,-17.51]],
    [[-9.53,-6.52],[8.51,-6.52],[8.51,6.47],[-9.53,6.47],[-9.53,-6.52]],
  ].map(path=>motionLeg(easeCorners(path.map(([x,z])=>new THREE.Vector3(x,.025,z)),.65)));
  const ambientCars=['#dba94a','#7c789d','#dd7a5a','#7babb8'].map((color,index)=>{
    const vehicle=makeDistrictVehicle(color);
    scene.add(vehicle);
    return {vehicle,path:ambientLoops[index%2],phase:index*.249,duration:index%2?27000:54000};
  });

  const routeLayer=new THREE.Group(), pulseGeometry=new THREE.SphereGeometry(1,10,7);
  scene.add(routeLayer);
  const routePulses=[];
  const fleet=new Map();
  let frame=0,moveTime=-1,lastEvent,lastStamp,shippingMotions=[];
  let viewWidth=1400,viewHeight=700,lastFrame=null;
  const camera=new THREE.OrthographicCamera(-15,15,8,-8,.2,180);
  const orbit=defaultOrbit.clone(),targetOrbit=defaultOrbit.clone();
  const offset=new THREE.Vector3(),targetOffset=new THREE.Vector3(),focusedOffset=new THREE.Vector3();
  const axis=new THREE.Vector3(),point=new THREE.Vector3();
  const reduce=window.matchMedia('(prefers-reduced-motion: reduce)');
  let targetZoom=1,cameraDirty=true,autoRotate=false,followTruck=false,zoomBeforeFollow=1;

  function fleetEntry(shipment,carrierName){
    const key=shipment.vendor+'|'+(carrierName??'');
    if(!fleet.has(key)){
      const carrier=carrierLots.get(carrierName);
      const vehicle=makeDistrictVehicle(carrier?.color??'#df9654',true);
      vehicle.visible=false;
      scene.add(vehicle);
      const parcel=new THREE.Group();
      const carton=new THREE.Mesh(new THREE.BoxGeometry(.41,.34,.38),new THREE.MeshStandardMaterial({color:'#e2ad65'}));
      carton.position.y=.17;carton.castShadow=true;
      const tape=new THREE.Mesh(new THREE.BoxGeometry(.06,.014,.37),new THREE.MeshStandardMaterial({color:'#f5e6aa'}));
      tape.position.y=.344;
      parcel.add(carton,tape);parcel.visible=false;scene.add(parcel);
      fleet.set(key,{vehicle,parcel});
    }
    return fleet.get(key);
  }

  function prepareShipping(event){
    if(event?.shipment!=='shipping')return [];
    const shipments=event.shipments?.length?event.shipments:[{vendor:event.vendor}];
    return shipments.flatMap(shipment=>{
      const vendor=vendorLots.get(shipment.vendor);
      if(!vendor)return [];
      const route=shipment.route?.path??[];
      const carrierName=shipment.route?.carrier??route.find(stop=>carrierLots.has(stop));
      const carrier=carrierLots.get(carrierName);
      return [{carrierName,motion:shipmentMotion(vendor,route,carrier),...fleetEntry(shipment,carrierName)}];
    });
  }

  function addRibbon(leg,color,strength,width){
    const material=new THREE.MeshBasicMaterial({
      color,transparent:true,opacity:strength,side:THREE.DoubleSide,depthWrite:false,toneMapped:false,
    });
    routeLayer.add(new THREE.Mesh(routeRibbon(leg.points,width),material));
  }

  function drawRoute(leg,color,highlight=false,live=false){
    if(!leg||leg.points.length<2)return;
    addRibbon(leg,color,highlight?.25:.19,highlight?.76:.42);
    addRibbon(leg,color,highlight?.98:.82,highlight?.28:.13);
    const pulse=new THREE.Mesh(pulseGeometry,new THREE.MeshBasicMaterial({color,transparent:true,depthWrite:false,toneMapped:false}));
    pulse.scale.setScalar(highlight?.23:.16);
    pulse.renderOrder=2;
    routeLayer.add(pulse);
    routePulses.push({leg,pulse,delay:routePulses.length*.147,live});
  }

  function prepareRoutes(event){
    routeLayer.traverse(item=>{
      if(!item.isMesh)return;
      if(item.geometry!==pulseGeometry)item.geometry.dispose();
      item.material.dispose();
    });
    routeLayer.clear();
    routePulses.length=0;
    if(event?.carrier_quote?.orders){
      for(const order of event.carrier_quote.orders){
        const vendor=vendorLots.get(order.vendor);
        if(!vendor)continue;
        const options=new Map();
        for(const option of order.options??[]){
          const previous=options.get(option.carrier);
          if(!previous||option.selected||(!previous.selected&&option.eligible&&!previous.eligible)){
            options.set(option.carrier,option);
          }
        }
        const colors=['#8de3ff','#b9b7ff','#ffc872'];
        for(const [carrierName,option] of [...options].sort((a,b)=>Number(!!a[1].selected)-Number(!!b[1].selected))){
          const carrier=carrierLots.get(carrierName);
          if(!carrier)continue;
          const motion=shipmentMotion(vendor,option.path??option.route?.path??[],carrier);
          const color=option.selected?'#86ffe0':colors[[...carrierLots.keys()].indexOf(carrierName)%3];
          drawRoute(motion.approach,color,!!option.selected);
          if(option.selected)drawRoute(motion.delivery,color,true);
        }
      }
    }
    for(const {motion} of shippingMotions){
      drawRoute(motion.approach,'#7debe2',true,true);
      drawRoute(motion.delivery,'#ffe093',true,true);
    }
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
      const nextAngle=phase==='pickup'?legPose(motion.delivery,0).angle:angle;
      const turn=Math.atan2(Math.sin(nextAngle-angle),Math.cos(nextAngle-angle));
      vehicle.rotation.y=angle+turn*THREE.MathUtils.smoothstep(load,.62,1);
      vehicle.visible=true;
      parcel.visible=!!motion.approach&&(phase==='approach'||phase==='pickup');
      if(parcel.visible){
        const pickup=motion.approach.points.at(-1);
        const loaded=phase==='pickup'?THREE.MathUtils.smoothstep(load,0,1):0;
        parcel.position.set(
          THREE.MathUtils.lerp(pickup.x+.77,pickup.x-.24*Math.cos(angle),loaded),
          .102+Math.sin(loaded*Math.PI)*.56+loaded*.45,
          THREE.MathUtils.lerp(pickup.z,pickup.z+.24*Math.sin(angle),loaded),
        );
      }
    });
    for(const {leg,pulse,delay,live} of routePulses){
      const progress=reduce.matches?.5:((Math.max(time-moveTime,0)/(live?1540:2500)+delay)%1);
      const pose=legPose(leg,progress);
      pulse.position.copy(pose.position);pulse.position.y=.235;
      pulse.material.opacity=reduce.matches?.9:.7+Math.sin(time*.007+delay)*.26;
    }
  }

  function positionMarkers(){
    const occupied=[];
    const buttons=[...markers.children].filter(button=>!bizMarker||!offices[button.dataset.role]);
    if(bizMarker)buttons.unshift(bizMarker);
    const dimensions=buttons.map(button=>({button,width:button.offsetWidth||52,height:button.offsetHeight||28}));
    for(const {button,width,height} of dimensions){
      const role=button===bizMarker?'biz':button.dataset.role;
      const anchor=anchors.get(role);
      if(!anchor)continue;
      const isFloor=!!offices[role];
      point.set(...anchor).project(camera);
      button.classList.toggle('floor-marker',isFloor);
      button.classList.toggle('carrier-marker',!!carriers[role]);
      button.hidden=Math.abs(point.x)>1.05||Math.abs(point.y)>1.05;
      if(button.hidden)continue;
      const minX=Math.min(viewWidth/2,width/2+7),maxX=viewWidth-minX;
      const minY=Math.min(viewHeight/2,height/2+6),maxY=viewHeight-minY;
      const homeX=(.5+.5*point.x)*viewWidth;
      const homeY=(.5-.5*point.y)*viewHeight-7;
      const step=height+4;
      const moves=[[0,0],[0,-step],[0,step],[-width*.52,0],[width*.52,0],[0,-step*2],[0,step*2]];
      const locations=moves.map(([dx,dy])=>({
        x:THREE.MathUtils.clamp(homeX+dx,minX,maxX),
        y:THREE.MathUtils.clamp(homeY+dy,minY,maxY),
      }));
      const placed=locations.find(({x,y})=>occupied.every(other=>
        Math.abs(other.x-x)>=(other.width+width)/2+3||Math.abs(other.y-y)>=(other.height+height)/2+3,
      ))??locations[0];
      occupied.push({...placed,width,height});
      button.style.left=100*placed.x/viewWidth+'%';
      button.style.top=100*placed.y/viewHeight+'%';
    }
  }

  function syncCamera(){
    fitDistrictCamera(camera,viewWidth/viewHeight,orbit);
    camera.position.add(offset);
    camera.updateMatrixWorld();
    positionMarkers();
    cameraDirty=false;
  }

  function updateCamera(dt){
    if(autoRotate)targetOrbit.theta+=dt*.26;
    const followVehicle=followTruck&&shippingMotions[0]?.vehicle;
    const target=followVehicle?.visible
      ?focusedOffset.copy(followVehicle.position).sub(districtCenter).add(axis.set(0,1.85,0))
      :targetOffset;
    const blend=reduce.matches?1:1-Math.exp(-dt*11.5);
    function settle(value,goal){
      return Math.abs(goal-value)<.0004?goal:THREE.MathUtils.lerp(value,goal,blend);
    }
    if(orbit.theta!==targetOrbit.theta||orbit.phi!==targetOrbit.phi||camera.zoom!==targetZoom||!offset.equals(target)){
      orbit.theta=settle(orbit.theta,targetOrbit.theta);
      orbit.phi=settle(orbit.phi,targetOrbit.phi);
      camera.zoom=settle(camera.zoom,targetZoom);
      if(offset.distanceToSquared(target)<.000002)offset.copy(target);
      else offset.lerp(target,blend);
      cameraDirty=true;
    }
    if(cameraDirty)syncCamera();
  }

  function draw(time){
    frame=0;
    if(!canvas.parentElement?.getClientRects().length){lastFrame=null;return;}
    const dt=lastFrame===null?1/60:Math.min(.18,Math.max(0,(time-lastFrame)/1000));
    lastFrame=time;
    const seconds=time/1000;
    for(const {role,actor} of actors){
      actor.animate(role===lastEvent?.role?'wave':'idle',seconds,{reducedMotion:reduce.matches});
    }
    for(const [role,floor] of floorLights){
      floor.material.emissive.set(role===lastEvent?.role?'#ffd979':'#000000');
      floor.material.emissiveIntensity=.55;
    }
    const arrivals=lastEvent?.role==='buyer'?(lastEvent.customers??[]):[];
    visitors.forEach((actor,index)=>{
      actor.root.visible=index<arrivals.length;
      if(!actor.root.visible)return;
      const t=reduce.matches?1:THREE.MathUtils.clamp((time-moveTime-index*180)/1550,0,1);
      actor.root.position.set(THREE.MathUtils.lerp(-17.7,-20.72,t)+index*.35,.14,3.22+index*.23);
      actor.animate(t<1?'walk':'idle',seconds,{reducedMotion:reduce.matches});
    });
    for(const [index,tree] of trees.entries()){
      tree.rotation.z=reduce.matches?0:.054*Math.sin(seconds*1.33+index*.94);
      tree.rotation.x=reduce.matches?0:.026*Math.sin(seconds*1.88+index*.91);
    }
    for(const {vehicle,path,duration,phase} of ambientCars){
      const progress=reduce.matches?phase:(time/duration+phase)%1;
      const pose=legPose(path,progress);
      vehicle.position.copy(pose.position);
      vehicle.rotation.y=pose.angle;
    }
    const activeCarriers=new Set(shippingMotions.map(shipment=>shipment.carrierName));
    if(lastEvent?.carrier)activeCarriers.add(lastEvent.carrier);
    for(const order of lastEvent?.carrier_quote?.orders??[])activeCarriers.add(order.selected_carrier);
    for(const [name,fascia] of carrierLights){
      fascia.material.emissive.set(activeCarriers.has(name)?'#f5b257':'#000000');
      fascia.material.emissiveIntensity=.39;
    }
    quarantine.visible=!!lastEvent?.inspection?.damaged||lastEvent?.inspection?.state==='invoice_hold';
    if(quarantine.visible){
      quarantineCrate.material.emissiveIntensity=reduce.matches?.51:.31+.38*(1+Math.sin(seconds*5.4));
    }
    animateShipping(time);
    updateCamera(dt);
    renderer.render(scene,camera);
    frame=requestAnimationFrame(draw);
  }

  function requestDraw(){
    if(!frame)frame=requestAnimationFrame(draw);
  }

  function resize(){
    const rect=canvas.parentElement.getBoundingClientRect();
    if(!rect.width||!rect.height)return;
    viewWidth=rect.width;viewHeight=rect.height;
    renderer.setSize(viewWidth,viewHeight,false);
    cameraDirty=true;
    requestDraw();
  }

  function setZoom(value){
    const zoom=THREE.MathUtils.clamp(value,.68,3);
    if(targetZoom===zoom)return;
    targetZoom=zoom;
    onZoom(zoom);
    requestDraw();
  }

  function setAutoRotate(enabled){
    const next=!!enabled;
    if(autoRotate===next)return;
    autoRotate=next;
    onAutoRotate(autoRotate);
    requestDraw();
  }

  function setFollowTruck(enabled){
    const next=!!enabled;
    if(followTruck===next)return;
    followTruck=next;
    if(followTruck){
      zoomBeforeFollow=targetZoom;
      setZoom(Math.max(targetZoom,1.7));
    }else{
      setZoom(zoomBeforeFollow);
    }
    onFollowTruck(followTruck);
    requestDraw();
  }

  function resetView(){
    setAutoRotate(false);
    setFollowTruck(false);
    targetOrbit.copy(defaultOrbit);
    const turns=Math.round((orbit.theta-targetOrbit.theta)/(2*Math.PI));
    targetOrbit.theta+=turns*2*Math.PI;
    targetOffset.set(0,0,0);
    setZoom(1);
    requestDraw();
  }

  function rotate(dx,dy){
    setAutoRotate(false);
    const speed=Math.PI/Math.min(viewWidth,viewHeight);
    targetOrbit.theta-=dx*speed;
    targetOrbit.phi=THREE.MathUtils.clamp(targetOrbit.phi-dy*speed,Math.PI/11,Math.PI*7/18);
    requestDraw();
  }

  function pan(dx,dy){
    setAutoRotate(false);
    setFollowTruck(false);
    const unitsPerPixel=(camera.top-camera.bottom)/(camera.zoom*viewHeight);
    targetOffset.addScaledVector(axis.setFromMatrixColumn(camera.matrixWorld,0),-dx*unitsPerPixel);
    targetOffset.addScaledVector(axis.setFromMatrixColumn(camera.matrixWorld,1),dy*unitsPerPixel);
    targetOffset.clampLength(0,43);
    requestDraw();
  }

  const pointers=new Map(),raycaster=new THREE.Raycaster(),cursor=new THREE.Vector2();
  function pick(clientX,clientY){
    const rect=surface.getBoundingClientRect();
    cursor.set((clientX-rect.left)*2/rect.width-1,1-(clientY-rect.top)*2/rect.height);
    raycaster.setFromCamera(cursor,camera);
    return raycaster.intersectObjects(pickables,false)[0]?.object.userData.role;
  }

  surface.addEventListener('pointerdown',event=>{
    if(event.button>2||pointers.size>=2)return;
    if(pointers.size&&event.pointerType!=='touch')return;
    for(const pointer of pointers.values())pointer.dragged=true;
    pointers.set(event.pointerId,{
      x:event.clientX,y:event.clientY,startX:event.clientX,startY:event.clientY,
      pan:event.button!==0,dragged:pointers.size>0,
    });
    surface.setPointerCapture(event.pointerId);
    surface.classList.add('dragging');
  });

  surface.addEventListener('pointermove',event=>{
    const pointer=pointers.get(event.pointerId);
    if(!pointer){
      if(!pointers.size&&event.pointerType==='mouse')surface.classList.toggle('over-building',!!pick(event.clientX,event.clientY));
      return;
    }
    const {x,y}=pointer;
    pointer.x=event.clientX;
    pointer.y=event.clientY;
    const dx=pointer.x-x,dy=pointer.y-y;
    if(Math.hypot(pointer.x-pointer.startX,pointer.y-pointer.startY)>5)pointer.dragged=true;
    if(pointers.size===2){
      const other=[...pointers.values()].find(contact=>contact!==pointer);
      const previousDistance=Math.hypot(x-other.x,y-other.y);
      const distance=Math.hypot(pointer.x-other.x,pointer.y-other.y);
      pan(dx/2,dy/2);
      if(previousDistance>0)setZoom(targetZoom*distance/previousDistance);
    }else if(pointer.dragged){
      if(pointer.pan||event.shiftKey)pan(dx,dy);
      else rotate(dx,dy);
    }
  });

  for(const type of ['pointerup','pointercancel','lostpointercapture']){
    surface.addEventListener(type,event=>{
      const pointer=pointers.get(event.pointerId);
      pointers.delete(event.pointerId);
      if(!pointers.size)surface.classList.remove('dragging');
      if(type==='pointerup'&&pointer&&!pointer.pan&&!pointer.dragged){
        const role=pick(event.clientX,event.clientY);
        if(role)onSelect(role);
      }
    });
  }
  surface.addEventListener('contextmenu',event=>event.preventDefault());
  surface.addEventListener('wheel',event=>{
    event.preventDefault();
    const distance=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?viewHeight:1);
    setZoom(targetZoom*Math.exp(-distance*.0015));
  },{passive:false});
  const arrows={ArrowLeft:[-26,0],ArrowRight:[26,0],ArrowUp:[0,-26],ArrowDown:[0,26]};
  surface.addEventListener('keydown',event=>{
    const {key}=event;
    if(Object.hasOwn(arrows,key)){
      const move=event.shiftKey?pan:rotate;
      move(...arrows[key]);
    }else if(key==='+'||key==='='){
      setZoom(targetZoom+.15);
    }else if(key==='-'){
      setZoom(targetZoom-.15);
    }else if(key==='Home'){
      resetView();
    }else{
      return;
    }
    event.preventDefault();
  });

  canvas.hidden=true;
  canvas.after(surface);
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
      prepareRoutes(event);
    }
    lastEvent=event;
    requestDraw();
  },setZoom,resetView,setAutoRotate,setFollowTruck};
}
