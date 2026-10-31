import {defineConfig, type Plugin} from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import {createHash} from 'node:crypto';
const proxy={'/api':{target:process.env.SUBAKO_API_TARGET||'http://127.0.0.1:8000'},'/ws':{target:process.env.SUBAKO_API_TARGET||'http://127.0.0.1:8000',ws:true},'/health':{target:process.env.SUBAKO_API_TARGET||'http://127.0.0.1:8000'}};
function shellWorker():Plugin{return {name:'subako-shell-worker',generateBundle(_,bundle){
 const assets=['/','/index.html','/manifest.webmanifest','/icon.svg','/icon-192.png','/icon-512.png',...Object.keys(bundle).map(k=>'/'+k)];
 const version=createHash('sha256').update(JSON.stringify(assets)).digest('hex').slice(0,12);
 const source=`const CACHE='subako-shell-${version}',ASSETS=${JSON.stringify(assets)};
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('subako-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('message',event=>{if(event.data==='SKIP_WAITING')self.skipWaiting()});
self.addEventListener('fetch',event=>{const request=event.request,url=new URL(request.url);if(request.method!=='GET'||url.origin!==self.location.origin||url.pathname.startsWith('/api/')||url.pathname.startsWith('/ws/')||url.pathname.startsWith('/health/'))return;if(request.mode==='navigate'){event.respondWith(fetch(request).catch(()=>caches.match('/index.html')));return;}if(ASSETS.includes(url.pathname)){event.respondWith(caches.match(request,{ignoreVary:true}).then(hit=>hit||fetch(request)));}});
// Only same-origin predeclared public assets ignore Vary: Origin; API is excluded.
// No API caching, mutation queue, background sync, or persisted session data.
`;
 this.emitFile({type:'asset',fileName:'sw.js',source});
}};}
export default defineConfig({plugins:[react(),tailwindcss(),shellWorker()],server:{proxy,strictPort:true},preview:{proxy,strictPort:true},build:{chunkSizeWarningLimit:750}});
