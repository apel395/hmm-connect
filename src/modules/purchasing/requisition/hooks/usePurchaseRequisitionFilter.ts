import { useMemo, useState } from "react";

export function usePurchaseRequisitionFilters(
  data: any,
) {

  const [
    keyword,
    setKeyword,
  ] = useState("");

  const [
    status,
    setStatus,
  ] = useState("ALL");

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

            keyword.trim() === "" ||

            row.pr_number
              ?.toLowerCase()
              .includes(
                keyword.toLowerCase(),
              ) ||

            row.requester_name
              ?.toLowerCase()
              .includes(
                keyword.toLowerCase(),
              );

          const matchStatus =

            status === "ALL" ||

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

  return {

    rows,

    keyword,

    setKeyword,

    status,

    setStatus,

  };

}
