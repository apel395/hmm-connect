import axios from "axios";

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

response=>response,

async error=>{

if(error.response?.status===401){

localStorage.clear();

window.location.href="/login";

}

return Promise.reject(error);

}

);

export default api;
