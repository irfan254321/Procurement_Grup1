import * as THREE from './three/three.module.min.js';

export const ROAD_X=Object.freeze([-25,-9,9,25]);
export const ROAD_Z=Object.freeze([-17,-6,6,17]);
export const ROAD_WIDTH=2.35;
export const CITY_SIZE=Object.freeze({width:56,depth:40});
export const MEADOW_SIZE=Object.freeze({width:80,depth:62});
export const BIZ_DOCK=Object.freeze({x:-13.68,z:3.76,roadZ:6});

const vendorParcels=[
  {x:0,z:-11.3,roadZ:-6,width:12.8,depth:8.1,height:4.6,color:'#5079a6'},
  {x:17,z:-11.3,roadZ:-6,width:12.8,depth:8.1,height:3.7,color:'#a46e4b'},
  {x:13.2,z:-.44,roadZ:6,width:6,depth:8.7,height:3.15,color:'#e3a83d'},
  {x:20.8,z:-.44,roadZ:6,width:6,depth:8.7,height:4.1,color:'#7469a5'},
];
const vendorIndex=new Map([
  ['CloudSoft Corp.',0],['FurniWorks Ltd.',1],['QuickDeliver Ltd.',2],['TechMart Inc.',3],
]);
const carrierParcels=[
  {x:-17,z:10.9,color:'#b53136',light:'#e7c6ac',roof:'#7e3739',sign:'JNE'},
  {x:0,z:10.9,color:'#9f252b',light:'#e6d8cf',roof:'#542d30',sign:'J&T CARGO'},
  {x:17,z:10.9,color:'#dc842b',light:'#f2d9a5',roof:'#8f5b33',sign:'POS LOGISTIK'},
];

export function districtTransport(vendor,route=[],carrier){
  // Trucks travel in assigned lanes, entering each lot only at its driveway.
  const throughZ=route.includes('Hub Selatan')?5.5:-5.5;
  const east=vendor.x>=9;
  const innerX=east?9.58:-8.42;
  const outerX=east?24.47:-24.45;
  const southZ=16.48;
  const depotZ=BIZ_DOCK.roadZ-.5;
  const pickup=[vendor.x,vendor.z+vendor.dockOffset];
  const pickupStreet=vendor.roadZ+(vendor.roadZ<0?.5:-.5);
  const hubTransfer=throughZ<pickupStreet?outerX:innerX;
  const delivery=[
    pickup,[vendor.x,pickupStreet],[innerX,pickupStreet],
    [innerX,throughZ],
    ...(throughZ===depotZ?[]:[[-24.45,throughZ],[-24.45,depotZ]]),
    [BIZ_DOCK.x,depotZ],[BIZ_DOCK.x,BIZ_DOCK.z],
  ];
  const approach=carrier?[
    [carrier.x,carrier.dockZ],[carrier.x,southZ],[innerX,southZ],
    [innerX,throughZ],[hubTransfer,throughZ],[hubTransfer,pickupStreet],[vendor.x,pickupStreet],pickup,
  ]:null;
  const compact=points=>points.filter(([x,z],index)=>!index||x!==points[index-1][0]||z!==points[index-1][1])
    .map(([x,z])=>new THREE.Vector3(x,0,z));
  return {approach:approach&&compact(approach),delivery:compact(delivery)};
}

function createBatch(scene){
  const cube=new THREE.BoxGeometry(1,1,1);
  const groups=new Map();
  const matrix=new THREE.Matrix4(),position=new THREE.Vector3(),scale=new THREE.Vector3(),rotation=new THREE.Quaternion();
  const yAxis=new THREE.Vector3(0,1,0);
  function box(x,y,z,w,h,d,color,{yaw=0,cast=true}={}){
    const key=color+'|'+cast;
    if(!groups.has(key))groups.set(key,{color,cast,transforms:[]});
    matrix.compose(position.set(x,y,z),rotation.setFromAxisAngle(yAxis,yaw),scale.set(w,h,d));
    groups.get(key).transforms.push(matrix.clone());
  }
  function flush(){
    for(const {color,cast,transforms} of groups.values()){
      const mesh=new THREE.InstancedMesh(cube,new THREE.MeshStandardMaterial({color,roughness:.84}),transforms.length);
      transforms.forEach((transform,index)=>mesh.setMatrixAt(index,transform));
      mesh.castShadow=cast;mesh.receiveShadow=true;
      mesh.computeBoundingSphere();
      scene.add(mesh);
    }
  }
  return {box,flush};
}

