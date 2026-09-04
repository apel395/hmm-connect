import api from "@/api/client";
export const getBalanceSheet=async(params:any)=>(await api.get("/balance-sheet",{params})).data;
export const getProfitLoss=async(params:any)=>(await api.get("/profit-loss",{params})).data;
export const getFiscalBalanceSheet=async(params:any)=>(await api.get("/fiscal-balance-sheet",{params})).data;
export async function exportStatement(kind:"balance-sheet"|"profit-loss"|"fiscal-balance-sheet",params:any,format:"xlsx"|"csv"){
 const response=await api.get(`/${kind}/export`,{params:{...params,format},responseType:"blob"});const url=URL.createObjectURL(response.data);const link=document.createElement("a");link.href=url;link.download=`${kind}.${format}`;link.click();URL.revokeObjectURL(url);
}
