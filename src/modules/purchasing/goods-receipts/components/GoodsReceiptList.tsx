import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";

import {
  useGoodsReceipts,
} from "../hooks/useGoodsReceipts";


interface Props {

  purchaseOrderId:number;

}



export default function GoodsReceiptList({
  purchaseOrderId,
}:Props){


  const {
    data=[],
    isLoading,
  } =
    useGoodsReceipts(
      purchaseOrderId
    );



  if(isLoading){

    return (

      <Card>

        <Loading />

      </Card>

    );

  }



  return (

    <Card>


      <div className="mb-4">

        <h2 className="text-lg font-semibold">

          Goods Receipts

        </h2>


        <p className="text-sm text-slate-500">

          Receiving history from supplier

        </p>


      </div>




      {
        data.length === 0

        ?

        <div className="p-6 text-center text-slate-500">

          No goods receipt found

        </div>


        :


        <div className="space-y-4">


          {
            data.map(
              receipt => (


                <div

                  key={
                    receipt.id
                  }

                  className="rounded-lg border p-4"

                >


                  <div className="flex justify-between">


                    <div>


                      <div className="font-semibold">

                        {
                          receipt.receipt_number
                        }

                      </div>


                      <div className="text-sm text-slate-500">

                        {
                          new Date(
                            receipt.received_at
                          ).toLocaleString(
                            "en-US"
                          )
                        }

                      </div>


                    </div>



                    <div className="text-right">


                      <div className="font-medium">

                        {
                          receipt.destination_type
                        }

                      </div>


                      {
                        receipt.warehouse_id && (

                          <div className="text-sm text-slate-500">

                            Warehouse ID:
                            {" "}
                            {
                              receipt.warehouse_id
                            }

                          </div>

                        )
                      }


                    </div>


                  </div>





                  <table className="mt-4 w-full">


                    <thead>


                      <tr className="border-b text-left">


                        <th className="py-2">

                          Product

                        </th>


                        <th>

                          Quantity

                        </th>


                        <th>

                          Unit Cost

                        </th>


                      </tr>


                    </thead>



                    <tbody>


                      {
                        receipt.items.map(
                          item => (


                            <tr

                              key={
                                item.id
                              }

                              className="border-b"

                            >


                              <td className="py-2">

                                Product #
                                {
                                  item.product_id
                                }

                              </td>


                              <td>

                                {
                                  item.quantity
                                }

                              </td>



                              <td>

                                {
                                  Number(
                                    item.unit_cost
                                  ).toLocaleString(
                                    "en-US",
                                    {
                                      minimumFractionDigits:2,
                                    }
                                  )
                                }

                              </td>


                            </tr>


                          )

                        )
                      }


                    </tbody>


                  </table>



                </div>


              )

            )

          }


        </div>

      }


    </Card>

  );

}
