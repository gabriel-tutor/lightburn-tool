
/* ===== product visuals ===== */
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

/* ===== live data state ===== */
let ORDERS = [];     // dashboard cards from the backend
let CURRENT = null;  // full order detail for the open order

/* ===== ui state ===== */
let active=0, busy=false;

/* ===== helpers ===== */
const GIFT_SVG='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 12v10H4V12"/><rect x="2" y="7" width="20" height="5"/><path d="M12 22V7"/><path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"/><path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"/></svg>';

// Works on a full order detail object (CURRENT). sides use .name and .engraved.
function tasksOf(o){const t=[];o.products.forEach((p,pi)=>p.sides.forEach((s,si)=>t.push({pi,si,s,p})));return t;}
function doneOf(o){return tasksOf(o).filter(t=>t.s.engraved).length;}
function totOf(o){return tasksOf(o).length;}
function allEng(o){return totOf(o)>0 && doneOf(o)===totOf(o);}

// statusOf works on CURRENT (detail object) — reads .status string from backend.
function statusOf(o){
  const key = o.status || 'not_done_yet';
  const labels = {not_done_yet:'Open', graviert_verschickt:'Engraved & shipped', revision:'Needs review'};
  return {key, label: labels[key] || key};
}

/* ===== dashboard loader ===== */
async function loadDashboard(){
  const filter = document.querySelector('#filterChips .chip.active')?.dataset.f || 'all';
  const q = document.getElementById('searchInput').value || '';
  const res = await API.listOrders(filter, q);
  ORDERS = (res && res.orders) || [];
  renderBanner(res && res.error);
  renderDashboard();
}
function renderBanner(error){
  let bar = document.getElementById('apiBanner');
  if(!bar){
    bar = document.createElement('div'); bar.id='apiBanner'; bar.className='api-banner';
    document.body.prepend(bar);
  }
  if(error){ bar.textContent = '⚠ '+error+' — check the API key in ~/.flanacom-tool/config.json'; bar.hidden=false; }
  else { bar.hidden = true; }
}

/* ===== views ===== */
function showView(v){
  document.getElementById('view-dashboard').hidden=v!=='dashboard';
  document.getElementById('view-order').hidden=v!=='order';
  document.getElementById('actionbar').style.display=v==='order'?'flex':'none';
  window.scrollTo(0,0);
}
function goDashboard(){ showView('dashboard'); loadDashboard(); }
function setFilter(f){ document.querySelectorAll('#filterChips .chip').forEach(c=>c.classList.toggle('active',c.dataset.f===f)); loadDashboard(); }

function renderDashboard(){
  const head='<div class="lrow head"><div>Order number</div><div>Product</div><div>Date</div><div>Status</div><div>Engraving</div><div></div></div>';
  let html=head, lastBucket=null;
  document.getElementById('dashSub').textContent=ORDERS.length+' order'+(ORDERS.length!==1?'s':'');
  if(ORDERS.length){
    ORDERS.forEach(card=>{
      const b = card.bucket || 'Other';
      if(b!==lastBucket){
        const cnt=ORDERS.filter(c=>c.bucket===b).length;
        html+='<div class="lgroup">'+b+' <span class="gc">'+cnt+'</span></div>';
        lastBucket=b;
      }
      const stKey = card.status || 'not_done_yet';
      const stLabels = {not_done_yet:'Open',graviert_verschickt:'Engraved & shipped',revision:'Needs review'};
      const stLabel = stLabels[stKey] || stKey;
      html+='<button class="lrow" onclick="openOrder(\''+card.order_number+'\')">'
        +'<div class="ono">'+card.order_number+'</div>'
        +'<div class="otype">'+card.product_summary+(card.gift_box?'<span class="gift" title="With gift box">'+GIFT_SVG+'</span>':'')+'</div>'
        +'<div class="odate">'+(card.placed_label||'')+'</div>'
        +'<div><span class="stat '+stKey+'"><span class="d"></span>'+stLabel+'</span></div>'
        +'<div class="oprog">'+(card.progress?card.progress.done+'/'+card.progress.total:'')+'</div>'
        +'<svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>'
        +'</button>';
    });
  } else html+='<div class="empty">No orders match your search.</div>';
  document.getElementById('orderList').innerHTML=html;
}

