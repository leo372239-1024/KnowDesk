import { client } from "./client";
import { DocumentItem, DocumentList, DocumentListSchema } from "../types/document";

export async function listDocuments(): Promise<DocumentList> {
  const { data } = await client.get("/documents/");
  return DocumentListSchema.parse(data);
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post("/documents/upload", form);
  return data as DocumentItem;
}
