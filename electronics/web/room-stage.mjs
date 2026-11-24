import {placePoly} from './poly-assets.mjs';

// Display order is Laptop, Monitor, Printer.
export const showroomPositions = {
  buyer: [[4.75, 1.38], [6.95, 1.38], [9.15, 1.38]],
  seller: [[1.7, 1.32], [4, 1.32], [6.3, 1.32]],
};
export const showroomProducts = ['Laptop', 'Monitor', 'Printer'];
const deskSeat = (x, z, work = 'type') => ({x, z, facing: Math.PI, work});
const officeSeats = {
  'staff-0': deskSeat(3.02, 3.78),
  'staff-1': deskSeat(7.19, 4.18),
  'staff-2': deskSeat(7.34, 6.82),
};
export const roomSeats = {
  buyer: {'staff-0': deskSeat(2.27, 3.48)},
  seller: {'staff-0': deskSeat(7.81, 3.66), 'staff-2': deskSeat(8.30, 5.72)},
  stock: {'staff-0': deskSeat(7.15, 3.83)},
  finance: officeSeats, procurement: officeSeats,
  deal: {
    'staff-0': deskSeat(4.35, 4.44, 'read'),
    'staff-1': deskSeat(7.99, 4.60),
    visitor: {x:6.49, z:2.64, facing:0, work:'read'},
  },
  vendor: {'staff-0':officeSeats['staff-0']},
  carrier: {'staff-0':officeSeats['staff-0']},
};
const warehouseRacks = [[2.1, 1.05], [4.53, 1.05], [6.96, 1.05], [9.39, 1.05], [2.4, 2.85], [4.82, 2.85]];
const shelfLevels = [.169, .638, 1.107];

