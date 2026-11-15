#!/usr/bin/env python3
"""Local Piper speech behind Open WebUI's standard OpenAI-compatible adapter."""

import asyncio
from contextlib import asynccontextmanager
import hmac
import io
from pathlib import Path
import subprocess
import wave

from fastapi import FastAPI, Header, HTTPException, Response
from piper import PiperVoice, SynthesisConfig
from pydantic import BaseModel, Field
import uvicorn

MODEL = Path('/app/backend/data/models/piper/en_US-lessac-medium.onnx')
TOKEN = Path('/run/kit-config/speech-api-key').read_text().strip()
VOICE_ID = 'en_US-lessac-medium'
lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app):
    app.state.voice = await asyncio.to_thread(PiperVoice.load, MODEL)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


class SpeechRequest(BaseModel):
    input: str = Field(min_length=1, max_length=8000)
    model: str = 'piper'
    voice: str = VOICE_ID
    response_format: str = 'mp3'
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


@app.get('/health')
async def health():
    return {'status': 'ok', 'engine': 'piper'}


@app.get('/v1/audio/voices')
async def voices():
    # Open WebUI requests voice metadata without an Authorization header.
    return {'voices': [{'id': VOICE_ID, 'name': 'Lessac — English (local)'}]}


@app.get('/v1/models')
async def models():
    return {'data': [{'id': 'piper', 'object': 'model', 'owned_by': 'local'}]}


def synthesize(body):
    output = io.BytesIO()
    with wave.open(output, 'wb') as stream:
        app.state.voice.synthesize_wav(
            body.input, stream, syn_config=SynthesisConfig(length_scale=1 / body.speed)
        )
    audio = output.getvalue()
    if body.response_format == 'wav':
        return audio, 'audio/wav'
    result = subprocess.run(
        ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', 'pipe:0',
         '-f', 'mp3', '-codec:a', 'libmp3lame', '-b:a', '96k', 'pipe:1'],
        input=audio, capture_output=True, check=True, timeout=60,
    )
    return result.stdout, 'audio/mpeg'


@app.post('/v1/audio/speech')
async def speech(body: SpeechRequest, authorization: str = Header(default='')):
    if not hmac.compare_digest(authorization, 'Bearer ' + TOKEN):
        raise HTTPException(401, 'Invalid speech API key')
    if body.model != 'piper' or body.voice not in (VOICE_ID, 'alloy'):
        raise HTTPException(400, 'Unsupported model or voice')
    if body.response_format not in ('mp3', 'wav') or not body.input.strip():
        raise HTTPException(400, 'Use nonempty text and mp3 or wav output')
    async with lock:
        audio, content_type = await asyncio.to_thread(synthesize, body)
    return Response(audio, media_type=content_type)


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8082, access_log=False)
