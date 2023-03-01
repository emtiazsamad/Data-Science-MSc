from collections import deque
import pickle
import zlib
import random
import numpy as np

class Memory:

    def __init__(self, capacity):

        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)
        self.count = 0

    def __len__(self):
        return len(self.buffer)

    def add(self, state, action, reward, next_state, terminal):

        e = (state, action, reward, next_state, terminal)
        e = zlib.compress(pickle.dumps(e))
        self.buffer.append(e)

    def sample_batch(self, batch_size):

        batch = random.sample(self.buffer, batch_size)
        batch = [pickle.loads(zlib.decompress(i)) for i in batch]
        states, actions, rewards, next_states, terminals = zip(*batch)

        states = np.vstack(states).astype(np.float32)
        actions = np.vstack(actions).astype(np.float32)
        rewards = np.array(rewards).reshape(-1, 1)
        next_states = np.vstack(next_states).astype(np.float32)
        terminals = np.array(terminals).reshape(-1, 1)

        return (states, actions, rewards, next_states, terminals)