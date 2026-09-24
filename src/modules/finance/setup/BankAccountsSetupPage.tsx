import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { listBankAccounts } from "@/modules/finance/cash-flow/bankAccountApi";

export default function BankAccountsSetupPage() {
  const navigate = useNavigate();
  const accounts = useQuery({
    queryKey: ["bank-accounts"],
    queryFn: () => listBankAccounts(false),
  });

  return (
    <div className="space-y-5">
      <PageHeader
        title="Bank Accounts"
        description="Configure bank/cash funding accounts and their linked posting COA."
        actions={<>
<Button onClick={() => navigate("/finance-setup/bank-accounts/new")}>Create Bank Account</Button>
<PrintPreviewButton src="/finance-setup/bank-accounts/print" title="Bank Account Register" ariaLabel="Preview bank account register" label="Print" />
</>}
      />
      <Card className="p-0">
        <Table className="min-w-[860px]">
          <THead><TR><TH>Bank Account</TH><TH>Business Unit</TH><TH>Location</TH><TH>Linked COA</TH><TH>Status</TH><TH numeric>Action</TH></TR></THead>
          <TBody>
            {(accounts.data ?? []).map((row) => (
              <TR key={row.id}>
                <TD><TableCellStack primary={`${row.bank_name} — ${row.account_name}`} secondary={row.account_number}/></TD>
                <TD>{row.business_unit_name ?? "—"}</TD>
                <TD>{row.location_name ?? "Global / all locations"}</TD>
                <TD><TableCellStack primary={row.coa_account_name ?? "—"} secondary={row.coa_account_code ?? undefined}/></TD>
                <TD>{row.is_active ? "Active" : "Inactive"}</TD>
                <TD><div className="flex justify-end"><Button size="xs" variant="outline" onClick={() => navigate(`/finance-setup/bank-accounts/${row.id}/edit`)}>Edit</Button></div></TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </Card>
    </div>
  );
}
