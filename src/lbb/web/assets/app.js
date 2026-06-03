
/* ===== product visuals (placeholder; real image from Airtable) ===== */
const DEFS='<defs><linearGradient id="g1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f3d98a"/><stop offset=".5" stop-color="#c79a3f"/><stop offset="1" stop-color="#9c7320"/></linearGradient><linearGradient id="s1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f4f6f8"/><stop offset=".5" stop-color="#c3c9d2"/><stop offset="1" stop-color="#9aa1ab"/></linearGradient></defs>';
function productSVG(type,color){
  const f = color==='Silver' ? 'url(#s1)' : 'url(#g1)';
  let shape='';
  if(type==='Necklace'||type==='Pendant'){
    shape='<path d="M100 122 C40 86 38 44 64 36 C82 30 98 44 100 56 C102 44 118 30 136 36 C162 44 160 86 100 122 Z" fill="none" stroke="'+f+'" stroke-width="13" stroke-linejoin="round" stroke-linecap="round"/><circle cx="148" cy="62" r="20" fill="'+f+'"/>';
  } else if(type==='Bracelet'){
    shape='<ellipse cx="100" cy="80" rx="64" ry="40" fill="none" stroke="'+f+'" stroke-width="11"/><rect x="74" y="63" width="52" height="34" rx="8" fill="'+f+'"/>';
  } else if(type==='Keychain'){
    shape='<circle cx="66" cy="78" r="26" fill="none" stroke="'+f+'" stroke-width="11"/><rect x="88" y="72" width="74" height="13" rx="6" fill="'+f+'"/><rect x="150" y="85" width="9" height="15" rx="2" fill="'+f+'"/><rect x="134" y="85" width="9" height="11" rx="2" fill="'+f+'"/>';
  } else if(type==='Flask'){
    shape='<rect x="88" y="30" width="24" height="15" rx="3" fill="'+f+'"/><path d="M68 47 h64 a12 12 0 0 1 12 12 v40 a18 18 0 0 1 -18 18 h-52 a18 18 0 0 1 -18 -18 v-40 a12 12 0 0 1 12 -12 z" fill="'+f+'"/>';
  } else { shape='<rect x="60" y="45" width="80" height="60" rx="12" fill="'+f+'"/>'; }
  return '<svg viewBox="0 0 200 150" xmlns="http://www.w3.org/2000/svg">'+DEFS+shape+'</svg>';
}
const REAL_DRIVE='https://drive.google.com/file/d/17UCEpbZiYHLuJNULILJKsrleaEgulMev/view?usp=drive_link';

function prod(name,type,color,qty,sidesEngraved,instr){
  const silver=color==='Silver';
  const sides=sidesEngraved.map((eng,i)=>({side:i===0?'Front':'Back',file:'#',engraved:eng}));
  return { name,type,color,qty, img:productSVG(type,color), imgClass:silver?'silver':'', colorClass:silver?'badge silver':'badge', instructions:instr||'#', sides };
}

