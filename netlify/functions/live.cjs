const fs = require('node:fs');
const path = require('node:path');
const sanitize = require('sanitize-html');
const ROOT = [process.cwd(), path.resolve(__dirname, '../..')].find(p => fs.existsSync(path.join(p, 'templates/article.template.html'))) || process.cwd();
const SITE = 'https://dasiyeontimes.kr';
const CATS = ['마음','경영','AI','컬럼'];
const META = 'id,title,summary,category,image,author,status,date_str,created_at';
// Reuse the site's existing public anon configuration. No new credential or privilege.
function config() {
  const s = fs.readFileSync(path.join(ROOT, 'assets/site.js'), 'utf8');
  return { url:s.match(/const SUPABASE_URL='([^']+)'/)[1], key:s.match(/const SUPABASE_KEY='([^']+)'/)[1] };
}
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function safeUrl(s) { try { const u = new URL(String(s)); return u.protocol === 'https:' ? u.href : ''; } catch { return ''; } }
function body(s) { return sanitize(String(s||''), {allowedTags:['p','br','h2','h3','h4','strong','b','em','i','u','s','blockquote','ul','ol','li','hr','a','img','figure','figcaption','table','thead','tbody','tr','th','td','span','div'],allowedAttributes:{a:['href','title'],img:['src','alt','width','height'],th:['colspan','rowspan'],td:['colspan','rowspan']},allowedSchemes:['https','http','mailto','tel'],allowedSchemesByTag:{img:['https']},allowProtocolRelative:false,transformTags:{a:(tag,attrs)=>({tagName:tag,attribs:{...attrs,rel:'noopener noreferrer'}}),img:(tag,attrs)=>({tagName:tag,attribs:{...attrs,loading:'lazy',decoding:'async'}})}}); }
function norm(a) { return {...a,title:a.title||'제목 없음',summary:a.summary||'',category:a.category||'컬럼',author:a.author||'최형규',image:safeUrl(a.image),dateStr:String(a.date_str||a.created_at||'').slice(0,10).replace(/-/g,'.')}; }
const href = a => `/articles/${encodeURIComponent(a.id)}.html`;
const json = a => JSON.stringify(a).replace(/</g,'\\u003c');
async function query(q, fetcher=fetch) {
  const c = config();
  const r=await fetcher(`${c.url}/rest/v1/articles?${q}`,{headers:{apikey:c.key,Authorization:`Bearer ${c.key}`},signal:AbortSignal.timeout(8000),cache:'no-store'});
  if(!r.ok) throw new Error('upstream');
  const rows=await r.json();
  if(!Array.isArray(rows)) throw new Error('upstream');
  return rows.filter(a=>a.status==='발행' && /^\d+$/.test(String(a.id))).map(norm);
}
const xmlEsc = s => esc(String(s ?? '').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]|[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/g,''));
const published = `status=eq.${encodeURIComponent('발행')}`;
async function list(fetcher, limit) {
  if (limit) return query(`select=${META}&${published}&order=id.desc&limit=${limit}`,fetcher);
  const rows=[]; let batchLength=500;
  for (let offset=0; ; offset+=batchLength) {
    const batch=await query(`select=${META}&${published}&order=id.desc&limit=500&offset=${offset}`,fetcher);
    rows.push(...batch); batchLength=batch.length;
    if(!batchLength) return rows;
    if(offset>=49500) throw new Error('article limit');
  }
}
function fill(file, values) { return fs.readFileSync(path.join(ROOT,file),'utf8').replace(/\{\{([A-Z_]+)\}\}/g,(_,k)=>values[k]??''); }
function image(a, eager=false) { return a.image?`<img src="${esc(a.image)}" alt="${esc(a.title)}" ${eager?'fetchpriority="high"':'loading="lazy"'} decoding="async">`:''; }
function card(a, cls='card') { return `<article class="${cls}"><a href="${href(a)}"><div class="card-img">${image(a)}</div><div class="card-body"><span class="tag">${esc(a.category)}</span><h3>${esc(a.title)}</h3><p>${esc(a.summary)}</p><div class="meta">${esc(a.author)} · ${esc(a.dateStr)}</div></div></a></article>`; }
function home(arts) {
  const top=arts[0];
  let result=fill('templates/index.template.html',{TOP_ID:top?.id||'',PRELOAD:'',HERO:top?`<a href="${href(top)}" style="position:absolute;inset:0;z-index:3" aria-label="${esc(top.title)}"></a>${image(top,true)}<div class="hero-copy"><span class="tag">${esc(top.category)}</span><h1>${esc(top.title)}</h1><p>${esc(top.summary)}</p><div class="meta">${esc(top.author)} · ${esc(top.dateStr)}</div></div>`:'<p class="empty">발행된 기사가 없습니다.</p>',LATEST:arts.slice(0,5).map(a=>`<article class="latest-item"><div class="latest-thumb">${image(a)}</div><div><div class="latest-title"><a href="${href(a)}">${esc(a.title)}</a></div><div class="latest-meta">${esc(a.dateStr)} ${esc(a.category)}</div></div></article>`).join(''),SECTIONS:CATS.map(cat=>`<section class="section"><div class="section-head"><h2>${cat==='컬럼'?'대표 칼럼':cat}</h2><a href="/category.html?cat=${encodeURIComponent(cat)}">더보기 →</a></div><div class="${cat==='컬럼'?'column-cards':'cards'}">${arts.filter(a=>a.category===cat).slice(0,2).map(a=>card(a,cat==='컬럼'?'column-card':'card')).join('')}</div></section>`).join('')});
  // SSR is authoritative: remove old top-ID short circuit and client query duplication.
  result=result.replace(/<script>\s*const _na[\s\S]*?<\/script>/,'');
  return result.replace('</body>', '<script src="/assets/live-ui.js" defer></script></body>');
}
function article(a, related) {
  const url=SITE+href(a),og=a.image||SITE+'/images/og-image.png';
  const date=String(a.created_at||a.date_str||'').slice(0,10).replace(/\./g,'-');
  return fill('templates/article.template.html',{TITLE_ESC:esc(a.title),SUMMARY_ESC:esc(a.summary),AUTHOR_ESC:esc(a.author),CATEGORY_ESC:esc(a.category),DATE_ISO:esc(date),DATE_STR:esc(a.dateStr),CAT_URLENC:encodeURIComponent(a.category),URL:url,OG_IMAGE:esc(og),PRELOAD:'',HERO_FIGURE:image(a,true)||'<div class="article-fallback"></div>',BODY:body(a.body)||'<p>본문 내용이 없습니다.</p>',RELATED:related.map(a=>`<article class="related-item"><a href="${href(a)}"><span class="tag">${esc(a.category)}</span><h3>${esc(a.title)}</h3><div class="meta">${esc(a.author)} · ${esc(a.dateStr)}</div></a></article>`).join(''),JSONLD:json({'@context':'https://schema.org','@type':'NewsArticle',headline:a.title,description:a.summary,image:[og],datePublished:date,author:{'@type':'Person',name:a.author},publisher:{'@type':'NewsMediaOrganization',name:'다시연타임즈'},mainEntityOfPage:url})});
}
function category(arts, cat, q, page) {
  const filtered=arts.filter(a=>(!cat||a.category===cat)&&(!q||(a.title+' '+a.summary).toLowerCase().includes(q.toLowerCase())));
  const max=Math.max(1,Math.ceil(filtered.length/10));page=Math.min(page,max);
  let s=fs.readFileSync(path.join(ROOT,'category.html'),'utf8');
  s=s.replace(/<h1 id="title">[\s\S]*?<\/h1>/,`<h1 id="title">${esc(cat||'전체 기사')}</h1>`)
    .replace(/<div id="list"[\s\S]*?<\/main>/,`<div id="list" class="category-list">${filtered.slice((page-1)*10,page*10).map(a=>`<article class="list-card"><a href="${href(a)}"><div class="list-img">${image(a)}</div><div class="list-body"><span class="tag">${esc(a.category)}</span><h2>${esc(a.title)}</h2><p>${esc(a.summary)}</p><div class="meta">${esc(a.author)} · ${esc(a.dateStr)}</div></div></a></article>`).join('')||'<div class="empty">검색 결과가 없습니다.</div>'}</div><div id="pages" class="pagination">${Array.from({length:max},(_,i)=>`<a class="page-btn ${page===i+1?'active':''}" href="/category.html?${new URLSearchParams({cat,q,page:String(i+1)})}">${i+1}</a>`).join('')}</div></main>`)
    .replace(/<script>\s*const p=[\s\S]*?<\/script>/,'')
    .replace(/<div class="searchbar">[\s\S]*?<\/div>/,`<form class="searchbar" action="/category.html"><input type="hidden" name="cat" value="${esc(cat)}"><input id="q" name="q" type="search" placeholder="기사 검색" value="${esc(q)}"><button type="submit">검색</button></form>`);
  return s.replace('</body>', '<script src="/assets/live-ui.js" defer></script></body>');
}
function feeds(arts,rss) {
  if(!rss) return `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${['/','/about.html','/ethics.html','/privacy.html','/terms.html','/youth.html',...arts.map(href)].map(p=>`<url><loc>${xmlEsc(SITE+p)}</loc></url>`).join('')}</urlset>`;
  return `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>다시연타임즈</title><link>${SITE}/</link><description>회복과 성장의 미디어</description><language>ko</language>${arts.slice(0,50).map(a=>`<item><title>${xmlEsc(a.title)}</title><link>${SITE+href(a)}</link><guid isPermaLink="true">${SITE+href(a)}</guid><description>${xmlEsc(a.summary)}</description><category>${xmlEsc(a.category)}</category>${a.created_at && !isNaN(Date.parse(a.created_at))?`<pubDate>${new Date(a.created_at).toUTCString()}</pubDate>`:''}</item>`).join('')}</channel></rss>`;
}
function errorPage(status) { return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="robots" content="noindex"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${status===404?'기사를 찾을 수 없습니다':'잠시 연결할 수 없습니다'} — 다시연타임즈</title></head><body><main><h1>${status===404?'기사를 찾을 수 없습니다':'잠시 연결할 수 없습니다'}</h1><p>${status===404?'주소가 잘못되었거나 공개되지 않은 기사입니다.':'최신 기사를 확인할 수 없습니다. 잠시 후 새로고침해 주세요.'}</p><a href="/">홈으로</a></main></body></html>`; }
function handlerWith(fetcher=fetch) { return async event=>{
  const headers={'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','Netlify-CDN-Cache-Control':'no-store','CDN-Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
  if(event.httpMethod && !['GET','HEAD'].includes(event.httpMethod)) return {statusCode:405,headers:{...headers,Allow:'GET, HEAD'},body:''};
  const q=event.queryStringParameters||{};
  // Derive the view from the request path; visitor query parameters cannot override a rewrite.
  const requestPath=event.path||'';
  const match=requestPath.match(/^\/articles\/(\d{1,20})(?:\.html)?$/);
  const mode=match?'article':requestPath==='/'?'home':/^\/category(?:\.html)?$/.test(requestPath)?'category':requestPath==='/rss.xml'?'rss':requestPath==='/sitemap.xml'?'sitemap':q.mode||'article';
  const id=match?match[1]:q.id;
  try {
    let output;
    if(mode==='article') {
      if(!/^\d{1,20}$/.test(id||'')) return {statusCode:404,headers,body:errorPage(404)};
      const arts=await query(`select=${META},body&${published}&id=eq.${id}&limit=1`,fetcher);
      if(!arts.length) return {statusCode:404,headers,body:errorPage(404)};
      let related=[];try{related=(await list(fetcher,6)).filter(a=>String(a.id)!==id).slice(0,5)}catch{}
      output=article(arts[0],related);
    } else if(['home','category','rss','sitemap'].includes(mode)) {
      const arts=await list(fetcher);
      output=mode==='home'?home(arts):mode==='category'?category(arts,String(q.cat||''),String(q.q||'').slice(0,200),Math.max(1,parseInt(q.page)||1)):feeds(arts,mode==='rss');
      if(mode==='rss'||mode==='sitemap') headers['Content-Type']=mode==='rss'?'application/rss+xml; charset=utf-8':'application/xml; charset=utf-8';
    } else return {statusCode:404,headers,body:errorPage(404)};
    // Every relative asset/navigation URL must work on nested /articles paths.
    output=output.replace(/(href|src)="(assets\/|category\.html|index\.html|about\.html|ethics\.html|privacy\.html|terms\.html|youth\.html)/g,'$1="/$2');
    return {statusCode:200,headers,body:event.httpMethod==='HEAD'?'':output};
  } catch { return {statusCode:503,headers:{...headers,'Retry-After':'30'},body:errorPage(503)}; }
}; }
exports.handler=handlerWith();
exports.handlerWith=handlerWith;
exports.sanitizeBody=body;
