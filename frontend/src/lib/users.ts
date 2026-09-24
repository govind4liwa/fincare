import { apiFetch } from "@/lib/api";

export type Me = {
  id: string;
  email: string;
  full_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  roles: string[];
  /** `null` means unrestricted (superuser) — see apps.tenants.views.accessible_entity_ids. */
  entities: string[] | null;
};

export async function getMe(): Promise<Me> {
  const res = await apiFetch("/users/me/");
  if (!res.ok) throw new Error(`Failed to load the current user (${res.status})`);
  return (await res.json()) as Me;
}
