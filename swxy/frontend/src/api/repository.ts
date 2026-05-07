import { AxiosRequestConfig } from 'axios'
import { request } from './request'

export function list(params?: Record<string, unknown>, options?: AxiosRequestConfig) {
  return request.get<API.Repository[]>('/get_files', {
    ...options,
    params,
  })
}

export function upload(
  params: { files: File; session_id?: string },
  options?: AxiosRequestConfig,
) {
  const form = new FormData()
  form.append('files', params.files)
  return request.post<API.Result<{ file_id: string }>>(`/upload_files`, form, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    params: params.session_id ? { session_id: params.session_id } : undefined,
    ...options,
  })
}

export function remove(
  params: { file_name: string },
  options?: AxiosRequestConfig,
) {
  const { file_name, ..._params } = params
  return request.delete(`/delete_file/${encodeURIComponent(file_name)}`, {
    ...options,
    params: _params,
  })
}
