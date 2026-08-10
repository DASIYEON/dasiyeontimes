
const SUPABASE_URL='https://lguvdtesdetteasnniif.supabase.co';
const SUPABASE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxndXZkdGVzZGV0dGVhc25uaWlmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAwNzk1MjUsImV4cCI6MjA5NTY1NTUyNX0.SBUdAzeAwwJ-v2CVYBPdIvTyXLePWZuthNTmWdRjwig';
const REST_URL=SUPABASE_URL+'/rest/v1/articles';
const HDR={apikey:SUPABASE_KEY,Authorization:'Bearer '+SUPABASE_KEY};
function esc(s){return String(s??'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]))}
function fmtDate(v){if(!v)return'';if(/^\d{4}[.-]\d{1,2}[.-]\d{1,2}$/.test(String(v)))return String(v).replace(/-/g,'.');const d=new Date(v);if(Number.isNaN(d.getTime()))return String(v);return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')}`}
function norm(a){return{id:a.id,title:a.title||'제목 없음',summary:a.summary||'',body:a.body||'',category:a.category||'컬럼',image:a.image||'',author:a.author||'최형규',status:a.status||'발행',dateStr:a.date_str||a.dateStr||fmtDate(a.created_at||a.date)}}
async function rest(q){const c=new AbortController();const t=setTimeout(()=>c.abort(),15000);try{const r=await fetch(REST_URL+'?'+q,{headers:HDR,signal:c.signal});if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}finally{clearTimeout(t)}}
function artUrl(a){return `article.html?id=${encodeURIComponent(a.id)}`}
function img(a){return a.image?`<img src="${esc(a.image)}" alt="" loading="lazy" decoding="async">`:''}

/* ---- 모바일 메뉴 토글 (2026-08-10 hotfix) ---- */
document.addEventListener('DOMContentLoaded',function(){
  var t=document.querySelector('.menu-toggle'),n=document.querySelector('.nav');
  if(t&&n)t.addEventListener('click',function(){n.classList.toggle('open');t.setAttribute('aria-expanded',n.classList.contains('open'))});
});

/* ---- 목록 캐시: stale-while-revalidate, 30분 TTL (성능 V2 복원) ---- */
const CACHE_TTL=30*60*1000;
function cacheSet(k,d){try{sessionStorage.setItem(k,JSON.stringify({t:Date.now(),d:d}))}catch(e){}}
async function restCached(q){
  const k='dt:'+q;let c=null;
  try{c=JSON.parse(sessionStorage.getItem(k)||'null')}catch(e){}
  if(c&&Array.isArray(c.d)){
    if(Date.now()-c.t>CACHE_TTL){rest(q).then(d=>cacheSet(k,d)).catch(()=>{})}
    return c.d;
  }
  const d=await rest(q);cacheSet(k,d);return d;
}