/* ===== order view ===== */
function firstPendingProduct(o){ const np=tasksOf(o).find(t=>!t.s.engraved); return np?np.pi:0; }

async function openOrder(orderNumber){
  CURRENT = await API.getOrder(orderNumber);
  if(!CURRENT){ toast('Order not found','gold'); return; }
  active = firstPendingProduct(CURRENT);
  showView('order'); renderOrder();
}

async function loadProductPhoto(orderNumber, idx){
  let res;
  try { res = await API.productImage(orderNumber, idx); }
  catch(e){ return; }                    // keep the icon on any failure
  // ignore if the operator moved to another product/order while loading
  if(!CURRENT || CURRENT.order_number!==orderNumber || active!==idx) return;
  if(res && res.ok && res.data_uri){
    const img=document.getElementById('prodPhoto');
    if(img){
      img.onload=function(){ img.hidden=false; const ic=document.querySelector('#productVisual .prod-icon'); if(ic) ic.style.display='none'; };
      img.src=res.data_uri;
    }
  }
}

async function startEngraving(){
  const first = ORDERS.find(c => c.status !== 'graviert_verschickt');
  if(first){ await openOrder(first.order_number); toast('Starting with '+first.order_number); }
  else toast('No open orders to engrave','gold');
}

function renderOrder(){
  const O = CURRENT;
  if(!O.products || !O.products.length){
    document.getElementById('ordNo').textContent='#'+O.order_number;
    document.getElementById('abLead').textContent='';
    document.getElementById('abState').textContent='Nothing to engrave in this order';
    document.getElementById('engraveBtn').disabled=true;
    document.getElementById('shipBtn').disabled=true;
    return;
  }
  document.getElementById('ordNo').textContent='#'+O.order_number;
  const amLink=document.getElementById('amazonLink');
  const hasAmazon = O.amazon_url && O.amazon_url !== '#' && O.amazon_url !== '';
  amLink.style.opacity = hasAmazon ? '1' : '.5';
  amLink.onclick = hasAmazon ? null : function(e){ e.preventDefault(); API.openAmazon(O.amazon_url); };
  amLink.href = '#';
  if(hasAmazon){ amLink.onclick = function(e){ e.preventDefault(); API.openAmazon(O.amazon_url); }; }

  // Label
  document.getElementById('labelCarrier').textContent = O.has_label ? 'Shipping label' : '—';
  document.getElementById('labelFile').textContent = O.has_label ? (O.label_name || 'label.pdf') : '(no label file)';

  document.getElementById('giftPill').innerHTML = O.gift_box ? '<span class="pill gift"><span class="gi">'+GIFT_SVG+'</span>With gift box</span>' : '';

  document.getElementById('pCount').textContent=O.products.length;
  document.getElementById('pCountLab').innerHTML=(O.products.length===1?'product':'products')+'<small>in this order</small>';
  document.getElementById('ptabs').innerHTML=O.products.map((p,i)=>{
    const done=p.sides.every(s=>s.engraved), eng=p.sides.filter(s=>s.engraved).length;
    return '<button class="ptab'+(i===active?' active':'')+(done?' complete':'')+'" onclick="setActive('+i+')"><span class="pi">'+(done?'✓':(i+1))+'</span><span class="ptxt"><b>'+p.name+'</b><span>'+eng+'/'+p.sides.length+' engraved</span></span>'+(done?'<svg class="pchk" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>':'')+'</button>';
  }).join('');

  const p=O.products[active];
  document.getElementById('prodCardTitle').textContent=p.name;
  const vis=document.getElementById('productVisual');
  const imgClass = p.color==='Silver' ? 'silver' : '';
  vis.className='product '+(imgClass||'');
  const svgHtml = productSVG(p.product_type, p.color);
  const chips='<div class="sidechips">'+p.sides.map(s=>'<span class="schip'+(s.engraved?' done':'')+'">'+(s.engraved?'<svg class="sd" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"/></svg>':'<svg class="sd" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/></svg>')+s.name+'</span>').join('')+'</div>';
  vis.innerHTML='<div class="prod-icon">'+svgHtml+'</div><img class="prod-photo" id="prodPhoto" alt="Product reference" hidden>'+chips;
  if(p.has_image){ loadProductPhoto(O.order_number, active); }

  document.getElementById('orderKv').innerHTML=
    '<div class="k">Order no.</div><div class="v mono">'+O.order_number+'</div>'
   +'<div class="k">Order date</div><div class="v">'+(O.placed_label||'')+'</div>'
   +(O.created_label?'<div class="k">Received</div><div class="v">'+O.created_label+'</div>':'')
   +(O.updated_label?'<div class="k">Last updated</div><div class="v">'+O.updated_label+'</div>':'')
   +'<div class="k">Link to Order</div><div class="v">'+(hasAmazon?'<a href="#" onclick="API.openAmazon(CURRENT.amazon_url);return false;">Open on Amazon ↗</a>':'<span style="color:var(--ink-faint)">—</span>')+'</div>'
   +(O.link_to_graphic?'<div class="k">Graphic</div><div class="v"><a href="#" onclick="API.openAmazon(CURRENT.link_to_graphic);return false;">Open graphic ↗</a></div>':'')
   +'<div class="k">Gift box</div><div class="v">'+(O.gift_box?'<span class="badge gift">'+GIFT_SVG+' With gift box</span>':'<span style="color:var(--ink-faint)">No</span>')+'</div>'
   +'<div class="k">Items</div><div class="v">'+(O.amount||O.products.length)+'</div>';

  const colorClass = p.color==='Silver' ? 'badge silver' : 'badge';
  document.getElementById('prodSubh').innerHTML='Product '+(active+1)+' of '+O.products.length+' <span class="c">'+p.product_type+'</span>';
  document.getElementById('prodKv').innerHTML=
    '<div class="k">Product type</div><div class="v"><span class="badge">'+p.product_type+'</span></div>'
   +'<div class="k">Coin / plate color</div><div class="v"><span class="'+colorClass+'">'+(p.color||'—')+'</span></div>'
   +(p.band_color?'<div class="k">Chain / band color</div><div class="v"><span class="badge">'+p.band_color+'</span></div>':'')
   +(p.multiple_coins||(p.coin_count>1)?'<div class="k">Coins</div><div class="v">'+(p.coin_count||2)+' coins</div>':'')
   +(p.special_length?'<div class="k">Special length</div><div class="v">'+(p.length?p.length:'Yes')+'</div>':'')
   +'<div class="k">Engraving</div><div class="v">'+(p.sides_summary||'')+'</div>';

  document.getElementById('sideC').textContent=p.sides.filter(s=>s.engraved).length+' / '+p.sides.length+' done';
  document.getElementById('sides').innerHTML=p.sides.map((s,si)=>{
    const btn=s.engraved
      ? '<button class="sbtn ok" onclick="engrave('+active+','+si+')" title="Re-open in LightBurn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>Engraved</button>'
      : '<button class="sbtn go" onclick="engrave('+active+','+si+')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/></svg>Engrave '+s.name.toLowerCase()+'</button>';
    return '<div class="side'+(s.engraved?' done':'')+'"><span class="sicon">'+s.name.slice(0,1)+'</span><div class="smeta"><div class="sn">'+s.name+'</div><div class="sf">LightBurn job · design file</div></div>'+btn+'</div>';
  }).join('');

  const stageEng=document.getElementById('stageEng'), stageShip=document.getElementById('stageShip');
  const flowBar=document.getElementById('flowBar'), flowRev=document.getElementById('flowRev'), flowEl=document.getElementById('flow');
  const done=doneOf(O), tot=totOf(O);
  const isShipped=O.status==='graviert_verschickt';
  const isRevision=O.status==='revision';
  const isAllEng=allEng(O);
  stageEng.classList.remove('done','active'); stageShip.classList.remove('done','active');
  flowRev.hidden=!isRevision; flowEl.classList.toggle('revision', isRevision);
  document.getElementById('engSub').textContent = isShipped||isAllEng ? 'Done' : done+'/'+Math.max(tot,0);
  if(isShipped){
    stageEng.classList.add('done'); stageShip.classList.add('done');
    flowBar.style.width='100%'; document.getElementById('shipSub').textContent='Done';
  } else if(isAllEng){
    stageEng.classList.add('done'); stageShip.classList.add('active');
    flowBar.style.width='50%'; document.getElementById('shipSub').textContent='Ready';
  } else {
    stageEng.classList.add('active');
    flowBar.style.width='0%'; document.getElementById('shipSub').textContent='Pending';
  }

  const pill=document.getElementById('livePill'), pillTxt=document.getElementById('livePillText'), sel=document.getElementById('statusSel');
  pill.classList.remove('hold');
  const st=statusOf(O);
  if(st.key==='revision'){ pill.classList.add('hold'); pillTxt.textContent='Needs review'; }
  else if(st.key==='graviert_verschickt'){ pillTxt.textContent='Engraved & shipped'; }
  else if(isAllEng){ pillTxt.textContent='Engraved · ready to ship'; }
  else if(done>0){ pillTxt.textContent='Engraving in progress'; }
  else { pillTxt.textContent='Open · ready to engrave'; }
  sel.value=st.key;
  const instrBox=document.getElementById('instruction');
  if(instrBox){ instrBox.textContent = O.instruction || '—'; }

  const np=tasksOf(O).find(t=>!t.s.engraved);
  const engBtn=document.getElementById('engraveBtn'), engLbl=document.getElementById('engraveBtnLbl'), shipBtn=document.getElementById('shipBtn');
  document.getElementById('abProg').textContent=done+'/'+tot+' engraved';
  document.getElementById('abTrack').style.width=(done/Math.max(tot,1)*100)+'%';
  if(isShipped){ document.getElementById('abLead').textContent='Done'; document.getElementById('abState').innerHTML='Order complete ✓ — sides still re-engravable below'; engLbl.textContent='All engraved'; engBtn.disabled=true; shipBtn.disabled=true; }
  else if(np){ document.getElementById('abLead').textContent='Next:'; document.getElementById('abState').innerHTML='Product '+(np.pi+1)+' · <b>'+np.s.name+'</b>'; engLbl.textContent='Engrave '+np.s.name.toLowerCase()+' · LightBurn'; engBtn.disabled=busy; shipBtn.disabled=true; }
  else if(tot===0){ document.getElementById('abLead').textContent=''; document.getElementById('abState').textContent='Nothing to engrave'; engLbl.textContent='Nothing to engrave'; engBtn.disabled=true; shipBtn.disabled=true; }
  else { document.getElementById('abLead').textContent='Next:'; document.getElementById('abState').textContent='All engraved — ready to ship'; engLbl.textContent='All sides engraved'; engBtn.disabled=true; shipBtn.disabled=false; }

}

