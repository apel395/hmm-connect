import { useParams } from "react-router-dom";

import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import Badge from "@/components/ui/Badge";
import PageHeader from "@/components/common/PageHeader";

import {
  usePurchaseOrder,
  useApprovePurchaseOrder,
  useCancelPurchaseOrder,
} from "../hooks/usePurchaseOrders";

import GoodsReceiptList from "@/modules/purchasing/goods-receipts/components/GoodsReceiptList";
import GoodsReceiptHistory from "../components/GoodsReceiptHistory";

export default function PurchaseOrderDetailPage(){

  const { id } = useParams();


  const {
    data,
    isLoading,
  } = usePurchaseOrder(
    Number(id)
  );


  const approve =
    useApprovePurchaseOrder();




  const cancel =
    useCancelPurchaseOrder();



  if(isLoading){

    return <Loading/>;

  }


  if(!data){

    return null;

  }



  return (

    <div className="space-y-6">


      <PageHeader

        title={data.po_number}

        description="Purchase Order"

      />




      <Card>


        <div className="flex items-center justify-between">


          <div>


            <div className="text-sm text-slate-500">

              Supplier

            </div>


            <div className="text-xl font-semibold">

              {data.supplier_name}

            </div>


          </div>



          <Badge>

            {data.status}

          </Badge>


        </div>



        <div className="mt-6 grid grid-cols-4 gap-6">


          <div>

            <div className="text-xs text-slate-500">

              Order Date

            </div>

            <div>

              {data.order_date}

            </div>

          </div>



          <div>

            <div className="text-xs text-slate-500">

              Expected

            </div>

            <div>

              {data.expected_date}

            </div>

          </div>



          <div>

            <div className="text-xs text-slate-500">

              Total

            </div>

            <div>

              {Number(
                data.total_amount
              ).toLocaleString(
                "en-US"
              )}

            </div>

          </div>


        </div>


      </Card>





      <Card>


        <table className="min-w-full">


          <thead>

            <tr>

              <th className="text-left">
                Product
              </th>

              <th>
                Qty
              </th>

              <th>
                Received
              </th>

              <th>
                Remaining
              </th>

              <th>
                Price
              </th>

              <th>
                Total
              </th>

            </tr>

          </thead>



          <tbody>


            {
              data.items.map(
                (item:any)=>(


                  <tr
                    key={item.id}
                    className="border-b"
                  >


                    <td>

                      {item.product_code}

                      {" - "}

                      {item.product_name}

                    </td>



                    <td className="text-center">

                      {item.quantity}

                    </td>



                    <td className="text-center">

                      {item.received_quantity}

                    </td>



                    <td className="text-center">

                      {
                        item.remaining_quantity ??
                        (
                            Number(item.quantity) -
                            Number(item.received_quantity)
                        )
                        }

                    </td>



                    <td>

                      {item.unit_price}

                    </td>



                    <td>

                      {item.total_price}

                    </td>


                  </tr>


                )
              )
            }


          </tbody>


        </table>


      </Card>



      <GoodsReceiptHistory
        purchaseOrderId={data.id}
      />




      <GoodsReceiptList

        purchaseOrderId={
          data.id
        }

      />





      <div className="flex gap-3">


        



        {
          data.status==="DRAFT" && (

            <Button

              onClick={()=>
                approve.mutate(
                  data.id
                )
              }

            >

              Approve

            </Button>

          )
        }






        <Button

          variant="danger"

          onClick={()=>
            cancel.mutate(
              data.id
            )
          }

        >

          Cancel

        </Button>


      </div>


    </div>

  );

}