/* ===== ORDERS (sample; from Airtable in production) ===== */
const TYPE_ORDER=['Bracelet','Necklace','Keychain','Flask'];
const ORDERS=[
  { id:'306-2309613-0964321', date:'Jan 3, 2026', dateISO:'2026-01-03', amazon:'https://sellercentral-europe.amazon.com/orders-v3/order/306-2309613-0964321',
    recipient:'Sabrina Wollweber · 52525 Heinsberg, DE', label:{carrier:'DHL Kleinpaket · 1 kg', file:'00340434514536106988.pdf'},
    shipped:false, hold:false, giftBox:true,
    products:[ prod('Heart necklace','Necklace','Gold',1,[false,false],REAL_DRIVE), prod('ID bracelet','Bracelet','Silver',1,[false],'#') ] },

  { id:'304-9988776-1122334', date:'Jan 1, 2026', dateISO:'2026-01-01', amazon:'#',
    recipient:'Nina Hofmann · 70173 Stuttgart, DE', label:{carrier:'DHL Kleinpaket · 1 kg', file:'00340434511122334776.pdf'},
    shipped:false, hold:true, giftBox:false,
    products:[ prod('Bangle','Bracelet','Gold',1,[false],'#') ] },

  { id:'305-4490912-2237815', date:'Jan 2, 2026', dateISO:'2026-01-02', amazon:'#',
    recipient:'Lea Brandt · 20095 Hamburg, DE', label:{carrier:'DHL Kleinpaket · 1 kg', file:'00340434512237815998.pdf'},
    shipped:false, hold:false, giftBox:true,
    products:[ prod('Cuff bracelet','Bracelet','Silver',1,[true,false],'#') ] },

  { id:'306-7781204-1135870', date:'Jan 3, 2026', dateISO:'2026-01-03', amazon:'#',
    recipient:'Markus Pfeiffer · 80331 München, DE', label:{carrier:'DHL Kleinpaket · 1 kg', file:'00340434511135870421.pdf'},
    shipped:false, hold:false, giftBox:false,
    products:[ prod('Name necklace','Necklace','Gold',1,[true],'#') ] },

  { id:'306-5512309-7781234', date:'Jan 2, 2026', dateISO:'2026-01-02', amazon:'#',
    recipient:'Jonas Weber · 04109 Leipzig, DE', label:{carrier:'DHL Kleinpaket · 1 kg', file:'00340434517781234605.pdf'},
    shipped:false, hold:false, giftBox:true,
    products:[ prod('Photo keychain','Keychain','Silver',1,[false],'#') ] },

  { id:'307-1199234-4456120', date:'Jan 3, 2026', dateISO:'2026-01-03', amazon:'#',
    recipient:'Sophie Lang · 60311 Frankfurt, DE', label:{carrier:'DHL Kleinpaket · 1 kg', file:'00340434514456120877.pdf'},
    shipped:false, hold:false, giftBox:false,
    products:[ prod('Hip flask','Flask','Gold',1,[false,false],'#') ] },

  { id:'306-1029384-5566778', date:'Jan 2, 2026', dateISO:'2026-01-02', amazon:'#',
    recipient:'Tobias Krüger · 50667 Köln, DE', label:{carrier:'DHL Kleinpaket · 1 kg', file:'00340434515566778310.pdf'},
    shipped:true, hold:false, giftBox:true,
    products:[ prod('Hip flask','Flask','Silver',1,[true],'#'), prod('Hip flask','Flask','Silver',1,[true],'#') ] }
];

/* ===== state ===== */
let curIdx=0, active=0, busy=false, filter='all';

/* ===== helpers ===== */
const GIFT_SVG='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 12v10H4V12"/><rect x="2" y="7" width="20" height="5"/><path d="M12 22V7"/><path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"/><path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"/></svg>';
function tasksOf(o){const t=[];o.products.forEach((p,pi)=>p.sides.forEach((s,si)=>t.push({pi,si,s,p})));return t;}
function doneOf(o){return tasksOf(o).filter(t=>t.s.engraved).length;}
function totOf(o){return tasksOf(o).length;}
function allEng(o){return doneOf(o)===totOf(o);}
function statusOf(o){
  if(o.shipped) return {key:'shipped',label:'Shipped'};
  if(o.hold) return {key:'hold',label:'On hold'};
  if(allEng(o)) return {key:'engraved',label:'Engraved'};
  if(doneOf(o)>0) return {key:'engraving',label:'Engraving'};
  return {key:'received',label:'Received'};
}
function typeRank(o){ const k=TYPE_ORDER.indexOf(o.products[0].type); return k>-1?k:99; }
function bucketName(o){ return TYPE_ORDER[typeRank(o)]||'Other'; }
function plural(t){ return ({Bracelet:'Bracelets',Necklace:'Necklaces',Keychain:'Keychains',Flask:'Flasks'})[t]||t+'s'; }
function typeSummary(o){ const n=o.products.length; return o.products[0].type+(n>1?' <small>+'+(n-1)+'</small>':''); }
// queue: by product type, then date (oldest first)
function queueSort(a,b){ return typeRank(ORDERS[a])-typeRank(ORDERS[b]) || ORDERS[a].dateISO.localeCompare(ORDERS[b].dateISO); }
function openQueue(){ return ORDERS.map((o,i)=>i).filter(i=>!ORDERS[i].shipped && !ORDERS[i].hold).sort(queueSort); }

/* ===== views ===== */
function showView(v){
  document.getElementById('view-dashboard').hidden=v!=='dashboard';
  document.getElementById('view-order').hidden=v!=='order';
  document.getElementById('actionbar').style.display=v==='order'?'flex':'none';
  window.scrollTo(0,0);
}
function goDashboard(){ showView('dashboard'); renderDashboard(); }
function setFilter(f){ filter=f; document.querySelectorAll('#filterChips .chip').forEach(c=>c.classList.toggle('active',c.dataset.f===f)); renderDashboard(); }

