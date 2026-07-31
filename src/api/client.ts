import axios from "axios";

const api=axios.create({

baseURL:

'https://feb-purchases-burlington-expanding.trycloudflare.com/api/v1',

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
