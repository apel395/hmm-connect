import axios from "axios";
import { publishMasterDataChange } from "@/lib/masterDataEvents";

const api=axios.create({

baseURL:

import.meta.env.VITE_API_URL,

timeout:30000,

headers:{

"Content-Type":"application/json",

},

});

api.interceptors.request.use(config=>{

const token=

localStorage.getItem("access_token");

if(token){

config.headers.Authorization=

`Bearer ${token}`;

}

if((config.method??"get").toLowerCase()==="get"&&config.params){

config.params=Object.fromEntries(Object.entries(config.params as Record<string,unknown>).filter(([,value])=>value!==undefined&&value!==null&&value!==""));

}

return config;

});

api.interceptors.response.use(

response=>{
const method=(response.config.method??"get").toLowerCase();
if(["post","put","patch","delete"].includes(method)){
  const url=response.config.url??"";
  if(/(?:^|\/)products(?:\/|$)/.test(url)) publishMasterDataChange("products");
  if(/(?:^|\/)suppliers(?:\/|$)/.test(url)) publishMasterDataChange("suppliers");
}
return response;
},

async error=>{

if(error.response?.status===401){

const currentToken = localStorage.getItem("access_token");
const requestToken = error.config?.headers?.Authorization;
if (currentToken && requestToken === `Bearer ${currentToken}` && !String(error.config?.url || "").includes("/auth/login")) {
  ["access_token", "refresh_token", "user", "hmm-last-activity-at"].forEach(key => localStorage.removeItem(key));
  window.location.replace("/login?reason=session");
}

}

return Promise.reject(error);

}

);

export default api;