function renderDashboard(){
  const q=(document.getElementById('searchInput').value||'').toLowerCase().replace(/\s/g,'');
  let rows=ORDERS.map((o,i)=>({o,i})).sort((a,b)=>queueSort(a.i,b.i));
  rows=rows.filter(({o})=>{
    const st=statusOf(o).key;
    if(filter==='open' && st==='shipped') return false;
    if(filter==='shipped' && st!=='shipped') return false;
    if(q && !o.id.toLowerCase().replace(/\s/g,'').includes(q)) return false;
    return true;
  });
  document.getElementById('dashSub').textContent=rows.length+' of '+ORDERS.length+' orders';
  const head='<div class="lrow head"><div>Order number</div><div>Product</div><div>Date</div><div>Status</div><div>Engraving</div><div></div></div>';
  let html=head, lastBucket=null;
  if(rows.length){
    rows.forEach(({o,i})=>{
      const b=bucketName(o);
      if(b!==lastBucket){ const cnt=rows.filter(r=>bucketName(r.o)===b).length; html+='<div class="lgroup">'+plural(b)+' <span class="gc">'+cnt+'</span></div>'; lastBucket=b; }
      const st=statusOf(o);
      html+='<button class="lrow" onclick="openOrder('+i+')">'
        +'<div class="ono">'+o.id+'</div>'
        +'<div class="otype">'+typeSummary(o)+(o.giftBox?'<span class="gift" title="With gift box">'+GIFT_SVG+'</span>':'')+'</div>'
        +'<div class="odate">'+o.date+'</div>'
        +'<div><span class="stat '+st.key+'"><span class="d"></span>'+st.label+'</span></div>'
        +'<div class="oprog">'+doneOf(o)+'/'+totOf(o)+'</div>'
        +'<svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>'
        +'</button>';
    });
  } else html+='<div class="empty">No orders match your search.</div>';
  document.getElementById('orderList').innerHTML=html;
}

/* ===== order view ===== */
function firstPendingProduct(o){ const np=tasksOf(o).find(t=>!t.s.engraved); return np?np.pi:0; }
function openOrder(i){ curIdx=i; active=firstPendingProduct(ORDERS[i]); showView('order'); renderOrder(); }
function startEngraving(){ const q=openQueue(); if(q.length){ openOrder(q[0]); toast('Starting with '+ORDERS[q[0]].id); } else toast('No open orders to engrave','gold'); }

