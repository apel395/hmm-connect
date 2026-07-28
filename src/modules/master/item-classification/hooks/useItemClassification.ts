import { useQuery } from "@tanstack/react-query";

import classificationApi from "../api/classificationApi";

export function useItemGroups() {
  return useQuery({
    queryKey: [
      "item-groups",
    ],

    queryFn: async () => {
      const res =
        await classificationApi.groups();

      return res.data;
    },
  });
}

export function useItemSubGroups(
  groupId?: number
) {
  return useQuery({
    queryKey: [
      "item-subgroups",
      groupId,
    ],

    enabled:
      groupId !== undefined &&
      groupId > 0,

    queryFn: async () => {
      const res =
        await classificationApi.subGroups(
          groupId!
        );

      return res.data;
    },
  });
}
