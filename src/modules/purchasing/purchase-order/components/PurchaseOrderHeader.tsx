import Input from "@/components/ui/Input";

interface Props {

  suppliers: any[];

  approvedPRs: any[];

  supplierId?: number;

  selectedPR?: any;

  expectedDate: string;

  expiryDate: string;

  receiptTolerance: number;

  notes: string;

  onSupplierChange: (
    id: number
  ) => void;

  onSelectPR: (
    id: number
  ) => void;

  onExpectedDateChange: (
    value: string
  ) => void;

  onExpiryDateChange: (
    value: string
  ) => void;

  onReceiptToleranceChange: (
    value: number
  ) => void;

  onNotesChange: (
    value: string
  ) => void;

}



export default function PurchaseOrderHeader({

  suppliers,

  approvedPRs,

  supplierId,

  selectedPR,

  expectedDate,

  expiryDate,

  receiptTolerance,

  notes,

  onSupplierChange,

  onSelectPR,

  onExpectedDateChange,

  onExpiryDateChange,

  onReceiptToleranceChange,

  onNotesChange,

}: Props) {

  return (

    <div className="grid grid-cols-2 gap-5">

      <div>

        <label className="mb-1 block text-sm font-medium">

          Approved Purchase Requisition

        </label>

        <select

          className="h-10 w-full rounded-md border border-slate-300 px-3"

          value={
            selectedPR?.id ?? ""
          }

          onChange={(e) =>

            onSelectPR(
              Number(
                e.target.value
              )
            )

          }

        >

          <option value="">

            Select Approved PR

          </option>

          {

            approvedPRs.map(
              (pr: any) => (

                <option

                  key={
                    pr.id
                  }

                  value={
                    pr.id
                  }

                >

                  {pr.pr_number}

                </option>

              )
            )

          }

        </select>

      </div>





      <div>

        <label className="mb-1 block text-sm font-medium">

          Supplier

        </label>

        <select

          className="h-10 w-full rounded-md border border-slate-300 px-3"

          value={
            supplierId ?? ""
          }

          onChange={(e) =>

            onSupplierChange(
              Number(
                e.target.value
              )
            )

          }

        >

          <option value="">

            Select Supplier

          </option>

          {

            suppliers.map(
              (supplier: any) => (

                <option

                  key={
                    supplier.id
                  }

                  value={
                    supplier.id
                  }

                >

                  {supplier.code}

                  {" - "}

                  {supplier.name}

                </option>

              )
            )

          }

        </select>

      </div>





      <div>

        <label className="mb-1 block text-sm font-medium">

          Expected Date

        </label>

        <Input

          type="date"

          value={
            expectedDate
          }

          onChange={(e) =>

            onExpectedDateChange(
              e.target.value
            )

          }

        />

      </div>





      <div>

        <label className="mb-1 block text-sm font-medium">

          Expiry Date

        </label>

        <Input

          type="date"

          value={
            expiryDate
          }

          onChange={(e) =>

            onExpiryDateChange(
              e.target.value
            )

          }

        />

      </div>





      <div>

        <label className="mb-1 block text-sm font-medium">

          Receipt Tolerance %

        </label>

        <Input

          type="number"

          value={
            receiptTolerance
          }

          onChange={(e) =>

            onReceiptToleranceChange(
              Number(
                e.target.value
              )
            )

          }

        />

      </div>





      <div className="col-span-2">

        <label className="mb-1 block text-sm font-medium">

          Notes

        </label>

        <textarea

          rows={4}

          className="w-full resize-none rounded-md border border-slate-300 p-3"

          value={
            notes
          }

          onChange={(e) =>

            onNotesChange(
              e.target.value
            )

          }

        />

      </div>

    </div>

  );

}
