import tensorflow as tf
from tensorflow.keras import Model, layers

class Network:

    def model(action_space):

        inputs = layers.Input(shape=(84, 84, 4,))

        conv1 = layers.Conv2D(32, 8, strides=4, activation='relu')(inputs)
        conv2 = layers.Conv2D(64, 4, strides=2, activation='relu')(conv1)
        conv3 = layers.Conv2D(64, 3, strides=1, activation='relu')(conv2)

        flatten1 = layers.Flatten()(conv3)

        dense1 = layers.Dense(512, activation='relu')(flatten1)
        qvalues = layers.Dense(action_space, activation='linear')(dense1)

        return Model(inputs=inputs, outputs=qvalues)