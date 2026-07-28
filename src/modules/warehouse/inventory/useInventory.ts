import{

useQuery,

}from"@tanstack/react-query";

import{

inventoryApi,

}from"./api";

export function useInventory(){

return useQuery({

queryKey:["inventory"],

queryFn:async()=>{

const res=

await inventoryApi.list();

return res.data;

},

});

}