/** Cutaway room geometry shared by the six BIZ floors and the vendor offices. */
export function buildRoomStage(THREE, scene, room, role, assets = {}) {
  const stage = new THREE.Group();
  stage.name = 'BIZ interior';
  scene.add(stage);
  const batch = new Map();
  const stockDisplays = [];
  const walkObstacles=[];
  function obstacle(x,z,width,depth,kind='furniture'){
    walkObstacles.push({minX:x-width/2,maxX:x+width/2,minZ:z-depth/2,maxZ:z+depth/2,kind});
  }
  stage.userData.walkObstacles=walkObstacles;
  const geometry = new THREE.BoxGeometry(1, 1, 1);
  function box(x, y, z, width, height, depth, color, castsShadow = true) {
    const key = color + '/' + castsShadow;
    if (!batch.has(key)) batch.set(key, { color, castsShadow, items: [] });
    batch.get(key).items.push([x, y, z, width, height, depth]);
  }
  function looseBox(parent, x, y, z, width, height, depth, color, castsShadow = true) {
    const object = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({color, roughness:.84}));
    object.position.set(x,y,z);
    object.scale.set(width,height,depth);
    object.castShadow=castsShadow;
    object.receiveShadow=true;
    parent.add(object);
    return object;
  }

  const concrete = ['stock','vendor','carrier'].includes(role);
  const grout = concrete ? '#a5b2b8' : '#ba9271';
  const cream = '#eff0e9', navy = '#253b52', metal = '#687d83';
  const wood = '#c6a37b', desktop = '#e4cca7';
  const softFloor = ['#e8d6bd', '#ddc7aa', '#e4ceb1', '#d9c1a2'];
  const hardFloor = ['#cad5d9', '#d3dce0', '#c4d3d8', '#d0d8dd'];
  const floorColors = concrete ? hardFloor : softFloor;

  box(5.5, -.18, 4, 11.18, .36, 8.18, '#546a76', false);
  box(5.5, -.04, 4, 11, .073, 8, grout, false);
  for (let row = 0; row < 16; row++) {
    const offset = row % 2 === 0 ? 0 : .75;
    for (let x = offset - 2.2; x < 11; x += 2.2) {
      const left = Math.max(0, x), right = Math.min(11, x + 2.2);
      if (right <= left) continue;
      const color = floorColors[(row + Math.round((x - offset) / 2.2) + 8) % floorColors.length];
      box((left + right) / 2, -.008, row * .5 + .25, right - left - .013, .017, .484, color, false);
    }
  }

  if(role==='vendor'||role==='carrier'){
    box(10.25,.014,7.72,1.28,.022,.48,'#738c88',false);
    for(const x of [9.61,10.89]){
      obstacle(x,7.82,.075,.12);
      box(x,1.05,7.82,.075,2.1,.12,'#6e8585',false);
    }
    box(10.25,2.12,7.82,1.36,.12,.12,'#6e8585',false);
    box(10.25,2.12,7.9,.45,.07,.025,'#d7edca',false);
  }

  // An open corner lets the camera see the workstations from above.
  box(-.07, 1.2, 4, .14, 2.4, 8.04, '#c9ddd8', false);
  box(5.5, 1.2, -.07, 11.16, 2.4, .14, '#f5e5d5', false);
  box(-.025, .065, 4, .07, .13, 8, '#78888d', false);
  box(5.5, .065, -.025, 11, .13, .07, '#87989c', false);
  box(0, 2.42, 4, .23, .045, 8.1, '#748990', false);
  box(5.5, 2.42, 0, 11.17, .045, .23, '#83979c', false);

  function window(x) {
    box(x, 1.52, .02, 2.05, 1.13, .07, cream, false);
    box(x, 1.52, .069, 1.9, .97, .036, '#85c6e2', false);
    box(x, 1.52, .089, .044, 1.04, .022, '#e5eff0', false);
    box(x, 1.54, .09, 1.93, .037, .024, '#e5eff0', false);
    box(x, .95, .13, 2.09, .07, .25, '#c1cfd0', false);
  }
  [1.85, 5.5, 9.15].forEach(window);
  for (const z of [2.1, 4, 5.9]) {
    box(.035, 1.57, z, .057, .74, .98, '#809296', false);
    box(.074, 1.57, z, .03, .62, .86, room.color, false);
    box(.095, 1.66, z - .13, .014, .032, .32, cream, false);
    box(.095, 1.49, z + .08, .014, .032, .39, cream, false);
  }

  function mat(x, z, width, depth, color, piping) {
    box(x, .014, z, width + .13, .017, depth + .13, piping, false);
    box(x, .023, z, width, .011, depth, color, false);
  }

  function plant(x,z){
    obstacle(x,z,.36,.36);
    box(x,.12,z,.29,.24,.29,'#d18c64');
    for(const [dx,dy,dz,color] of [[.06,.44,0,'#328965'],[-.09,.55,.025,'#5bb280'],[.07,.65,-.04,'#6ec08c']]){
      const leaf=new THREE.Mesh(new THREE.SphereGeometry(.15,11,8),new THREE.MeshStandardMaterial({color}));
      leaf.position.set(x+dx,dy,z+dz);
      leaf.scale.set(.85,1.2,.82);
      leaf.castShadow=true;
      stage.add(leaf);
    }
  }
  plant(.65, .72);
  plant(10.3, .75);
  plant(10.42, 7.35);

  function chair(x, z, facingWall = true, color = navy) {
    obstacle(x,z,.43,.43,'chair');
    box(x, .27, z, .39, .08, .38, color);
    box(x, .46, z + (facingWall ? .17 : -.17), .39, .34, .07, color);
    box(x, .115, z, .092, .22, .083, metal);
    box(x, .025, z, .43, .043, .29, metal);
  }

  function monitor(x, z, y = .74) {
    box(x, y + .012, z, .23, .024, .20, navy);
    box(x, y + .074, z, .052, .128, .07, navy);
    box(x, y + .184, z, .46, .27, .06, '#263940');
    box(x, y + .188, z + .033, .41, .221, .008, '#2f697b', false);
    for (const [i, width] of [.22, .16, .27].entries()) {
      box(x - .016, y + .25 - i * .043, z + .039, width, .011, .005, '#9fd4d2', false);
    }
    box(x, y + .016, z + .24, .35, .028, .105, '#758c8c');
  }

  function desk(x, z, width = 1.52, depth = .73, document = true) {
    obstacle(x,z,width,depth);
    box(x, .70, z, width, .08, depth, desktop);
    for (const dx of [-1, 1]) for (const dz of [-1, 1]) {
      box(x + dx * (width / 2 - .12), .325, z + dz * (depth / 2 - .10), .075, .65, .075, cream);
    }
    monitor(x - .2, z - .15);
    if (document) {
      box(x + .40, .75, z + .06, .32, .014, .25, room.color);
      box(x + .41, .763, z + .058, .23, .01, .21, '#f4f4ef');
      box(x + .41, .773, z + .11, .14, .005, .01, '#b6c9cb');
    }
  }

  function carton(x, z, y, size = 1) {
    if(y===0||y===.125)obstacle(x,z,.38*size,.32*size);
    box(x, y + .15 * size, z, .38 * size, .30 * size, .32 * size, '#c68b57');
    box(x, y + .302 * size, z, .079 * size, .009, .32 * size, '#eac38d');
    box(x, y + .22 * size, z + .163 * size, .075 * size, .16 * size, .008, '#eac38d');
  }

  function shelf(x, z, contents) {
    obstacle(x,z,1.97,.7);
    for (const dx of [-.92, .92]) {
      for (const dz of [-.29, .29]) box(x + dx, .77, z + dz, .068, 1.54, .068, metal);
    }
    [0.13, .60, 1.07, 1.51].forEach(y => box(x, y, z, 1.9, .073, .63, '#5b737b'));
    for (const y of shelfLevels) for (const dx of [-.57, 0, .57]) {
      if (contents === 'products') {
        box(x + dx, y + .12, z, .38, .24, .31, '#d8ebef');
        box(x + dx, y + .15, z + .159, .29, .107, .01, '#84aeb9');
      } else if (contents === 'cartons') {
        carton(x + dx, z, y, dx > 0 ? .80 : 1);
      }
    }
  }

  function displayStands() {
    const slate = '#263848', silver = '#afc3cd', glass = '#457e98';
    const accents = ['#2a867f', '#2481a3', '#9e753b'];
    showroomPositions[role].forEach(([x, z], index) => {
      obstacle(x,z,1.57,.92);
      const accent = accents[index];
      const base=looseBox(stage,x,.39,z,1.46,.76,.78,'#e8e5d8');
      const top=looseBox(stage,x,.77,z,1.57,.10,.92,'#fff3d9');
      const stripe=looseBox(stage,x,.18,z+.399,1.34,.13,.024,accent);
      const item=new THREE.Group();
      item.name=showroomProducts[index];
      stage.add(item);
      const modelBox=(...args)=>looseBox(item,...args);
      stockDisplays.push({item,base,top,stripe,accent});

      const model = assets[['laptop','monitor','printer'][index]];
      if (model) {
        placePoly(item,model,{x,y:.832,z,width:1.23,height:[.50,.84,.47][index],depth:.75});
        return;
      }
      if (index === 0) {
        // Open laptop with a combined keyboard deck and screen.
        modelBox(x, .856, z + .03, .93, .068, .57, silver);
        modelBox(x, .885, z - .015, .74, .013, .27, slate);
        for (let row = 0; row < 3; row++) {
          modelBox(x, .893, z - .10 + row * .079, .60, .006, .024, '#6a8595');
        }
        modelBox(x, .892, z + .212, .22, .01, .09, '#bdc9ce');
        modelBox(x, 1.095, z - .244, .93, .45, .069, slate);
        modelBox(x, 1.10, z - .202, .84, .36, .019, glass, false);
        modelBox(x - .16, 1.17, z - .19, .42, .039, .012, '#a6e1dc', false);
      } else if (index === 1) {
        // Standalone monitor with a taller widescreen and upright stand.
        modelBox(x, .855, z, .54, .059, .37, silver);
        modelBox(x, 1.016, z - .11, .15, .32, .17, slate);
        modelBox(x, 1.34, z - .116, 1.16, .63, .099, slate);
        modelBox(x, 1.347, z - .06, 1.05, .52, .022, '#437f9a', false);
        modelBox(x - .245, 1.35, z - .044, .35, .39, .011, '#a1ced8', false);
        for (const y of [1.20, 1.30, 1.41]) {
          modelBox(x + .23, y, z - .044, .40, .025, .011, '#90bdc8', false);
        }
      } else {
        // Printer has a scanner lid and a sheet coming out of the front slot.
        modelBox(x, 1.005, z - .04, 1.01, .36, .65, '#e3e9e6');
        modelBox(x, 1.225, z - .075, .96, .085, .58, slate);
        modelBox(x, 1.267, z - .085, .82, .024, .46, '#648392');
        modelBox(x - .10, 1.03, z + .293, .66, .13, .028, slate);
        modelBox(x - .10, .977, z + .355, .60, .036, .18, '#9bb0ba');
        modelBox(x - .10, .998, z + .38, .49, .012, .22, '#ffffee');
        modelBox(x + .35, 1.116, z + .29, .12, .045, .028, '#80b797');
      }
    });
  }

  if (role === 'stock') {
    mat(8.85, 6.2, 2.9, 1.85, '#748b91', '#d5ad61');
    for (const [x, z] of warehouseRacks) shelf(x,z);
    desk(7.3, 3.25, 1.45, .73);
    obstacle(9.8,6.52,1.08,.71);
    for (const z of [6.26,6.52,6.78]) box(9.8,.09,z,1.08,.1,.19,'#a9764d');
  } else if (role === 'seller') {
    mat(4.69, 5.6, 6.5, 2.45, '#4e728f', '#93b9cc');
    displayStands();
    shelf(2.37, 3.0, 'products');
    desk(7.96, 3.08, 1.9, .73, false);
    box(8.7, .82, 3.12, .46, .19, .32, '#779da8');
    box(8.7, .92, 3.14, .21, .009, .17, '#2c4e61');
    desk(8.45, 5.16, 1.12, .65, false);
  } else if (role === 'buyer') {
    mat(4.75, 5.69, 7.64, 2.75, '#679484', '#bfd8c5');
    desk(2.42, 2.9, 1.92);
    displayStands();
    obstacle(.61,5.72,.86,2.39);
    if (assets.sofa) {
      placePoly(stage,assets.sofa,{x:.61,z:5.72,width:.86,height:.9,depth:2.39,angle:Math.PI/2});
    } else {
      box(.51, .27, 5.72, .69, .34, 2.32, '#a1cab5');
      box(.23, .55, 5.72, .17, .42, 2.32, '#8eb49e');
      for (let i = 0; i < 3; i++) box(.595, .475, 4.98 + i * .74, .48, .085, .65, '#c0dbcc');
    }
  } else if (role === 'deal') {
    mat(5.9, 3.92, 6.2, 3.11, '#504f74', '#ada7bc');
    obstacle(5.42,3.58,3.4,1.12);
    box(5.42, .70, 3.58, 3.4, .11, 1.12, desktop);
    for (const x of [4.13, 6.67]) box(x, .35, 3.58, .15, .70, .77, wood);
    for (const x of [4.35, 5.42, 6.49]) {
      if(x!==4.35)chair(x, 4.44, true, '#635e81');
      if(x!==6.49)chair(x, 2.64, false, '#635e81');
      box(x, .768, 3.67, .32, .013, .24, '#f3f2e8');
    }
    desk(8.14, 4.05, 1.18, .60);
  } else {
    mat(5.37, 4.21, 7.09, 4.44, role === 'finance' ? '#4e537a' : '#485e76', room.color);
    for (const [x, z] of [[3.15, 3.19], [7.34, 3.6], [7.48, 6.24]]) desk(x, z);
    if (role === 'carrier') {
      shelf(2.0, 1.0, 'cartons');
      obstacle(9.75,6.28,1.14,.89);
      for (const z of [5.92,6.28,6.64]) box(9.75,.07,z,1.14,.11,.17,'#a9764d');
      carton(9.47,6.1,.125);
      carton(9.95,6.5,.125,1.12);
      box(10.57, .023, 6.68, .085, .013, 1.95, '#deac52', false);
    } else if (role === 'vendor') {
      shelf(2.0, 1.0, 'cartons');
      carton(9.82, 6.71, 0, 1.2);
      carton(10.3, 6.63, 0);
    } else {
      obstacle(10.08,3.37,.58,1);
      box(10.08, .48, 3.37, .58, .96, 1.0, '#bad0d0');
      for (const y of [.19, .48, .77]) {
        box(10.08, y, 3.88, .52, .24, .026, '#d8dfdb');
        box(10.08, y, 3.90, .18, .036, .022, metal);
      }
    }
  }

  for (const seat of Object.values(roomSeats[role]??{})) {
    chair(seat.x, seat.z, seat.facing===Math.PI, role==='deal'?'#635e81':navy);
  }

  const pose = new THREE.Matrix4();
  for (const { color, castsShadow, items } of batch.values()) {
    const material = new THREE.MeshStandardMaterial({ color, roughness: .88 });
    const mesh = new THREE.InstancedMesh(geometry, material, items.length);
    mesh.castShadow = castsShadow;
    mesh.receiveShadow = true;
    for (const [i, [x, y, z, width, height, depth]] of items.entries()) {
      pose.makeScale(width, height, depth).setPosition(x, y, z);
      mesh.setMatrixAt(i, pose);
    }
    mesh.instanceMatrix.needsUpdate = true;
    stage.add(mesh);
  }
  let cartons=[];
  if(role==='stock'){
    const slots=warehouseRacks.flatMap(([x,z])=>shelfLevels.flatMap(y=>
      Array.from({length:7},(_,index)=>[x+(index-3)*.24,y,z])));
    cartons=[
      ['#c68b57',.219,.275,.33,0,.1375,0],
      ['#f2d1a6',.055,.008,.33,0,.279,0],
      ['#f2d1a6',.061,.098,.008,0,.151,.167],
    ].map(([color,width,height,depth,dx,dy,dz],index)=>{
      const material=new THREE.MeshStandardMaterial({color,roughness:.87});
      const mesh=new THREE.InstancedMesh(geometry,material,slots.length);
      mesh.name=['Kardus persediaan','Pita kardus','Label kardus'][index];
      mesh.castShadow=true;
      mesh.receiveShadow=true;
      slots.forEach(([x,y,z],index)=>{
        pose.makeScale(width,height,depth).setPosition(x+dx,y+dy,z+dz);
        mesh.setMatrixAt(index,pose);
      });
      mesh.instanceMatrix.needsUpdate=true;
      mesh.computeBoundingSphere();
      stage.add(mesh);
      return mesh;
    });
    stage.userData.cartonCapacity=slots.length;
  }
  stage.userData.setStock=products=>{
    const counts=new Map(products.map(({name,units})=>[name,Math.max(0,Math.trunc(units)||0)]));
    const total=[...counts.values()].reduce((sum,count)=>sum+count,0);
    for(const mesh of cartons)mesh.count=Math.min(total,stage.userData.cartonCapacity);
    for(const [index,{item,base,top,stripe,accent}] of stockDisplays.entries()){
      const available=(counts.get(showroomProducts[index])??0)>0;
      item.visible=available;
      base.material.color.set(available?'#e8e5d8':'#c64848');
      top.material.color.set(available?'#fff3d9':'#e97564');
      stripe.material.color.set(available?accent:'#87302e');
    }
  };

  return stage;
}
