import {
  useState,
} from "react";
import { useNavigate } from "react-router-dom";


import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";


import PurchaseOrderTable from "../components/PurchaseOrderTable";
import PurchaseOrderForm from "../components/PurchaseOrderForm";
import MarketListPurchaseOrderDialog from "../components/MarketListPurchaseOrderDialog";


import ReceiveGoodsDialog from "@/modules/purchasing/goods-receipts/components/ReceiveGoodsDialog";


import type {
  PurchaseOrder,
} from "../types";


import {
  usePurchaseOrders,
  useCreatePurchaseOrder,
  useSubmitPurchaseOrder,
  useApprovePurchaseOrder,
  useRejectPurchaseOrder,
} from "../hooks/usePurchaseOrders";



export default function PurchaseOrderPage() {
  const navigate = useNavigate();


  const {
    data,
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



  const [open, setOpen] =
    useState(false);
  const [marketListOpen, setMarketListOpen] =
    useState(false);



  const [receivePO, setReceivePO] =
    useState<PurchaseOrder | null>(
      null
    );


  function createPO() {


    setOpen(true);

  }




  async function submit(
    payload: any
  ) {

    try {

      await createMutation.mutateAsync(
        payload
      );


      setOpen(false);



    } catch(err) {

      console.error(err);

    }

  }





  async function _submitForApproval(
    row: PurchaseOrder
  ) {


    if(
      !window.confirm(
        `Submit ${row.po_number} for approval?`
      )
    ) {

      return;

    }



    try {

      await submitMutation.mutateAsync(
        row.id
      );


    } catch(err) {

      console.error(err);

    }

  }






  async function _approvePO(
    row: PurchaseOrder
  ) {


    const comment =
      window.prompt(
        `Approve ${row.po_number} comment (optional)`
      );



    try {

      await approveMutation.mutateAsync({

        id: row.id,

        comment:
          comment || "",

      });


    } catch(err) {

      console.error(err);

    }

  }






  async function _rejectPO(
    row: PurchaseOrder
  ) {


    const comment =
      window.prompt(
        `Reject ${row.po_number} reason`
      );



    if(!comment) {

      return;

    }



    try {

      await rejectMutation.mutateAsync({

        id: row.id,

        comment,

      });


    } catch(err) {

      console.error(err);

    }

  }





  function _openReceive(
    row: PurchaseOrder
  ) {

    setReceivePO(row);

  }





  return (

    <>


      <div className="space-y-6">


        <PageHeader

          title="Purchase Orders"

          description="Purchase Order Management"


          actions={
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => setMarketListOpen(true)}>
                From Market List
              </Button>
              <Button onClick={createPO}>
                New Purchase Order
              </Button>
            </div>
          }

        />





        <Card>


          {
            isLoading ? (

              <Loading />

            ) : (


              <PurchaseOrderTable

                rows={data?.items ?? []}
                onView={(row) => navigate(`/purchase-orders/${row.id}`)}


              />

            )
          }


        </Card>


      </div>







      <PurchaseOrderForm


        open={
          open
        }


        loading={
          createMutation.isPending
        }


        onClose={() => {

          setOpen(false);


        }}



        onSubmit={
          submit
        }


      />

      <MarketListPurchaseOrderDialog
        open={marketListOpen}
        onClose={() => setMarketListOpen(false)}
        onCreated={(purchaseOrder) => {
          if (purchaseOrder?.id) navigate(`/purchase-orders/${purchaseOrder.id}`);
        }}
      />




      <ReceiveGoodsDialog


        open={
          !!receivePO
        }


        purchaseOrder={
          receivePO
        }


        onClose={() => {

          setReceivePO(null);

        }}


      />



    </>

  );

}
