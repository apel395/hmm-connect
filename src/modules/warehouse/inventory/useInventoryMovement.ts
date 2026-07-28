import{

useQuery,

}from"@tanstack/react-query";

import{

inventoryMovementApi,

}from"./movementApi";

export function useInventoryMovements(){

return useQuery({

queryKey:["inventory-movements"],

queryFn:async()=>{

const res=

await inventoryMovementApi.list();

return res.data;

},

});

}