/* ===== actions ===== */
function setActive(i){ if(busy) return; active=i; renderOrder(); }

async function engrave(pi, si){
  if(busy) return;
  const p = CURRENT.products[pi], side = p.sides[si];
  if(active!==pi){ active=pi; }
  busy=true; renderOrder();
  document.getElementById('livePillText').textContent='Opening LightBurn…';
  const res = await API.engraveSide(CURRENT.order_number, side.file_key);
  busy=false;
  if(!res || !res.ok){ toast((res && res.error) || 'Engrave failed','gold'); renderOrder(); return; }
  CURRENT = await API.getOrder(CURRENT.order_number);
  if(!CURRENT){ toast('Could not refresh order','gold'); goDashboard(); return; }
  const np = tasksOf(CURRENT).find(t=>!t.s.engraved); if(np) active=np.pi;
  renderOrder();
  toast(side.name+' engraved'+(allEng(CURRENT)?' · all done':''));
}

async function engraveNext(){
  if(!CURRENT) return;
  const np = tasksOf(CURRENT).find(t=>!t.s.engraved);
  if(np) await engrave(np.pi, np.si);
}

function askShip(){
  const O=CURRENT;
  if(!allEng(O)){ toast('Engrave all sides first','gold'); return; }
  document.getElementById('modalText').innerHTML='This marks <b>#'+O.order_number+'</b> as engraved &amp; shipped and opens the next order in the queue.';
  document.getElementById('modalGift').hidden = !O.gift_box;
  document.getElementById('modalBg').classList.add('show');
}
function closeModal(){ document.getElementById('modalBg').classList.remove('show'); }

