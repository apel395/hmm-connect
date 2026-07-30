import { useParams } from "react-router-dom";
import { toast } from "sonner";

import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import Badge from "@/components/ui/Badge";
import PageHeader from "@/components/common/PageHeader";
import useAuthStore from "@/store/auth";
import { useApproval } from "@/modules/purchasing/requisition/hooks/useApprovals";

import {
  usePurchaseOrder,
  useSubmitPurchaseOrder,
  useApprovePurchaseOrder,
  useRejectPurchaseOrder,
  useCancelPurchaseOrder,
} from "../hooks/usePurchaseOrders";

import GoodsReceiptList from "@/modules/purchasing/goods-receipts/components/GoodsReceiptList";
import GoodsReceiptHistory from "../components/GoodsReceiptHistory";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";

export default function PurchaseOrderDetailPage(){

  const { id } = useParams();


  const {
    data,
    isLoading,
  } = usePurchaseOrder(
    Number(id)
  );


  const approval = useApproval(
    "PURCHASE_ORDER",
    Number(id),
  );

  const user = useAuthStore((state) => state.user);
  const submit = useSubmitPurchaseOrder();
  const approve = useApprovePurchaseOrder();
  const reject = useRejectPurchaseOrder();




  const cancel =
    useCancelPurchaseOrder();



  if(isLoading){

    return <Loading/>;

  }


  if(!data){

    return null;

  }

  const roleNames = (user?.roles ?? []).map((role) => role.name);
  const isAdmin = roleNames.includes("ADMIN");
  const canManagePO = isAdmin || roleNames.includes("PURCHASING");
  const currentRole =
    approval.data?.current_approver_role ??
    data.current_approver_role;
  const canApprove =
    data.status === "PENDING_APPROVAL" &&
    (isAdmin || Boolean(currentRole && roleNames.includes(currentRole)));



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



<div className="text-right">
          <Badge>
            {data.status}
          </Badge>
          {data.status === "PENDING_APPROVAL" && (
            <div className="mt-2 text-sm text-amber-700">
              Approval needed: {currentRole ?? "assigned role"}
            </div>
          )}
          </div>


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





      <DocumentAttachments
        entityType="PURCHASE_ORDER"
        entityId={data.id}
      />

      <div className="flex gap-3">
        {data.status === "DRAFT" && canManagePO && (
          <Button
            loading={submit.isPending}
            onClick={() => submit.mutate(data.id)}
          >
            Submit
          </Button>
        )}

        {canApprove && (
          <>
            <Button
              variant="success"
              loading={approve.isPending}
              onClick={async () => {
                const requiredRole = currentRole ?? "current role";
                if (
                  !window.confirm(
                    `Approve ${data.po_number} for the ${requiredRole} step?`
                  )
                ) {
                  return;
                }
                try {
                  await approve.mutateAsync({
                    id: data.id,
                    comment: `Approved for ${requiredRole}`,
                  });
                  toast.success(`${requiredRole} step approved.`);
                } catch (error: any) {
                  toast.error(
                    typeof error?.response?.data?.detail === "string"
                      ? error.response.data.detail
                      : "Unable to approve purchase order."
                  );
                }
              }}
            >
              Approve
            </Button>
            <Button
              variant="danger"
              loading={reject.isPending}
              onClick={() => {
                const comment = window.prompt("Reject reason");
                if (comment) {
                  reject.mutate({ id: data.id, comment });
                }
              }}
            >
              Reject
            </Button>
          </>
        )}

        {canManagePO &&
          ["DRAFT", "PENDING_APPROVAL", "APPROVED"].includes(data.status) && (
            <Button
              variant="danger"
              loading={cancel.isPending}
              onClick={() => cancel.mutate(data.id)}
            >
              Cancel
            </Button>
          )}
      </div>
    </div>
  );
}
