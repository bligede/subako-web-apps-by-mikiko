import {useEffect,useState} from 'react';
import {useQueryClient} from '@tanstack/react-query';
export function useRealtime(siteId:string,online:boolean){
 const client=useQueryClient();const [status,setStatus]=useState('Menghubungkan');
 useEffect(()=>{
  if(!online){setStatus('Offline');return;}
  let socket:WebSocket|undefined,timer:ReturnType<typeof setTimeout>|undefined,disposed=false,attempt=0;
  const connect=()=>{
   if(disposed)return;
   socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/v1/sites/${siteId}?environment=simulation`);
   socket.onopen=()=>{setStatus('Terhubung');attempt=0;void client.invalidateQueries({predicate:q=>q.queryKey.includes(siteId)})};
   socket.onmessage=event=>{try{const value=JSON.parse(event.data);if(value.site_id===siteId&&value.environment==='simulation')void client.invalidateQueries({predicate:q=>q.queryKey.includes(siteId)})}catch{setStatus('Memuat ulang data');}};
   socket.onclose=event=>{if(disposed)return;if(event.code===1008){setStatus('Sesi/perizinan berakhir');window.dispatchEvent(new Event('subako:session-expired'));return;}setStatus('Terputus · polling cadangan');timer=setTimeout(connect,Math.min(1000*2**attempt++,15000))};
   socket.onerror=()=>socket?.close();
  };connect();
  return()=>{disposed=true;clearTimeout(timer);socket?.close()};
 },[siteId,online,client]);return status;
}
