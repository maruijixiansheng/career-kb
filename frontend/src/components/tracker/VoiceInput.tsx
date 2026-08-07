import { useState, useRef } from 'react'
import { speechToText } from '../../services/api'

interface Props {
  onTextReady: (text: string) => void
  disabled?: boolean
}

export default function VoiceInput({ onTextReady, disabled }: Props) {
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const mediaRecorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaRecorder.current = new MediaRecorder(stream)
      chunks.current = []

      mediaRecorder.current.ondataavailable = (e) => chunks.current.push(e.data)
      mediaRecorder.current.onstop = async () => {
        const blob = new Blob(chunks.current, { type: 'audio/webm' })
        const reader = new FileReader()
        reader.onload = async () => {
          setTranscribing(true)
          try {
            const base64 = (reader.result as string).split(',')[1]
            const result = await speechToText(base64)
            if (result.success && result.text) {
              onTextReady(result.text)
            }
          } catch { /* ignore */ }
          setTranscribing(false)
        }
        reader.readAsDataURL(blob)
        stream.getTracks().forEach(t => t.stop())
      }

      mediaRecorder.current.start()
      setRecording(true)
    } catch {
      alert('无法访问麦克风，请检查浏览器权限')
    }
  }

  const stopRecording = () => {
    mediaRecorder.current?.stop()
    setRecording(false)
  }

  return (
    <button
      type="button"
      onClick={recording ? stopRecording : startRecording}
      disabled={disabled || transcribing}
      className={`px-2 py-1 text-xs rounded border transition-colors ${
        recording
          ? 'bg-red-50 border-red-300 text-red-600 animate-pulse'
          : 'border-gray-200 text-gray-500 hover:bg-gray-50'
      }`}
    >
      {transcribing ? '⏳ 转写中...' : recording ? '⏹ 停止' : '🎤 语音'}
    </button>
  )
}
