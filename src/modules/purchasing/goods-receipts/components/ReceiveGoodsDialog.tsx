import {
  useEffect,
  useState,
} from "react";

import Button from "@/components/ui/Button";

import Dialog, {
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/Dialog";

import type {
  PurchaseOrder,
} from "@/modules/purchasing/purchase-order/types";

import {
  useWarehouses,
} from "@/modules/master/warehouses/hooks/useWarehouses";

import {
  useReceiveGoods,
} from "../hooks/useGoodsReceipts";


interface Props {

  open: boolean;

  purchaseOrder:
    | PurchaseOrder
    | null;

  onClose: () => void;

}


interface ReceiveLine {

  purchase_order_item_id:number;

  product_name:string;

  ordered:number;

  received:number;

  quantity:number;

}



export default function ReceiveGoodsDialog({

  open,

  purchaseOrder,

  onClose,

}:Props){


  const {
    data:warehouses=[]
  } = useWarehouses();



  const receiveMutation =
    useReceiveGoods();



  const [
    warehouseId,
    setWarehouseId
  ] =
  useState<number | null>(null);



  const [
    lines,
    setLines
  ] =
  useState<ReceiveLine[]>([]);



  const [
    notes,
    setNotes
  ] =
  useState("");



  useEffect(()=>{


    if(!purchaseOrder){

      setLines([]);

      setWarehouseId(null);

      setNotes("");

      return;

    }



    setLines(

      purchaseOrder.items.map(
        item=>{

          const remaining =
            Number(item.quantity)
            -
            Number(item.received_quantity);



          return {

            purchase_order_item_id:
              item.id,

            product_name:
              item.product_name,

            ordered:
              Number(item.quantity),

            received:
              Number(item.received_quantity),

            quantity:
              remaining > 0
              ? remaining
              : 0,

          };

        }

      )

    );


  },[purchaseOrder]);




  function updateQuantity(

    id:number,

    value:number

  ){


    setLines(

      current =>

        current.map(

          line =>

            line.purchase_order_item_id === id

            ?

            {

              ...line,

              quantity:

                Math.min(

                  Math.max(
                    value,
                    0
                  ),

                  line.ordered -
                  line.received

                ),

            }

            :

            line

        )

    );


  }




  async function submit(){


    if(!purchaseOrder){

      return;

    }



    if(!warehouseId){

      alert(
        "Please select warehouse"
      );

      return;

    }



    const items =

      lines

      .filter(
        line =>
          line.quantity > 0
      )

      .map(
        line => ({

          purchase_order_item_id:
            line.purchase_order_item_id,

          quantity:
            line.quantity,

        })
      );



    if(items.length===0){

      alert(
        "Please enter received quantity"
      );

      return;

    }




    try{


      await receiveMutation.mutateAsync({

        purchaseOrderId:
          purchaseOrder.id,


        payload:{

          destination_type:
            "INVENTORY",


          warehouse_id:
            warehouseId,


          items,


          notes:
            notes || null,

        },


      });



      onClose();


    }

    catch(error){

      console.error(
        error
      );

    }


  }





  return (

    <Dialog

      open={open}

      onOpenChange={
        value=>{

          if(!value){

            onClose();

          }

        }

      }

    >


      <DialogContent>


        <DialogHeader>

          <DialogTitle>

            Receive Goods

            {
              purchaseOrder
              &&
              ` - ${purchaseOrder.po_number}`
            }

          </DialogTitle>

        </DialogHeader>




        <DialogBody>


          <div className="space-y-5">


            <div>


              <label className="mb-1 block text-sm font-medium">

                Warehouse

              </label>


              <select

                className="w-full rounded-md border p-2"

                value={
                  warehouseId ?? ""
                }

                onChange={
                  e =>
                    setWarehouseId(
                      e.target.value
                      ?
                      Number(e.target.value)
                      :
                      null
                    )
                }

              >


                <option value="">

                  Select warehouse

                </option>



                {
                  warehouses.map(
                    (warehouse:any)=>(

                      <option

                        key={
                          warehouse.id
                        }

                        value={
                          warehouse.id
                        }

                      >

                        {
                          warehouse.code
                        }

                        {" - "}

                        {
                          warehouse.name
                        }

                      </option>

                    )

                  )
                }


              </select>


            </div>





            <div className="space-y-3">


              {
                lines.map(
                  line=>(

                    <div

                      key={
                        line.purchase_order_item_id
                      }

                      className="rounded-lg border p-3"

                    >


                      <div className="font-medium">

                        {
                          line.product_name
                        }

                      </div>



                      <div className="text-sm text-slate-500">

                        Ordered:
                        {" "}
                        {line.ordered}

                        {" | "}

                        Received:
                        {" "}
                        {line.received}

                      </div>




                      <input

                        type="number"

                        min="0"

                        className="mt-2 w-full rounded-md border p-2"

                        value={
                          line.quantity
                        }

                        onChange={
                          e =>
                            updateQuantity(
                              line.purchase_order_item_id,
                              Number(
                                e.target.value
                              )
                            )
                        }

                      />


                    </div>

                  )

                )
              }


            </div>




            <textarea

              className="w-full rounded-md border p-2"

              placeholder="Notes"

              value={
                notes
              }

              onChange={
                e =>
                  setNotes(
                    e.target.value
                  )
              }

            />



          </div>


        </DialogBody>




        <DialogFooter>


          <Button

            variant="outline"

            onClick={
              onClose
            }

          >

            Cancel

          </Button>



          <Button

            disabled={
              receiveMutation.isPending
            }

            onClick={
              submit
            }

          >

            {
              receiveMutation.isPending
              ?
              "Receiving..."
              :
              "Receive Goods"
            }


          </Button>


        </DialogFooter>


      </DialogContent>


    </Dialog>


  );

}