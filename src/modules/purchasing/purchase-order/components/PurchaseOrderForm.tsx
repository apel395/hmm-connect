import {
  useEffect,
  useMemo,
  useState,
} from "react";

import Dialog, {
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";

import {
  useSuppliers,
} from "@/modules/master/suppliers/hooks/useSuppliers";

import {
  useApprovedPurchaseRequisitions,
} from "../hooks/usePurchaseOrders";

import PurchaseOrderHeader from "./PurchaseOrderHeader";
import PurchaseOrderItems, {
  PurchaseOrderItemRow,
} from "./PurchaseOrderItems";
import PurchaseOrderSummary from "./PurchaseOrderSummary";
import PurchaseOrderFooter from "./PurchaseOrderFooter";



interface Props {

  open: boolean;

  loading?: boolean;

  onClose: () => void;

  onSubmit: (
    payload: any
  ) => Promise<void> | void;

}



export default function PurchaseOrderForm({

  open,

  loading,

  onClose,

  onSubmit,

}: Props) {

  const {

    data: suppliers = [],

  } =
    useSuppliers();



  const {

    data: approvedPRs = [],

  } =
    useApprovedPurchaseRequisitions();



  const [

    supplierId,

    setSupplierId,

  ] =
    useState<number>();



  const [

    selectedPR,

    setSelectedPR,

  ] =
    useState<any>();



  const [

    expectedDate,

    setExpectedDate,

  ] =
    useState("");



  const [

    expiryDate,

    setExpiryDate,

  ] =
    useState("");



  const [

    receiptTolerance,

    setReceiptTolerance,

  ] =
    useState(0);



  const [

    notes,

    setNotes,

  ] =
    useState("");



  const [

    items,

    setItems,

  ] =
    useState<PurchaseOrderItemRow[]>([]);





  useEffect(() => {

    if (!open) {

      return;

    }

    setSupplierId(undefined);

    setSelectedPR(undefined);

    setExpectedDate("");

    setExpiryDate("");

    setReceiptTolerance(0);

    setNotes("");

    setItems([]);

  }, [open]);





  function selectPR(
    id: number
  ) {

    const pr =
      approvedPRs.find(
        (item: any) =>
          item.id === id
      );

    setSelectedPR(pr);

    if (!pr) {

      setItems([]);

      return;

    }

    setItems(

      (pr.items ?? []).map(

        (item: any) => ({

          product_id:
            item.product_id,

          quantity:
            Number(
              item.quantity
            ),

          unit_price:
            Number(
              item.estimated_price
            ),

          purchase_requisition_item_id:
            item.id,

        })

      )

    );

  }





  const total =
    useMemo(() => {

      return items.reduce(

        (
          sum,
          item
        ) =>

          sum +

          item.quantity *

          item.unit_price,

        0

      );

    }, [items]);





  async function save() {

    if (!supplierId) {

      alert(
        "Supplier is required."
      );

      return;

    }

    if (!selectedPR) {

      alert(
        "Approved purchase requisition is required."
      );

      return;

    }

    if (!expectedDate) {

      alert(
        "Expected Date is required."
      );

      return;

    }

    if (items.length === 0) {

      alert(
        "Purchase requisition has no items."
      );

      return;

    }

    await onSubmit({

      supplier_id:
        supplierId,

      expected_date:
        expectedDate,

      expiry_date:
        expiryDate || null,

      receipt_tolerance_percent:
        receiptTolerance,

      notes,

      purchase_requisition_ids: [

        selectedPR.id,

      ],

      items,

    });

  }





  return (

    <Dialog

      open={open}

      onOpenChange={(value) => {

        if (!value) {

          onClose();

        }

      }}

    >

      <DialogContent

        className="flex max-h-[90vh] max-w-6xl flex-col overflow-hidden"

      >

        <DialogHeader>

          <DialogTitle>

            Create Purchase Order

          </DialogTitle>

        </DialogHeader>





        <DialogBody

          className="flex-1 overflow-y-auto"

        >

          <PurchaseOrderHeader

            suppliers={
              suppliers
            }

            approvedPRs={
              approvedPRs
            }

            supplierId={
              supplierId
            }

            selectedPR={
              selectedPR
            }

            expectedDate={
              expectedDate
            }

            expiryDate={
              expiryDate
            }

            receiptTolerance={
              receiptTolerance
            }

            notes={
              notes
            }

            onSupplierChange={
              setSupplierId
            }

            onSelectPR={
              selectPR
            }

            onExpectedDateChange={
              setExpectedDate
            }

            onExpiryDateChange={
              setExpiryDate
            }

            onReceiptToleranceChange={
              setReceiptTolerance
            }

            onNotesChange={
              setNotes
            }

          />





          <div className="mt-8">

            <PurchaseOrderItems

              items={
                items
              }

              supplierProducts={[]}

              onChange={
                setItems
              }

            />

          </div>





          <div className="mt-8">

            <PurchaseOrderSummary

              total={
                total
              }

            />

          </div>

        </DialogBody>





        <PurchaseOrderFooter

          loading={
            loading
          }

          onCancel={
            onClose
          }

          onSubmit={
            save
          }

        />

      </DialogContent>

    </Dialog>

  );

}