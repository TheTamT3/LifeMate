import itertools
from collections import defaultdict
import numpy as np
from lifemate.asr_eval.ctc_decoder import prefix_beam_search, BackoffLM

def test_ctc_beam_matches_exhaustive_path_marginal_with_repeats():
    probabilities=np.array([[.35,.4,.25],[.4,.35,.25],[.35,.4,.25]])
    masses=defaultdict(float)
    for path in itertools.product(range(3),repeat=3):
        prefix=[]; last=None
        for token in path:
            if token and token!=last: prefix.append(token)
            last=token
        masses[tuple(prefix)]+=float(np.prod([probabilities[i,t] for i,t in enumerate(path)]))
    best=max(masses,key=masses.get)
    labels=['','▁a','▁b']
    expected=''.join(labels[t] for t in best).replace('▁',' ').strip()
    assert prefix_beam_search(np.log(probabilities),labels,beam_width=100,token_top_k=3)==expected

def test_ctc_blank_separates_repeated_tokens():
    p=np.array([[.001,.999],[.999,.001],[.001,.999]])
    assert prefix_beam_search(np.log(p),['','▁mai'],beam_width=20,token_top_k=2)=='mai mai'

def test_word_lm_biases_completed_bpe_words_without_changing_acoustics():
    labels=['','▁tắt','▁tóc','▁đèn']
    p=np.array([[.001,.48,.518,.001],[.001,.001,.001,.997]])
    lm=BackoffLM(['tắt đèn']*20)
    assert prefix_beam_search(np.log(p),labels,beam_width=20,token_top_k=4)=='tóc đèn'
    assert prefix_beam_search(np.log(p),labels,beam_width=20,token_top_k=4,lm=lm,alpha=.5)=='tắt đèn'

def test_lm_json_roundtrip_preserves_scores():
    import json
    model=BackoffLM(['tắt đèn phòng khách','đặt báo thức sáng mai'])
    restored=BackoffLM.from_dict(json.loads(json.dumps(model.to_dict())))
    for words in [['tắt','đèn'],['tắt','báo','thức'],['từ','chưa','biết']]:
        assert model.score(words)==restored.score(words)
