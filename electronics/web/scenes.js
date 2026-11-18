
function inspectionCounts({ordered, accepted, damaged}) {
    return `<dl class="inspection-counts">
      <div><dt>Dipesan</dt><dd>${esc(ordered)} unit</dd></div>
      <div><dt>Layak jual</dt><dd>${esc(accepted)} unit</dd></div>
      <div${damaged ? ' class="inspection-damaged"' : ''}><dt>Rusak</dt><dd>${esc(damaged)} unit</dd></div>
    </dl>`;
}

function inspectionScene(event) {
    const {product, vendor} = event.inspection;
    return `<section class="ship-scene inspection-scene" aria-label="${esc(event.title)}" aria-live="polite">
      <div class="ship-caption">
        <strong>${esc(event.title)} · ${esc(product)}</strong>
        <span>${esc(vendor)}</span>
      </div>
      ${inspectionCounts(event.inspection)}
      <p>${esc(event.detail)}</p>
    </section>`;
}

function shippingScene(stage, vendor, inspectionEvent) {
    const titles = {
        request: ['Permintaan dicatat', 'Tim pengadaan menyiapkan kebutuhan dan anggaran.'],
        negotiation: ['Penawaran dipertukarkan', 'Pembeli dan vendor mencocokkan harga, margin, dan syarat pembayaran.'],
        packing: ['Pesanan disiapkan', 'Simulasi: gudang vendor mengemas barang untuk pengiriman.'],
        shipping: ['Barang dalam perjalanan', 'Simulasi: truk berangkat dari gudang vendor menuju titik penerimaan.'],
        delivered: ['Barang tiba', 'Simulasi: barang masuk ke area penerimaan untuk diperiksa.'],
        blocked: ['Pesanan ditahan', 'Belum ada kesepakatan yang layak; pengiriman tidak dimulai.'],
    };
    if (!Object.hasOwn(titles, stage)) stage = 'request';
    const [title, detail] = inspectionEvent ? [inspectionEvent.title, inspectionEvent.detail] : titles[stage];
    const activities = ['request', 'negotiation', 'packing', 'shipping', 'delivered'];
    const names = ['Permintaan', 'Negosiasi', 'Pengemasan', 'Pengiriman', 'Penerimaan'];
    const index = stage === 'blocked' ? 1 : activities.indexOf(stage);
    const steps = names.map((name, i) => `<li class="${i < index ? 'done' : i === index ? 'current' : ''}"${i === index ? ' aria-current="step"' : ''}><span>${i < index ? '✓' : i + 1}</span>${name}</li>`).join('');
    const parcel = (x, y) => `<g transform="translate(${x} ${y})"><rect width="32" height="26" rx="3" fill="#f6bf75" stroke="#925c2d" stroke-width="2"/><path d="M15 0v10h8V0M8 18h8" fill="none" stroke="#925c2d" stroke-width="2"/></g>`;
    const spoke = (x) => `<g class="ship-wheel" style="transform-origin:${x}px 251px"><circle cx="${x}" cy="251" r="13" fill="#172743"/><circle cx="${x}" cy="251" r="7" fill="#c8d8ea"/><path d="M${x} 244v14m-7-7h14" stroke="#617895" stroke-width="2"/></g>`;
    const truck = ['packing','shipping','delivered'].includes(stage) ? `<g class="ship-truck"><ellipse cx="335" cy="266" rx="100" ry="5" fill="#15223a" opacity=".2"/><path d="M249 239h178v10H249z" fill="#243650"/><rect x="244" y="175" width="127" height="66" rx="7" fill="#fff" stroke="#b2c8e3" stroke-width="2"/><path d="M372 202h33l22 23v17h-55z" fill="#156ee2"/><path d="M382 208h20l13 15h-33z" fill="#d5efff"/><path d="M255 220h108v14H255z" fill="#d9eaff"/><text x="256" y="211" class="ship-truck-text">BIZ LOGISTIK</text><path d="M417 232h10v7h-10z" fill="#ffd77b"/>${spoke(274)}${spoke(395)}</g>` : '';
    const parcels = stage === 'packing' ? `<g class="ship-parcels">${parcel(148,209)}${parcel(181,218)}${parcel(166,182)}</g>` : stage === 'delivered' ? `<g class="ship-parcels">${parcel(802,217)}${parcel(835,217)}${parcel(819,191)}</g>` : '';
    const badge = stage === 'request' ? 'PERMINTAAN' : stage === 'negotiation' ? 'TAWARAN ⇄ BALASAN' : stage === 'blocked' ? 'DITAHAN' : '';
    return `<section class="ship-scene ship-${stage}" aria-label="${esc(title)}">
      <svg class="ship-art" viewBox="0 0 1000 315" role="img" aria-label="Ilustrasi gudang vendor dan titik penerimaan">
        <rect width="1000" height="315" fill="#eaf4ff"/>
        <circle cx="701" cy="70" r="30" fill="#ffdc92"/>
        <path d="M66 79h109c-5-12-16-17-28-14-3-14-24-23-36-6-14-5-40 2-45 20zm470-32h108c-4-9-14-16-27-13-7-14-26-14-36-2-15-4-39 4-45 15z" fill="#fff" opacity=".84"/>
        <path d="M0 185Q115 116 260 176T522 159Q647 100 792 179T1000 157v96H0z" fill="#d5e7f6"/>
        <path d="M0 245h1000v70H0z" fill="#a8d5c2"/>
        <path d="M0 250h1000v46H0z" fill="#4c627c"/><path class="ship-road-line" d="M0 273h1000" fill="none" stroke="#fff" stroke-width="3" stroke-dasharray="23 15" opacity=".78"/>
        <path d="M77 165l71-50 87 50z" fill="#268386"/><path d="M88 165h136v85H88z" fill="#fbfdff" stroke="#8fa8bc" stroke-width="2"/>
        <path d="M109 195h62v55h-62z" fill="#55738b"/><path d="M113 201h54m-54 9h54m-54 9h54m-54 9h54" stroke="#97b1c6" stroke-width="2"/>
        <rect x="183" y="195" width="29" height="29" rx="3" fill="#cae9f8"/><path d="M197 195v29m-14-14h29" stroke="#729bb4" stroke-width="2"/>
        <text x="155" y="182" class="ship-svg-label">GUDANG VENDOR</text>
        <path d="M770 169h159v81H770z" fill="#fbfdff" stroke="#8fa8bc" stroke-width="2"/><path d="M759 169h181l-15-27H775z" fill="#305487"/>
        <path d="M792 199h39v51h-39z" fill="#52728f"/><path d="M845 198h61v28h-61z" fill="#b6dcef"/><path d="M875 198v28m-30-14h61" stroke="#779fb9" stroke-width="2"/>
        <text x="850" y="186" class="ship-svg-label">PENERIMAAN</text>
        <path d="M35 246v-27m6 27v-21m921 21v-27m9 27v-21" stroke="#448b69" stroke-width="3"/><path d="M21 216l14-35 15 35zm925 0 16-39 16 39z" fill="#5da984"/>
        ${truck}${parcels}
        ${badge ? `<g class="ship-notice"><rect x="374" y="145" width="252" height="46" rx="23" fill="${stage === 'blocked' ? '#fff0ed' : '#fff'}" stroke="${stage === 'blocked' ? '#d7907e' : '#a9c8ea'}" stroke-width="2"/><text x="500" y="174" class="ship-svg-label">${badge}</text></g>` : ''}
      </svg>
      <div class="ship-caption"><strong>${esc(title)} · ${esc(vendor)}</strong><span>${esc(detail)}</span></div>
      ${inspectionEvent ? inspectionCounts(inspectionEvent.inspection) : ''}
      <ol class="ship-steps" aria-label="Tahapan pengadaan">${steps}</ol>
    </section>`;
}

