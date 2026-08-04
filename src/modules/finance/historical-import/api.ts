import api from "@/api/client";

export const documentTypes = ["PURCHASE_REQUISITION","PURCHASE_ORDER","GOODS_RECEIPT","SUPPLIER_INVOICE","PAYMENT","JOURNAL_ENTRY"] as const;
export const slugs: Record<string,string> = {PURCHASE_REQUISITION:"purchase-requisition",PURCHASE_ORDER:"purchase-order",GOODS_RECEIPT:"goods-receipt",SUPPLIER_INVOICE:"supplier-invoice",PAYMENT:"payment",JOURNAL_ENTRY:"journal-entry"};
export const listBatches = async (params:any={}) => (await api.get("/historical-import/batches",{params})).data;
export const createBatch = async (payload:any) => (await api.post("/historical-import/batches",payload)).data;
export const getBatch = async (id:number) => (await api.get(`/historical-import/batches/${id}`)).data;
export const uploadBatch = async (id:number,file:File) => {const data=new FormData();data.append("file",file);return (await api.post(`/historical-import/batches/${id}/upload`,data,{headers:{"Content-Type":"multipart/form-data"}})).data};
export const validateBatch = async (id:number) => (await api.post(`/historical-import/batches/${id}/validate`)).data;
export const previewBatch = async (id:number,status?:string) => (await api.get(`/historical-import/batches/${id}/preview`,{params:{status:status||undefined}})).data;
export const confirmBatch = async (id:number,confirm_warnings=true) => (await api.post(`/historical-import/batches/${id}/confirm`,{confirm_warnings})).data;
export const cancelBatch = async (id:number) => (await api.post(`/historical-import/batches/${id}/cancel`)).data;
export const progress = async (year?:number) => (await api.get("/historical-import/progress",{params:{year}})).data;
export const downloadTemplate = async (kind:string) => {const response=await api.get(`/historical-import/templates/${slugs[kind]}`,{responseType:"blob"});const url=URL.createObjectURL(response.data);const link=document.createElement("a");link.href=url;link.download=`hmm-${slugs[kind]}-historical-import.xlsx`;link.click();URL.revokeObjectURL(url)};
export const downloadErrors = async (id:number,number:string) => {const response=await api.get(`/historical-import/batches/${id}/error-report`,{responseType:"blob"});const url=URL.createObjectURL(response.data);const link=document.createElement("a");link.href=url;link.download=`${number}-errors.csv`;link.click();URL.revokeObjectURL(url)};
