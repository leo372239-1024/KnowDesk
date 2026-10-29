export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  username: string;
  role: string;
  tenant_id: string;
  department: string;
  acl_tags: string[];
}