function renderOrder(){
  const O=ORDERS[curIdx];
  document.getElementById('ordNo').textContent='#'+O.id;
  document.getElementById('recSub').textContent=O.date;
  const am=document.getElementById('amazonLink'); am.href=O.amazon; am.style.opacity=(O.amazon&&O.amazon!=='#')?'1':'.5';
  document.getElementById('labelCarrier').textContent=O.label.carrier;
  document.getElementById('labelFile').textContent=O.label.file;
  document.getElementById('giftPill').innerHTML = O.giftBox ? '<span class="pill gift"><span class="gi">'+GIFT_SVG+'</span>With gift box</span>' : '';

  document.getElementById('pCount').textContent=O.products.length;
  document.getElementById('pCountLab').innerHTML=(O.products.length===1?'product':'products')+'<small>in this order</small>';
  document.getElementById('ptabs').innerHTML=O.products.map((p,i)=>{
    const done=p.sides.every(s=>s.engraved), eng=p.sides.filter(s=>s.engraved).length;
    return '<button class="ptab'+(i===active?' active':'')+(done?' complete':'')+'" onclick="setActive('+i+')"><span class="pi">'+(done?'✓':(i+1))+'</span><span class="ptxt"><b>'+p.name+'</b><span>'+eng+'/'+p.sides.length+' engraved</span></span>'+(done?'<svg class="pchk" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>':'')+'</button>';
  }).join('');

  const p=O.products[active];
  document.getElementById('prodCardTitle').textContent=p.name;
  const vis=document.getElementById('productVisual');
  vis.className='product '+(p.imgClass||'');
  vis.innerHTML=p.img+'<div class="sidechips">'+p.sides.map(s=>'<span class="schip'+(s.engraved?' done':'')+'">'+(s.engraved?'<svg class="sd" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"/></svg>':'<svg class="sd" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/></svg>')+s.side+'</span>').join('')+'</div>';

  const instr=document.getElementById('instrLink');
  if(p.instructions && p.instructions!=='#'){ instr.href=p.instructions; instr.onclick=null; }
  else { instr.href='#'; instr.onclick=function(e){e.preventDefault();toast('Opening engraving instructions','gold');}; }

  document.getElementById('orderKv').innerHTML=
    '<div class="k">Order no.</div><div class="v mono">'+O.id+'</div>'
   +'<div class="k">Order date</div><div class="v">'+O.date+'</div>'
   +'<div class="k">Link to Order</div><div class="v">'+(O.amazon&&O.amazon!=='#'?'<a href="'+O.amazon+'" target="_blank" rel="noopener">Open on Amazon ↗</a>':'<span style="color:var(--ink-faint)">—</span>')+'</div>'
   +'<div class="k">Gift box</div><div class="v">'+(O.giftBox?'<span class="badge gift">'+GIFT_SVG+' With gift box</span>':'<span style="color:var(--ink-faint)">No</span>')+'</div>'
   +'<div class="k">Recipient</div><div class="v">'+O.recipient+'</div>';

  document.getElementById('prodSubh').innerHTML='Product '+(active+1)+' of '+O.products.length+' <span class="c">'+p.type+'</span>';
  document.getElementById('prodKv').innerHTML=
    '<div class="k">Product type</div><div class="v"><span class="badge">'+p.type+'</span></div>'
   +'<div class="k">Color</div><div class="v"><span class="'+(p.colorClass)+'">'+p.color+'</span></div>'
   +'<div class="k">Quantity</div><div class="v">'+p.qty+'</div>'
   +'<div class="k">Sides</div><div class="v">'+(p.sides.length>1?'Front &amp; Back':'Front only')+'</div>';

  document.getElementById('sideC').textContent=p.sides.filter(s=>s.engraved).length+' / '+p.sides.length+' done';
  document.getElementById('sides').innerHTML=p.sides.map((s,si)=>{
    const btn=s.engraved
      ? '<button class="sbtn ok" onclick="engrave('+active+','+si+')" title="Re-open in LightBurn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>Engraved</button>'
      : '<button class="sbtn go" onclick="engrave('+active+','+si+')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/></svg>Engrave '+s.side.toLowerCase()+'</button>';
    return '<div class="side'+(s.engraved?' done':'')+'"><span class="sicon">'+s.side.slice(0,1)+'</span><div class="smeta"><div class="sn">'+s.side+'</div><div class="sf">LightBurn job · <a href="#" onclick="toast(\'Opening graphic file\',\'gold\');return false;">view file ↗</a></div></div>'+btn+'</div>';
  }).join('');

  const stepEng=document.getElementById('stepEng'), stepShip=document.getElementById('stepShip');
  stepEng.classList.remove('done','active'); stepShip.classList.remove('done','active');
  document.getElementById('bar1').style.width=(doneOf(O)/Math.max(totOf(O),1)*100)+'%';
  if(O.shipped){ stepEng.classList.add('done'); stepShip.classList.add('done'); document.getElementById('bar2').style.width='100%'; document.getElementById('engSub').textContent='Done'; document.getElementById('shipSub').textContent='Done'; }
  else if(allEng(O)){ stepEng.classList.add('done'); stepShip.classList.add('active'); document.getElementById('bar2').style.width='0%'; document.getElementById('engSub').textContent='Done'; document.getElementById('shipSub').textContent='Pending'; }
  else { stepEng.classList.add('active'); document.getElementById('bar2').style.width='0%'; document.getElementById('engSub').textContent=doneOf(O)+'/'+totOf(O); document.getElementById('shipSub').textContent='Pending'; }

  const pill=document.getElementById('livePill'), pillTxt=document.getElementById('livePillText'), sel=document.getElementById('statusSel');
  pill.classList.remove('hold'); const st=statusOf(O);
  if(st.key==='hold'){ pill.classList.add('hold'); pillTxt.textContent='On hold'; }
  else if(st.key==='shipped'){ pillTxt.textContent='Engraved & shipped'; }
  else if(st.key==='engraved'){ pillTxt.textContent='Engraved · ready to ship'; }
  else if(st.key==='engraving'){ pillTxt.textContent='Engraving in progress'; }
  else { pillTxt.textContent='In production'; }
  sel.value=st.key;

  const np=tasksOf(O).find(t=>!t.s.engraved);
  const engBtn=document.getElementById('engraveBtn'), engLbl=document.getElementById('engraveBtnLbl'), shipBtn=document.getElementById('shipBtn');
  document.getElementById('abProg').textContent=doneOf(O)+'/'+totOf(O)+' engraved';
  document.getElementById('abTrack').style.width=(doneOf(O)/Math.max(totOf(O),1)*100)+'%';
  if(O.shipped){ document.getElementById('abLead').textContent='Done'; document.getElementById('abState').innerHTML='Order complete ✓ — sides still re-engravable below'; engLbl.textContent='All engraved'; engBtn.disabled=true; shipBtn.disabled=true; }
  else if(np){ document.getElementById('abLead').textContent='Next:'; document.getElementById('abState').innerHTML='Product '+(np.pi+1)+' · <b>'+np.s.side+'</b>'; engLbl.textContent='Engrave '+np.s.side.toLowerCase()+' · LightBurn'; engBtn.disabled=false; shipBtn.disabled=true; }
  else { document.getElementById('abLead').textContent='Next:'; document.getElementById('abState').textContent='All engraved — ready to ship'; engLbl.textContent='All sides engraved'; engBtn.disabled=true; shipBtn.disabled=false; }
}

