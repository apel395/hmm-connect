import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import type { FinancePage, FinancePageParams } from "../types";

export type FinanceListParams = FinancePageParams & {
  page: number;
  page_size: number;
};

type PaginationOptions = {
  initialPageSize?: number;
  storageKey?: string;
  resetKey?: string;
};

/**
 * Shared finance pagination state. Filters and page-size changes reset to page
 * one so users never land on an empty page after narrowing a report.
 */
export function useFinancePagination({
  initialPageSize = 50,
  storageKey,
  resetKey = "",
}: PaginationOptions = {}) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(() => {
    if (!storageKey || typeof window === "undefined") return initialPageSize;
    const saved = Number(window.localStorage.getItem(storageKey));
    return Number.isFinite(saved) && saved > 0 ? saved : initialPageSize;
  });

  useEffect(() => {
    setPage(1);
  }, [resetKey, pageSize]);

  useEffect(() => {
    if (!storageKey || typeof window === "undefined") return;
    window.localStorage.setItem(storageKey, String(pageSize));
  }, [pageSize, storageKey]);

  const setPageSize = (size: number) => {
    if (Number.isFinite(size) && size > 0) setPageSizeState(size);
  };

  return { page, setPage, pageSize, setPageSize };
}

type FinanceListOptions<T> = {
  queryKey: readonly unknown[];
  queryFn: (params: FinanceListParams) => Promise<FinancePage<T>>;
  filters?: FinancePageParams;
  initialPageSize?: number;
  storageKey?: string;
  enabled?: boolean;
  staleTime?: number;
};

export type FinanceListResult<T> = UseQueryResult<FinancePage<T>> & {
  items: T[];
  page: number;
  pageSize: number;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
  total: number;
  pages: number;
  hasNext: boolean;
  hasPrevious: boolean;
  params: FinanceListParams;
};

/**
 * Shared data-first list query for finance pages. Backend query names, page
 * reset behavior, and pagination metadata stay consistent across modules.
 */
export function useFinanceList<T>({
  queryKey,
  queryFn,
  filters = {},
  initialPageSize = 50,
  storageKey,
  enabled = true,
  staleTime,
}: FinanceListOptions<T>): FinanceListResult<T> {
  const filtersKey = JSON.stringify(filters ?? {});
  const pagination = useFinancePagination({
    initialPageSize,
    storageKey,
    resetKey: filtersKey,
  });

  // Keep the latest filters without making the params object unstable.
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  const params = useMemo<FinanceListParams>(
    () => ({ page: pagination.page, page_size: pagination.pageSize, ...filtersRef.current }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [pagination.page, pagination.pageSize, filtersKey],
  );

  const query = useQuery({
    queryKey: [...queryKey, pagination.page, pagination.pageSize, filtersKey],
    queryFn: () => queryFn(params),
    enabled,
    staleTime,
  });

  return {
    ...query,
    items: query.data?.items ?? [],
    page: pagination.page,
    pageSize: pagination.pageSize,
    setPage: pagination.setPage,
    setPageSize: pagination.setPageSize,
    total: query.data?.total_items ?? 0,
    pages: query.data?.total_pages ?? 1,
    hasNext: query.data?.has_next ?? false,
    hasPrevious: query.data?.has_previous ?? false,
    params,
  };
}
