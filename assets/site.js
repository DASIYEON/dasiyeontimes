
const SUPABASE_URL='https://lguvdtesdetteasnniif.supabase.co';
const SUPABASE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxndXZkdGVzZGV0dGVhc25uaWlmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAwNzk1MjUsImV4cCI6MjA5NTY1NTUyNX0.SBUdAzeAwwJ-v2CVYBPdIvTyXLePWZuthNTmWdRjwig';
const REST_URL=SUPABASE_URL+'/rest/v1/articles';
const HDR={apikey:SUPABASE_KEY,Authorization:'Bearer '+SUPABASE_KEY};
function esc(s){return String(s??'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]))}
function fmtDate(v){if(!v)return'';if(/^\d{4}[.-]\d{1,2}[.-]\d{1,2}$/.test(String(v)))return String(v).replace(/-/g,'.');const d=new Date(v);if(Number.isNaN(d.getTime()))return String(v);return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')}`}
function norm(a){return{id:a.id,title:a.title||'제목 없음',summary:a.summary||'',body:a.body||'',category:a.category||'컬럼',image:a.image||'',author:a.author||'최형규',status:a.status||'발행',dateStr:a.date_str||a.dateStr||fmtDate(a.created_at||a.date)}}
async function rest(q){const r=await fetch(REST_URL+'?'+q,{headers:HDR});if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}
function artUrl(a){return `article.html?id=${encodeURIComponent(a.id)}`}
function img(a){return a.image?`<img src="${esc(a.image)}" alt="" loading="lazy" decoding="async">`:''}
