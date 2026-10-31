import {z} from 'zod';
export class ApiError extends Error{constructor(public status:number,public code:string,message:string,public requestId?:string){super(message)}}
const grantSchema=z.object({id:z.string().uuid(),name:z.string(),location:z.string(),environment:z.literal('simulation'),roles:z.array(z.string()),permissions:z.array(z.string())});
export const sessionSchema=z.object({user:z.object({id:z.string().uuid(),email:z.string(),display_name:z.string()}),sites:z.array(grantSchema),csrf_token:z.string(),expires_at:z.string(),environment:z.literal('simulation')});
export type Session=z.infer<typeof sessionSchema>;
export type SiteGrant=z.infer<typeof grantSchema>;
export type Device={id:string;site_id:string;environment:'simulation';code:string;name:string;node_type:'gate'|'measure';channel:string;capabilities:string[];firmware_version:string;calibration_version:string;scenario:string;mode:string;connectivity:'ONLINE'|'STALE'|'OFFLINE';observed_at:string|null;received_at:string|null;quality:Record<string,string>;water_level_m:number|null;water_level_down_m:number|null;flow_lps:number|null;gate_position_pct:number|null;battery_pct:number|null;battery_voltage:number|null;rssi_dbm:number|null;snr_db:number|null};
export type Dashboard={site_id:string;environment:'simulation';mean_water_level_m:number|null;mean_flow_lps:number|null;online_devices:number;total_devices:number;gate_nodes:number;measure_nodes:number;active_alerts:number;last_received_at:string|null;generated_at:string;freshness:{stale_seconds:number;offline_seconds:number};devices:Device[]};
export function ageSnapshot(data:Dashboard,elapsedMs:number):Dashboard{
 const now=new Date(data.generated_at).getTime()+Math.max(0,elapsedMs);
 const devices=data.devices.map(device=>{const age=device.received_at?(now-new Date(device.received_at).getTime())/1000:Infinity;return {...device,connectivity:(age>data.freshness.offline_seconds?'OFFLINE':age>data.freshness.stale_seconds?'STALE':'ONLINE') as Device['connectivity']}});
 const fresh=devices.filter(d=>d.connectivity==='ONLINE');
 const levels=fresh.filter(d=>d.water_level_m!==null&&d.quality.level==='OK').map(d=>d.water_level_m!);
 const flows=fresh.filter(d=>d.flow_lps!==null&&d.quality.flow==='OK').map(d=>d.flow_lps!);
 return {...data,devices,online_devices:fresh.length,mean_water_level_m:levels.length?levels.reduce((a,b)=>a+b,0)/levels.length:null,mean_flow_lps:flows.length?flows.reduce((a,b)=>a+b,0)/flows.length:null};
}
export type Reading={id:string;device_id:string;site_id:string;observed_at:string;metric:string;value:number|null;unit:string;quality:string;raw_reference:string};
export type Alert={id:string;device_id:string;site_id:string;code:string;severity:string;title:string;evidence:Record<string,unknown>;suggested_action:string;observed_at:string;status:string;advisory:boolean};
export type Ledger={id:string;chain_index:number;occurred_at:string;payload:{data:{title?:string;device_id?:string;kind?:string;raw_reference?:string;reported_mode?:string}};previous_hash:string;current_hash:string};
export type Integrity={result:string;checked_count:number;first_index:number;last_index:number;head_hash:string;limitation:string;verified_at:string;failures:string[]};
export async function api<T>(path:string,options:RequestInit={},csrf?:string):Promise<T>{
 const mutation=Boolean(options.method&&options.method!=='GET');
 if(mutation&&!navigator.onLine)throw new ApiError(0,'OFFLINE','Anda sedang offline. Tindakan tidak disimpan atau dikirim ulang.');
 let response:Response;
 try{response=await fetch('/api/v1'+path,{...options,credentials:'same-origin',cache:'no-store',headers:{...(options.body?{'Content-Type':'application/json'}:{}),...(csrf?{'X-CSRF-Token':csrf}:{}),...options.headers}})}catch{throw new ApiError(0,'NETWORK_ERROR','Server belum dapat dijangkau. Periksa koneksi Anda.');}
 if(!response.ok){const error=await response.json().catch(()=>({}));if(response.status===401&&!['/auth/login','/auth/me'].includes(path))window.dispatchEvent(new Event('subako:session-expired'));throw new ApiError(response.status,error.code||'REQUEST_FAILED',error.message||'Permintaan belum berhasil.',error.request_id)}
 return response.status===204?undefined as T:response.json();
}
export const scoped=(siteId:string,extra:Record<string,string>={})=>new URLSearchParams({site_id:siteId,environment:'simulation',...extra}).toString();
export const wita=(value:string|null|undefined,full=false)=>value?new Intl.DateTimeFormat('id-ID',{timeZone:'Asia/Makassar',...(full?{day:'2-digit',month:'short',year:'numeric'}:{}),hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(value))+' WITA':'Belum ada data';
export const number=(value:number|null|undefined,digits=2)=>value==null?'—':new Intl.NumberFormat('id-ID',{maximumFractionDigits:digits,minimumFractionDigits:digits}).format(value);