function negotiationScene({company,vendor,event,round,vendorPosition,vendorTotal,blocked}) {
    const buyer=event?.speaker==='buyer', active=event?.speaker==='buyer'||event?.speaker==='vendor';
    const actor=buyer?company:vendor, label={opening:'Penawaran awal',counter:'Tawar balik',accept:'Setuju',reject:'Tolak'};
    const title=!event?'Persiapan':round===0?'Pembukaan':`Putaran ${round}`;
    const person=(x,flip,skin,jacket,hair,speaking)=>`<g transform="translate(${x} 0) scale(${flip} 1)">
      <path d="M-29 182v-25q0-15 15-15h26q13 0 13 14v26" fill="#b3c7df" stroke="#849dbd" stroke-width="3"/>
      <path d="M-21 182v-24q0-22 19-25h15q20 5 20 24v25" fill="${jacket}"/>
      <path d="M4 131l11 28 9-26" fill="#f4f7fc"/><path d="M13 142l3 13-3 18-5-14z" fill="#d99e4b"/>
      <path d="M2 132v-13h15v14q-7 7-15-1" fill="${skin}"/>
      <path d="M-5 100q-2-17 14-20q20-2 20 17l4 11-6 3q-2 15-16 15q-13-4-16-26" fill="${skin}"/>
      <path d="M-7 103q-9-26 12-29q19-7 28 11l-5 7q-6-3-11-9q-9 5-16 6l-2 15z" fill="${hair}"/>
      <circle cx="22" cy="100" r="1.8" fill="#162943"/><path d="M23 114h4" stroke="#6f463c" stroke-width="1.8" stroke-linecap="round"/>
      <g class="${speaking?'meeting-moving-hand':''}"><path d="M22 157l18 13 22-12" stroke="${jacket}" stroke-width="12" fill="none" stroke-linecap="round"/><path d="M61 158l10-6" stroke="${skin}" stroke-width="8" stroke-linecap="round"/></g>
      ${speaking?'<path class="meeting-voice" d="M39 103l9-3m-8 10h11m-12 6 9 4" stroke="#2874d6" stroke-width="2.5" stroke-linecap="round"/>':''}
      </g>`;
    return `<section class="meeting" aria-label="Simulasi negosiasi ${esc(company)} dengan ${esc(vendor)}">
      <div class="meeting-heading"><div><small>MEJA NEGOSIASI · VENDOR ${esc(vendorPosition)}/${esc(vendorTotal)}</small><strong>${esc(company)} <span aria-hidden="true">↔</span> ${esc(vendor)}</strong></div><span class="meeting-chip">${esc(title)}</span></div>
      <div class="meeting-room"><svg viewBox="0 0 620 205" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <rect width="620" height="205" fill="#e9f2ff"/><path d="M0 153h620v52H0z" fill="#d4e3f4"/>
      <rect x="349" y="24" width="207" height="98" rx="7" fill="#c4d5ec"/><rect x="357" y="32" width="191" height="82" rx="2" fill="#e6f6ff"/>
      <path d="M359 114V91h20v23m8 0V78h21v36m10 0V95h25v19m6 0V70h26v44m7 0V89h17v25m12 0V80h28v34" fill="#bed6f0"/>
      <path d="M452 32v82m-95-44h191" stroke="#c4d5ec" stroke-width="3"/>
      <rect x="65" y="28" width="112" height="62" rx="5" fill="#c4d5ec"/><rect x="71" y="34" width="100" height="50" rx="3" fill="#f8fbff"/>
      <path d="M84 72l19-15 15 6 30-20" stroke="#2a7bc8" stroke-width="3" fill="none"/><circle cx="148" cy="43" r="3" fill="#2a7bc8"/>
      <path d="M52 143q-13-18 0-26l5 18q9-24 21-18q-4 15-14 23" fill="#4d9c8a"/><path d="M49 141h24l-4 16H53z" fill="#a37464"/>
      ${person(173,1,'#b4765a','#224778','#26364e',active&&buyer)}
      ${person(447,-1,'#d59b78','#287869','#3f302d',active&&!buyer)}
      <path d="M216 165h188l21 14H195z" fill="#c59569"/><path d="M195 179h230v9H195z" fill="#9b6a49"/>
      <path d="M208 188h8v17h-8zm196 0h8v17h-8z" fill="#8e5f43"/>
      <path d="M277 171l9-8h42l8 8z" fill="#f8fbff" stroke="#abc0dd"/><path d="M289 166h27m-30 3h27" stroke="#8aa7c9"/>
      </svg></div>
      <div class="meeting-parties"><span class="${active&&buyer?'meeting-speaking':''}"><small>Pembeli</small>${esc(company)}</span><span class="${active&&!buyer?'meeting-speaking':''}"><small>Vendor</small>${esc(vendor)}</span></div>
      ${event?`<div class="meeting-message ${buyer?'meeting-from-buyer':'meeting-from-vendor'}" role="status"><small>${esc(actor)} · ${esc(label[event.action]??event.action)}</small><strong>${esc(rupiah(event.amount))} <span>per unit</span></strong><p>${esc(event.reason)}</p></div>`:`<div class="meeting-message meeting-intro" role="status"><strong>${blocked?'Tidak lanjut ke tawar-menawar':'Negosiasi akan dimulai'}</strong><p>${blocked?'Syarat awal belum terpenuhi.':`Tim ${esc(company)} bertemu dengan ${esc(vendor)} untuk membahas penawaran pengadaan.`}</p></div>`}
      </section>`;
}

