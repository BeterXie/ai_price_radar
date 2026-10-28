import type { RelayGroup, RelayModelInfo, RelayStationPublic } from "@/lib/types";

export function relayGroups(station: RelayStationPublic) {
  const automatic = station.model_catalog?.group_catalog;
  const groups = new Map<string, RelayGroup & { source: string }>();
  const source = automatic?.source === "public_model_plaza" ? "模型广场" : automatic?.source === "key_billing" ? "密钥接口" : "公开价格接口";
  for (const group of automatic?.groups || []) groups.set(group.id, { ...group, source });
  for (const group of station.groups || []) groups.set(group.id, { ...group, source: "站方填写" });
  return [...groups.values()];
}

export function modelsForGroup(models: RelayModelInfo[], group?: RelayGroup | null): RelayModelInfo[] {
  if (!group || group.models === null || group.models === undefined) return models;
  const byId = new Map(models.map((model) => [model.id, model]));
  return group.models.map((id) => byId.get(id) || {
    id, name: id, description: "", provider: "", context_token_limit: null,
    input_token_limit: null, output_token_limit: null, capabilities: [],
  });
}
