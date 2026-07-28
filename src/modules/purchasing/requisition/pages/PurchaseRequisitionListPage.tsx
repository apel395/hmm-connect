import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import PageHeader from "@/components/common/PageHeader";

import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";

import PurchaseRequisitionTable from "../components/PurchaseRequisitionTable";
import PurchaseRequisitionForm from "../components/PurchaseRequisitionForm";

import {
  usePurchaseRequisitions,
  useCreatePurchaseRequisition,
  useSubmitPurchaseRequisition,
} from "../hooks/usePurchaseRequisitions";

export default function PurchaseRequisitionListPage() {

  const navigate =
    useNavigate();

  const {
    data = [],
    isLoading,
    refetch,
  }: any =
    usePurchaseRequisitions();

  const createPurchaseRequisition =
    useCreatePurchaseRequisition();

  const submitPurchaseRequisition =
    useSubmitPurchaseRequisition();

  const [
    open,
    setOpen,
  ] =
    useState(false);

  const [
    keyword,
    setKeyword,
  ] =
    useState("");

  const [
    status,
    setStatus,
  ] =
    useState("ALL");

  const rows =
    useMemo(() => {

      const source =
        Array.isArray(data)
          ? data
          : Array.isArray(data?.items)
          ? data.items
          : Array.isArray(data?.data)
          ? data.data
          : [];

      return source.filter(
        (row: any) => {

          const matchKeyword =

            keyword.trim() === ""

            ||

            row.pr_number
              ?.toLowerCase()
              .includes(
                keyword.toLowerCase()
              )

            ||

            row.requester_name
              ?.toLowerCase()
              .includes(
                keyword.toLowerCase()
              );

          const matchStatus =

            status === "ALL"

            ||

            row.status === status;

          return (
            matchKeyword &&
            matchStatus
          );

        },
      );

    }, [
      data,
      keyword,
      status,
    ]);

  async function handleCreate(
    payload: any,
  ) {

    await createPurchaseRequisition
      .mutateAsync(payload);

    setOpen(false);

  }

  async function handleSubmit(
    row: any,
  ) {

    await submitPurchaseRequisition
      .mutateAsync(row.id);

  }

  function handleView(
    row: any,
  ) {

    navigate(
      `/purchase-requisitions/${row.id}`,
    );

  }

  function handleConvert(
    row: any,
  ) {

    navigate(
      `/purchase-orders/create?pr=${row.id}`,
    );

  }

  function handleTraceability(
    row: any,
  ) {

    navigate(
      `/purchase-requisitions/${row.id}/traceability`,
    );

  }

  return (

    <div className="space-y-6">

      <PageHeader

        title="Purchase Requisitions"

        description="Manage purchasing requests before creating Purchase Orders."

        actions={

          <div className="flex items-center gap-2">

            <Button
              variant="outline"
              onClick={() =>
                refetch?.()
              }
            >

              Refresh

            </Button>

            <Button
              onClick={() =>
                setOpen(true)
              }
            >

              + New Requisition

            </Button>

          </div>

        }

      />

      <Card className="p-5">

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">

          <Input

            placeholder="Search PR Number or Requester..."

            value={keyword}

            onChange={(e) =>
              setKeyword(
                e.target.value,
              )
            }

          />

          <select

            className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"

            value={status}

            onChange={(e) =>
              setStatus(
                e.target.value,
              )
            }

          >

            <option value="ALL">
              All Status
            </option>

            <option value="DRAFT">
              Draft
            </option>

            <option value="PENDING_APPROVAL">
              Pending Approval
            </option>

            <option value="APPROVED">
              Approved
            </option>

            <option value="CONVERTED">
              Converted
            </option>

            <option value="REJECTED">
              Rejected
            </option>

            <option value="CANCELLED">
              Cancelled
            </option>

          </select>

          <div className="flex items-center justify-end text-sm text-slate-500">

            Showing

            <span className="mx-1 font-semibold text-slate-700">

              {rows.length}

            </span>

            requisition

            {rows.length !== 1
              ? "s"
              : ""}

          </div>

        </div>

      </Card>

      <Card className="overflow-hidden p-0">

        {isLoading ? (

          <div className="py-16">

            <Loading />

          </div>

        ) : (

          <PurchaseRequisitionTable

            rows={rows}

            onView={
              handleView
            }

            onSubmit={
              handleSubmit
            }

            onConvert={
              handleConvert
            }

            onTraceability={
              handleTraceability
            }

          />

        )}

      </Card>

      {open && (

        <PurchaseRequisitionForm

          onClose={() =>
            setOpen(false)
          }

          onSubmit={
            handleCreate
          }

        />

      )}

    </div>

  );

}