// Local preview of Netlify rewrites. Uses the function's existing read-only DB request.
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');process.chdir(root);const {handler,handlerWith}=require('../netlify/functions/live.cjs');
const types={'.js':'application/javascript','.css':'text/css','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml','.html':'text/html'};
http.createServer(async(req,res)=>{const url=new URL(req.url,'http://localhost');
if(url.pathname==='/__test/network-error'){const r=await handlerWith(async()=>{throw new Error('simulated upstream offline')})({httpMethod:req.method,path:'/',queryStringParameters:{}});res.writeHead(r.statusCode,r.headers);return res.end(r.body);}
if(url.pathname==='/article.html'&&url.searchParams.has('id')){res.writeHead(301,{Location:'/articles/'+encodeURIComponent(url.searchParams.get('id'))+'.html'});return res.end();}
if(['/index.html','/index'].includes(url.pathname)){res.writeHead(301,{Location:'/'});return res.end();}
if(url.pathname==='/'||/^\/articles\/[^/]+$/.test(url.pathname)||['/category.html','/category','/rss.xml','/sitemap.xml'].includes(url.pathname)){const r=await handler({httpMethod:req.method,path:url.pathname,queryStringParameters:Object.fromEntries(url.searchParams)});res.writeHead(r.statusCode,r.headers);return res.end(r.body);}
const file=path.resolve(root,'.'+decodeURIComponent(url.pathname));if(!file.startsWith(root+path.sep)){res.writeHead(404);return res.end();}try{const content=fs.readFileSync(file);res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'});res.end(content);}catch{res.writeHead(404);res.end('Not found');}
}).listen(8787,'127.0.0.1',()=>console.log('Preview http://127.0.0.1:8787'));
