import api from "@/api/client";

export interface ItemGroup {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
}

export interface ItemSubGroup {
  id: number;
  code: string;
  name: string;
  group_id: number;
  is_active: boolean;
}

export const classificationApi = {
  groups: () =>
    api.get<ItemGroup[]>(
      "/item-classification/groups"
    ),

  subGroups: (
    groupId: number
  ) =>
    api.get<ItemSubGroup[]>(
      "/item-classification/subgroups",
      {
        params: {
          group_id: groupId,
        },
      }
    ),
};

export default classificationApi;
