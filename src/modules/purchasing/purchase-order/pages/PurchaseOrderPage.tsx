import {
  useState,
} from "react";


import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";


import PurchaseOrderTable from "../components/PurchaseOrderTable";
import PurchaseOrderForm from "../components/PurchaseOrderForm";


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


  const {
    data = [],
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



  const [selected, setSelected] =
    useState<PurchaseOrder | null>(
      null
    );



  const [receivePO, setReceivePO] =
    useState<PurchaseOrder | null>(
      null
    );



  function createPO() {

    setSelected(null);

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

      setSelected(null);


    } catch(err) {

      console.error(err);

    }

  }





  async function submitForApproval(
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






  async function approvePO(
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






  async function rejectPO(
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





  function openReceive(
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


          action={

            <Button

              onClick={
                createPO
              }

            >

              New Purchase Order

            </Button>

          }

        />





        <Card>


          {
            isLoading ? (

              <Loading />

            ) : (


              <PurchaseOrderTable

                rows={data}


                onSubmit={
                  submitForApproval
                }


                onApprove={
                  approvePO
                }


                onReject={
                  rejectPO
                }


                onReceive={
                  openReceive
                }


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

          setSelected(null);

        }}



        onSubmit={
          submit
        }


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