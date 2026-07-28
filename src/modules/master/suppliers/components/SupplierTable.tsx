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

import type { Supplier } from "../types";

interface Props {
  rows?: Supplier[];

  onEdit?: (
    supplier: Supplier
  ) => void;

  onDelete?: (
    supplier: Supplier
  ) => void;

  onProducts?: (
    supplier: Supplier
  ) => void;
}

export default function SupplierTable({
  rows = [],
  onEdit,
  onDelete,
  onProducts,
}: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">

      <div className="overflow-x-auto">

        <Table>

          <THead>

            <TR>

              <TH>Code</TH>

              <TH>Supplier</TH>

              <TH>PIC</TH>

              <TH>Bank</TH>

              <TH>Status</TH>

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
                  No Suppliers Found
                </TD>

              </TR>
            ) : (
              rows.map((row) => (
                <TR key={row.id}>

                  <TD>
                    {row.code}
                  </TD>

                  <TD>

                    <div className="font-medium">
                      {row.name}
                    </div>

                    <div className="text-xs text-slate-500">
                      {row.address}
                    </div>

                  </TD>

                  <TD>

                    {row.rows.length === 0 ? (
                      "-"
                    ) : (
                      <div className="space-y-1">

                        {row.rows.map(
                          (pic) => (
                            <div
                              key={pic.id}
                            >
                              <div className="text-sm">
                                {
                                  pic.pic_name
                                }
                              </div>

                              {pic.item && (
                                <div className="text-xs text-slate-500">
                                  {
                                    pic.item
                                  }
                                </div>
                              )}
                            </div>
                          )
                        )}

                      </div>
                    )}

                  </TD>

                  <TD>

                    <div className="text-sm">
                      {row.bank_name ||
                        "-"}
                    </div>

                    <div className="text-xs text-slate-500">
                      {
                        row.bank_account_number
                      }
                    </div>

                  </TD>

                  <TD>

                    <Badge
                      variant={
                        row.is_active
                          ? "success"
                          : "secondary"
                      }
                    >
                      {row.is_active
                        ? "ACTIVE"
                        : "INACTIVE"}
                    </Badge>

                  </TD>

                  <TD>

                    <div className="flex justify-end gap-2">

                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() =>
                          onProducts?.(
                            row
                          )
                        }
                      >
                        Products
                      </Button>

                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          onEdit?.(
                            row
                          )
                        }
                      >
                        Edit
                      </Button>

                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() =>
                          onDelete?.(
                            row
                          )
                        }
                      >
                        Delete
                      </Button>

                    </div>

                  </TD>

                </TR>
              ))
            )}

          </TBody>

        </Table>

      </div>

    </div>
  );
}