function solid(parent,geometry,color,x,y,z,cast=true){
  const object=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,roughness:.83}));
  object.position.set(x,y,z);object.castShadow=cast;object.receiveShadow=true;
  parent.add(object);
  return object;
}

function board(parent,text,{x,y,z,w,h,color='#f9f4e5',background='',horizontal=false}){
  const canvas=document.createElement('canvas');
  canvas.width=512;canvas.height=96;
  const pen=canvas.getContext('2d');
  if(background){
    pen.fillStyle=background;
    pen.fillRect(0,0,canvas.width,canvas.height);
  }
  pen.fillStyle=color;
  pen.font='800 59px system-ui';
  pen.textAlign='center';pen.textBaseline='middle';
  pen.fillText(text,256,48,475);
  const texture=new THREE.CanvasTexture(canvas);
  texture.colorSpace=THREE.SRGBColorSpace;
  const sign=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:texture,transparent:!background}));
  sign.position.set(x,y,z);
  if(horizontal)sign.rotation.x=-Math.PI/2;
  parent.add(sign);
}

export function makeDistrictVehicle(color='#bd425b',cargo=false){
  const vehicle=new THREE.Group();
  const shape=(x,y,z,w,h,d,tint)=>solid(vehicle,new THREE.BoxGeometry(w,h,d),tint,x,y,z);
  if(cargo){
    shape(-.37,.52,0,1.18,.63,.71,'#f2dfb4');
    shape(-.45,.852,0,1.25,.045,.73,color);
    shape(.59,.44,0,.64,.53,.69,color);
    shape(.72,.62,0,.33,.2,.71,'#537c92');
    shape(.929,.38,0,.022,.097,.55,'#afc2c2');
  }else{
    shape(0,.27,0,1.29,.3,.58,color);
    shape(-.04,.47,0,.65,.2,.50,'#546f80');
    shape(-.1,.575,0,.51,.06,.49,color);
    shape(.648,.28,0,.025,.073,.46,'#f9dfa5');
  }
  for(const x of cargo?[-.69,.64]:[-.4,.4]){
    for(const z of cargo?[-.365,.365]:[-.302,.302]){
      const wheel=solid(vehicle,new THREE.CylinderGeometry(cargo?.17:.132,cargo?.17:.132,.09,12),'#2f3541',x,.175,z);
      wheel.rotation.x=Math.PI/2;
    }
  }
  return vehicle;
}

