import{

useQuery,
useMutation,
useQueryClient,

}from"@tanstack/react-query";

import{

putAwayApi,

}from"./api";

export function usePutAway(){

return useQuery({

queryKey:["put-away"],

queryFn:async()=>{

const res=

await putAwayApi.list();

return res.data;

},

});

}

export function useCompletePutAway(){

const qc=useQueryClient();

return useMutation({

mutationFn:(payload:any)=>

putAwayApi.complete(payload),

onSuccess(){

qc.invalidateQueries();

},

});

}
