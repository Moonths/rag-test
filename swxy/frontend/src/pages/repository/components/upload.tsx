import * as api from '@/api'
import IconUpload from '@/assets/repository/upload.svg'
import { Upload, UploadFile, UploadProps } from 'antd'
import { forwardRef, useImperativeHandle, useState } from 'react'
import { userState } from '@/store/user'
import styles from './upload.module.scss'

export type RepositoryUploadRef = {
  submit: () => Promise<void>
}

function getUserIdFromJwt(token: string | null): string | null {
  if (!token) return null
  const parts = token.split('.')
  if (parts.length < 2) return null
  try {
    const payloadJson = decodeURIComponent(
      atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'))
        .split('')
        .map((c) => `%${`00${c.charCodeAt(0).toString(16)}`.slice(-2)}`)
        .join(''),
    )
    const payload = JSON.parse(payloadJson) as unknown
    const p = payload as {
      user_id?: string
      sub?: string | { user_id?: string }
      subject?: { user_id?: string }
    }
    return (
      p?.user_id ??
      (typeof p?.sub === 'object' ? p?.sub?.user_id : null) ??
      (typeof p?.sub === 'string' ? p?.sub : null) ??
      p?.subject?.user_id ??
      null
    )
  } catch {
    return null
  }
}

export default forwardRef<RepositoryUploadRef, UploadProps>(
  function RepositoryUpload(props: UploadProps, ref) {
    const { ...otherProps } = props

    const [fileList, setFileList] = useState<UploadFile[]>([])

    useImperativeHandle(ref, () => {
      return {
        submit: async () => {
          let hasError = false
          const errors: Error[] = []

          for (const file of fileList) {
            if (file.status === 'done') continue

            setFileList((prev) =>
              prev.map((item) => {
                if (item.uid === file.uid) {
                  return {
                    ...item,
                    status: 'uploading',
                  }
                }
                return item
              }),
            )
            try {
              // 检查文件大小
              if ((file.size ?? 0) > 5 * 1024 * 1024) {
                throw new Error('文件大小不能超过5M')
              }
              // 后端会用 session_id 作为 ES 索引名；为了让检索用到同一份索引，这里传 user_id
              const userId = getUserIdFromJwt(userState.token)
              //上传接口
              await api.repository.upload({
                files: file.originFileObj as File,
                session_id: userId ?? undefined,
              })

              setFileList((prev) =>
                prev.map((item) => {
                  if (item.uid === file.uid) {
                    return {
                      ...item,
                      status: 'done',
                      url: '#',
                    }
                  }
                  return item
                }),
              )
            } catch (error) {
              hasError = true
              errors.push(error as Error)
              setFileList((prev) =>
                prev.map((item) => {
                  if (item.uid === file.uid) {
                    return {
                      ...item,
                      status: 'error',
                      response: (error as Error | undefined)?.message,
                    }
                  }
                  return item
                }),
              )
            }
          }

          if (hasError) {
            window.$app.message.error(errors?.[0]?.message)
            throw new Error(errors?.[0]?.message)
          } else {
            window.$app.message.success('上传已完成')
          }
        },
      }
    })

    return (
      <div className={styles['repository-upload']}>
        <Upload.Dragger
          {...otherProps}
          showUploadList={false}
          maxCount={10}
          fileList={fileList}
          onChange={(info) => setFileList(info.fileList)}
        >
          <img src={IconUpload} />
          <p
            className="ant-upload-text"
            style={{
              color: '#666',
            }}
          >
            拖拽文件到此 或{' '}
            <span style={{ color: '#409EFF' }}>点击上传</span>
          </p>
        </Upload.Dragger>

        <p className={styles['repository-upload__desc']}>
          支持单个或批量文件上传。文件大小不能超过5M，最多支持10个文件。
        </p>

        <Upload
          fileList={fileList}
          onChange={(info) => setFileList(info.fileList)}
        />
      </div>
    )
  },
)
