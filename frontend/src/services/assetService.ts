import type { Asset, Host, ServiceStatusSnapshot } from "../types";
import { catalogApi } from "../api/catalog";

export interface AssetSource {
  list(environmentId: string): Promise<Host[]>;
}

export function createAssetService(source: AssetSource) {
  return {
    async list(
      environmentId: string,
      environmentName: string,
      snapshots: ServiceStatusSnapshot[] = [],
    ): Promise<Asset[]> {
      const hosts = await source.list(environmentId);
      return mapHostsToAssets(hosts, environmentName, snapshots);
    },
  };
}

export const assetService = createAssetService({
  list: catalogApi.hosts,
});

export function mapHostsToAssets(
  hosts: Host[],
  environmentName: string,
  snapshots: ServiceStatusSnapshot[] = [],
): Asset[] {
  const lastServiceCheckByHost = new Map<string, string>();
  for (const snapshot of snapshots) {
    const current = lastServiceCheckByHost.get(snapshot.host_id);
    if (!current || Date.parse(snapshot.observed_at) > Date.parse(current)) {
      lastServiceCheckByHost.set(snapshot.host_id, snapshot.observed_at);
    }
  }
  return hosts.map((host) => ({
    id: host.id,
    name: host.name,
    environmentId: host.environment_id,
    environmentName,
    type: null,
    serviceCheckStatus: host.last_status,
    lastServiceCheckAt: lastServiceCheckByHost.get(host.id) ?? null,
    serviceCount: host.service_count,
    dataSource: "adapter",
  }));
}