async function confirmShip(){
  const orderNumber = CURRENT.order_number;
  const res = await API.shipOrder(orderNumber);
  closeModal();
  if(!res || !res.ok){ toast((res && res.error)||'Cannot ship','gold'); return; }
  toast('"'+orderNumber+'" shipped');
  await loadDashboard();
  const first = ORDERS.find(c => c.status !== 'graviert_verschickt');
  if(first){ await openOrder(first.order_number); }
  else { goDashboard(); toast('All open orders done!'); }
}

async function onStatusSelect(v){
  if(busy){ renderOrder(); return; }
  if(v==='graviert_verschickt'){
    if(allEng(CURRENT)) askShip();
    else toast('Engrave all sides first','gold');
    renderOrder(); return;
  }
  const res = await API.setStatus(CURRENT.order_number, v);
  if(!res || !res.ok){ toast((res && res.error)||'Status change failed','gold'); }
  CURRENT = await API.getOrder(CURRENT.order_number);
  if(!CURRENT){ toast('Could not refresh order','gold'); goDashboard(); return; }
  renderOrder();
  if(v==='revision') toast('Flagged for revision','gold');
}

async function flagRevision(){
  if(!CURRENT) return;
  const res = await API.flagRevision(CURRENT.order_number);
  if(!res || !res.ok){ toast((res && res.error)||'Could not flag','gold'); return; }
  CURRENT = await API.getOrder(CURRENT.order_number);
  renderOrder();
  toast('Order flagged for revision','gold');
}

