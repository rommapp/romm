import api from "@/services/api";

export interface ClientTokenSchema {
  id: number;
  name: string;
  scopes: string[];
  expires_at: string | null;
  last_used_at: string | null;
  created_at: string;
  user_id: number;
}

export interface ClientTokenCreateSchema extends ClientTokenSchema {
  raw_token: string;
}

export interface ClientTokenAdminSchema extends ClientTokenSchema {
  username: string;
}

export interface ClientTokenPairSchema {
  code: string;
  expires_in: number;
}

async function createToken({
  name,
  scopes,
  expires_in,
}: {
  name: string;
  scopes: string[];
  expires_in?: string;
}) {
  return api.post<ClientTokenCreateSchema>("/client-tokens", {
    name,
    scopes,
    expires_in,
  });
}

async function fetchTokens() {
  return api.get<ClientTokenSchema[]>("/client-tokens");
}

async function deleteToken(tokenId: number) {
  return api.delete(`/client-tokens/${tokenId}`);
}

async function regenerateToken(tokenId: number) {
  return api.put<ClientTokenCreateSchema>(
    `/client-tokens/${tokenId}/regenerate`,
  );
}

async function pairToken(tokenId: number) {
  return api.post<ClientTokenPairSchema>(`/client-tokens/${tokenId}/pair`);
}

async function pollPairStatus(code: string) {
  return api.get(`/client-tokens/pair/${code}/status`);
}

async function exchangeCode(code: string) {
  return api.post<ClientTokenCreateSchema>("/client-tokens/exchange", {
    code,
  });
}

async function fetchAllTokens() {
  return api.get<ClientTokenAdminSchema[]>("/client-tokens/all");
}

async function adminDeleteToken(tokenId: number) {
  return api.delete(`/client-tokens/${tokenId}/admin`);
}

export default {
  createToken,
  fetchTokens,
  deleteToken,
  regenerateToken,
  pairToken,
  pollPairStatus,
  exchangeCode,
  fetchAllTokens,
  adminDeleteToken,
};
