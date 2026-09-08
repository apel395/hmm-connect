import { Printer } from "lucide-react";
import {useState} from "react";
import {useNavigate} from "react-router-dom";
import {toast} from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import PurchaseOrderTable from "../components/PurchaseOrderTable";
import PurchaseOrderForm from "../components/PurchaseOrderForm";
import ReceiveGoodsDialog from "@/modules/purchasing/goods-receipts/components/ReceiveGoodsDialog";
import type {PurchaseOrder} from "../types";
import {usePurchaseOrders,useCreatePurchaseOrder} from "../hooks/usePurchaseOrders";
import {useConvertMarketList} from "@/modules/purchasing/market-list/useMarketLists";

export default function PurchaseOrderPage(){
 const navigate=useNavigate();const{data,isLoading}=usePurchaseOrders();const createMutation=useCreatePurchaseOrder();const convertMLMutation=useConvertMarketList();const[open,setOpen]=useState(false);const[receivePO,setReceivePO]=useState<PurchaseOrder|null>(null);
 async function submit(payload:any){try{if(payload.creation_type==="FROM_ML"){const response=await convertMLMutation.mutateAsync({id:Number(payload.market_list_id),supplier_id:Number(payload.supplier_id),items:payload.market_list_items});setOpen(false);toast.success("Purchase Order created from Market List.");if(response.data?.id)navigate(`/purchase-orders/${response.data.id}`);return}await createMutation.mutateAsync(payload);setOpen(false);toast.success("Purchase Order created")}catch(err:any){toast.error(err?.response?.data?.detail||"Could not create Purchase Order")}}
 return <><div className="space-y-6"><PageHeader title="Purchase Orders" description="Purchase Order Management" actions={<>
<Button onClick={()=>setOpen(true)}>New Purchase Order</Button>
<Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</>}/><Card>{isLoading?<Loading/>:<PurchaseOrderTable rows={data?.items??[]} onView={row=>navigate(`/purchase-orders/${row.id}`)}/>}</Card></div><PurchaseOrderForm open={open} loading={createMutation.isPending||convertMLMutation.isPending} onClose={()=>setOpen(false)} onSubmit={submit}/><ReceiveGoodsDialog open={!!receivePO} purchaseOrder={receivePO} onClose={()=>setReceivePO(null)}/></>;
}