/* ===== actions ===== */
function setActive(i){ if(busy) return; active=i; renderOrder(); }
function engrave(pi,si){
  if(busy) return;
  const O=ORDERS[curIdx], side=O.products[pi].sides[si];
  if(active!==pi){ active=pi; }
  const reEngrave=side.engraved;
  busy=true; renderOrder();
  const sideEls=document.querySelectorAll('#sides .sbtn');
  if(sideEls[si]) sideEls[si].classList.add('is-loading');
  document.getElementById('livePillText').textContent='Opening LightBurn…';
  toast((reEngrave?'Re-opening':'Launching')+' LightBurn · '+O.products[pi].name+' '+side.side,'pdf');
  setTimeout(()=>{
    side.engraved=true; busy=false;
    if(!reEngrave){ const np=tasksOf(O).find(t=>!t.s.engraved); if(np) active=np.pi; }
    renderOrder();
    toast(reEngrave?(side.side+' re-sent to LightBurn'):(side.side+' engraved'+(allEng(O)?' · all done':''))); setLastUpd();
  },1500);
}
function engraveNext(){ const O=ORDERS[curIdx]; const np=tasksOf(O).find(t=>!t.s.engraved); if(np) engrave(np.pi,np.si); }

function askShip(){
  const O=ORDERS[curIdx];
  if(!allEng(O)){ toast('Engrave all sides first','gold'); return; }
  document.getElementById('modalText').innerHTML='This marks <b>#'+O.id+'</b> as engraved &amp; shipped and opens the next order in the queue.';
  document.getElementById('modalGift').hidden = !O.giftBox;
  document.getElementById('modalBg').classList.add('show');
}
function closeModal(){ document.getElementById('modalBg').classList.remove('show'); }
function confirmShip(){
  const O=ORDERS[curIdx]; O.shipped=true; O.hold=false; closeModal(); toast('“'+O.id+'” shipped');
  const q=openQueue();
  if(q.length){ openOrder(q[0]); } else { goDashboard(); toast('All open orders done 🎉'); }
}

function onStatusSelect(v){
  if(busy){ renderOrder(); return; }
  const O=ORDERS[curIdx];
  if(v==='shipped'){ if(allEng(O)) askShip(); else toast('Engrave all sides first','gold'); renderOrder(); return; }
  if(v==='engraved'){ if(!allEng(O)) toast('Not all sides engraved yet','gold'); O.hold=false; renderOrder(); return; }
  if(v==='hold'){ O.hold=true; renderOrder(); toast('Order put on hold','gold'); return; }
  O.hold=false; renderOrder();
}

function sendComment(){ const c=document.getElementById('comment'); if(!c.value.trim()){ toast('Write a comment first','gold'); return; } toast('Comment sent to A. Fink'); c.value=''; setLastUpd(); }
function copyOrder(){ navigator.clipboard?.writeText(ORDERS[curIdx].id); toast('Order number copied'); }
function setLastUpd(){ const e=document.getElementById('lastUpd'); if(e) e.textContent='just now'; }
function toast(msg,kind){
  const wrap=document.getElementById('toastWrap'); const el=document.createElement('div');
  el.className='toast'+(kind==='gold'||kind==='pdf'?' gold':'');
  el.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>'+msg;
  wrap.appendChild(el); requestAnimationFrame(()=>el.classList.add('show'));
  setTimeout(()=>{el.classList.remove('show');setTimeout(()=>el.remove(),300)},2600);
}

renderDashboard(); showView('dashboard');
