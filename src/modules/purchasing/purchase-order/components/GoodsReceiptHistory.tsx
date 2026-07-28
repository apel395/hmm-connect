import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";

import {
  useGoodsReceipts,
} from "@/modules/purchasing/goods-receipts/hooks/useGoodsReceipts";



interface Props {

  purchaseOrderId: number;

}



export default function GoodsReceiptHistory({

  purchaseOrderId,

}: Props) {


  const {
    data = [],
    isLoading,

  } = useGoodsReceipts(
    purchaseOrderId
  );



  if (isLoading) {

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

          Receiving history for this purchase order

        </p>


      </div>




      {
        data.length === 0

        ?

        <div className="p-6 text-center text-slate-500">

          No goods receipt found

        </div>


        :


        <table className="w-full border-collapse">


          <thead>

            <tr className="border-b bg-slate-50">


              <th className="p-3 text-left">

                Receipt Number

              </th>


              <th className="p-3 text-left">

                Received Date

              </th>


              <th className="p-3 text-left">

                Destination

              </th>


              <th className="p-3 text-center">

                Items

              </th>


            </tr>

          </thead>




          <tbody>


          {
            data.map(
              (receipt:any)=>(


                <tr

                  key={
                    receipt.id
                  }

                  className="border-b"

                >


                  <td className="p-3 font-medium">

                    {
                      receipt.receipt_number
                    }

                  </td>



                  <td className="p-3">

                    {
                      new Date(
                        receipt.received_at
                      )
                      .toLocaleDateString()
                    }

                  </td>




                  <td className="p-3">


                    {
                      receipt.destination_type
                    }


                    {
                      receipt.warehouse_id

                      &&

                      ` (Warehouse #${receipt.warehouse_id})`

                    }


                  </td>




                  <td className="p-3 text-center">

                    {
                      receipt.items?.length ?? 0
                    }

                  </td>



                </tr>


              )
            )
          }


          </tbody>


        </table>

      }



    </Card>

  );

}
