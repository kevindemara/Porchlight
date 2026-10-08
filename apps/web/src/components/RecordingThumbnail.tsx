import { useState } from 'react'
import { Video } from 'lucide-react'

export default function RecordingThumbnail({ mediaId }: { mediaId: string }) {
  const [failed, setFailed] = useState(false)
  return <div className="recording-symbol">{failed ? <Video size={28} /> : <img loading="lazy" src={`/api/v1/media/${mediaId}/thumbnail`} alt="" onError={() => setFailed(true)} />}</div>
}
