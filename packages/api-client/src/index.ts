import createClient, { type ClientOptions } from "openapi-fetch";
import type { components, paths } from "./schema";

export const createApiClient = (baseUrl: string, options: Omit<ClientOptions, "baseUrl"> = {}) =>
  createClient<paths>({ baseUrl, ...options });

export type { components, paths };
export type Schemas = components["schemas"];
