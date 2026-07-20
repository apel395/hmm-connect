import { useEffect, useState } from "react";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  createSupplier,
  getSuppliers,
  updateSupplier,
  type CreateSupplierRowRequest,
  type Supplier,
} from "../features/suppliers/suppliersApi";

interface SupplierRowForm extends CreateSupplierRowRequest {
  key: number;
}

const emptyRow = (key: number): SupplierRowForm => ({
  key,
  pic_name: "",
  phone: "",
  unit: "",
  item: "",
});

export default function SuppliersPage() {
  const queryClient = useQueryClient();

  const [modalMode, setModalMode] = useState<
    "create" | "edit" | null
  >(null);
  const [editingSupplierId, setEditingSupplierId] =
    useState<number | null>(null);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [bankName, setBankName] = useState("");
  const [bankAccountNumber, setBankAccountNumber] =
    useState("");
  const [bankAccountName, setBankAccountName] =
    useState("");
  const [rows, setRows] = useState<SupplierRowForm[]>([
    emptyRow(1),
  ]);

  const suppliersQuery = useQuery({
    queryKey: ["suppliers"],
    queryFn: getSuppliers,
  });

  const createMutation = useMutation({
    mutationFn: createSupplier,
    onSuccess: () => {
      resetForm();
      setModalMode(null);
      queryClient.invalidateQueries({
        queryKey: ["suppliers"],
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      supplierId,
      data,
    }: {
      supplierId: number;
      data: Parameters<typeof updateSupplier>[1];
    }) => updateSupplier(supplierId, data),
    onSuccess: () => {
      resetForm();
      setModalMode(null);
      setEditingSupplierId(null);
      queryClient.invalidateQueries({
        queryKey: ["suppliers"],
      });
    },
  });

  const suppliers = suppliersQuery.data ?? [];
  const isPending =
    createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (!modalMode) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !isPending) {
        setModalMode(null);
        setEditingSupplierId(null);
      }
    }

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener(
        "keydown",
        handleKeyDown,
      );
    };
  }, [modalMode, isPending]);

  function resetForm() {
    setCode("");
    setName("");
    setAddress("");
    setBankName("");
    setBankAccountNumber("");
    setBankAccountName("");
    setRows([emptyRow(nextSupplierRowKey())]);
  }

  function openCreateModal() {
    createMutation.reset();
    updateMutation.reset();
    setEditingSupplierId(null);
    resetForm();
    setModalMode("create");
  }

  function openEditModal(supplier: Supplier) {
    createMutation.reset();
    updateMutation.reset();
    setEditingSupplierId(supplier.id);
    setCode(supplier.code);
    setName(supplier.name);
    setAddress(supplier.address ?? "");
    setBankName(supplier.bank_name ?? "");
    setBankAccountNumber(
      supplier.bank_account_number ?? "",
    );
    setBankAccountName(
      supplier.bank_account_name ?? "",
    );
    setRows(
      supplier.rows.length > 0
        ? supplier.rows.map((row) => ({
            key: row.id,
            pic_name: row.pic_name ?? "",
            phone: row.phone ?? "",
            unit: row.unit ?? "",
            item: row.item ?? "",
          }))
        : [emptyRow(nextSupplierRowKey())],
    );
    setModalMode("edit");
  }

  function closeModal() {
    if (isPending) {
      return;
    }

    setModalMode(null);
    setEditingSupplierId(null);
  }

  function updateRow(
    key: number,
    field: keyof CreateSupplierRowRequest,
    value: string,
  ) {
    setRows((currentRows) =>
      currentRows.map((row) =>
        row.key === key
          ? {
              ...row,
              [field]: value,
            }
          : row,
      ),
    );
  }

  function addRow() {
    setRows((currentRows) => [
      ...currentRows,
      emptyRow(nextSupplierRowKey()),
    ]);
  }

  function removeRow(key: number) {
    setRows((currentRows) => {
      if (currentRows.length === 1) {
        return currentRows;
      }

      return currentRows.filter((row) => row.key !== key);
    });
  }

  function buildPayload() {
    return {
      code,
      name,
      address: address || undefined,
      bank_name: bankName || undefined,
      bank_account_number:
        bankAccountNumber || undefined,
      bank_account_name:
        bankAccountName || undefined,
      rows: rows.map((row) => ({
        pic_name: row.pic_name || undefined,
        phone: row.phone || undefined,
        unit: row.unit || undefined,
        item: row.item || undefined,
      })),
    };
  }

  function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const data = buildPayload();

    if (modalMode === "edit" && editingSupplierId) {
      updateMutation.mutate({
        supplierId: editingSupplierId,
        data,
      });
      return;
    }

    createMutation.mutate(data);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">
            Suppliers
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            Manage suppliers using the supplier master format.
          </p>
        </div>

        <button
          type="button"
          onClick={openCreateModal}
          className="h-10 rounded-lg bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-800"
        >
          Add supplier
        </button>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 p-6">
          <h2 className="font-semibold text-slate-900">
            Supplier master
          </h2>

          <span className="text-sm text-slate-500">
            {suppliers.length} suppliers
          </span>
        </div>

        {suppliersQuery.isLoading && (
          <div className="p-8 text-center text-sm text-slate-500">
            Loading suppliers...
          </div>
        )}

        {suppliersQuery.isError && (
          <div className="p-8 text-center text-sm text-red-600">
            Failed to load suppliers.
          </div>
        )}

        {suppliers.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1180px]">
              <thead>
                <tr className="border-b border-slate-200 text-left">
                  <th className="px-4 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    No
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Nama Supplier
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Alamat
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Nama PIC
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    No HP PIC
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Unit
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Item
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Bank
                  </th>
                  <th className="px-4 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Action
                  </th>
                </tr>
              </thead>

              <tbody>
                {suppliers.map((supplier) => {
                  const supplierRows =
                    supplier.rows.length > 0
                      ? supplier.rows
                      : [
                          {
                            id: 0,
                            pic_name: null,
                            phone: null,
                            unit: null,
                            item: null,
                          },
                        ];

                  return supplierRows.map(
                    (row, rowIndex) => (
                      <tr
                        key={`${supplier.id}-${row.id || rowIndex}`}
                        className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                      >
                        <td className="px-4 py-4 text-sm text-slate-600">
                          {rowIndex === 0
                            ? supplier.code
                            : ""}
                        </td>

                        <td className="px-4 py-4 text-sm font-medium text-slate-900">
                          {rowIndex === 0
                            ? supplier.name
                            : ""}
                        </td>

                        <td className="max-w-[240px] px-4 py-4 text-sm text-slate-600">
                          {rowIndex === 0
                            ? supplier.address || "-"
                            : ""}
                        </td>

                        <td className="px-4 py-4 text-sm text-slate-700">
                          {row.pic_name || "-"}
                        </td>

                        <td className="px-4 py-4 text-sm text-slate-600">
                          {row.phone || "-"}
                        </td>

                        <td className="px-4 py-4 text-sm text-slate-600">
                          {row.unit || "-"}
                        </td>

                        <td className="max-w-[260px] px-4 py-4 text-sm text-slate-600">
                          {row.item || "-"}
                        </td>

                        <td className="px-4 py-4 text-sm text-slate-600">
                          {rowIndex === 0 ? (
                            <div>
                              <p>
                                {supplier.bank_name || "-"}
                              </p>
                              <p className="text-xs text-slate-500">
                                {supplier.bank_account_number ||
                                  "-"}
                              </p>
                              <p className="text-xs text-slate-500">
                                {supplier.bank_account_name ||
                                  "-"}
                              </p>
                            </div>
                          ) : (
                            ""
                          )}
                        </td>

                        <td className="px-4 py-4 text-right">
                          {rowIndex === 0 && (
                            <button
                              type="button"
                              onClick={() =>
                                openEditModal(supplier)
                              }
                              className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
                            >
                              Edit
                            </button>
                          )}
                        </td>
                      </tr>
                    ),
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {!suppliersQuery.isLoading &&
          !suppliersQuery.isError &&
          suppliers.length === 0 && (
            <div className="p-8 text-center text-sm text-slate-500">
              No suppliers yet.
            </div>
          )}
      </div>

      {modalMode && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setModalMode(null);
        setEditingSupplierId(null);
            }
          }}
        >
          <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <h2 className="font-semibold text-slate-900">
                  {modalMode === "edit"
                    ? "Edit supplier"
                    : "Add supplier"}
                </h2>

                <p className="mt-1 text-sm text-slate-500">
                  Use the supplier master format.
                </p>
              </div>

              <button
                type="button"
                onClick={closeModal}
                disabled={isPending}
                className="text-2xl leading-none text-slate-400 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <form
              onSubmit={handleSubmit}
              className="flex min-h-0 flex-col"
            >
              <div className="space-y-5 overflow-y-auto p-6">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">
                      Supplier code
                    </label>
                    <input
                      value={code}
                      onChange={(event) =>
                        setCode(event.target.value)
                      }
                      placeholder="SUP-001"
                      className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900"
                      required
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">
                      Nama supplier
                    </label>
                    <input
                      value={name}
                      onChange={(event) =>
                        setName(event.target.value)
                      }
                      placeholder="Nama supplier"
                      className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">
                    Alamat
                  </label>
                  <textarea
                    value={address}
                    onChange={(event) =>
                      setAddress(event.target.value)
                    }
                    rows={2}
                    className="w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-900"
                  />
                </div>

                <div className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">
                      Nama bank
                    </label>
                    <input
                      value={bankName}
                      onChange={(event) =>
                        setBankName(event.target.value)
                      }
                      className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900"
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">
                      No rekening
                    </label>
                    <input
                      value={bankAccountNumber}
                      onChange={(event) =>
                        setBankAccountNumber(
                          event.target.value,
                        )
                      }
                      className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900"
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">
                      Nama pemilik rekening
                    </label>
                    <input
                      value={bankAccountName}
                      onChange={(event) =>
                        setBankAccountName(
                          event.target.value,
                        )
                      }
                      className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900"
                    />
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-slate-900">
                      PIC / Unit / Item
                    </h3>

                    <button
                      type="button"
                      onClick={addRow}
                      className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      Add row
                    </button>
                  </div>

                  {rows.map((row) => (
                    <div
                      key={row.key}
                      className="rounded-lg border border-slate-200 p-4"
                    >
                      <div className="grid gap-3 sm:grid-cols-2">
                        <input
                          value={row.pic_name}
                          onChange={(event) =>
                            updateRow(
                              row.key,
                              "pic_name",
                              event.target.value,
                            )
                          }
                          placeholder="Nama PIC"
                          className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900"
                        />

                        <input
                          value={row.phone}
                          onChange={(event) =>
                            updateRow(
                              row.key,
                              "phone",
                              event.target.value,
                            )
                          }
                          placeholder="No HP PIC"
                          className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900"
                        />

                        <input
                          value={row.unit}
                          onChange={(event) =>
                            updateRow(
                              row.key,
                              "unit",
                              event.target.value,
                            )
                          }
                          placeholder="Unit"
                          className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900"
                        />

                        <input
                          value={row.item}
                          onChange={(event) =>
                            updateRow(
                              row.key,
                              "item",
                              event.target.value,
                            )
                          }
                          placeholder="Item"
                          className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-slate-900"
                        />
                      </div>

                      <button
                        type="button"
                        onClick={() => removeRow(row.key)}
                        className="mt-3 text-xs font-medium text-red-600 hover:text-red-700"
                      >
                        Remove row
                      </button>
                    </div>
                  ))}
                </div>

                {(createMutation.isError ||
                  updateMutation.isError) && (
                  <p className="text-sm text-red-600">
                    Failed to save supplier.
                  </p>
                )}
              </div>

              <div className="flex justify-end gap-3 border-t border-slate-200 px-6 py-4">
                <button
                  type="button"
                  onClick={closeModal}
                  disabled={isPending}
                  className="h-10 rounded-lg border border-slate-300 px-4 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={isPending}
                  className="h-10 rounded-lg bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isPending
                    ? "Saving..."
                    : modalMode === "edit"
                      ? "Save changes"
                      : "Create supplier"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}let supplierRowKey = 0;

function nextSupplierRowKey() {
  supplierRowKey += 1;
  return supplierRowKey;
}


