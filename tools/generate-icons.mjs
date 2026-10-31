import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright-core';
const root=fileURLToPath(new URL('../',import.meta.url));
const executablePath=[process.env.CHROME_PATH,'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p=>p&&fs.existsSync(p));
const browser=await chromium.launch({executablePath,headless:true});
try{
 const page=await browser.newPage();const svg=fs.readFileSync(root+'apps/web/public/icon.svg','utf8');
 for(const size of [192,512]){
  const data=await page.evaluate(async({svg,size})=>{const image=new Image();image.src='data:image/svg+xml;base64,'+btoa(svg);await image.decode();const canvas=document.createElement('canvas');canvas.width=canvas.height=size;const ctx=canvas.getContext('2d');ctx.fillStyle='#10443B';ctx.fillRect(0,0,size,size);ctx.drawImage(image,size*.1,size*.1,size*.8,size*.8);return canvas.toDataURL('image/png').split(',')[1]},{svg,size});
  fs.writeFileSync(root+`apps/web/public/icon-${size}.png`,Buffer.from(data,'base64'));
 }
 console.log('PWA icons generated: 192px and 512px.');
}finally{await browser.close()}
