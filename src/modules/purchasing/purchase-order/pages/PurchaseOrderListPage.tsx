import {
  useState,
} from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import useAuthStore from "@/store/auth";

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

  const navigate = useNavigate();

  const user = useAuthStore((state) => state.user);
  const roleNames = (user?.roles ?? []).map((role) => role.name);
  const isAdmin = roleNames.includes("ADMIN");
  const canManagePO = isAdmin || roleNames.includes("PURCHASING");
  const canReceive = isAdmin || roleNames.includes("WAREHOUSE");

  const [scope, setScope] =
    useState<"active" | "history">("active");

  const {
    data=[],
    isLoading,
  } =
    usePurchaseOrders(scope);



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







  async function approve(row: PurchaseOrder) {
    const requiredRole =
      row.current_approver_role ?? "current role";
    if (
      !window.confirm(
        `Approve ${row.po_number} for the ${requiredRole} step?`
      )
    ) {
      return;
    }
    try {
      await approveMutation.mutateAsync({
        id: row.id,
        comment: `Approved by administrator for ${requiredRole}`,
      });
      toast.success(`${row.po_number}: ${requiredRole} step approved.`);
    } catch (error: any) {
      toast.error(
        typeof error?.response?.data?.detail === "string"
          ? error.response.data.detail
          : "Unable to approve purchase order."
      );
    }
  }

  async function reject(row: PurchaseOrder) {
    const comment = window.prompt("Reject reason");
    if (!comment) {
      return;
    }
    await rejectMutation.mutateAsync({
      id: row.id,
      comment,
    });
  }

return (

<>

<div className="space-y-6">


<PageHeader

title="Purchase Orders"

description="Manage supplier orders"

actions={
  <div className="flex gap-2">
    <Button
      variant={scope === "active" ? "primary" : "outline"}
      onClick={() => setScope("active")}
    >
      Active
    </Button>
    <Button
      variant={scope === "history" ? "primary" : "outline"}
      onClick={() => setScope("history")}
    >
      History
    </Button>
    {scope === "active" && canManagePO && (
      <Button onClick={() => setOpenForm(true)}>
        New Purchase Order
      </Button>
    )}
  </div>
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

onEdit={(row) =>
  navigate(`/purchase-orders/${row.id}`)
}

onTrace={(row) =>
  navigate(`/traceability/po/${row.id}`)
}



onSubmit={
  canManagePO ? submit : undefined
}

onApprove={
  isAdmin ? approve : undefined
}

onReject={
  isAdmin ? reject : undefined
}

onReceive={
  canReceive
    ? (row) => setSelectedPO(row)
    : undefined
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