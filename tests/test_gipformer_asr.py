import sys
import types
from pathlib import Path
import numpy as np
import pytest
from lifemate.asr import GipformerASR


def test_gipformer_keeps_streams_isolated_and_passes_audio_only(monkeypatch, tmp_path):
    for name in ['encoder.onnx','decoder.onnx','joiner.onnx','tokens.txt']:
        (tmp_path/name).write_bytes(b'model')
    streams=[];config={}
    class Stream:
        result=types.SimpleNamespace(text='  TẮT ĐÈN  ')
        def accept_waveform(self, rate, samples):
            assert rate==16000
            np.testing.assert_allclose(samples,[.2,.4])
    class Recognizer:
        def create_stream(self):
            stream=Stream();streams.append(stream);return stream
        def decode_streams(self, batch): assert batch==[streams[-1]]
    def create(**kwargs): config.update(kwargs);return Recognizer()
    monkeypatch.setitem(sys.modules,'sherpa_onnx',types.SimpleNamespace(__version__='1.13.3',OfflineRecognizer=types.SimpleNamespace(from_transducer=create)))
    monkeypatch.setitem(sys.modules,'soundfile',types.SimpleNamespace(read=lambda *a,**kw:(np.array([[.1,.3],[.3,.5]],dtype='float32'),16000)))
    audio=tmp_path/'a.wav';audio.write_bytes(b'audio')
    asr=GipformerASR(tmp_path,provider='cpu')
    assert asr.transcribe_batch([audio,audio])==['TẮT ĐÈN','TẮT ĐÈN']
    assert len(streams)==2 and streams[0] is not streams[1]
    assert config['provider']=='cpu' and config['decoding_method']=='modified_beam_search'
    assert config['max_active_paths']==4 and config['feature_dim']==80
    assert set(config)=={'encoder','decoder','joiner','tokens','num_threads','sample_rate','feature_dim','decoding_method','max_active_paths','provider'}


def test_gipformer_rejects_cpu_wheel_when_cuda_requested(monkeypatch,tmp_path):
    monkeypatch.setitem(sys.modules,'sherpa_onnx',types.SimpleNamespace(__version__='1.13.3'))
    with pytest.raises(RuntimeError,match='CPU-only'): GipformerASR(tmp_path)._load()


def test_gipformer_rejects_missing_local_weights(monkeypatch,tmp_path):
    monkeypatch.setitem(sys.modules,'sherpa_onnx',types.SimpleNamespace(__version__='1.13.3'))
    with pytest.raises(FileNotFoundError): GipformerASR(tmp_path,provider='cpu')._load()


def test_cuda_rejects_cpu_wheel_even_with_transducer_factory(monkeypatch, tmp_path):
    for name in ['encoder.onnx', 'decoder.onnx', 'joiner.onnx', 'tokens.txt']:
        (tmp_path / name).write_bytes(b'model')
    def factory(**kwargs):
        pytest.fail('CPU wheel must be rejected before constructing recognizer')
    monkeypatch.setitem(sys.modules, 'sherpa_onnx', types.SimpleNamespace(
        __version__='1.13.3',
        OfflineRecognizer=types.SimpleNamespace(from_transducer=factory),
    ))
    with pytest.raises(RuntimeError, match='CUDA-enabled'):
        GipformerASR(tmp_path, device='cuda')._load()


def test_cuda_wheel_passes_cuda_provider(monkeypatch, tmp_path):
    for name in ['encoder.onnx', 'decoder.onnx', 'joiner.onnx', 'tokens.txt']:
        (tmp_path / name).write_bytes(b'model')
    config = {}
    recognizer = object()
    def factory(**kwargs):
        config.update(kwargs)
        return recognizer
    monkeypatch.setitem(sys.modules, 'sherpa_onnx', types.SimpleNamespace(
        __version__='1.13.3+cuda12.cudnn9',
        OfflineRecognizer=types.SimpleNamespace(from_transducer=factory),
    ))
    asr = GipformerASR(tmp_path, device='cuda')
    assert asr._load() is recognizer
    assert config['provider'] == 'cuda'