function copyOrder(){ navigator.clipboard?.writeText(CURRENT.order_number); toast('Order number copied'); }
function toast(msg,kind){
  const wrap=document.getElementById('toastWrap'); const el=document.createElement('div');
  el.className='toast'+(kind==='gold'||kind==='pdf'?' gold':'');
  el.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>'+msg;
  wrap.appendChild(el); requestAnimationFrame(()=>el.classList.add('show'));
  setTimeout(()=>{el.classList.remove('show');setTimeout(()=>el.remove(),300)},2600);
}

/* ===== label / instructions / amazon handlers ===== */
async function openLabel(){
  if(!CURRENT) return;
  const res = await API.openLabel(CURRENT.order_number);
  if(res && !res.ok) toast(res.error||'Cannot open label','gold');
}
async function printLabel(){
  if(!CURRENT) return;
  const res = await API.printLabel(CURRENT.order_number);
  if(res && !res.ok) toast(res.error||'Cannot print label','gold');
}

/* ===== LightBurn live status poll ===== */
async function pollLightBurn(){
  const { running } = await API.lightburnStatus();
  const pill = document.getElementById('livePill');
  if(pill){ pill.classList.toggle('lb-off', !running); }
}
setInterval(pollLightBurn, 3000); pollLightBurn();

/* ===== bootstrap ===== */
window.addEventListener('pywebviewready', loadDashboard);
document.addEventListener('DOMContentLoaded', () => { showView('dashboard'); });
