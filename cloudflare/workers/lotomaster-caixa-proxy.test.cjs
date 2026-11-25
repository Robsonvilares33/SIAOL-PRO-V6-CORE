'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(__filename.replace('.test.cjs','.js'),'utf8');
async function invoke(upstream) {
  let listener;
  const context=vm.createContext({URL,Headers,Request,Response,JSON,Set,fetch:async()=>upstream,caches:{default:{match:async()=>null,put:async()=>{}}},addEventListener:(_name,fn)=>{listener=fn;}});
  vm.runInContext(source,context);
  const request=new Request('https://worker.test/quina/123',{headers:{Origin:'https://lotomaster-public-v6.vercel.app'}});
  let response; listener({request,respondWith:promise=>{response=promise;},waitUntil(){}});
  return await response;
}
const upstream=(text=async()=>'{"numero":123}')=>({ok:true,status:200,headers:new Headers({'Content-Type':'application/json'}),text});
test('Worker não aceita/cacheia concurso CAIXA diferente do solicitado',async()=>{
 const response=await invoke(upstream(async()=>'{"numero":124}'));
 assert.equal(response.status,502);assert.equal((await response.json()).error,'caixa_contest_mismatch');
 assert.equal(response.headers.get('Access-Control-Allow-Origin'),'https://lotomaster-public-v6.vercel.app');
});
test('Worker converte falha ao ler body upstream em 502 com CORS',async()=>{
 const response=await invoke(upstream(async()=>{throw Error('stream failure');}));
 assert.equal(response.status,502);assert.equal((await response.json()).error,'caixa_body_read_error');
 assert.equal(response.headers.get('Access-Control-Allow-Origin'),'https://lotomaster-public-v6.vercel.app');
});
