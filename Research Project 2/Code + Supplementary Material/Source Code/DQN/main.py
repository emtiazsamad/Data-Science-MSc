from pathlib import Path
import shutil
import os

import gym
import numpy as np
import tensorflow as tf
from tensorflow.keras.optimizers import Adam
import collections

from model import Network
from buffer import Memory
from wrapper import preprocess

'''
os.environ['CUDA_VISIBLE_DEVICES']='-1'

physical_devices = tf.config.list_physical_devices('GPU')
for device in physical_devices:
    tf.config.experimental.set_memory_growth(device, True)

'''

class Agent:

    def __init__(self, env_name='PongDeterministic-v4',
                 gamma=0.99,
                 batch_size=32,
                 learning_rate=0.00025,
                 action_period=4,
                 target_period=1e4,
                 n_frames=4):

        self.env_name = env_name
        env = gym.make(self.env_name)
        self.action_space = env.action_space.n
        
        self.gamma = gamma
        self.batch_size = batch_size
        self.epsilon_decay = (lambda steps: max(1.0 - 0.9 * steps / 1e6, 0.1))
        self.action_period = action_period
        self.target_period = target_period
        self.n_frames = n_frames

        self.network = Network.model(self.action_space)
        self.target_network = Network.model(self.action_space)
        self.optimizer = Adam(learning_rate=learning_rate, epsilon=0.01/self.batch_size)
        self.loss_function = tf.keras.losses.Huber()
    
    def policy(self, state, epsilon):

        if epsilon < np.random.random():
            qvalues = self.network(state)
            selected_actions = tf.cast(tf.argmax(qvalues, axis=1), tf.int32)
            selected_action = selected_actions.numpy()[0]
        else:
            selected_action = np.random.choice(self.action_space)
        
        return selected_action

    def train(self, n_steps, buffer_size=int(1e6), logdir='log'):

        logdir = Path(__file__).parent / self.env_name / logdir
        if logdir.exists():
            shutil.rmtree(logdir)
        self.summary = tf.summary.create_file_writer(str(logdir), flush_millis=60000)

        self.memory = Memory(capacity=buffer_size)
        steps, ep = 0, 0

        while steps < n_steps:
            env = gym.make(self.env_name)
            env.reset()
            _, _, _, info = env.step(0)
            env.reset()
            
            frame = preprocess(env.reset())
            frames = collections.deque([frame] * self.n_frames, maxlen=self.n_frames)

            ep_rewards, ep_steps = 0, 0
            terminal = False
            lives = info['lives']

            while not terminal:
                steps, ep_steps = steps + 1, ep_steps + 1
                epsilon = self.epsilon_decay(steps)
                state = np.expand_dims(np.stack(frames, axis=2), 0)
                action = self.policy(state, epsilon=epsilon)
                next_frame, reward, terminal, info = env.step(action)
                
                ep_rewards += reward
                frames.append(preprocess(next_frame))
                next_state = np.expand_dims(np.stack(frames, axis=2), 0)

                if info['lives'] != lives:
                    lives = info['lives']
                    terminal = True

                self.memory.add(state, action, reward, next_state, terminal)

                if len(self.memory) > 5e4:
                    if steps % self.action_period == 0:
                        loss = self.update()
                        with self.summary.as_default():
                            tf.summary.scalar('loss', loss, step=steps)
                            tf.summary.scalar('train_score', ep_rewards, step=steps)

                    if steps % self.target_period == 0:
                        self.target_network.set_weights(self.network.get_weights())
                
                if steps % 5e5 == 0:
                    self.network.save_weights(f'{self.env_name}/checkpoints/qnet_{steps}')

                if terminal:
                    ep += 1
                    break

            print(f'episode: {ep}, score: {ep_rewards}, steps: {ep_steps}, total steps: {steps}')
            
            if ep % 20 == 0:
                test_scores = self.test(n_test=1)
                with self.summary.as_default():
                    tf.summary.scalar('test_score', test_scores[0], step=steps)

    def update(self):

        states, actions, rewards, next_states, terminals = self.memory.sample_batch(self.batch_size)
        rewards = np.clip(rewards, -1, 1)
        future_rewards = self.target_network(next_states)
        next_actions = tf.cast(tf.argmax(future_rewards, axis=1), tf.int32)
        
        masks = tf.one_hot(next_actions, self.action_space)
        updated_q = tf.reduce_sum(future_rewards * masks, axis=1, keepdims=True)
        target_q = rewards + self.gamma * (1 - terminals) * updated_q

        with tf.GradientTape() as tape:
            qvalues = self.network(states)
            actions_onehot = tf.one_hot(actions.flatten().astype(np.int32), self.action_space)
            q = tf.reduce_sum(qvalues * actions_onehot, axis=1, keepdims=True)
            loss = self.loss_function(target_q, q)

        grads = tape.gradient(loss, self.network.trainable_variables)
        self.optimizer.apply_gradients(zip(grads, self.network.trainable_variables))

        return loss

    def test(self, n_test=1, env=None):

        if not env:
            env = gym.make(self.env_name)
        
        scores, steps = [], []

        for _ in range(n_test):
            frame = preprocess(env.reset())
            frames = collections.deque([frame] * self.n_frames, maxlen=self.n_frames)
            terminal = False
            ep_steps, ep_rewards = 0, 0

            while not terminal:
                state = np.expand_dims(np.stack(frames, axis=2), 0)
                action = self.policy(state, epsilon=0.05)
                next_frame, reward, terminal, _ = env.step(action)
                frames.append(preprocess(next_frame))

                ep_rewards += reward
                ep_steps += 1

            scores.append(ep_rewards)
            steps.append(ep_steps)

        return scores

    def record_video(self, checkpoint, video_dir):

            env = gym.make(self.env_name)
            frame = preprocess(env.reset())
            frames = collections.deque([frame] * self.n_frames, maxlen=self.n_frames)
            state = np.expand_dims(np.stack(frames, axis=2), 0)
            self.network(state)
            self.network.load_weights(checkpoint)

            video_dir = Path(video_dir)
            if video_dir.exists():
                shutil.rmtree(video_dir)
            video_dir.mkdir()
            rec = gym.wrappers.RecordVideo(gym.make(self.env_name), video_dir)

            self.test(n_test=1, env=rec)

def main():
    agent = Agent(env_name='PongDeterministic-v4')
    agent.train(n_steps=2.5e6)
    agent.network.save_weights(f'{agent.env_name}/checkpoints/qnet_final')
    agent.record_video(checkpoint=f'{agent.env_name}/checkpoints/qnet_final', video_dir=f'{agent.env_name}/mp4')


if __name__ == '__main__':
    main()