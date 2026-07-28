import {
  Table,
  THead,
  TBody,
  TR,
  TH,
  TD,
} from "@/components/ui/Table";

import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";

interface Props {
  rows?: any[];

  loading?: boolean;

  onView?: (
    row: any,
  ) => void;

  onSubmit?: (
    row: any,
  ) => void;

  onApprove?: (
    row: any,
  ) => void;

  onReject?: (
    row: any,
  ) => void;

  onConvert?: (
    row: any,
  ) => void;

  onTraceability?: (
    row: any,
  ) => void;
}

function formatDate(
  value: string,
) {

  if (!value) {
    return "-";
  }

  try {

    return new Date(
      value,
    ).toLocaleDateString();

  } catch {

    return value;

  }

}

function statusVariant(
  status: string,
) {

  switch (
    (
      status ?? ""
    ).toUpperCase()
  ) {

    case "APPROVED":
      return "success";

    case "PENDING":
    case "PENDING_APPROVAL":
      return "warning";

    case "REJECTED":
      return "danger";

    case "CONVERTED":
      return "info";

    case "CANCELLED":
      return "secondary";

    default:
      return "outline";

  }

}

export default function PurchaseRequisitionTable({

  rows = [],

  onView,

  onSubmit,

  onApprove,

  onReject,

  onConvert,

  onTraceability,

}: Props) {

  return (

    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">

      <div className="overflow-x-auto">

        <Table>

          <THead>

            <TR>

              <TH>
                PR Number
              </TH>

              <TH>
                Date
              </TH>

              <TH>
                Requester
              </TH>

              <TH>
                Status
              </TH>

              <TH className="text-right">
                Total
              </TH>

              <TH className="text-right">
                Actions
              </TH>

            </TR>

          </THead>

          <TBody>

            {rows.length === 0 ? (

              <TR>

                <TD
                  colSpan={6}
                  className="py-10 text-center"
                >

                  No Purchase Requisition

                </TD>

              </TR>

            ) : (

              rows.map(
                (row: any) => (

                  <TR
                    key={row.id}
                  >

                    <TD>
                      {row.pr_number}
                    </TD>

                    <TD>
                      {formatDate(
                        row.request_date,
                      )}
                    </TD>

                    <TD>
                      {row.requester_name ??
                        "-"}
                    </TD>

                    <TD>

                      <Badge
                        variant={statusVariant(
                          row.status,
                        )}
                      >

                        {row.status}

                      </Badge>

                    </TD>

                    <TD className="text-right">

                      {Number(
                        row.total_amount ??
                          0,
                      ).toLocaleString(
                        "en-US",
                        {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        },
                      )}

                    </TD>

                    <TD>

                      <div className="flex justify-end gap-2">

                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            onView?.(
                              row,
                            )
                          }
                        >

                          View

                        </Button>

                        {row.status ===
                          "DRAFT" && (

                          <Button
                            size="sm"
                            onClick={() =>
                              onSubmit?.(
                                row,
                              )
                            }
                          >

                            Submit

                          </Button>

                        )}

                        {row.status ===
                          "PENDING_APPROVAL" && (

                          <>

                            <Button
                              size="sm"
                              onClick={() =>
                                onApprove?.(
                                  row,
                                )
                              }
                            >

                              Approve

                            </Button>

                            <Button
                              size="sm"
                              variant="danger"
                              onClick={() =>
                                onReject?.(
                                  row,
                                )
                              }
                            >

                              Reject

                            </Button>

                          </>

                        )}

                        {row.status ===
                          "APPROVED" && (

                          <Button
                            size="sm"
                            onClick={() =>
                              onConvert?.(
                                row,
                              )
                            }
                          >

                            Convert PO

                          </Button>

                        )}

                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            onTraceability?.(
                              row,
                            )
                          }
                        >

                          Trace

                        </Button>

                      </div>

                    </TD>

                  </TR>

                ),
              )

            )}

          </TBody>

        </Table>

      </div>

    </div>

  );

}