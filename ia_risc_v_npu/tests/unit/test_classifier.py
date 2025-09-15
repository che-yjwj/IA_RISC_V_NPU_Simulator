import pytest
from src.simulator.classifier import Classifier

@pytest.fixture
def classifier():
    return Classifier(window_size=5)

def test_classify_single_instruction(classifier):
    instruction = {'opcode': 'ADD'}
    complexity = classifier.classify(instruction)
    assert complexity == 0.2

def test_roi_detection_with_memory_pattern(classifier):
    # Fill the window with non-memory instructions first
    for _ in range(3):
        classifier.classify({'opcode': 'ADD'})
    
    # Add memory instructions
    classifier.classify({'opcode': 'LD'}) # score = max(0.8, 1/4) = 0.8
    assert classifier.classify({'opcode': 'SW'}) == max(0.8, 2/5) # score = max(0.8, 2/5) = 0.8

    # Check score after more memory instructions
    classifier.classify({'opcode': 'LW'})
    classifier.classify({'opcode': 'SD'})
    # Now 4 out of 5 are memory ops
    score = classifier.classify({'opcode': 'LD'})
    assert score == 1.0 # 5/5 memory ops

def test_roi_score_decay(classifier):
    # Fill with memory instructions
    for _ in range(5):
        classifier.classify({'opcode': 'LD'})
    assert classifier.classify({'opcode': 'LD'}) == 1.0

    # Add non-memory instructions, score should decrease
    classifier.classify({'opcode': 'ADD'}) # 4 mem, 1 non-mem
    assert classifier.classify({'opcode': 'ADD'}) < 1.0 # 3 mem, 2 non-mem
