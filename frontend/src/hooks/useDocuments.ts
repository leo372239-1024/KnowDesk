import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listDocuments, uploadDocument } from "../api/documents";

export function useDocuments() {
  return useQuery({ queryKey: ["documents"], queryFn: listDocuments });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadDocument(file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });
}
