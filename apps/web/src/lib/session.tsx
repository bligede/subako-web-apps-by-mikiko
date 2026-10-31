import {createContext,useContext,useEffect,useState,type ReactNode} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {api,sessionSchema,type Session} from './api';
type Value={session:Session|null;loading:boolean;unavailable:boolean;setSession:(value:Session|null)=>void};
const Context=createContext<Value|null>(null);
export function SessionProvider({children}:{children:ReactNode}){
 const client=useQueryClient();const [session,setValue]=useState<Session|null>(null);const [settled,setSettled]=useState(false);
 const bootstrap=useQuery({queryKey:['session'],queryFn:async()=>sessionSchema.parse(await api('/auth/me')),retry:false,staleTime:Infinity,refetchOnWindowFocus:false,refetchInterval:query=>{const error=query.state.error as {status?:number}|null;return error&&(error.status===0||(error.status??0)>=500)?5000:false}});
 useEffect(()=>{if(bootstrap.data){setValue(bootstrap.data);setSettled(true)}if(bootstrap.isError)setSettled(true)},[bootstrap.data,bootstrap.isError]);
 const setSession=(value:Session|null)=>{client.clear();setValue(value);setSettled(true);if(value)client.setQueryData(['session'],value)};
 useEffect(()=>{const expired=()=>{setValue(null);client.clear();setSettled(true)};window.addEventListener('subako:session-expired',expired);return()=>window.removeEventListener('subako:session-expired',expired)},[client]);
 return <Context.Provider value={{session,loading:!settled,unavailable:bootstrap.isError&&(bootstrap.error as {status?:number}).status!==401,setSession}}>{children}</Context.Provider>
}
export function useSession(){const value=useContext(Context);if(!value)throw new Error('SessionProvider required');return value}
export function useOnline(){const [online,set]=useState(navigator.onLine);useEffect(()=>{const on=()=>set(true),off=()=>set(false);addEventListener('online',on);addEventListener('offline',off);return()=>{removeEventListener('online',on);removeEventListener('offline',off)}},[]);return online}