export function buildDistrictScenery(scene,offices,vendors,carriers,createActor){
  const {box,flush}=createBatch(scene);
  const trees=[],pickables=[],actors=[],floorLights=new Map(),carrierLights=new Map(),anchors=new Map();
  const vendorLots=new Map(),carrierLots=new Map();
  const asphalt='#48515b',curb='#d8d7c4',dash='#f3e8b2',concrete='#e3e5d7';
  const noShadow={cast:false};
  const ground=(x,z,w,d,color,y=-.025,h=.05)=>box(x,y,z,w,h,d,color,noShadow);
  function clickable(role,x,y,z,w,h,d){
    const proxy=new THREE.Mesh(new THREE.BoxGeometry(w,h,d));
    proxy.position.set(x,y,z);proxy.userData.role=role;proxy.updateMatrixWorld();
    pickables.push(proxy);
  }
  function tree(x,z,size=1,variant=0){
    const crown=new THREE.Group();
    crown.position.set(x,1.01*size,z);
    crown.scale.setScalar(size);
    scene.add(crown);
    const colors=variant%2?['#3f8466','#62a461','#86b76c']:['#4b8a65','#72a969','#9fc27b'];
    box(x,.51*size,z,.14*size,1.04*size,.15*size,'#8b6a4d');
    solid(crown,new THREE.SphereGeometry(.46,13,10),colors[0],0,.18,0);
    solid(crown,new THREE.SphereGeometry(.41,13,10),colors[1],-.25,.35,.04);
    solid(crown,new THREE.SphereGeometry(.36,13,10),colors[2],.23,.5,-.05);
    trees.push(crown);
  }
  function lamp(x,z,yaw=0){
    box(x,1.02,z,.065,1.98,.065,'#5c6b68');
    const d=.3;
    box(x+Math.cos(yaw)*d/2,2.01,z-Math.sin(yaw)*d/2,.36,.055,.055,'#5c6b68',{yaw});
    box(x+Math.cos(yaw)*d,1.99,z-Math.sin(yaw)*d,.18,.084,.16,'#ffedaa');
  }
  function pad(x,z,w,d){ground(x,z,w,d,curb,.032,.104);}
  function access(x,frontZ,roadZ,w=1.42){
    const end=roadZ-ROAD_WIDTH/2+.13;
    ground(x,(end+frontZ)/2,w,end-frontZ,'#a4aaab',.024,.048);
  }
  function parking(x,z,count=3){
    ground(x,z,count*.74+.36,1.15,'#879598',.092);
    for(let i=0;i<=count;i++)box(x+(i-count/2)*.74,.126,z,.04,.018,1.02,'#e9e8da',noShadow);
  }
  function shutter(x,y,z,w,h,color='#708890'){
    box(x,y,z,w+.18,h+.18,.09,'#43575b');
    box(x,y,z+.061,w,h,.065,color);
    for(let s=.13;s<h;s+=.15)box(x,y-h/2+s,z+.103,w,.023,.026,'#c4cdcb',noShadow);
  }
  function windowStrip(x,y,z,width,color='#83bdca'){
    box(x,y,z,width,.44,.075,'#4c646f');
    box(x,y,z+.044,width-.14,.33,.026,color,noShadow);
    for(let i=-width/2+.58;i<width/2;i+=.6)box(x+i,y,z+.063,.038,.33,.022,'#b0d2cf',noShadow);
  }
  function container(x,z,y,color,turned=false){
    const w=turned?1.9:.88,d=turned?.88:1.9;
    box(x,y,z,w,.64,d,color);
    for(let r=-d/2+.14;r<d/2;r+=.19)box(x+w/2+.012,y,z+r,.036,.47,.026,'#bcb9a6',noShadow);
    box(x,y+.337,z,w,.035,d,'#6c726c',noShadow);
  }

  box(0,-.62,0,MEADOW_SIZE.width,1.04,MEADOW_SIZE.depth,'#82a76d',noShadow);
  ground(0,0,79.93,61.93,'#a1c17e',-.104,.055);
  ground(0,0,CITY_SIZE.width,CITY_SIZE.depth,'#c9d4aa',-.064,.1);
  const lanes=(axis,across,span)=>{
    const isX=axis==='x';
    for(const lane of across){
      ground(isX?0:lane,isX?lane:0,isX?span:ROAD_WIDTH,isX?ROAD_WIDTH:span,asphalt,isX?-.012:-.014,.05);
      for(let step=-span/2+.45;step<span/2-.4;step+=1.3){
        const joins=isX?ROAD_X:ROAD_Z;
        if(joins.some(join=>Math.abs(join-step)<2.36))continue;
        box(isX?step:lane,.019,isX?lane:step,isX?.58:.045,.014,isX?.045:.58,dash,noShadow);
      }
    }
  };
  lanes('x',ROAD_Z,CITY_SIZE.width);
  lanes('z',ROAD_X,CITY_SIZE.depth);
  for(const x of ROAD_X)for(const z of ROAD_Z){
    for(const side of [-1,1])for(let i=-3;i<=3;i++){
      box(x+i*.258,.027,z+side*1.53,.137,.017,.51,'#ede9ce',noShadow);
      box(x+side*1.53,.027,z+i*.258,.51,.017,.137,'#ede9ce',noShadow);
    }
    const west=x===ROAD_X[0]?-1:1;
    const north=z===ROAD_Z[0]?-1:1;
    lamp(x+west*1.62,z+north*1.72,west===1?Math.PI:0);
  }
  for(let col=0;col<ROAD_X.length-1;col++)for(let row=0;row<ROAD_Z.length-1;row++){
    const a=ROAD_X[col],b=ROAD_X[col+1],c=ROAD_Z[row],d=ROAD_Z[row+1];
    const x=(a+b)/2,z=(c+d)/2,w=b-a-ROAD_WIDTH-.36,l=d-c-ROAD_WIDTH-.36;
    pad(x,z,w,l);
    ground(x,z,w-.55,l-.54,'#b7c78d',.087,.023);
  }

  // Civic campus: distinct retail and receiving entrances plus a visible six-floor tower.
  const towerX=-17,towerZ=-11.4,towerW=7.6,floorH=1.36,roofY=8.91;
  pad(towerX,towerZ,11.55,6.6);
  ground(towerX,-8.33,8.65,1.15,concrete,.115);
  box(towerX,4.47,towerZ-.56,towerW,8.39,3.55,'#486f71');
  box(towerX,4.48,towerZ-1.65,towerW*.95,8.43,.87,'#6ca1a2');
  box(towerX,.32,towerZ,8.31,.4,5.27,'#e4debe');
  for(const [role,o] of Object.entries(offices)){
    const y=.52+o.level*floorH;
    box(towerX,y,towerZ,8.19,.15,5.08,'#e2dec0');
    box(towerX,y+.83,towerZ-2.36,7.83,.87,.1,'#7aa5aa');
    for(const dx of [-2.96,-1.8,-.6,.6,1.8,2.96]){
      box(towerX+dx,y+.83,towerZ-2.285,.022,.85,.026,'#a5c2b8',noShadow);
    }
    for(const s of [-1,1]){
      box(towerX+s*3.64,y+.64,towerZ+1.68,.18,1.19,1.5,o.color);
      box(towerX+s*3.855,y+.77,towerZ-1.03,.062,.68,.98,'#8bbeb9');
    }
    box(towerX+1.3,y+.27,towerZ+1.69,.95,.36,.56,'#ac855d');
    box(towerX+1.3,y+.59,towerZ+1.64,.38,.28,.095,'#7ea0b1');
    // Small, separate floor lamps show the active team.
    const strip=solid(scene,new THREE.BoxGeometry(.48,.075,.075),o.color,towerX+3.36,y+.34,towerZ+2.545,false);
    floorLights.set(role,strip);
    anchors.set(role,[towerX-3.95,y+.65,towerZ+2.5]);
    if(o.level%2===1){
      const actor=createActor({role,index:o.level,variant:o.level,briefcase:false,detail:'compact'});
      actor.root.scale.setScalar(.39);
      actor.root.position.set(towerX+.34,y+.075,towerZ+1.84);
      scene.add(actor.root);
      actors.push({role,actor});
    }
  }
  box(towerX,roofY,towerZ,8.6,.41,5.22,'#d5b970');
  box(towerX,roofY+.26,towerZ,7.84,.19,4.54,'#9aa487');
  for(const dx of [-2.05,0,2.05]){
    box(towerX+dx,roofY+.41,towerZ-.23,1.87,.15,2.69,'#345a71');
    for(const sep of [-.46,0,.46])box(towerX+dx+sep,roofY+.493,towerZ-.23,.024,.014,2.63,'#80abb6',noShadow);
    for(const sep of [-.8,0,.8])box(towerX+dx,roofY+.495,towerZ-.23+sep,1.81,.014,.027,'#80abb6',noShadow);
  }
  board(scene,'BIZ MARKET',{x:towerX,y:roofY,z:towerZ+2.624,w:3.6,h:.5});
  anchors.set('biz',[towerX,roofY+.75,towerZ+.4]);
  clickable('procurement',towerX,4.7,towerZ,8.9,9.4,5.4);
  for(const [x,z] of [[-22.1,-9.43],[-11.6,-9.55],[-22,-14.6],[-11.45,-14.5]])tree(x,z,.89,1);

  const storeX=-20.7,storeZ=-.52;
  pad(storeX,storeZ,5.88,7.34);
  box(storeX,1.49,storeZ,4.85,2.84,4.57,'#dfd8ad');
  box(storeX,2.98,storeZ,5.15,.28,4.87,'#527c6e');
  box(storeX,1.3,storeZ+2.318,4.29,1.7,.125,'#80aab3');
  for(let i=-2;i<=2;i++)box(storeX+i*.82,1.36,storeZ+2.397,.079,1.65,.04,'#d4e7d1');
  box(storeX,2.21,storeZ+2.454,4.61,.46,.21,'#305848');
  board(scene,'BIZ STORE',{x:storeX,y:2.2,z:storeZ+2.575,w:3.2,h:.36});
  parking(storeX-1.72,2.59,2);
  parking(storeX+1.72,2.59,2);
  access(storeX,3.27,6);
  clickable('seller',storeX,1.63,storeZ,5.22,3.22,4.95);
  const warehouseX=BIZ_DOCK.x,warehouseZ=-.05;
  pad(warehouseX,warehouseZ,6.65,7.85);
  access(warehouseX,3.44,6,2);
  box(warehouseX,1.53,warehouseZ,5.92,2.85,4.71,'#ddd9b3');
  box(warehouseX,3.04,warehouseZ,6.08,.32,4.92,'#658d60');
  for(const dx of [-1.42,.1,1.62])shutter(warehouseX+dx,1.0,warehouseZ+2.38,1.22,1.71,'#849aa0');
  box(warehouseX,2.59,warehouseZ+2.411,5.68,.5,.121,'#47735f');
  board(scene,'GUDANG BIZ',{x:warehouseX,y:2.59,z:warehouseZ+2.49,w:3.28,h:.37});
  container(warehouseX-2.58,warehouseZ+.25,.48,'#a88b56');
  tree(-23.05,-3.48,.61);tree(-10.78,-3.58,.62,1);
  clickable('stock',warehouseX,1.67,warehouseZ,6.18,3.38,4.98);

  for(const [name,data] of Object.entries(vendors)){
    const parcel=vendorParcels[vendorIndex.get(name)??(data.index??0)%vendorParcels.length];
    if(!parcel)continue;
    const {x,z,roadZ,width,depth,height,color}=parcel;
    const dockOffset=roadZ<0?3.03:3.52,w=Math.min(width-.92,6.32),d=4.24;
    vendorLots.set(name,{x,z,roadZ,dockOffset});
    pad(x,z,width,depth);
    access(x,z+dockOffset-.4,roadZ,1.54);
    box(x,height/2+.16,z,w,height,d,'#dddcd2');
    box(x,height+.16,z,w+.18,.20,d+.22,color);
    box(x,height+.39,z-.47,w*.43,.36,1.36,'#819796');
    box(x,height*.50,z+d/2+.018,w,.95,.10,color);
    board(scene,name.toUpperCase(),{x,y:height*.50,z:z+d/2+.08,w:w*.82,h:.48});
    for(let y=1.1;y<height+.06;y+=.84){
      if(Math.abs(y-height*.5)>.64)windowStrip(x,y,z+d/2+.062,w*.86);
      for(const dz of [-1.27,-.41,.43,1.25])box(x+w/2+.045,y,z+dz,.061,.4,.49,'#759ea9',noShadow);
    }
    ground(x,z+d/2+.32,1.7,.6,'#d9c196',.118,.16);
    parking(x+Math.min(w*.34,width/2-1.12),z+d/2+.99,2);
    for(const side of [-1,1])tree(x+side*(width/2-.73),z-depth/2+.65,.56,side===1?1:0);
    anchors.set(name,[x,height+.91,z+.36]);
    clickable(name,x,height/2+.22,z,w+.32,height+.45,d+.3);
  }

  for(const [index,name] of Object.keys(carriers).entries()){
    const {x,z,color,light,roof,sign}=carrierParcels[index%carrierParcels.length];
    const w=8.7,d=4.11, dockZ=z+3.48;
    carrierLots.set(name,{x,z,dockZ,color});
    pad(x,z+.46,12.1,7.42);
    access(x,dockZ-.25,17,2.24);
    ground(x,z+3.07,9.02,1.86,'#abb0a7',.10,.055);
    box(x,1.58,z,w,3,d,light);
    box(x,3.18,z,w+.18,.31,d+.21,roof);
    const fascia=solid(scene,new THREE.BoxGeometry(w,.48,.14),color,x,2.71,z+d/2+.025);
    carrierLights.set(name,fascia);
    board(scene,sign,{x,y:2.71,z:z+d/2+.112,w:w*.59,h:.4});
    const docks=index===1?[-3.1,-1.03,1.03,3.1]:[-2.52,0,2.52];
    for(const dx of docks){
      shutter(x+dx,1.13,z+d/2+.02,1.44,1.83);
      ground(x+dx,z+d/2+.36,1.7,.61,'#d2b16b',.153,.17);
      for(const s of [-1,1])box(x+dx+s*.82,.25,z+d/2+.62,.085,.46,.085,'#ceb04a');
    }
    if(index===0){
      box(x+1.91,3.38,z-.35,2.72,.21,1.65,'#8aa9a8');
      box(x+1.91,3.50,z-.35,2.38,.08,1.36,'#5a7a88');
    }else{
      for(const side of [-1,1])box(x+side*2.16,3.4,z-.14,3.95,.18,1.68,index===1?'#bc7770':'#b28b53');
    }
    for(const side of [-1,1]){
      const cx=x+side*5.19;
      for(const [dz,tint] of [[-.97,'#7a9a92'],[1.05,color]])container(cx,z+dz,.428,tint);
      if(side>0)container(cx,z-.97,1.11,color);
      tree(x+side*5.77,z-1.99,.60,side===1?1:0);
    }
    anchors.set(name,[x,4.04,z+.4]);
    clickable(name,x,1.78,z,9,3.55,4.36);
  }

  // Landscaping and pedestrian-only bridge remain clear of all asphalt.
  pad(0,0,15.13,9.28);
  ground(0,0,14.35,8.55,'#83ae75',.1,.07);
  ground(0,0,14.33,1,'#e4d6b1',.145,.045);
  ground(0,0,1.2,8.55,'#e4d6b1',.147,.049);
  solid(scene,new THREE.CylinderGeometry(1.85,1.85,.21,26),'#ded7bc',0,.227,0);
  solid(scene,new THREE.CylinderGeometry(1.61,1.61,.14,26),'#6fadaa',0,.353,0,false);
  solid(scene,new THREE.CylinderGeometry(.18,.22,.45,14),'#eadbb7',0,.55,0);
  solid(scene,new THREE.SphereGeometry(.22,12,9),'#b7e3dd',0,.87,0,false);
  board(scene,'CENTRAL PARK',{x:0,y:.177,z:3.36,w:3.6,h:.56,color:'#416244',horizontal:true});
  for(const [x,z,size] of [[-6.1,-3.04,.92],[-2.7,-2.8,.75],[2.62,-2.94,.93],[6.12,-3.05,.75],[-5.82,2.7,.98],[-3.25,2.64,.68],[3.5,2.6,.80],[6.18,2.8,1.02]])tree(x,z,size,Math.floor(x<0));
  for(const x of [-5,-2.5,2.5,5]){
    box(x,.27,1.19,1.03,.17,.35,'#9f7459');
    box(x,.44,1.34,1,.12,.09,'#a78163');
  }

  const hillGeom=new THREE.SphereGeometry(1,19,10,0,Math.PI*2,0,Math.PI/2);
  for(const [x,z,w,h,d,tint] of [
    [-34.7,-19.7,5.05,2.9,7.2,'#91b577'],[-35,1.9,4.47,3.55,6.9,'#84ad72'],
    [-35.15,22.1,4.43,2.9,6.16,'#87b271'],[35.45,-22.08,4.09,3.58,7.3,'#82a86d'],
    [36.6,19.63,2.91,2.58,5.73,'#9cbd78'],[3.0,-27.25,5.84,1.8,3.05,'#8fb36f'],
  ]){
    const hill=solid(scene,hillGeom,tint,x,-.096,z,false);
    hill.scale.set(w,h,d);
  }
  for(const [x,z,size] of [[-32,-12.3,.94],[-30.8,-6.4,.85],[-32.8,10.2,1.08],[-30.91,14.42,.85],[-36,13,1.03],[30.74,-22.8,.88],[36,-13.6,.81],[36.4,11.74,1.05],[32,22.85,1.1],[28,24.5,.85],[-27.9,-23.8,.8],[25,-25.2,.84]])tree(x,z,size,1);
  ground(32.7,1.0,2.73,31.75,'#699ba5',-.08,.028);
  ground(32.68,1.0,1.43,31.67,'#81b5b7',-.064,.019);
  for(const x of [30.9,34.41])ground(x,1,.59,31.64,'#bdcaa4',-.074,.023);
  ground(29.45,1.8,2.75,1.5,'#dfcfaa',-.04,.05);
  ground(36.05,1.8,2.1,1.5,'#dfcfaa',-.04,.05);
  const arch=(t)=>.86*Math.sin(Math.PI*t);
  for(let index=0;index<14;index++){
    const t=(index+.5)/14,x=30.12+t*5;
    const inclination=(arch(t+.003)-arch(t-.003))/(.006*5);
    const deck=solid(scene,new THREE.BoxGeometry(.394,.13,1.49),'#c49362',x,arch(t)+.02,1.8);
    deck.rotation.z=Math.atan(inclination);
    if(index%3===1)for(const dz of [-.66,.66])box(x,arch(t)+.32,1.8+dz,.095,.68,.087,'#936c4d');
  }
  for(const dz of [-.67,.67]){
    const curve=new THREE.CatmullRomCurve3(Array.from({length:7},(_,i)=>new THREE.Vector3(30.12+5*i/6,.59+arch(i/6),1.8+dz)));
    solid(scene,new THREE.TubeGeometry(curve,22,.055,7,false),'#99794e',0,0,0);
  }

  function roof(x,z,w,d,y,color){
    const rafters=solid(scene,new THREE.CylinderGeometry(1,1,d,3,1),color,x,y+.11,z);
    rafters.rotation.x=-Math.PI/2;
    rafters.scale.set(w*.64,1,.83);
  }
  const houseColors=['#ba745d','#577f8c','#aa8d59','#966999','#5a9b81'];
  for(const [index,x] of [-25.4,-20.47,-15.57,-10.71,9.1,14.13,19.14,24.17].entries()){
    const z=index%2?-24.3:-24.82,c=houseColors[index%houseColors.length];
    ground(x,z,3.38,3.25,'#c8cd9f',-.014,.054);
    box(x,.81,z,2.56,1.51,2.52,'#e4d8b7');
    roof(x,z,2.8,2.91,1.77,c);
    box(x,.51,z+1.285,.49,.98,.071,'#8e7862');
    for(const dx of [-.77,.8])box(x+dx,.91,z+1.29,.36,.43,.065,'#7da8b2');
    for(const dx of [-1.25,1.25])tree(x+dx,z-1.4,.55,index);
  }
  ground(0,-22.14,51.9,.91,'#d8cba8',-.051,.031);
  for(const [index,x] of [-20.5,-14.9,-9.3].entries()){
    const z=24.1,color=['#a75852','#5d9381','#b39b5b'][index];
    ground(x,z,4.45,4.2,'#d9d5ae',.006,.037);
    box(x,1.05,z,3.9,2.07,3.2,'#e2dcc0');
    box(x,2.12,z,4,.27,3.43,color);
    box(x,.82,z-1.64,3.12,1.2,.095,'#6f989e');
    for(const dx of [-1.1,0,1.1])box(x+dx,1.49,z-1.8,1.1,.16,.43,color);
    box(x,1.93,z-1.689,2.86,.31,.085,color);
    tree(x-1.77,z+1.42,.59,index);
  }
  ground(-14.9,21.82,16.8,1.06,'#d9caa4',-.034,.046);

  const quarantine=new THREE.Group();
  quarantine.position.set(warehouseX-2.45,.035,warehouseZ+2.85);
  for(const z of [-.33,0,.33])solid(quarantine,new THREE.BoxGeometry(1.75,.13,.24),'#876540',0,.094,z);
  solid(quarantine,new THREE.BoxGeometry(1.01,.63,.77),'#bb6145',-.3,.47,0);
  const crate=solid(quarantine,new THREE.BoxGeometry(.54,.48,.68),'#e33f3c',.5,.40,0);
  crate.material.emissive.set('#ff443c');
  for(const x of [-.65,.18,.72])solid(quarantine,new THREE.BoxGeometry(.055,.69,.8),'#f1b875',x,.47,0);
  quarantine.visible=false;
  scene.add(quarantine);
  flush();
  return {anchors,pickables,actors,floorLights,carrierLights,trees,vendorLots,carrierLots,quarantine,quarantineCrate:crate};
}
