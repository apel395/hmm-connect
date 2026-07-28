import Card from "@/components/ui/Card";

interface Props {
  total: number;
}

export default function PurchaseOrderSummary({
  total,
}: Props) {

  return (

    <Card>

      <div className="flex items-center justify-between">

        <div>

          <div className="text-sm text-slate-500">

            Grand Total

          </div>

          <div className="mt-1 text-xs text-slate-400">

            Total Purchase Order Amount

          </div>

        </div>

        <div className="text-right">

          <div className="text-3xl font-bold text-slate-900">

            {total.toLocaleString(

              "en-US",

              {

                minimumFractionDigits: 2,

                maximumFractionDigits: 2,

              }

            )}

          </div>

        </div>

      </div>

    </Card>

  );

}
