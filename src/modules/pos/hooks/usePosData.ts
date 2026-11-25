import { useEffect, useMemo, useState } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { posApi, type PosListParams } from "../api";
import { operationsApi, type OutletContext, type OperationsContext, type OutletReport } from "../operationsApi";
import type { CateringProfile } from "../cateringTypes";
import type { PosBillingOptions, PosOptions, PosRevenueAccount, PosSale, PosSalesPage } from "../types";

export const POS_SALES_PAGE_SIZE = 25;

export type PosSalesFilters = Omit<PosListParams, "page" | "page_size">;

/** Sales history list with backend names and stable page reset on filter changes. */
export function usePosSales(filters: PosSalesFilters = {}) {
  const filtersKey = JSON.stringify(filters);
  const [page, setPage] = useState(1);

  useEffect(() => setPage(1), [filtersKey]);

  const params = useMemo<PosListParams>(
    () => ({ ...filters, page, page_size: POS_SALES_PAGE_SIZE }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [filtersKey, page],
  );

  const query = useQuery({
    queryKey: ["pos-sales", filtersKey, page],
    queryFn: async (): Promise<PosSalesPage> => (await posApi.list(params)).data,
  });

  return {
    ...query,
    items: query.data?.items ?? [],
    total: query.data?.total_items ?? 0,
    pages: Math.max(query.data?.total_pages ?? 0, 1),
    page,
    setPage,
  };
}

export function usePosSaleDetail(id: number | null): UseQueryResult<PosSale | null> {
  return useQuery({
    queryKey: ["pos-sale-detail", id],
    queryFn: async () => (id === null ? null : (await posApi.detail(id)).data),
    enabled: id !== null,
  });
}

export function usePosOptions(userId?: number) {
  return useQuery({
    queryKey: ["pos-options", userId],
    queryFn: async (): Promise<PosOptions> => (await posApi.options()).data,
  });
}

export function usePosCateringProfile(userId: number | undefined, locationId: number | undefined, enabled = true) {
  return useQuery<CateringProfile>({
    queryKey: ["catering-billing", userId, locationId],
    queryFn: async () => (await posApi.cateringSettings(locationId!)).data,
    enabled,
  });
}

export function usePosBillingOptions(userId?: number, enabled = true) {
  return useQuery({
    queryKey: ["pos-billing-options", userId],
    queryFn: async (): Promise<PosBillingOptions> => (await posApi.billingOptions()).data,
    enabled,
  });
}

export function usePosRevenueAccounts(userId: number | undefined, locationId: number | undefined, enabled = true) {
  return useQuery({
    queryKey: ["pos-revenue-accounts", userId, locationId],
    queryFn: async (): Promise<PosRevenueAccount[]> => (await posApi.revenueAccounts(locationId)).data,
    enabled,
  });
}

export function usePosOperations(userId: number | undefined, scope: OutletContext, enabled: boolean) {
  return useQuery({
    queryKey: ["pos-operations", userId, scope.location_id, scope.department_id],
    queryFn: async (): Promise<OperationsContext> => (await operationsApi.context(scope)).data,
    enabled,
    refetchInterval: 15000,
  });
}

export function usePosOutletReport(
  userId: number | undefined,
  scope: OutletContext,
  params: { from: string; to: string; cashier?: number },
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["pos-outlet-report", userId, scope.location_id, scope.department_id, params.from, params.to, params.cashier],
    queryFn: async (): Promise<OutletReport> =>
      (await operationsApi.report(scope, params.from, params.to, params.cashier)).data,
    enabled,
  });
}
