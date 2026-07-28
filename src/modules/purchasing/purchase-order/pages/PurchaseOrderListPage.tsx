import {
  useState,
} from "react";

import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";

import PurchaseOrderTable from "../components/PurchaseOrderTable";
import PurchaseOrderForm from "../components/PurchaseOrderForm";

import {
  usePurchaseOrders,
  useCreatePurchaseOrder,
  useSubmitPurchaseOrder,
  useApprovePurchaseOrder,
  useRejectPurchaseOrder,
} from "../hooks/usePurchaseOrders";


import ReceiveGoodsDialog from "@/modules/purchasing/goods-receipts/components/ReceiveGoodsDialog";


import type {
  PurchaseOrder,
} from "../types";



export default function PurchaseOrderListPage(){


  const {
    data=[],
    isLoading,
  } =
    usePurchaseOrders();



  const createMutation =
    useCreatePurchaseOrder();


  const submitMutation =
    useSubmitPurchaseOrder();


  const approveMutation =
    useApprovePurchaseOrder();


  const rejectMutation =
    useRejectPurchaseOrder();




  const [
    selectedPO,
    setSelectedPO
  ] =
    useState<PurchaseOrder|null>(null);



  const [
    openForm,
    setOpenForm
  ] =
    useState(false);





  async function createPO(
    payload:any
  ){

    await createMutation.mutateAsync(
      payload
    );


    setOpenForm(false);

  }







  async function submit(
    row:PurchaseOrder
  ){

    if(
      !window.confirm(
        `Submit ${row.po_number} for approval?`
      )
    ){

      return;

    }


    await submitMutation.mutateAsync(
      row.id
    );

  }







  async function approve(
    row:PurchaseOrder
  ){

    await approveMutation.mutateAsync({

      id:
        row.id,

    });

  }







  async function reject(
    row:PurchaseOrder
  ){

    const comment =
      window.prompt(
        "Reject reason"
      );


    await rejectMutation.mutateAsync({

      id:
        row.id,

      comment:
        comment ?? "",

    });

  }







return (

<>

<div className="space-y-6">


<PageHeader

title="Purchase Orders"

description="Manage supplier orders"

actions={

<Button

onClick={()=>{

  setOpenForm(true);

}}

>

New Purchase Order

</Button>

}

/>




<Card>


{
isLoading

?

<Loading/>

:

<PurchaseOrderTable


rows={data}



onSubmit={
  submit
}



onApprove={
  approve
}



onReject={
  reject
}



onReceive={
  (row)=>
    setSelectedPO(row)
}



 />

}


</Card>


</div>





<PurchaseOrderForm


open={
  openForm
}



loading={
  createMutation.isPending
}



onClose={()=>{

  setOpenForm(false);

}}



onSubmit={
  createPO
}



/>





<ReceiveGoodsDialog


open={
  !!selectedPO
}



purchaseOrder={
  selectedPO
}



onClose={()=>{

  setSelectedPO(null);

}}



/>


</>

);


}